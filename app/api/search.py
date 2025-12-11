from enum import Enum
from fastapi import HTTPException
from sqlalchemy import or_, asc, desc
from app.schema_new import ComplexFilter
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.core import (
    row_to_dict,
    apply_filters,
    get_model_class,
    validate_columns,
    get_searchable_columns,
)

# ==========================================
#               SCHEMAS
# ==========================================


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SearchRequest(BaseModel):
    # --- 1. Precise Filters (The "Context") ---
    filters: Optional[ComplexFilter] = Field(
        None,
        description="Structured filters with AND/OR logic (e.g., gene IN [TP53, BRCA1])",
    )

    # --- 2. Text Search (The "Refinement") ---
    term: Optional[str] = Field(
        None, description="Single search term for global text search (partial match)"
    )
    search_columns: Optional[List[str]] = Field(
        None, description="Specific columns to text-search (defaults to all searchable)"
    )

    # --- 3. Pagination & Sorting ---
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=1000, description="Results per page")
    sort_by: Optional[str] = Field(None, description="Column to sort by")
    sort_order: SortOrder = Field(SortOrder.ASC, description="Sort direction")

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
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
#           INTERNAL HELPERS
# ==========================================


def apply_sorting(query, model_class, sort_by: Optional[str], sort_order: SortOrder):
    if not sort_by:
        return query
    if not hasattr(model_class, sort_by):
        raise HTTPException(
            status_code=400, detail=f"Column '{sort_by}' does not exist"
        )

    col_attr = getattr(model_class, sort_by)
    if sort_order == SortOrder.DESC:
        return query.order_by(desc(col_attr))
    return query.order_by(asc(col_attr))


# ==========================================
#           MAIN SEARCH API
# ==========================================


async def generic_search(table_name: str, request: SearchRequest, db) -> SearchResponse:
    """
    Combined Search API:
    1. Applies precise 'filters' (Structured Logic)
    2. Applies global 'term' search (Partial Text Match)
    3. Handles Sorting & Pagination
    """
    try:
        model_class = get_model_class(table_name)
        query = db.query(model_class)

        # ---------------------------------------------------------
        # 1. Apply Structured Filters (Context)
        # ---------------------------------------------------------
        query = apply_filters(query, model_class, request.filters)

        # ---------------------------------------------------------
        # 2. Apply Text Search (Refinement)
        # ---------------------------------------------------------
        if request.term and request.term.strip():
            term = request.term.strip()

            # Determine target columns
            if request.search_columns:
                columns_to_search = validate_columns(
                    model_class, request.search_columns
                )
            else:
                columns_to_search = [
                    col
                    for col in get_searchable_columns(table_name)
                    if hasattr(model_class, col)
                ]

            # Build Search Logic: Partial match (ilike) in ANY column
            conditions = []
            for col in columns_to_search:
                attr = getattr(model_class, col)
                conditions.append(attr.ilike(f"%{term}%"))

            if conditions:
                query = query.filter(or_(*conditions))

        # ---------------------------------------------------------
        # 3. Sorting
        # ---------------------------------------------------------
        query = apply_sorting(query, model_class, request.sort_by, request.sort_order)

        # ---------------------------------------------------------
        # 4. Pagination & Execution
        # ---------------------------------------------------------
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

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
