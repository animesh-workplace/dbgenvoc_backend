from app.core import (
    row_to_dict,
    get_model_class,
    validate_columns,
    get_searchable_columns,
)
from sqlalchemy import or_
from fastapi import HTTPException
from app.schema import SearchResponse, SearchRequest


async def generic_search(table_name, request: SearchRequest, db):
    """Generic search across any table."""
    try:
        model_class = get_model_class(table_name)

        # Get searchable columns
        if request.search_columns:
            columns_to_search = validate_columns(model_class, request.search_columns)
        else:
            columns_to_search = get_searchable_columns(table_name)
            # Filter to only existing columns
            columns_to_search = [
                col for col in columns_to_search if hasattr(model_class, col)
            ]

        # Build query
        query = db.query(model_class)

        # Create search conditions
        search_conditions = []
        for column in columns_to_search:
            col_attr = getattr(model_class, column)
            if request.exact_match:
                search_conditions.append(col_attr == request.term)
            else:
                search_conditions.append(col_attr.ilike(f"%{request.term}%"))

        if search_conditions:
            query = query.filter(or_(*search_conditions))

        # Get total count
        total_results = query.count()

        # Apply pagination
        offset = (request.page - 1) * request.page_size
        results = query.offset(offset).limit(request.page_size).all()

        # Convert to dictionaries
        result_dicts = [row_to_dict(row) for row in results]

        return SearchResponse(
            page=request.page,
            results=result_dicts,
            table_name=table_name,
            total_results=total_results,
            page_size=request.page_size,
        )

    except Exception as e:
        print(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
