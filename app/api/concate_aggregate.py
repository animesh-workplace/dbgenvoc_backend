from app.core import (
    get_model_class,
    validate_columns,
)
from sqlalchemy import and_, func
from fastapi import HTTPException
from app.schema import (
    AggregationType,
    AggregationResponse,
    ConcatenatedAggregationRequest,
)


async def generic_concatenated_aggregate(
    request: ConcatenatedAggregationRequest, table_name, db
):
    """Generic concatenated aggregation (e.g., ref_allele>tumor_seq_allele2)."""
    try:
        model_class = get_model_class(table_name)

        # Validate columns
        validate_columns(model_class, request.columns)
        col_attrs = [getattr(model_class, col_name) for col_name in request.columns]

        # Validate group_by columns
        if request.group_by:
            validate_columns(model_class, request.group_by)

        # Create concatenated column expression
        concatenated_col = col_attrs[0]
        for i in range(1, len(col_attrs)):
            concatenated_col = func.concat(
                concatenated_col, request.separator, col_attrs[i]
            )

        # Build query with filters
        query = db.query(model_class)
        filter_conditions = []

        if request.filters:
            for filter_col, filter_value in request.filters.items():
                if hasattr(model_class, filter_col):
                    filter_attr = getattr(model_class, filter_col)
                    if isinstance(filter_value, list):
                        filter_conditions.append(filter_attr.in_(filter_value))
                    else:
                        filter_conditions.append(filter_attr == filter_value)

        if filter_conditions:
            query = query.filter(and_(*filter_conditions))

        total_records = query.count()

        # Perform aggregation
        if request.group_by:
            group_columns = [getattr(model_class, col) for col in request.group_by]

            if request.aggregation_type in [
                AggregationType.count,
                AggregationType.distinct_count,
            ]:
                if request.aggregation_type == AggregationType.count:
                    agg_func = func.count(concatenated_col)
                else:
                    agg_func = func.count(func.distinct(concatenated_col))

                agg_query = db.query(
                    *group_columns,
                    concatenated_col.label("concatenated_value"),
                    agg_func.label("count"),
                ).group_by(*group_columns, concatenated_col)

                if filter_conditions:
                    agg_query = agg_query.filter(and_(*filter_conditions))

                results = agg_query.all()

                formatted_results = []
                for result in results:
                    result_dict = {}
                    for i, group_col in enumerate(request.group_by):
                        result_dict[group_col] = result[i]
                    result_dict["concatenated_value"] = result[-2]
                    result_dict["count"] = result[-1]
                    formatted_results.append(result_dict)

                return AggregationResponse(
                    table_name=table_name,
                    column=f"{'+'.join(request.columns)}",
                    aggregation_type=request.aggregation_type.value,
                    result=formatted_results,
                    total_records=total_records,
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Only count and distinct_count are supported for concatenated columns with grouping",
                )

        else:
            # Simple concatenated aggregation
            if request.aggregation_type == AggregationType.count:
                agg_query = db.query(
                    concatenated_col.label("concatenated_value"),
                    func.count(concatenated_col).label("count"),
                ).group_by(concatenated_col)

                if filter_conditions:
                    agg_query = agg_query.filter(and_(*filter_conditions))

                results = agg_query.all()
                formatted_results = [
                    {
                        "concatenated_value": result.concatenated_value,
                        "count": result.count,
                    }
                    for result in results
                ]

                return AggregationResponse(
                    table_name=table_name,
                    column=f"{'+'.join(request.columns)}",
                    aggregation_type=request.aggregation_type.value,
                    result=formatted_results,
                    total_records=total_records,
                )

            elif request.aggregation_type == AggregationType.distinct_count:
                result = db.query(func.count(func.distinct(concatenated_col)))
                if filter_conditions:
                    result = result.filter(and_(*filter_conditions))
                result = result.scalar() or 0

                return AggregationResponse(
                    table_name=table_name,
                    column=f"{'+'.join(request.columns)}",
                    aggregation_type=request.aggregation_type.value,
                    result={"distinct_count": result},
                    total_records=total_records,
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail="Only count and distinct_count are supported for concatenated columns",
                )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Concatenated aggregation failed: {str(e)}"
        )
