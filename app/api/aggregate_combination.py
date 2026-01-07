from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.schema_new import ComplexFilter, HavingClause, HavingCondition
from app.core import (
    apply_filters,
    get_model_class,
    validate_columns,
    _build_filter_expression,
)


# ==========================================
#               SCHEMAS
# ==========================================


class AggregationType(str, Enum):
    count = "count"
    percentage = "percentage"
    distinct_count = "distinct_count"


class ConcatenatedAggregationRequest(BaseModel):
    separator: str = Field(", ", description="Separator for concatenation (e.g. ' > ')")
    columns: List[str] = Field(..., description="List of columns to concatenate")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")

    # New Field: percentage_by
    # Usage: If group_by=['disease', 'gene'], percentage_by=['disease']
    # Result: Gene mutation combo % within that Disease.
    percentage_by: Optional[List[str]] = Field(
        None, description="Columns to calculate percentage against (denominator scope)"
    )

    filters: Optional[ComplexFilter] = Field(
        None,
        description="Filters to apply before concatenation (applied before GROUP BY)",
    )

    aggregation_type: AggregationType = Field(
        AggregationType.count,
        description="Type of aggregation (count, percentage, or distinct_count)",
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
    total_records: int
    aggregation_type: str
    having_applied: bool = False  # Whether HAVING clause was used
    groups_after_having: Optional[int] = None  # Number of groups after HAVING
    groups_before_having: Optional[int] = None  # Number of groups before HAVING

    # New Key: Group Totals
    group_totals: Optional[Dict[str, int]] = None

    result: Union[Dict[str, Any], List[Dict[str, Any]]]


# ==========================================
#           INTERNAL HELPERS
# ==========================================


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


# ==========================================
#           MAIN API FUNCTION
# ==========================================


async def generic_concatenated_aggregate(
    request: ConcatenatedAggregationRequest, table_name: str, db
) -> AggregationResponse:
    """
    Concatenates values from multiple columns (e.g., "Ref>Alt") and aggregates them.
    Supports Scoped Percentages (percentage_by), Group Totals, and HAVING clause.

    Query execution order:
    1. FROM table_name
    2. WHERE (filters)
    3. GROUP BY (group_by + concatenated_value)
    4. HAVING (having clause on aggregated results)
    5. SELECT (final result)
    """
    try:
        model_class = get_model_class(table_name)

        # 1. Validation
        allowed_types = [
            AggregationType.count,
            AggregationType.distinct_count,
            AggregationType.percentage,
        ]
        if request.aggregation_type not in allowed_types:
            raise HTTPException(
                400, "Supported types: count, distinct_count, percentage"
            )

        validate_columns(model_class, request.columns)
        if request.group_by:
            validate_columns(model_class, request.group_by)

        if request.percentage_by:
            validate_columns(model_class, request.percentage_by)

        # 2. Build Concatenated Expression (with NULL Safety)
        col_attrs = [getattr(model_class, col) for col in request.columns]
        concatenated_col = func.coalesce(col_attrs[0], "")
        for i in range(1, len(col_attrs)):
            concatenated_col = func.concat(
                concatenated_col, request.separator, func.coalesce(col_attrs[i], "")
            )

        # 3. Base Query & Apply WHERE Filters
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        # 4. Capture Total Records (After WHERE, Before GROUP BY)
        total_records = query.count()

        # 5. Aggregation Logic
        formatted_results = []
        final_result = None
        group_totals_map = {}
        groups_before_having = None
        groups_after_having = None

        # Re-build filter expression for the specific aggregation query
        filter_expr = (
            _build_filter_expression(model_class, request.filters)
            if request.filters
            else True
        )

        if request.group_by:
            # === GROUPED AGGREGATION WITH CONCATENATION ===
            group_attrs = [getattr(model_class, c) for c in request.group_by]
            extra_selects = []

            if request.aggregation_type in [
                AggregationType.count,
                AggregationType.percentage,
            ]:
                if (
                    request.aggregation_type == AggregationType.percentage
                    and request.percentage_by
                ):
                    # --- SCOPED PERCENTAGE (Window Function) ---
                    partition_attrs = [
                        getattr(model_class, c) for c in request.percentage_by
                    ]

                    denominator = func.sum(func.count(concatenated_col)).over(
                        partition_by=partition_attrs
                    )
                    count_col = func.count(concatenated_col)

                    # For HAVING, we use the count expression
                    agg_expr = count_col

                    extra_selects = [
                        count_col.label("count"),
                        denominator.label("group_total"),
                    ]
                elif request.aggregation_type == AggregationType.percentage:
                    # --- GLOBAL PERCENTAGE ---
                    count_col = func.count(concatenated_col)
                    agg_expr = count_col
                    extra_selects = [count_col.label("count")]
                else:
                    # Standard Count
                    count_col = func.count(concatenated_col)
                    agg_expr = count_col
                    extra_selects = [count_col.label("count")]

                # Build Grouped Query
                grouped_query = (
                    db.query(
                        *group_attrs,
                        concatenated_col.label("concatenated_value"),
                        *extra_selects,
                    )
                    .filter(filter_expr)
                    .group_by(*group_attrs, concatenated_col)
                )

                # Count groups before HAVING
                groups_before_having = (
                    db.query(func.count())
                    .select_from(grouped_query.subquery())
                    .scalar()
                )

                # Apply HAVING clause if present
                if request.having:
                    having_filter = _build_having_filter(request.having, agg_expr)
                    grouped_query = grouped_query.having(having_filter)

                # Execute Query
                results = grouped_query.all()
                groups_after_having = len(results)

                # Indices Helper for percentage_by
                pct_indices = []
                if request.percentage_by:
                    pct_indices = [
                        request.group_by.index(c) for c in request.percentage_by
                    ]

                for res in results:
                    item = {}
                    # 1. Map Group Columns
                    for i, g_col in enumerate(request.group_by):
                        item[g_col] = res[i]

                    # 2. Map Concat Value (It's at index len(group_by))
                    concat_idx = len(request.group_by)
                    item["concatenated_value"] = res[concat_idx]

                    # 3. Extract Count and Total
                    count_val = res[concat_idx + 1]

                    if request.aggregation_type == AggregationType.percentage:
                        if request.percentage_by:
                            group_total = res[concat_idx + 2]
                            val = (
                                (count_val / group_total * 100)
                                if group_total > 0
                                else 0.0
                            )
                            item["aggregated_value"] = round(val, 2)

                            # Add to Totals Map
                            key_parts = [str(res[idx]) for idx in pct_indices]
                            key = "|".join(key_parts)
                            group_totals_map[key] = int(group_total)
                        else:
                            # Global %
                            val = (
                                (count_val / total_records * 100)
                                if total_records > 0
                                else 0.0
                            )
                            item["aggregated_value"] = round(val, 2)
                            group_totals_map["global"] = total_records
                    else:
                        item["aggregated_value"] = count_val

                    formatted_results.append(item)

                final_result = formatted_results

            elif request.aggregation_type == AggregationType.distinct_count:
                # Distinct count logic
                agg_expr = func.count(func.distinct(concatenated_col))

                grouped_query = (
                    db.query(
                        *group_attrs,
                        agg_expr.label("distinct_cnt"),
                    )
                    .filter(filter_expr)
                    .group_by(*group_attrs)
                )

                # Count groups before HAVING
                groups_before_having = (
                    db.query(func.count())
                    .select_from(grouped_query.subquery())
                    .scalar()
                )

                # Apply HAVING clause if present
                if request.having:
                    having_filter = _build_having_filter(request.having, agg_expr)
                    grouped_query = grouped_query.having(having_filter)

                results = grouped_query.all()
                groups_after_having = len(results)

                for res in results:
                    item = {}
                    for i, g_col in enumerate(request.group_by):
                        item[g_col] = res[i]
                    item["concatenated_value"] = "N/A"
                    item["aggregated_value"] = res[-1]
                    formatted_results.append(item)

                final_result = formatted_results

        else:
            # === NO GROUPING (Global Distribution) ===
            if request.aggregation_type in [
                AggregationType.count,
                AggregationType.percentage,
            ]:
                count_col = func.count(concatenated_col)

                agg_query = (
                    db.query(
                        concatenated_col.label("concatenated_value"),
                        count_col.label("count"),
                    )
                    .filter(filter_expr)
                    .group_by(concatenated_col)
                )

                # Count groups before HAVING
                groups_before_having = (
                    db.query(func.count()).select_from(agg_query.subquery()).scalar()
                )

                # Apply HAVING clause if present
                if request.having:
                    having_filter = _build_having_filter(request.having, count_col)
                    agg_query = agg_query.having(having_filter)

                results = agg_query.all()
                groups_after_having = len(results)

                for row in results:
                    count_val = row.count
                    if request.aggregation_type == AggregationType.percentage:
                        val = (
                            (count_val / total_records * 100)
                            if total_records > 0
                            else 0.0
                        )
                        formatted_results.append(
                            {
                                "concatenated_value": row.concatenated_value,
                                "aggregated_value": round(val, 2),
                            }
                        )
                        group_totals_map["global"] = total_records
                    else:
                        formatted_results.append(
                            {
                                "concatenated_value": row.concatenated_value,
                                "aggregated_value": count_val,
                            }
                        )

                final_result = formatted_results

            elif request.aggregation_type == AggregationType.distinct_count:
                cnt = (
                    db.query(func.count(func.distinct(concatenated_col)))
                    .filter(filter_expr)
                    .scalar()
                    or 0
                )
                final_result = {"value": cnt}

        # 6. Return Response
        return AggregationResponse(
            table_name=table_name,
            column="+".join(request.columns),
            aggregation_type=request.aggregation_type.value,
            result=final_result,
            total_records=total_records,
            groups_before_having=groups_before_having,
            groups_after_having=groups_after_having,
            having_applied=request.having is not None,
            group_totals=group_totals_map if group_totals_map else None,
        )

    except HTTPException as he:
        raise he
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Concatenated aggregation failed: {str(e)}"
        )
