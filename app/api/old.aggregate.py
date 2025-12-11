from app.core import (
    get_model_class,
    validate_columns,
)
from sqlalchemy import and_, func
from fastapi import HTTPException
from app.schema import AggregationRequest, AggregationType, AggregationResponse


async def generic_aggregate(request: AggregationRequest, db, table_name):
    """Generic aggregation for any table."""
    try:
        model_class = get_model_class(table_name)

        # Validate column
        validate_columns(model_class, [request.column])
        col_attr = getattr(model_class, request.column)

        # Validate group_by columns if provided
        if request.group_by:
            validate_columns(model_class, request.group_by)

        # Start building query
        query = db.query(model_class)

        # Apply filters
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

        # Get total records
        total_records = query.count()

        # Perform aggregation
        if request.group_by:
            # Group by aggregation
            group_columns = [getattr(model_class, col) for col in request.group_by]

            # Build aggregation function
            agg_functions = {
                AggregationType.count: func.count(col_attr),
                AggregationType.sum: func.sum(col_attr),
                AggregationType.avg: func.avg(col_attr),
                AggregationType.min: func.min(col_attr),
                AggregationType.max: func.max(col_attr),
                AggregationType.distinct_count: func.count(func.distinct(col_attr)),
            }

            agg_func = agg_functions[request.aggregation_type]
            agg_query = db.query(
                *group_columns, agg_func.label("aggregated_value")
            ).group_by(*group_columns)

            # Apply filters to aggregation query
            if filter_conditions:
                agg_query = agg_query.filter(and_(*filter_conditions))

            results = agg_query.all()

            # Format results
            formatted_results = []
            for result in results:
                result_dict = {}
                for i, group_col in enumerate(request.group_by):
                    result_dict[group_col] = result[i]
                result_dict["aggregated_value"] = result[-1]
                formatted_results.append(result_dict)

            return AggregationResponse(
                table_name=table_name,
                column=request.column,
                result=formatted_results,
                total_records=total_records,
                aggregation_type=request.aggregation_type.value,
            )

        else:
            # Simple aggregation
            agg_functions = {
                AggregationType.count: query.count(),
                AggregationType.sum: db.query(func.sum(col_attr))
                .filter(*filter_conditions)
                .scalar()
                or 0
                if filter_conditions
                else db.query(func.sum(col_attr)).scalar() or 0,
                AggregationType.avg: db.query(func.avg(col_attr))
                .filter(*filter_conditions)
                .scalar()
                or 0
                if filter_conditions
                else db.query(func.avg(col_attr)).scalar() or 0,
                AggregationType.min: db.query(func.min(col_attr))
                .filter(*filter_conditions)
                .scalar()
                if filter_conditions
                else db.query(func.min(col_attr)).scalar(),
                AggregationType.max: db.query(func.max(col_attr))
                .filter(*filter_conditions)
                .scalar()
                if filter_conditions
                else db.query(func.max(col_attr)).scalar(),
                AggregationType.distinct_count: db.query(
                    func.count(func.distinct(col_attr))
                )
                .filter(*filter_conditions)
                .scalar()
                or 0
                if filter_conditions
                else db.query(func.count(func.distinct(col_attr))).scalar() or 0,
            }

            result = agg_functions[request.aggregation_type]

            return AggregationResponse(
                table_name=table_name,
                column=request.column,
                result={"value": result},
                total_records=total_records,
                aggregation_type=request.aggregation_type.value,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
