from app.core import (
    row_to_dict,
    get_model_class,
    validate_columns,
    get_searchable_columns,
)
from sqlalchemy import or_
from fastapi import HTTPException
from app.schema import SearchResponse


async def generic_search(
    table_name,
    term,
    page,
    page_size,
    exact_match,
    search_columns,
    db,
):
    """Generic search across any table."""
    try:
        model_class = get_model_class(table_name)

        # Get searchable columns
        if search_columns:
            columns_to_search = validate_columns(model_class, search_columns)
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
            if exact_match:
                search_conditions.append(col_attr == term)
            else:
                search_conditions.append(col_attr.ilike(f"%{term}%"))

        if search_conditions:
            query = query.filter(or_(*search_conditions))

        # Get total count
        total_results = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        # Convert to dictionaries
        result_dicts = [row_to_dict(row) for row in results]

        return SearchResponse(
            table_name=table_name,
            total_results=total_results,
            page=page,
            page_size=page_size,
            results=result_dicts,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
