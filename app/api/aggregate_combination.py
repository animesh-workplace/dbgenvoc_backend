from sqlalchemy import func
from fastapi import HTTPException
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.core import get_model_class, apply_filters, validate_columns
from app.api.utils import (
    _AGGREGATION_FUNCS,
    _build_having_filter,
    _apply_genomic_position_filter,
)
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
    separator: str = Field("")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        if not v.isidentifier():
            raise ValueError("Computed field name must be a valid identifier")
        return v


class ConcatenatedAggregationRequest(BaseModel):
    aggregate_column: str = Field(
        ..., description="Column to aggregate (e.g., 'variant_id' for counting)"
    )
    combination_columns: List[str] = Field(
        ..., min_length=1, description="Columns to combine/concatenate for grouping"
    )
    aggregation_type: AggregationType = Field(
        AggregationType.count, description="Type of aggregation operation"
    )
    filters: Optional[ComplexFilter] = Field(
        None, description="Complex filters with AND/OR logic (applied before GROUP BY)"
    )
    genomic_filter: Optional[GenomicPositionFilter] = Field(
        None, description="Genomic position/pathway filters (applied before GROUP BY)"
    )
    percentage_by: Optional[List[str]] = Field(
        None,
        description=(
            "Columns to partition by for percentage calculation. "
            "Must be subset of combination_columns. "
            "If None, calculates global percentage."
        ),
    )
    having: Optional[HavingClause] = Field(
        None,
        description="HAVING clause to filter aggregated results (applied after GROUP BY)",
    )
    order_by: Optional[Union[str, List[str]]] = Field(
        None,
        description=(
            "Column(s) to order by. "
            "Use 'aggregated_value' to sort by aggregation result, "
            "or any column from combination_columns."
        ),
    )
    order_direction: SortOrder = Field(
        SortOrder.DESC,
        description="Sort direction (applies to all order_by columns)",
    )
    limit: Optional[int] = Field(None, ge=1, description="Limit number of results")
    computed_fields: Optional[List[ComputedField]] = Field(
        None,
        description="Fields to compute from combination_columns (e.g., concatenation)",
    )

    @field_validator("percentage_by", "order_by")
    @classmethod
    def _validate_subset_of_combo(cls, v, info):
        if v:
            combo = info.data.get("combination_columns", [])

            if info.field_name == "percentage_by":
                if not set(v).issubset(combo):
                    raise ValueError(
                        "percentage_by must be subset of combination_columns"
                    )

            elif info.field_name == "order_by":
                order_cols = [v] if isinstance(v, str) else v
                invalid = [
                    col
                    for col in order_cols
                    if col != "aggregated_value" and col not in combo
                ]
                if invalid:
                    raise ValueError(
                        f"order_by columns {invalid} must be 'aggregated_value' or in combination_columns"
                    )
        return v


class ConcatenatedAggregationResponse(BaseModel):
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
    """Apply ordering to the query."""
    if not order_by:
        return query

    order_clauses = []
    order_by_list = [order_by] if isinstance(order_by, str) else order_by

    for order_col in order_by_list:
        if order_col == "aggregated_value":
            column_expr = agg_expr
        elif order_col in combination_columns:
            idx = combination_columns.index(order_col)
            column_expr = group_attrs[idx]
        else:
            raise ValueError(
                f"Cannot order by '{order_col}'. Must be 'aggregated_value' "
                f"or one of combination_columns: {combination_columns}"
            )
        order_clauses.append(
            column_expr.desc()
            if order_direction == SortOrder.DESC
            else column_expr.asc()
        )

    return query.order_by(*order_clauses)


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
    Enhanced concatenated aggregation with partitioned percentage calculation.
    """
    try:
        # 1. Validation (combined)
        model = get_model_class(table_name)
        columns_to_validate = set(
            request.combination_columns + [request.aggregate_column]
        )
        if request.percentage_by:
            columns_to_validate.update(request.percentage_by)
        validate_columns(model, list(columns_to_validate))

        # 2. Get column attributes
        agg_col = getattr(model, request.aggregate_column)
        group_attrs = [getattr(model, c) for c in request.combination_columns]

        # 3. Build base query with filters
        query = db.query(model)
        if request.filters:
            query = apply_filters(query, model, request.filters)
        if request.genomic_filter:
            query = _apply_genomic_position_filter(query, model, request.genomic_filter)

        total_records = query.count()

        # 4. Build aggregation expression
        extra_selects = []
        group_totals_map = {}
        combination_cols = request.combination_columns

        if request.aggregation_type == AggregationType.percentage:
            if request.percentage_by:
                partition_attrs = [getattr(model, c) for c in request.percentage_by]
                denominator = func.sum(func.count(agg_col)).over(
                    partition_by=partition_attrs
                )
                agg_expr = func.count(agg_col) * 100.0 / denominator
                extra_selects.append(denominator.label("group_total"))
            else:
                agg_expr = func.count(agg_col) * 100.0 / (total_records or 1)
        else:
            agg_expr = _AGGREGATION_FUNCS[request.aggregation_type](agg_col)

        # 5. Build and execute grouped query
        grouped_query = query.with_entities(
            *group_attrs, agg_expr.label("aggregated_value"), *extra_selects
        ).group_by(*group_attrs)

        # More efficient groups_before_having calculation
        groups_before_having = (
            query.with_entities(*group_attrs).group_by(*group_attrs).count()
        )

        if request.having:
            grouped_query = grouped_query.having(
                _build_having_filter(request.having, agg_expr)
            )

        if request.order_by:
            grouped_query = _apply_ordering(
                grouped_query,
                request.order_by,
                request.order_direction,
                group_attrs,
                agg_expr,
                combination_cols,
            )

        if request.limit:
            grouped_query = grouped_query.limit(request.limit)

        rows = grouped_query.all()
        groups_after_having = len(rows)

        # 6. Format results
        results = []
        pct_indices = (
            [combination_cols.index(c) for c in request.percentage_by]
            if request.percentage_by
            else []
        )

        for row in rows:
            # Build result dict with combination columns
            item = {combination_cols[i]: row[i] for i in range(len(combination_cols))}

            # Add aggregated value
            val = row[len(combination_cols)]
            if (
                request.aggregation_type == AggregationType.percentage
                and val is not None
            ):
                val = round(float(val), 2)
            item["aggregated_value"] = val

            # Handle percentage totals
            if request.aggregation_type == AggregationType.percentage:
                if request.percentage_by:
                    total_val = row[len(combination_cols) + 1]
                    key = ".".join(str(row[idx]) for idx in pct_indices)
                    group_totals_map[key] = int(total_val) if total_val else 0
                else:
                    group_totals_map["global"] = total_records

            results.append(item)

        # 7. Apply computed fields
        if request.computed_fields:
            results = _apply_computed_fields(results, request.computed_fields)

        # 8. Return response
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
