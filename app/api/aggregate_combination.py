from fastapi import HTTPException
from sqlalchemy import func
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.core import get_model_class, apply_filters, validate_columns
from app.api.utils import _apply_genomic_position_filter, _build_having_filter
from app.api.schema import (
    SortOrder,
    HavingClause,
    ComplexFilter,
    AggregationType,
    ComputedFieldType,
    GenomicPositionFilter,
)

# ==========================================
# AGGREGATION SCHEMAS
# ==========================================


class ComputedField(BaseModel):
    name: str
    type: ComputedFieldType = ComputedFieldType.concat
    columns: List[str]
    separator: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v.isidentifier():
            raise ValueError("Computed field name must be a valid identifier")
        return v


class ConcatenatedAggregationRequest(BaseModel):
    """Request for concatenated/combination aggregation."""

    aggregate_column: str = Field(
        ..., description="Column to aggregate (e.g., 'variant_id' for counting)"
    )

    combination_columns: List[str] = Field(
        ..., min_length=1, description="Columns to combine/concatenate for grouping"
    )

    aggregation_type: AggregationType = Field(
        AggregationType.count, description="Type of aggregation operation"
    )

    # --- Filters ---
    filters: Optional[ComplexFilter] = Field(
        None, description="Complex filters with AND/OR logic (applied before GROUP BY)"
    )

    genomic_filter: Optional[GenomicPositionFilter] = Field(
        None, description="Genomic position/pathway filters (applied before GROUP BY)"
    )

    # --- Percentage Options ---
    percentage_by: Optional[List[str]] = Field(
        None,
        description=(
            "Columns to partition by for percentage calculation. "
            "Must be subset of combination_columns. "
            "If None, calculates global percentage."
        ),
    )

    # --- Post-Aggregation Filters ---
    having: Optional[HavingClause] = Field(
        None,
        description="HAVING clause to filter aggregated results (applied after GROUP BY)",
    )

    # --- Sorting ---
    order_by: Optional[Union[str, List[str]]] = Field(
        None,
        description=(
            "Column(s) to order by. "
            "Use 'aggregated_value' to sort by aggregation result, "
            "or any column from combination_columns. "
            "Can be string or list of strings."
        ),
    )

    order_direction: SortOrder = Field(
        SortOrder.DESC,
        description="Sort direction (applies to all order_by columns)",
    )

    # --- Pagination ---
    limit: Optional[int] = Field(None, ge=1, description="Limit number of results")

    # --- Computed Fields ---
    computed_fields: Optional[List[ComputedField]] = Field(
        None,
        description="Fields to compute from combination_columns (e.g., concatenation)",
    )

    @field_validator("percentage_by")
    @classmethod
    def validate_percentage_by(cls, v, info):
        if v:
            combo = info.data.get("combination_columns")
            if not combo or not set(v).issubset(set(combo)):
                raise ValueError("percentage_by must be subset of combination_columns")
        return v

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, v, info):
        if v:
            combo = info.data.get("combination_columns", [])
            order_cols = [v] if isinstance(v, str) else v

            for col in order_cols:
                if col != "aggregated_value" and col not in combo:
                    raise ValueError(
                        f"order_by column '{col}' must be 'aggregated_value' "
                        f"or one of combination_columns: {combo}"
                    )
        return v


class ConcatenatedAggregationResponse(BaseModel):
    """Response for concatenated aggregation."""

    table_name: str
    total_records: int
    limit: Optional[int]
    aggregate_column: str
    aggregation_type: str
    total_combinations: int
    result: List[Dict[str, Any]]
    combination_columns: List[str]
    order_direction: Optional[str]
    groups_after_having: Optional[int] = None
    order_by: Optional[Union[str, List[str]]]
    groups_before_having: Optional[int] = None
    group_totals: Optional[Dict[str, int]] = None


# ==========================================
# HELPER FUNCTIONS
# ==========================================


def _apply_ordering(
    query,
    order_by: Optional[Union[str, List[str]]],
    order_direction: SortOrder,
    group_attrs,
    agg_expr,
    combination_columns: List[str],
):
    """Apply ordering to the query (matching aggregate.py style)."""

    order_clauses = []

    def add_order_clause(column_expr):
        if order_direction == SortOrder.DESC:
            return column_expr.desc()
        else:
            return column_expr.asc()

    if order_by:
        if isinstance(order_by, str):
            # Single column
            if order_by == "aggregated_value":
                order_clauses.append(add_order_clause(agg_expr))
            elif order_by in combination_columns:
                idx = combination_columns.index(order_by)
                order_clauses.append(add_order_clause(group_attrs[idx]))
            else:
                raise ValueError(
                    f"Cannot order by '{order_by}'. Must be 'aggregated_value' "
                    f"or one of combination_columns: {combination_columns}"
                )
        else:
            # Multiple columns
            for order_col in order_by:
                if order_col == "aggregated_value":
                    order_clauses.append(add_order_clause(agg_expr))
                elif order_col in combination_columns:
                    idx = combination_columns.index(order_col)
                    order_clauses.append(add_order_clause(group_attrs[idx]))
                else:
                    raise ValueError(
                        f"Cannot order by '{order_col}'. Must be 'aggregated_value' "
                        f"or one of combination_columns: {combination_columns}"
                    )

    if order_clauses:
        query = query.order_by(*order_clauses)

    return query


def _apply_computed_fields(rows, computed_fields):
    """Apply computed fields to result rows."""
    if not computed_fields:
        return rows

    for row in rows:
        for field in computed_fields:
            if field.type == ComputedFieldType.concat:
                row[field.name] = field.separator.join(
                    "" if row.get(c) is None else str(row.get(c)) for c in field.columns
                )

    return rows


# ==========================================
# MAIN AGGREGATION FUNCTION
# ==========================================


async def generic_concatenated_aggregate(
    request: ConcatenatedAggregationRequest,
    db,
    table_name: str,
) -> ConcatenatedAggregationResponse:
    """
    Enhanced concatenated aggregation with:
    - Partitioned percentage calculation
    - Multi-column ordering
    - HAVING clause support
    - Maintained combination logic
    """
    try:
        # 1. Validation
        model = get_model_class(table_name)
        validate_columns(model, request.combination_columns)
        validate_columns(model, [request.aggregate_column])
        if request.percentage_by:
            validate_columns(model, request.percentage_by)

        # Get column attributes
        agg_col = getattr(model, request.aggregate_column)
        group_attrs = [getattr(model, c) for c in request.combination_columns]

        # 2. Build base query with filters
        query = db.query(model)
        query = apply_filters(query, model, request.filters)
        query = _apply_genomic_position_filter(query, model, request.genomic_filter)

        # 3. Capture total records (before grouping)
        total_records = query.count()

        # 4. Build aggregation expression
        extra_selects = []
        group_totals_map = {}

        if request.aggregation_type == AggregationType.count:
            agg_expr = func.count(agg_col)

        elif request.aggregation_type == AggregationType.distinct_count:
            agg_expr = func.count(func.distinct(agg_col))

        elif request.aggregation_type == AggregationType.percentage:
            if request.percentage_by:
                # PARTITIONED PERCENTAGE (like aggregate.py)
                partition_attrs = [getattr(model, c) for c in request.percentage_by]
                denominator = func.sum(func.count(agg_col)).over(
                    partition_by=partition_attrs
                )
                agg_expr = func.count(agg_col) * 100.0 / denominator
                extra_selects.append(denominator.label("group_total"))
            else:
                # GLOBAL PERCENTAGE
                agg_expr = (
                    func.count(agg_col) * 100.0 / total_records if total_records else 1
                )

        elif request.aggregation_type == AggregationType.sum:
            agg_expr = func.sum(agg_col)
        elif request.aggregation_type == AggregationType.avg:
            agg_expr = func.avg(agg_col)
        elif request.aggregation_type == AggregationType.min:
            agg_expr = func.min(agg_col)
        elif request.aggregation_type == AggregationType.max:
            agg_expr = func.max(agg_col)
        else:
            raise HTTPException(400, detail="Unsupported aggregation type")

        # 5. Build grouped query
        grouped_query = query.with_entities(
            *group_attrs, agg_expr.label("aggregated_value"), *extra_selects
        ).group_by(*group_attrs)

        # 6. Count groups before HAVING
        groups_before_having = (
            db.query(func.count()).select_from(grouped_query.subquery()).scalar() or 0
        )

        # 7. Apply HAVING clause
        if request.having:
            having_filter = _build_having_filter(request.having, agg_expr)
            grouped_query = grouped_query.having(having_filter)

        # 8. Apply ordering
        grouped_query = _apply_ordering(
            grouped_query,
            request.order_by,
            request.order_direction,
            group_attrs,
            agg_expr,
            request.combination_columns,
        )

        # 9. Apply LIMIT
        if request.limit:
            grouped_query = grouped_query.limit(request.limit)

        # 10. Execute query
        rows = grouped_query.all()
        groups_after_having = len(rows)

        # 11. Format results
        results = []
        pct_indices = None

        if request.percentage_by:
            pct_indices = [
                request.combination_columns.index(c) for c in request.percentage_by
            ]

        for row in rows:
            item = {}

            # Add combination columns
            for i, col in enumerate(request.combination_columns):
                item[col] = row[i]

            # Add aggregated value
            val_index = len(request.combination_columns)
            val = row[val_index]

            # Round percentage values
            if (
                request.aggregation_type == AggregationType.percentage
                and val is not None
            ):
                val = round(float(val), 2)

            item["aggregated_value"] = val

            # Store group totals for partitioned percentages
            if request.aggregation_type == AggregationType.percentage:
                if request.percentage_by:
                    # Extract partition key
                    total_val = row[val_index + 1]
                    key_parts = [str(row[idx]) for idx in pct_indices]
                    key = ".".join(key_parts)
                    group_totals_map[key] = int(total_val) if total_val else 0
                else:
                    group_totals_map["global"] = total_records

            results.append(item)

        # 12. Apply computed fields
        results = _apply_computed_fields(results, request.computed_fields)

        # 13. Return response
        return ConcatenatedAggregationResponse(
            result=results,
            limit=request.limit,
            table_name=table_name,
            order_by=request.order_by,
            total_records=total_records,
            groups_after_having=groups_after_having,
            total_combinations=groups_before_having,
            groups_before_having=groups_before_having,
            aggregate_column=request.aggregate_column,
            order_direction=request.order_direction.value,
            aggregation_type=request.aggregation_type.value,
            combination_columns=request.combination_columns,
            group_totals=group_totals_map if group_totals_map else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Combination aggregation failed: {str(e)}")
