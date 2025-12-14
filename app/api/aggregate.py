from enum import Enum
from sqlalchemy import func
from fastapi import HTTPException
from pydantic import BaseModel, Field
from app.schema_new import ComplexFilter
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

    # If provided, calculates % share relative to these columns
    percentage_by: Optional[List[str]] = Field(
        None, description="Columns to calculate percentage against (denominator scope)"
    )

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

    # New Key: Contains the total count for each group defined in percentage_by
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


# ==========================================
#           MAIN AGGREGATION API
# ==========================================


async def generic_aggregate(
    request: AggregationRequest, db, table_name: str
) -> AggregationResponse:
    try:
        model_class = get_model_class(table_name)

        # 1. Validation
        validate_columns(model_class, [request.column])
        if request.group_by:
            validate_columns(model_class, request.group_by)

        if request.percentage_by:
            validate_columns(model_class, request.percentage_by)
            if not request.group_by or not set(request.percentage_by).issubset(
                set(request.group_by)
            ):
                raise HTTPException(
                    status_code=400,
                    detail="percentage_by columns must be present in group_by columns",
                )

        col_attr = getattr(model_class, request.column)

        # 2. Build Query & Apply Filters
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        # 3. Capture Total Records (Filtered)
        total_records = query.count()

        # 4. Perform Aggregation
        final_result = None
        group_totals_map = {}

        if request.group_by:
            group_attrs = [getattr(model_class, c) for c in request.group_by]
            extra_selects = []

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
                funcs = {
                    AggregationType.count: func.count(col_attr),
                    AggregationType.sum: func.sum(col_attr),
                    AggregationType.avg: func.avg(col_attr),
                    AggregationType.min: func.min(col_attr),
                    AggregationType.max: func.max(col_attr),
                    AggregationType.distinct_count: func.count(func.distinct(col_attr)),
                }
                agg_expr = funcs.get(request.aggregation_type)

            # Execute Query
            results = (
                query.with_entities(*group_attrs, agg_expr.label("val"), *extra_selects)
                .group_by(*group_attrs)
                .all()
            )

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

                # B. Map Value
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

                        # 2. Build Composite Key for the map (e.g. "DiseaseA" or "DiseaseA|Male")
                        key_parts = [str(result[idx]) for idx in pct_indices]
                        key = "|".join(key_parts)

                        # 3. Store in map
                        group_totals_map[key] = int(total_val) if total_val else 0
                    else:
                        group_totals_map["global"] = total_records

                formatted_results.append(result_dict)

            final_result = formatted_results

        else:
            # --- Scalar Aggregation ---
            if request.aggregation_type == AggregationType.percentage:
                val = await _calculate_global_percentage(
                    query, db, model_class, col_attr
                )
                final_result = {"value": val}
                group_totals_map["global"] = (
                    total_records  # Global total matches DB total approx
                )
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
            aggregation_type=request.aggregation_type.value,
            group_totals=group_totals_map if group_totals_map else None,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
