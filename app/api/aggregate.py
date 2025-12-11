from enum import Enum
from sqlalchemy import func
from fastapi import HTTPException
from app.schema_new import ComplexFilter
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from app.core import get_model_class, validate_columns, apply_filters

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
    # Recursive AND/OR logic
    filters: Optional[ComplexFilter] = Field(
        None, description="Complex filters with AND/OR logic"
    )
    aggregation_type: AggregationType = Field(
        AggregationType.count, description="Type of aggregation"
    )


class AggregationResponse(BaseModel):
    column: str
    table_name: str
    total_records: int
    aggregation_type: str
    # Flexible result: either a simple dict (value) or list of grouped dicts
    result: Union[Dict[str, Any], List[Dict[str, Any]]]


# ==========================================
#           INTERNAL HELPERS
# ==========================================


async def _calculate_standard_agg(query, col_attr, agg_type: AggregationType):
    """Handles standard scalar aggregations (Count, Sum, Avg, etc)."""
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
    """Calculates percentage for non-grouped queries: (Filtered / Total) * 100"""
    numerator = query.with_entities(func.count(col_attr)).scalar() or 0
    # Denominator: Total count in table (ignoring filters)
    denominator = db.query(func.count(col_attr)).select_from(model_class).scalar() or 1

    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


# ==========================================
#           MAIN AGGREGATION API
# ==========================================


async def generic_aggregate(
    request: AggregationRequest, db, table_name: str
) -> AggregationResponse:
    """
    Generic aggregation for any table supporting complex filters and grouping.
    """
    try:
        model_class = get_model_class(table_name)

        # 1. Validate Columns
        validate_columns(model_class, [request.column])
        if request.group_by:
            validate_columns(model_class, request.group_by)

        col_attr = getattr(model_class, request.column)

        # 2. Build Query & Apply Filters
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        # 3. Capture Total Records (Snapshot of filtered dataset)
        total_records = query.count()

        # 4. Perform Aggregation
        if request.group_by:
            # --- Grouped Aggregation ---
            group_attrs = [getattr(model_class, c) for c in request.group_by]

            if request.aggregation_type == AggregationType.percentage:
                # Formula: (Group Count / Total Filtered Records) * 100
                agg_expr = (func.count(col_attr) * 100.0) / (
                    total_records if total_records > 0 else 1
                )
            else:
                funcs = {
                    AggregationType.count: func.count(col_attr),
                    AggregationType.sum: func.sum(col_attr),
                    AggregationType.avg: func.avg(col_attr),
                    AggregationType.min: func.min(col_attr),
                    AggregationType.max: func.max(col_attr),
                    AggregationType.distinct_count: func.count(func.distinct(col_attr)),
                }
                agg_expr = funcs.get(request.aggregation_type)

            # Execute Group By
            results = (
                query.with_entities(*group_attrs, agg_expr.label("val"))
                .group_by(*group_attrs)
                .all()
            )

            # Format Results
            formatted_results = []
            for result in results:
                result_dict = {}
                # Map group columns to their values
                for i, group_col in enumerate(request.group_by):
                    result_dict[group_col] = result[i]

                # Handle value formatting
                val = result[-1]
                if (
                    request.aggregation_type == AggregationType.percentage
                    and val is not None
                ):
                    val = round(float(val), 2)

                result_dict["aggregated_value"] = val
                formatted_results.append(result_dict)

            final_result = formatted_results

        else:
            # --- Scalar Aggregation (No Group By) ---
            if request.aggregation_type == AggregationType.percentage:
                val = await _calculate_global_percentage(
                    query, db, model_class, col_attr
                )
                final_result = {"value": val}
            else:
                val = await _calculate_standard_agg(
                    query, col_attr, request.aggregation_type
                )
                final_result = {"value": val}

        # 5. Return Response
        return AggregationResponse(
            result=final_result,
            table_name=table_name,
            column=request.column,
            total_records=total_records,
            aggregation_type=request.aggregation_type.value,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
