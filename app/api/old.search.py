from app.core import (
    row_to_dict,
    get_model_class,
    validate_columns,
    get_searchable_columns,
)
from typing import Optional
from fastapi import HTTPException
from sqlalchemy import or_, asc, desc
from app.schema import SearchResponse, SearchRequest, SearchMode, SortOrder


async def generic_search(table_name, request: SearchRequest, db):
    """Generic search across any table with support for multiple terms and sorting."""
    try:
        model_class = get_model_class(table_name)

        # Normalize terms to always be a list
        search_terms = []
        if isinstance(request.term, str):
            search_terms = [request.term]
        elif isinstance(request.term, list):
            search_terms = [term.strip() for term in request.term if term.strip()]

        if not search_terms:
            raise HTTPException(
                status_code=400, detail="At least one search term is required"
            )

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

        # Create search conditions based on search mode
        if request.search_mode == SearchMode.ANY:
            # OR logic: match ANY term in ANY column
            search_conditions = []
            for column in columns_to_search:
                col_attr = getattr(model_class, column)
                for term in search_terms:
                    if request.exact_match:
                        search_conditions.append(col_attr == term)
                    else:
                        search_conditions.append(col_attr.ilike(f"%{term}%"))

            if search_conditions:
                query = query.filter(or_(*search_conditions))

        elif request.search_mode == SearchMode.ALL:
            # AND logic: must match ALL terms (each term in at least one column)
            for term in search_terms:
                term_conditions = []
                for column in columns_to_search:
                    col_attr = getattr(model_class, column)
                    if request.exact_match:
                        term_conditions.append(col_attr == term)
                    else:
                        term_conditions.append(col_attr.ilike(f"%{term}%"))

                if term_conditions:
                    query = query.filter(or_(*term_conditions))

        # Apply sorting
        query = apply_sorting(query, model_class, request.sort_by, request.sort_order)

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
            search_terms=search_terms,
            search_mode=request.search_mode.value,
            sort_by=request.sort_by,
            sort_order=request.sort_order.value,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


def apply_sorting(query, model_class, sort_by: Optional[str], sort_order: SortOrder):
    """Apply sorting to the query if sort_by is specified."""
    if not sort_by:
        return query

    # Validate that the column exists
    if not hasattr(model_class, sort_by):
        raise HTTPException(
            status_code=400, detail=f"Column '{sort_by}' does not exist in table"
        )

    col_attr = getattr(model_class, sort_by)

    if sort_order == SortOrder.DESC:
        return query.order_by(desc(col_attr))
    else:
        return query.order_by(asc(col_attr))
