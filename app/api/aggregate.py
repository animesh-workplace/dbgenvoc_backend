from sqlalchemy import func
from fastapi import HTTPException
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.core import get_model_class, validate_columns, apply_filters
from app.api.utils import _apply_genomic_position_filter, _build_having_filter
from app.api.schema import (
    SortOrder,
    HavingClause,
    ComplexFilter,
    AggregationType,
    GenomicPositionFilter,
)


# ==========================================
# AGGREGATION SCHEMAS
# ==========================================


class AggregationRequest(BaseModel):
    column: str = Field(..., description="Target column for aggregation")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")

    percentage_by: Optional[List[str]] = Field(
        None, description="Columns to calculate percentage against (denominator scope)"
    )

    filters: Optional[ComplexFilter] = Field(
        None, description="Complex filters with AND/OR logic (applied before GROUP BY)"
    )

    genomic_filter: Optional[GenomicPositionFilter] = Field(
        None,
        description="Filter by genomic positions/ranges or pathway (applied before GROUP BY)",
    )

    aggregation_type: AggregationType = Field(
        AggregationType.count, description="Type of aggregation"
    )

    having: Optional[HavingClause] = Field(
        None,
        description="HAVING clause to filter aggregated results (applied after GROUP BY)",
    )

    order_by: Optional[Union[str, List[str]]] = Field(
        None,
        description="Column(s) to order results by. Use 'aggregated_value' for ordering by the aggregation result.",
    )

    order_direction: SortOrder = Field(
        SortOrder.DESC, description="Order direction: asc or desc"
    )

    limit: Optional[int] = Field(
        None, description="Limit the number of results returned"
    )

    @field_validator("having")
    @classmethod
    def validate_having_requires_group_by(cls, v, info):
        if v is not None and not info.data.get("group_by"):
            raise ValueError("HAVING clause requires group_by to be specified")
        return v

    @field_validator("percentage_by")
    @classmethod
    def validate_percentage_by(cls, v, info):
        if v:
            group_by = info.data.get("group_by")
            if not group_by or not set(v).issubset(set(group_by)):
                raise ValueError(
                    "percentage_by columns must be present in group_by columns"
                )
        return v

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, v, info):
        if v is not None and not info.data.get("group_by"):
            if isinstance(v, str) and v != "aggregated_value":
                raise ValueError(
                    "For scalar aggregations (without group_by), order_by must be 'aggregated_value' or None"
                )
            elif isinstance(v, list):
                raise ValueError(
                    "For scalar aggregations (without group_by), order_by cannot be a list"
                )
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v < 1:
            raise ValueError("Limit must be greater than 0")
        return v


class AggregationResponse(BaseModel):
    column: str
    table_name: str
    total_records: int
    aggregation_type: str
    limit: Optional[int] = None
    order_direction: Optional[str] = None
    groups_after_having: Optional[int] = None
    groups_before_having: Optional[int] = None
    group_totals: Optional[Dict[str, int]] = None
    order_by: Optional[Union[str, List[str]]] = None
    result: Union[Dict[str, Any], List[Dict[str, Any]]]


# ==========================================
# INTERNAL HELPERS
# ==========================================


async def _calculate_standard_agg(query, col_attr, agg_type: AggregationType):
    """Handles standard scalar aggregations."""
    funcs = {
        AggregationType.sum: func.sum(col_attr),
        AggregationType.avg: func.avg(col_attr),
        AggregationType.min: func.min(col_attr),
        AggregationType.max: func.max(col_attr),
        AggregationType.count: func.count(col_attr),
        AggregationType.distinct_count: func.count(func.distinct(col_attr)),
    }
    return query.with_entities(funcs[agg_type]).scalar() or 0


async def _calculate_global_percentage(query, db, model_class, col_attr):
    """Calculates percentage for non-grouped queries."""
    numerator = query.with_entities(func.count(col_attr)).scalar() or 0
    denominator = db.query(func.count(col_attr)).select_from(model_class).scalar() or 1
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _apply_ordering(
    query, order_by, order_direction, group_attrs, agg_expr, group_by_columns
):
    """Apply ordering to the query."""
    order_clauses = []

    def add_order_clause(column_expr):
        if order_direction == SortOrder.DESC:
            return column_expr.desc()
        else:
            return column_expr.asc()

    if order_by:
        if isinstance(order_by, str):
            if order_by == "aggregated_value":
                order_clauses.append(add_order_clause(agg_expr))
            elif order_by in group_by_columns:
                idx = group_by_columns.index(order_by)
                order_clauses.append(add_order_clause(group_attrs[idx]))
            else:
                raise ValueError(
                    f"Cannot order by '{order_by}'. Must be 'aggregated_value' or one of group_by columns: {group_by_columns}"
                )
        else:
            for order_col in order_by:
                if order_col == "aggregated_value":
                    order_clauses.append(add_order_clause(agg_expr))
                elif order_col in group_by_columns:
                    idx = group_by_columns.index(order_col)
                    order_clauses.append(add_order_clause(group_attrs[idx]))
                else:
                    raise ValueError(
                        f"Cannot order by '{order_col}'. Must be 'aggregated_value' or one of group_by columns: {group_by_columns}"
                    )

    if order_clauses:
        query = query.order_by(*order_clauses)

    return query


# ==========================================
# MAIN AGGREGATION API
# ==========================================


async def generic_aggregate(
    request: AggregationRequest, db, table_name: str
) -> AggregationResponse:
    """
    Enhanced generic aggregation endpoint with unified genomic position filtering.

    Query execution order:
    1. FROM table_name
    2. WHERE (filters)
    3. WHERE (genomic_filter - unified positions/ranges)
    4. GROUP BY (group_by)
    5. HAVING (having clause on aggregated results)
    6. ORDER BY (order_by)
    7. LIMIT (limit)
    8. SELECT (final result)
    """
    try:
        model_class = get_model_class(table_name)

        # 1. Validation
        validate_columns(model_class, [request.column])
        if request.group_by:
            validate_columns(model_class, request.group_by)
        if request.percentage_by:
            validate_columns(model_class, request.percentage_by)

        col_attr = getattr(model_class, request.column)

        # 2. Build Query & Apply WHERE Filters
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        # 2b. Apply Genomic Position Filters (UNIFIED)
        query = _apply_genomic_position_filter(
            query, model_class, request.genomic_filter
        )

        # 3. Capture Total Records
        total_records = query.count()

        # 4. Perform Aggregation
        final_result = None
        group_totals_map = {}
        groups_before_having = None
        groups_after_having = None

        if request.group_by:
            # === GROUPED AGGREGATION ===
            group_attrs = [getattr(model_class, c) for c in request.group_by]
            group_by_columns = request.group_by
            extra_selects = []

            # Determine aggregation expression
            if request.aggregation_type == AggregationType.percentage:
                if request.percentage_by:
                    partition_attrs = [
                        getattr(model_class, c) for c in request.percentage_by
                    ]
                    denominator = func.sum(func.count(col_attr)).over(
                        partition_by=partition_attrs
                    )
                    agg_expr = (func.count(col_attr) * 100.0) / denominator
                    extra_selects.append(denominator.label("group_total"))
                else:
                    agg_expr = (func.count(col_attr) * 100.0) / (
                        total_records if total_records > 0 else 1
                    )
            else:
                funcs_map = {
                    AggregationType.count: func.count(col_attr),
                    AggregationType.sum: func.sum(col_attr),
                    AggregationType.avg: func.avg(col_attr),
                    AggregationType.min: func.min(col_attr),
                    AggregationType.max: func.max(col_attr),
                    AggregationType.distinct_count: func.count(func.distinct(col_attr)),
                }
                agg_expr = funcs_map.get(request.aggregation_type)

            # Build grouped query
            grouped_query = query.with_entities(
                *group_attrs, agg_expr.label("val"), *extra_selects
            ).group_by(*group_attrs)

            # Count groups before HAVING
            groups_before_having = (
                db.query(func.count()).select_from(grouped_query.subquery()).scalar()
            )

            # Apply HAVING
            if request.having:
                having_filter = _build_having_filter(request.having, agg_expr)
                grouped_query = grouped_query.having(having_filter)

            # Apply ORDER BY
            if request.order_by:
                grouped_query = _apply_ordering(
                    grouped_query,
                    request.order_by,
                    request.order_direction,
                    group_attrs,
                    agg_expr,
                    group_by_columns,
                )

            # Apply LIMIT
            if request.limit:
                grouped_query = grouped_query.limit(request.limit)

            # Execute Query
            results = grouped_query.all()
            groups_after_having = len(results)

            # Format Results
            formatted_results = []
            pct_indices = []
            if request.percentage_by:
                pct_indices = [group_by_columns.index(c) for c in request.percentage_by]

            for result in results:
                result_dict = {}

                for i, group_col in enumerate(group_by_columns):
                    result_dict[group_col] = result[i]

                val_index = len(group_by_columns)
                val = result[val_index]
                if (
                    request.aggregation_type == AggregationType.percentage
                    and val is not None
                ):
                    val = round(float(val), 2)
                result_dict["aggregated_value"] = val

                if request.aggregation_type == AggregationType.percentage:
                    if request.percentage_by:
                        total_val = result[val_index + 1]
                        key_parts = [str(result[idx]) for idx in pct_indices]
                        key = "|".join(key_parts)
                        group_totals_map[key] = int(total_val) if total_val else 0
                    else:
                        group_totals_map["global"] = total_records

                formatted_results.append(result_dict)

            final_result = formatted_results

        else:
            # === SCALAR AGGREGATION ===
            if request.aggregation_type == AggregationType.percentage:
                val = await _calculate_global_percentage(
                    query, db, model_class, col_attr
                )
                final_result = {"value": val}
                group_totals_map["global"] = total_records
            else:
                val = await _calculate_standard_agg(
                    query, col_attr, request.aggregation_type
                )
                final_result = {"value": val}

        return AggregationResponse(
            result=final_result,
            limit=request.limit,
            table_name=table_name,
            column=request.column,
            order_by=request.order_by,
            total_records=total_records,
            groups_after_having=groups_after_having,
            groups_before_having=groups_before_having,
            order_direction=request.order_direction.value,
            aggregation_type=request.aggregation_type.value,
            group_totals=group_totals_map if group_totals_map else None,
        )

    except HTTPException as he:
        raise he
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
