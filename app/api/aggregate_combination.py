from enum import Enum
from sqlalchemy import func
from fastapi import HTTPException
from pydantic import BaseModel, Field
from app.schema_new import ComplexFilter
from typing import Any, Dict, List, Optional, Union
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

    # Updated to ComplexFilter for powerful AND/OR logic
    filters: Optional[ComplexFilter] = Field(
        None, description="Filters to apply before concatenation"
    )

    aggregation_type: AggregationType = Field(
        AggregationType.count,
        description="Type of aggregation (count or distinct_count)",
    )


class AggregationResponse(BaseModel):
    column: str
    table_name: str
    total_records: int
    aggregation_type: str
    result: Union[Dict[str, Any], List[Dict[str, Any]]]


# ==========================================
#           MAIN API FUNCTION
# ==========================================


async def generic_concatenated_aggregate(
    request: ConcatenatedAggregationRequest, table_name: str, db
) -> AggregationResponse:
    """
    Concatenates values from multiple columns (e.g., "Ref>Alt") and aggregates them.
    Supports: Count, Distinct Count, and Percentage.
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

        # 2. Build Concatenated Expression
        col_attrs = [getattr(model_class, col) for col in request.columns]
        concatenated_col = col_attrs[0]
        for i in range(1, len(col_attrs)):
            concatenated_col = func.concat(
                concatenated_col, request.separator, col_attrs[i]
            )

        # 3. Base Query & Filters (Calculate Total Records)
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        total_records = query.count()

        # 4. Aggregation Logic
        formatted_results = []
        final_result = None

        # We need the filter expression again for the specific aggregation query
        # (See internal helper explanation)
        filter_expr = (
            _build_filter_expression(model_class, request.filters)
            if request.filters
            else True
        )

        if request.group_by:
            # --- Group By + Concatenation ---
            group_attrs = [getattr(model_class, c) for c in request.group_by]

            if request.aggregation_type in [
                AggregationType.count,
                AggregationType.percentage,
            ]:
                # Both Count and Percentage need the raw count first
                agg_query = (
                    db.query(
                        *group_attrs,
                        concatenated_col.label("concatenated_value"),
                        func.count(concatenated_col).label("count"),
                    )
                    .filter(filter_expr)
                    .group_by(*group_attrs, concatenated_col)
                )

                results = agg_query.all()

                for res in results:
                    item = {}
                    for i, g_col in enumerate(request.group_by):
                        item[g_col] = res[i]

                    item["concatenated_value"] = res[-2]
                    count_val = res[-1]

                    if request.aggregation_type == AggregationType.percentage:
                        # Calculation: (Count / Total) * 100
                        val = (
                            (count_val / total_records * 100)
                            if total_records > 0
                            else 0.0
                        )
                        item["aggregated_value"] = round(val, 2)
                    else:
                        item["aggregated_value"] = count_val

                    formatted_results.append(item)

                final_result = formatted_results

            elif request.aggregation_type == AggregationType.distinct_count:
                # Distinct Count of unique combos per group
                agg_query = (
                    db.query(
                        *group_attrs,
                        func.count(func.distinct(concatenated_col)).label(
                            "distinct_cnt"
                        ),
                    )
                    .filter(filter_expr)
                    .group_by(*group_attrs)
                )

                results = agg_query.all()

                for res in results:
                    item = {}
                    for i, g_col in enumerate(request.group_by):
                        item[g_col] = res[i]
                    item["concatenated_value"] = (
                        "N/A"  # Not applicable for distinct scalar
                    )
                    item["aggregated_value"] = res[-1]
                    formatted_results.append(item)

                final_result = formatted_results

        else:
            # --- No Grouping (Global Distribution) ---

            if request.aggregation_type in [
                AggregationType.count,
                AggregationType.percentage,
            ]:
                # Frequency distribution of the concatenated string across whole table
                agg_query = (
                    db.query(
                        concatenated_col.label("concatenated_value"),
                        func.count(concatenated_col).label("count"),
                    )
                    .filter(filter_expr)
                    .group_by(concatenated_col)
                )

                results = agg_query.all()
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
                    else:
                        formatted_results.append(
                            {
                                "concatenated_value": row.concatenated_value,
                                "aggregated_value": count_val,
                            }
                        )

                final_result = formatted_results

            elif request.aggregation_type == AggregationType.distinct_count:
                # Scalar distinct count
                cnt = (
                    db.query(func.count(func.distinct(concatenated_col)))
                    .filter(filter_expr)
                    .scalar()
                    or 0
                )
                final_result = {"value": cnt}

        # 5. Return Response
        return AggregationResponse(
            table_name=table_name,
            column="+".join(request.columns),
            aggregation_type=request.aggregation_type.value,
            result=final_result,
            total_records=total_records,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Concatenated aggregation failed: {str(e)}"
        )
