from enum import Enum
from fastapi import HTTPException
from app.schema_new import ComplexFilter
from sqlalchemy import or_, and_, asc, desc
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
# SEARCH SCHEMAS
# ==========================================


class GenomicRegion(BaseModel):
    """
    Single genomic region specification.

    Can represent either:
    - Exact position: Provide chromosome + start only
    - Range: Provide chromosome + start + end

    Examples:
        Exact position: {"chromosome": "chr17", "start": 7577538}
        Range: {"chromosome": "chr17", "start": 7577000, "end": 7579000}
    """

    chromosome: str = Field(
        ..., description="Chromosome name (e.g., 'chr1', '1', 'X', 'Y', 'MT')"
    )
    start: int = Field(..., ge=1, description="Start position (1-based, inclusive)")
    end: Optional[int] = Field(
        None,
        ge=1,
        description="End position (1-based, inclusive). Omit for exact position match.",
    )

    @field_validator("end")
    @classmethod
    def validate_end_after_start(cls, v, info):
        if v is not None:
            start = info.data.get("start")
            if start and v < start:
                raise ValueError("end must be >= start")
        return v


class GenomicPositionFilter(BaseModel):
    """
    Genomic position filtering - unified approach.

    All genomic locations (ranges and exact positions) are specified in the
    'positions' field. All conditions are combined with OR logic.

    Features:
    - Mix ranges and exact positions freely
    - Multiple chromosomes in one query
    - Natural OR logic (match ANY position/range)
    - Optional pathway filtering

    Examples:
        # Single range
        {"positions": [{"chromosome": "chr17", "start": 7577000, "end": 7579000}]}

        # Multiple exact positions
        {"positions": [
            {"chromosome": "chr17", "start": 7577538},
            {"chromosome": "chr17", "start": 7578406}
        ]}

        # Mixed ranges and positions
        {"positions": [
            {"chromosome": "chr17", "start": 7571000, "end": 7572000},  # Regulatory region
            {"chromosome": "chr17", "start": 7577538},                   # R175H hotspot
            {"chromosome": "chr17", "start": 7578406}                    # R248Q hotspot
        ]}

        # Multiple genes (different chromosomes)
        {"positions": [
            {"chromosome": "chr17", "start": 7577000, "end": 7579000},   # TP53
            {"chromosome": "chr13", "start": 32889611, "end": 32973805}  # BRCA2
        ]}
    """

    positions: Optional[List[GenomicRegion]] = Field(
        None,
        description=(
            "List of genomic positions or ranges. "
            "Can mix exact positions (start only) and ranges (start + end). "
            "All conditions combined with OR logic - matches ANY position/range. "
            "Examples: "
            "[{'chromosome': 'chr17', 'start': 7577538}] for exact position, "
            "[{'chromosome': 'chr17', 'start': 7577000, 'end': 7579000}] for range, "
            "or combine both in the same list."
        ),
    )

    pathway: Optional[str] = Field(
        None,
        description=(
            "Filter by pathway name (case-insensitive partial match). "
            "Examples: 'PI3K-AKT', 'TP53 pathway', 'DNA repair'"
        ),
    )

    @field_validator("positions")
    @classmethod
    def validate_positions_not_empty(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("positions list cannot be empty")
        return v


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SearchRequest(BaseModel):
    # --- Precise Filters  ---
    filters: Optional[ComplexFilter] = Field(
        None,
        description="Structured filters with AND/OR logic (e.g., gene IN [TP53, BRCA1])",
    )

    # --- Genomic Position Filters  ---
    genomic_filter: Optional[GenomicPositionFilter] = Field(
        None,
        description="Filter by genomic positions/ranges or pathway",
    )

    # --- Text Search ---
    term: Optional[str] = Field(
        None, description="Single search term for global text search (partial match)"
    )

    search_columns: Optional[List[str]] = Field(
        None, description="Specific columns to text-search (defaults to all searchable)"
    )

    # --- Pagination & Sorting ---
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
# INTERNAL HELPERS
# ==========================================


def _normalize_chromosome(chrom: str) -> str:
    """
    Normalize chromosome name for flexible matching.

    Examples:
        'chr1' -> '1'
        'CHR17' -> '17'
        '17' -> '17'
        'chrX' -> 'X'
    """
    if not chrom:
        return chrom
    chrom_str = str(chrom).upper()
    if chrom_str.startswith("CHR"):
        return chrom_str[3:]
    return chrom_str


def _apply_genomic_position_filter(
    query, model_class, genomic_filter: Optional[GenomicPositionFilter]
):
    """
    Apply genomic position filtering to query.

    Features:
    1. Unified positions list - mix ranges and exact positions
    2. Flexible chromosome naming ('chr17' or '17')
    3. Overlap detection (if dataset has 'end' column)
    4. Exact position matching (if no 'end' column)
    5. Pathway filtering (if pathway column exists)
    6. OR logic - match ANY position/range

    Args:
        query: SQLAlchemy query
        model_class: Model class
        genomic_filter: GenomicPositionFilter object

    Returns:
        Filtered query

    Examples:
        # Query matches variants that satisfy ANY of:
        # - In chr17:7571000-7572000 (regulatory region)
        # - At chr17:7577538 (R175H hotspot)
        # - At chr17:7578406 (R248Q hotspot)
    """
    if not genomic_filter:
        return query

    # Detect chromosome and position column names in the dataset
    chr_col_name = "chrom"
    pos_col_name = "start"
    end_col_name = "end"

    # Validate required columns exist
    if not chr_col_name or not pos_col_name:
        raise HTTPException(
            400,
            detail=(
                "Dataset must have chromosome and position columns for genomic filtering. "
                f"Found columns: {[c.name for c in model_class.__table__.columns]}"
            ),
        )

    chr_col = getattr(model_class, chr_col_name)
    pos_col = getattr(model_class, pos_col_name)
    end_col = getattr(model_class, end_col_name) if end_col_name else None

    # Build genomic position conditions
    conditions = []

    if genomic_filter.positions:
        for region in genomic_filter.positions:
            norm_chrom = _normalize_chromosome(region.chromosome)

            # Flexible chromosome matching
            # Handles: 'chr17', '17', 'CHR17' all match chromosome '17' or 'chr17' in DB
            chrom_cond = or_(
                chr_col == norm_chrom,
                chr_col == f"chr{norm_chrom}",
                chr_col == region.chromosome,
                chr_col == region.chromosome.upper(),
                chr_col == region.chromosome.lower(),
            )

            if region.end:
                # Range query: find overlapping variants
                if end_col:
                    # Dataset has end column - check for overlap
                    # Variants overlap region if: variant.start <= region.end AND variant.end >= region.start
                    pos_cond = and_(pos_col <= region.end, end_col >= region.start)
                else:
                    # Dataset only has start position - check if start is within range
                    pos_cond = and_(pos_col >= region.start, pos_col <= region.end)
            else:
                # Exact position match
                pos_cond = pos_col == region.start

            # Combine chromosome and position conditions
            conditions.append(and_(chrom_cond, pos_cond))

    # Apply all genomic conditions with OR logic
    if conditions:
        if len(conditions) == 1:
            query = query.filter(conditions[0])
        else:
            # Match ANY position/range
            query = query.filter(or_(*conditions))

    # Apply pathway filter (independent of positions)
    if genomic_filter.pathway:
        pathway_col_name = None
        for col in ["pathway", "pathway_name", "kegg_pathway", "reactome_pathway"]:
            if hasattr(model_class, col):
                pathway_col_name = col
                break

        if pathway_col_name:
            pathway_col = getattr(model_class, pathway_col_name)
            # Case-insensitive partial match
            query = query.filter(pathway_col.ilike(f"%{genomic_filter.pathway}%"))
        else:
            # Pathway column not found - issue warning but don't fail
            import warnings

            warnings.warn(
                f"Pathway filter '{genomic_filter.pathway}' specified but no pathway column found in dataset"
            )

    return query


def apply_sorting(query, model_class, sort_by: Optional[str], sort_order: SortOrder):
    """Apply sorting to query"""
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
# MAIN SEARCH API
# ==========================================


async def generic_search(table_name: str, request: SearchRequest, db) -> SearchResponse:
    """
    Enhanced Combined Search API with unified genomic position filtering.

    Query execution order:
    1. FROM table_name
    2. WHERE filters (structured filters)
    3. WHERE genomic_filter (unified positions/ranges + pathway)
    4. WHERE term (text search)
    5. ORDER BY sort_by
    6. LIMIT/OFFSET (pagination)

    Genomic Filtering Features:
    - Mix ranges and exact positions in single query
    - Multi-chromosome queries
    - Flexible chromosome naming ('chr17' or '17')
    - Overlap detection (if 'end' column exists)
    - OR logic (match ANY position/range)
    - Optional pathway filtering
    """
    try:
        model_class = get_model_class(table_name)
        query = db.query(model_class)

        # ---------------------------------------------------------
        # 1. Apply Structured Filters (Context)
        # ---------------------------------------------------------
        query = apply_filters(query, model_class, request.filters)

        # ---------------------------------------------------------
        # 2. Apply Genomic Position Filters (Unified)
        # ---------------------------------------------------------
        query = _apply_genomic_position_filter(
            query, model_class, request.genomic_filter
        )

        # ---------------------------------------------------------
        # 3. Apply Text Search (Refinement)
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
        # 4. Sorting
        # ---------------------------------------------------------
        query = apply_sorting(query, model_class, request.sort_by, request.sort_order)

        # ---------------------------------------------------------
        # 5. Pagination & Execution
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
