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

    # New Field: percentage_by
    # Usage: If group_by=['disease', 'gene'], percentage_by=['disease']
    # Result: Gene mutation combo % within that Disease.
    percentage_by: Optional[List[str]] = Field(
        None, description="Columns to calculate percentage against (denominator scope)"
    )

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

    # New Key: Group Totals
    group_totals: Optional[Dict[str, int]] = None

    result: Union[Dict[str, Any], List[Dict[str, Any]]]


# ==========================================
#           MAIN API FUNCTION
# ==========================================


async def generic_concatenated_aggregate(
    request: ConcatenatedAggregationRequest, table_name: str, db
) -> AggregationResponse:
    """
    Concatenates values from multiple columns (e.g., "Ref>Alt") and aggregates them.
    Supports Scoped Percentages (percentage_by) and Group Totals.
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
            if not request.group_by or not set(request.percentage_by).issubset(
                set(request.group_by)
            ):
                raise HTTPException(
                    status_code=400,
                    detail="percentage_by columns must be present in group_by columns",
                )

        # 2. Build Concatenated Expression (with NULL Safety)
        col_attrs = [getattr(model_class, col) for col in request.columns]
        concatenated_col = func.coalesce(col_attrs[0], "")
        for i in range(1, len(col_attrs)):
            concatenated_col = func.concat(
                concatenated_col, request.separator, func.coalesce(col_attrs[i], "")
            )

        # 3. Base Query & Filters (Calculate Total Records)
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        total_records = query.count()

        # 4. Aggregation Logic
        formatted_results = []
        final_result = None
        group_totals_map = {}

        # Re-build filter expression for the specific aggregation query
        filter_expr = (
            _build_filter_expression(model_class, request.filters)
            if request.filters
            else True
        )

        if request.group_by:
            # --- Group By + Concatenation ---
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
                    # Denominator = Sum of counts (1 per row for concat string), partitioned by percentage_by
                    partition_attrs = [
                        getattr(model_class, c) for c in request.percentage_by
                    ]

                    # Note: We are counting occurrences of the concatenated string.
                    # Since we group by (GroupCols + ConcatString), count(*) gives the numerator.
                    # To get the denominator (Group Total), we sum that count over the partition.

                    # Logic:
                    # 1. Group by [Disease, ConcatStr] -> Count = 20 (Numerator)
                    # 2. Window Sum over [Disease] -> Sum(20, 30, ...) = 500 (Denominator)

                    # However, standard SQL aggregate-window mixing can be tricky.
                    # A cleaner way in SQLAlchemy ORM for this specific combo pattern:
                    # We usually need a subquery or strict windowing.

                    # SIMPLIFIED APPROACH:
                    # Since we are already grouping by (GroupAttrs + Concat), we can't easily window over just GroupAttrs
                    # in the same query level in all SQL dialects without a subquery.

                    # BUT, for standard Postgres/MySQL 8+, we can do:
                    # sum(count(concat_col)) OVER (PARTITION BY partition_attrs)

                    denominator = func.sum(func.count(concatenated_col)).over(
                        partition_by=partition_attrs
                    )
                    count_col = func.count(concatenated_col)

                    extra_selects = [
                        count_col.label("count"),
                        denominator.label("group_total"),
                    ]

                    # Note: We calculate percentage in Python loop to be safe with float division types across DBs
                else:
                    # Standard Count or Global Percentage
                    extra_selects = [func.count(concatenated_col).label("count")]

                # Build Query
                agg_query = (
                    db.query(
                        *group_attrs,
                        concatenated_col.label("concatenated_value"),
                        *extra_selects,
                    )
                    .filter(filter_expr)
                    .group_by(*group_attrs, concatenated_col)
                )

                results = agg_query.all()

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
                    # If Scoped %, we have count at +1 and total at +2
                    # If Standard, we have count at +1

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
                # Distinct count logic (rarely used with percentage_by in this context)
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
                    item["concatenated_value"] = "N/A"
                    item["aggregated_value"] = res[-1]
                    formatted_results.append(item)

                final_result = formatted_results

        else:
            # --- No Grouping (Global Distribution) ---
            if request.aggregation_type in [
                AggregationType.count,
                AggregationType.percentage,
            ]:
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

        # 5. Return Response
        return AggregationResponse(
            table_name=table_name,
            column="+".join(request.columns),
            aggregation_type=request.aggregation_type.value,
            result=final_result,
            total_records=total_records,
            group_totals=group_totals_map if group_totals_map else None,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Concatenated aggregation failed: {str(e)}"
        )
