from fastapi import HTTPException
from sqlalchemy import or_, asc, desc
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.api.utils import _apply_genomic_position_filter
from app.api.schema import GenomicPositionFilter, SortOrder, ComplexFilter
from app.core import (
    row_to_dict,
    apply_filters,
    get_model_class,
    validate_columns,
    get_searchable_columns,
)


# ==========================================
# SEARCH SCHEMAS
# ==========================================


class SearchRequest(BaseModel):
    filters: Optional[ComplexFilter] = Field(
        None,
        description="Structured filters with AND/OR logic (e.g., gene IN [TP53, BRCA1])",
    )
    genomic_filter: Optional[GenomicPositionFilter] = Field(
        None,
        description="Filter by genomic positions/ranges or pathway",
    )
    term: Optional[str] = Field(
        None, description="Single search term for global text search (partial match)"
    )
    search_columns: Optional[List[str]] = Field(
        None, description="Specific columns to text-search (defaults to all searchable)"
    )
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=1000, description="Results per page")
    sort_by: Optional[str] = Field(None, description="Column to sort by")
    sort_order: SortOrder = Field(SortOrder.ASC, description="Sort direction")

    @field_validator("sort_by", "term")
    @classmethod
    def _strip_and_validate(cls, v: Optional[str], info) -> Optional[str]:
        if v is not None and isinstance(v, str):
            v = v.strip()
            if not v and info.field_name == "term":
                return None
        return v


class SearchResponse(BaseModel):
    page: int
    page_size: int
    table_name: str
    sort_order: str
    total_results: int
    sort_by: Optional[str]
    search_term: Optional[str]
    results: List[Dict[str, Any]]


# ==========================================
# MAIN SEARCH API
# ==========================================


async def generic_search(table_name: str, request: SearchRequest, db) -> SearchResponse:
    """
    Enhanced Combined Search API with unified genomic position filtering.
    """
    try:
        model_class = get_model_class(table_name)
        query = db.query(model_class)

        # Apply structured filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Apply genomic position filters
        if request.genomic_filter:
            query = _apply_genomic_position_filter(
                query, model_class, request.genomic_filter
            )

        # Apply text search
        if request.term:
            # Determine and validate search columns
            if request.search_columns:
                search_columns = validate_columns(model_class, request.search_columns)
            else:
                search_columns = [
                    col
                    for col in get_searchable_columns(table_name)
                    if hasattr(model_class, col)
                ]

            if search_columns:
                # Build search conditions using list comprehension
                conditions = [
                    getattr(model_class, col).ilike(f"%{request.term}%")
                    for col in search_columns
                ]
                query = query.filter(or_(*conditions))

        # Apply sorting
        if request.sort_by:
            if not hasattr(model_class, request.sort_by):
                raise HTTPException(
                    status_code=400, detail=f"Column '{request.sort_by}' does not exist"
                )

            col_attr = getattr(model_class, request.sort_by)
            query = query.order_by(
                desc(col_attr)
                if request.sort_order == SortOrder.DESC
                else asc(col_attr)
            )

        # Pagination and execution
        total_results = query.count()
        offset = (request.page - 1) * request.page_size
        results = query.offset(offset).limit(request.page_size).all()

        return SearchResponse(
            page=request.page,
            table_name=table_name,
            sort_by=request.sort_by,
            search_term=request.term,
            total_results=total_results,
            page_size=request.page_size,
            sort_order=request.sort_order.value,
            results=[row_to_dict(row) for row in results],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
