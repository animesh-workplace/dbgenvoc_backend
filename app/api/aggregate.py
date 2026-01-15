from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.schema_new import ComplexFilter, HavingClause, HavingCondition


# ==========================================
#               SCHEMAS
# ==========================================


class AggregationType(str, Enum):
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"
    count = "count"
    percentage = "percentage"
    distinct_count = "distinct_count"


class OrderDirection(str, Enum):
    asc = "asc"
    desc = "desc"


class AggregationRequest(BaseModel):
    column: str = Field(..., description="Target column for aggregation")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")

    # If provided, calculates % share relative to these columns
    percentage_by: Optional[List[str]] = Field(
        None, description="Columns to calculate percentage against (denominator scope)"
    )

    filters: Optional[ComplexFilter] = Field(
        None, description="Complex filters with AND/OR logic (applied before GROUP BY)"
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
        description="Column(s) to order results by. Use 'aggregated_value' for ordering by the aggregation result. For multiple columns, provide as list.",
    )

    order_direction: OrderDirection = Field(
        OrderDirection.desc, description="Order direction: asc or desc"
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
            # For scalar aggregations, only allow ordering by aggregated_value
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
    aggregation_type: str
    total_records: int  # Total records after WHERE filtering
    having_applied: bool = False  # Whether HAVING clause was used
    groups_after_having: Optional[int] = None  # Number of groups after HAVING
    groups_before_having: Optional[int] = None  # Number of groups before HAVING
    # Contains the total count for each group defined in percentage_by
    # Key = "Value" (or "Value1|Value2" for composite), Value = Total Count
    group_totals: Optional[Dict[str, int]] = None
    # Ordering and limiting information
    order_by: Optional[Union[str, List[str]]] = None
    order_direction: Optional[str] = None
    limit: Optional[int] = None
    result: Union[Dict[str, Any], List[Dict[str, Any]]]


# ==========================================
#           INTERNAL HELPERS
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


def _build_having_filter(having_clause: HavingClause, agg_expr):
    """
    Recursively builds SQLAlchemy HAVING conditions.

    Args:
        having_clause: The HavingClause to process
        agg_expr: The aggregation expression to apply conditions to

    Returns:
        SQLAlchemy BinaryExpression for HAVING clause
    """
    conditions = []

    for condition in having_clause.conditions:
        if isinstance(condition, HavingCondition):
            # Base case: single condition
            if condition.operator == "eq":
                conditions.append(agg_expr == condition.value)
            elif condition.operator == "neq":
                conditions.append(agg_expr != condition.value)
            elif condition.operator == "gt":
                conditions.append(agg_expr > condition.value)
            elif condition.operator == "gte":
                conditions.append(agg_expr >= condition.value)
            elif condition.operator == "lt":
                conditions.append(agg_expr < condition.value)
            elif condition.operator == "lte":
                conditions.append(agg_expr <= condition.value)
        else:
            # Recursive case: nested HavingClause
            conditions.append(_build_having_filter(condition, agg_expr))

    # Combine with appropriate logic
    if having_clause.logic == "AND":
        return and_(*conditions)
    else:  # OR
        return or_(*conditions)


def _apply_ordering(
    query, order_by, order_direction, group_attrs, agg_expr, group_by_columns
):
    """
    Apply ordering to the query based on order_by specification.

    Args:
        query: The SQLAlchemy query to order
        order_by: String or list of strings specifying what to order by
        order_direction: 'asc' or 'desc'
        group_attrs: List of SQLAlchemy column attributes for group_by columns
        agg_expr: The aggregation expression
        group_by_columns: List of group_by column names

    Returns:
        Ordered query
    """
    order_clauses = []

    def add_order_clause(column_expr):
        """Helper to add order clause with direction."""
        if order_direction == OrderDirection.desc:
            return column_expr.desc()
        else:
            return column_expr.asc()

    if order_by:
        if isinstance(order_by, str):
            # Single order by column
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
            # Multiple order by columns
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

    # Apply ordering to query
    if order_clauses:
        query = query.order_by(*order_clauses)

    return query


# ==========================================
#           MAIN AGGREGATION API
# ==========================================


async def generic_aggregate(
    request: AggregationRequest, db, table_name: str
) -> AggregationResponse:
    """
    Generic aggregation endpoint with HAVING, ORDER BY, and LIMIT support.

    Query execution order:
    1. FROM table_name
    2. WHERE (filters)
    3. GROUP BY (group_by)
    4. HAVING (having clause on aggregated results)
    5. ORDER BY (order_by)
    6. LIMIT (limit)
    7. SELECT (final result)
    """
    try:
        from app.core import get_model_class, validate_columns, apply_filters

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

        # 3. Capture Total Records (After WHERE, Before GROUP BY)
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
                    # --- SCOPED PERCENTAGE ---
                    partition_attrs = [
                        getattr(model_class, c) for c in request.percentage_by
                    ]
                    denominator = func.sum(func.count(col_attr)).over(
                        partition_by=partition_attrs
                    )
                    agg_expr = (func.count(col_attr) * 100.0) / denominator
                    extra_selects.append(denominator.label("group_total"))
                else:
                    # --- GLOBAL PERCENTAGE ---
                    agg_expr = (func.count(col_attr) * 100.0) / (
                        total_records if total_records > 0 else 1
                    )
            else:
                # --- STANDARD AGGREGATIONS ---
                funcs_map = {
                    AggregationType.count: func.count(col_attr),
                    AggregationType.sum: func.sum(col_attr),
                    AggregationType.avg: func.avg(col_attr),
                    AggregationType.min: func.min(col_attr),
                    AggregationType.max: func.max(col_attr),
                    AggregationType.distinct_count: func.count(func.distinct(col_attr)),
                }
                agg_expr = funcs_map.get(request.aggregation_type)

            # Build base grouped query
            grouped_query = query.with_entities(
                *group_attrs, agg_expr.label("val"), *extra_selects
            ).group_by(*group_attrs)

            # Count groups before HAVING
            groups_before_having = (
                db.query(func.count()).select_from(grouped_query.subquery()).scalar()
            )

            # Apply HAVING clause if present
            if request.having:
                having_filter = _build_having_filter(request.having, agg_expr)
                grouped_query = grouped_query.having(having_filter)

            # Apply ORDER BY if specified
            if request.order_by:
                grouped_query = _apply_ordering(
                    grouped_query,
                    request.order_by,
                    request.order_direction,
                    group_attrs,
                    agg_expr,
                    group_by_columns,
                )

            # Apply LIMIT if specified
            if request.limit:
                grouped_query = grouped_query.limit(request.limit)

            # Execute Query
            results = grouped_query.all()
            groups_after_having = len(results)

            # Format Results
            formatted_results = []

            # Helper to find indices of percentage_by columns in result tuple
            pct_indices = []
            if request.percentage_by:
                pct_indices = [group_by_columns.index(c) for c in request.percentage_by]

            for result in results:
                result_dict = {}

                # A. Map Group Columns
                for i, group_col in enumerate(group_by_columns):
                    result_dict[group_col] = result[i]

                # B. Map Aggregated Value
                val_index = len(group_by_columns)
                val = result[val_index]
                if (
                    request.aggregation_type == AggregationType.percentage
                    and val is not None
                ):
                    val = round(float(val), 2)
                result_dict["aggregated_value"] = val

                # C. Extract Group Totals (if percentage_by active)
                if request.aggregation_type == AggregationType.percentage:
                    if request.percentage_by:
                        # 1. Get total from query
                        total_val = result[val_index + 1]

                        # 2. Build Composite Key for the map
                        key_parts = [str(result[idx]) for idx in pct_indices]
                        key = "|".join(key_parts)

                        # 3. Store in map
                        group_totals_map[key] = int(total_val) if total_val else 0
                    else:
                        group_totals_map["global"] = total_records

                formatted_results.append(result_dict)

            final_result = formatted_results

        else:
            # === SCALAR AGGREGATION (No GROUP BY) ===
            # For scalar aggregations, ordering and limiting don't make sense
            # (except ordering by aggregated_value, but that's trivial for scalar)

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
            table_name=table_name,
            column=request.column,
            total_records=total_records,
            groups_before_having=groups_before_having,
            groups_after_having=groups_after_having,
            aggregation_type=request.aggregation_type.value,
            having_applied=request.having is not None,
            group_totals=group_totals_map if group_totals_map else None,
            order_by=request.order_by,
            order_direction=request.order_direction.value,
            limit=request.limit,
        )

    except HTTPException as he:
        raise he
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
