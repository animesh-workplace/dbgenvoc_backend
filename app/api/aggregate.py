from sqlalchemy import func
from fastapi import HTTPException
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.core import get_model_class, validate_columns, apply_filters
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

    @field_validator("having", "order_by")
    @classmethod
    def _validate_requires_group_by(cls, v, info):
        field_name = info.field_name
        if v is not None and not info.data.get("group_by"):
            if field_name == "having":
                raise ValueError("HAVING clause requires group_by to be specified")
            elif field_name == "order_by" and v != "aggregated_value":
                raise ValueError(
                    "For scalar aggregations (without group_by), order_by must be 'aggregated_value' or None"
                )
        return v

    @field_validator("percentage_by")
    @classmethod
    def _validate_percentage_by(cls, v, info):
        if v and (
            not (group_by := info.data.get("group_by")) or not set(v).issubset(group_by)
        ):
            raise ValueError(
                "percentage_by columns must be present in group_by columns"
            )
        return v

    @field_validator("limit")
    @classmethod
    def _validate_limit(cls, v):
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


def _apply_ordering(
    query, order_by, order_direction, group_attrs, agg_expr, group_by_columns
):
    """Apply ordering to the query."""
    if not order_by:
        return query

    order_clauses = []
    order_by_list = [order_by] if isinstance(order_by, str) else order_by

    for order_col in order_by_list:
        if order_col == "aggregated_value":
            column_expr = agg_expr
        elif order_col in group_by_columns:
            idx = group_by_columns.index(order_col)
            column_expr = group_attrs[idx]
        else:
            raise ValueError(
                f"Cannot order by '{order_col}'. Must be 'aggregated_value' or one of group_by columns: {group_by_columns}"
            )
        order_clauses.append(
            column_expr.desc()
            if order_direction == SortOrder.DESC
            else column_expr.asc()
        )

    return query.order_by(*order_clauses)


# ==========================================
# MAIN AGGREGATION API
# ==========================================


async def generic_aggregate(
    request: AggregationRequest, db, table_name: str
) -> AggregationResponse:
    """
    Enhanced generic aggregation endpoint with unified genomic position filtering.
    """
    try:
        model_class = get_model_class(table_name)

        # Validate all columns at once
        columns_to_validate = {request.column}
        if request.group_by:
            columns_to_validate.update(request.group_by)
        if request.percentage_by:
            columns_to_validate.update(request.percentage_by)
        validate_columns(model_class, list(columns_to_validate))

        # Build initial query with filters
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)
        query = _apply_genomic_position_filter(
            query, model_class, request.genomic_filter
        )

        total_records = query.count()

        # Handle scalar vs grouped aggregation
        if request.group_by:
            # === GROUPED AGGREGATION ===
            group_by_columns = request.group_by
            group_attrs = [getattr(model_class, c) for c in group_by_columns]
            col_attr = getattr(model_class, request.column)
            extra_selects = []

            # Build aggregation expression
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
                    agg_expr = (func.count(col_attr) * 100.0) / (total_records or 1)
            else:
                agg_expr = _AGGREGATION_FUNCS[request.aggregation_type](col_attr)

            # Build and execute grouped query
            grouped_query = query.with_entities(
                *group_attrs, agg_expr.label("val"), *extra_selects
            ).group_by(*group_attrs)

            # Get groups before HAVING more efficiently
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
                    group_by_columns,
                )

            if request.limit:
                grouped_query = grouped_query.limit(request.limit)

            results = grouped_query.all()
            groups_after_having = len(results)

            # Format results
            formatted_results = []
            group_totals_map = {}
            pct_indices = (
                [group_by_columns.index(c) for c in request.percentage_by]
                if request.percentage_by
                else []
            )

            for result in results:
                result_dict = {
                    group_by_columns[i]: result[i] for i in range(len(group_by_columns))
                }
                val = result[len(group_by_columns)]

                if (
                    request.aggregation_type == AggregationType.percentage
                    and val is not None
                ):
                    val = round(float(val), 2)

                result_dict["aggregated_value"] = val

                if (
                    request.aggregation_type == AggregationType.percentage
                    and request.percentage_by
                ):
                    total_val = result[len(group_by_columns) + 1]
                    key = "|".join(str(result[idx]) for idx in pct_indices)
                    group_totals_map[key] = int(total_val) if total_val else 0

                formatted_results.append(result_dict)

            if (
                request.aggregation_type == AggregationType.percentage
                and not request.percentage_by
            ):
                group_totals_map = {"global": total_records}

            final_result = formatted_results

        else:
            # === SCALAR AGGREGATION ===
            col_attr = getattr(model_class, request.column)
            group_totals_map = None

            if request.aggregation_type == AggregationType.percentage:
                numerator = query.with_entities(func.count(col_attr)).scalar() or 0
                denominator = (
                    db.query(func.count(col_attr)).select_from(model_class).scalar()
                    or 1
                )
                val = round((numerator / denominator) * 100, 2) if denominator else 0.0
                group_totals_map = {"global": total_records}
            else:
                val = (
                    query.with_entities(
                        _AGGREGATION_FUNCS[request.aggregation_type](col_attr)
                    ).scalar()
                    or 0
                )

            final_result = {"value": val}
            groups_before_having = groups_after_having = None

        return AggregationResponse(
            result=final_result,
            limit=request.limit,
            table_name=table_name,
            column=request.column,
            order_by=request.order_by,
            total_records=total_records,
            group_totals=group_totals_map or None,
            groups_after_having=groups_after_having,
            groups_before_having=groups_before_having,
            order_direction=request.order_direction.value,
            aggregation_type=request.aggregation_type.value,
        )

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
