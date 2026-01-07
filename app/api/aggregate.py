from enum import Enum
from sqlalchemy import func
from fastapi import HTTPException
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
    from sqlalchemy import and_, or_

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


# ==========================================
#           MAIN AGGREGATION API
# ==========================================


async def generic_aggregate(
    request: AggregationRequest, db, table_name: str
) -> AggregationResponse:
    """
    Generic aggregation endpoint with HAVING clause support.

    Query execution order:
    1. FROM table_name
    2. WHERE (filters)
    3. GROUP BY (group_by)
    4. HAVING (having clause on aggregated results)
    5. SELECT (final result)
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

            # Execute Query
            results = grouped_query.all()
            groups_after_having = len(results)

            # Format Results
            formatted_results = []

            # Helper to find indices of percentage_by columns in result tuple
            pct_indices = []
            if request.percentage_by:
                pct_indices = [request.group_by.index(c) for c in request.percentage_by]

            for result in results:
                result_dict = {}

                # A. Map Group Columns
                for i, group_col in enumerate(request.group_by):
                    result_dict[group_col] = result[i]

                # B. Map Aggregated Value
                val_index = len(request.group_by)
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
        )

    except HTTPException as he:
        raise he
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
