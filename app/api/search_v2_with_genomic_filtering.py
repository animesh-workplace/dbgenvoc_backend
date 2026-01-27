"""
search.py

Enhanced search API with genomic position and pathway filtering.

Features:
- Structured filters (ComplexFilter)
- Text search across columns
- Genomic position filtering (ranges and specific positions)
- Pathway filtering
- Sorting and pagination

Author: Generated for dbGENVOC API
Date: 2026-01-26
Version: 2.0 (With Genomic Position Filtering)
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import or_, and_, asc, desc
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
# GENOMIC POSITION SCHEMAS
# ==========================================

class GenomicRegion(BaseModel):
    """Single genomic region specification"""
    chromosome: str = Field(..., description="Chromosome (e.g., 'chr1', '1', 'X')")
    start: int = Field(..., ge=1, description="Start position (1-based, inclusive)")
    end: Optional[int] = Field(None, ge=1, description="End position (1-based, inclusive)")

    @field_validator("end")
    @classmethod
    def validate_end_after_start(cls, v, info):
        if v is not None:
            start = info.data.get("start")
            if start and v < start:
                raise ValueError("end must be >= start")
        return v


class GenomicPositionFilter(BaseModel):
    """Genomic position filtering - supports ranges and specific positions"""

    # Option 1: Single range [chr1:915188-1015188]
    region: Optional[GenomicRegion] = Field(
        None,
        description="Single genomic region (chr + start + optional end)"
    )

    # Option 2: Multiple specific positions [chr11:534289, chr17:7578406]
    positions: Optional[List[GenomicRegion]] = Field(
        None,
        description="List of specific genomic positions or regions"
    )

    # Pathway filter (optional)
    pathway: Optional[str] = Field(
        None,
        description="Filter by pathway name (e.g., 'PI3K-AKT', 'TP53 pathway')"
    )

    @field_validator("positions")
    @classmethod
    def validate_positions_or_region(cls, v, info):
        region = info.data.get("region")
        if v is not None and region is not None:
            raise ValueError("Cannot specify both 'region' and 'positions'")
        if v is None and region is None and not info.data.get("pathway"):
            return None  # All filters are optional
        return v


# ==========================================
# SEARCH SCHEMAS
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

    # --- 1b. Genomic Position Filters (NEW) ---
    genomic_filter: Optional[GenomicPositionFilter] = Field(
        None,
        description="Filter by genomic position/range or pathway",
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
    genomic_filter_applied: bool  # NEW: Indicates if genomic filter was used
    results: List[Dict[str, Any]]


# ==========================================
# INTERNAL HELPERS
# ==========================================

def _normalize_chromosome(chrom: str) -> str:
    """Normalize chromosome name (remove 'chr' prefix)"""
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

    Supports:
    1. Single range: chr1:915188-1015188
    2. Multiple positions: chr11:534289, chr17:7578406, chr17:7577538
    3. Pathway filtering (if pathway column exists)

    Args:
        query: SQLAlchemy query
        model_class: Model class
        genomic_filter: GenomicPositionFilter object

    Returns:
        Filtered query
    """
    if not genomic_filter:
        return query

    # Determine chromosome and position column names
    chr_col_name = None
    for col in ["chrom", "chromosome", "chr"]:
        if hasattr(model_class, col):
            chr_col_name = col
            break

    pos_col_name = None
    for col in ["start", "start_position", "pos", "position"]:
        if hasattr(model_class, col):
            pos_col_name = col
            break

    end_col_name = None
    for col in ["end", "end_position"]:
        if hasattr(model_class, col):
            end_col_name = col
            break

    if not chr_col_name or not pos_col_name:
        raise HTTPException(
            400, 
            "Dataset must have chromosome and position columns for genomic filtering"
        )

    chr_col = getattr(model_class, chr_col_name)
    pos_col = getattr(model_class, pos_col_name)
    end_col = getattr(model_class, end_col_name) if end_col_name else None

    # Apply filters
    conditions = []

    # Option 1: Single region filter
    if genomic_filter.region:
        region = genomic_filter.region
        norm_chrom = _normalize_chromosome(region.chromosome)

        # Chromosome match (flexible - handles both 'chr1' and '1')
        chrom_cond = or_(
            chr_col == norm_chrom,
            chr_col == f"chr{norm_chrom}",
            chr_col == region.chromosome
        )

        if region.end:
            # Range query: variants overlapping [start, end]
            if end_col:
                # If dataset has end column, check for overlap
                # Overlap: variant.start <= region.end AND variant.end >= region.start
                pos_cond = and_(
                    pos_col <= region.end,
                    end_col >= region.start
                )
            else:
                # No end column, just check if position is within range
                pos_cond = and_(
                    pos_col >= region.start,
                    pos_col <= region.end
                )
        else:
            # Exact position match
            pos_cond = pos_col == region.start

        conditions.append(and_(chrom_cond, pos_cond))

    # Option 2: Multiple specific positions
    elif genomic_filter.positions:
        for pos_spec in genomic_filter.positions:
            norm_chrom = _normalize_chromosome(pos_spec.chromosome)

            chrom_cond = or_(
                chr_col == norm_chrom,
                chr_col == f"chr{norm_chrom}",
                chr_col == pos_spec.chromosome
            )

            if pos_spec.end:
                # Range for this position
                if end_col:
                    pos_cond = and_(
                        pos_col <= pos_spec.end,
                        end_col >= pos_spec.start
                    )
                else:
                    pos_cond = and_(
                        pos_col >= pos_spec.start,
                        pos_col <= pos_spec.end
                    )
            else:
                # Exact position
                pos_cond = pos_col == pos_spec.start

            conditions.append(and_(chrom_cond, pos_cond))

    # Apply genomic conditions (OR logic for multiple positions)
    if conditions:
        if len(conditions) == 1:
            query = query.filter(conditions[0])
        else:
            query = query.filter(or_(*conditions))

    # Option 3: Pathway filter (if column exists)
    if genomic_filter.pathway:
        pathway_col_name = None
        for col in ["pathway", "pathway_name", "kegg_pathway", "reactome_pathway"]:
            if hasattr(model_class, col):
                pathway_col_name = col
                break

        if pathway_col_name:
            pathway_col = getattr(model_class, pathway_col_name)
            query = query.filter(pathway_col.ilike(f"%{genomic_filter.pathway}%"))

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
    Enhanced Combined Search API:

    1. Applies precise 'filters' (Structured Logic)
    2. Applies genomic position filters (NEW: Range/Position/Pathway)
    3. Applies global 'term' search (Partial Text Match)
    4. Handles Sorting & Pagination

    Query execution order:
    1. FROM table_name
    2. WHERE filters (structured filters)
    3. WHERE genomic_filter (position/pathway filters)
    4. WHERE term (text search)
    5. ORDER BY sort_by
    6. LIMIT/OFFSET (pagination)

    Examples:
    ---------

    Example 1: Search with genomic range
    {
      "filters": {
        "conditions": [{"column": "gene", "operator": "eq", "value": "TP53"}]
      },
      "genomic_filter": {
        "region": {"chromosome": "chr17", "start": 7577000, "end": 7579000}
      },
      "page": 1,
      "page_size": 100
    }

    Example 2: Search multiple specific positions
    {
      "genomic_filter": {
        "positions": [
          {"chromosome": "chr11", "start": 534289},
          {"chromosome": "chr17", "start": 7578406},
          {"chromosome": "chr17", "start": 7577538}
        ]
      }
    }

    Example 3: Pathway search
    {
      "filters": {
        "conditions": [{"column": "variant_class", "operator": "eq", "value": "Missense_Mutation"}]
      },
      "genomic_filter": {"pathway": "PI3K-AKT"},
      "sort_by": "gene",
      "sort_order": "asc"
    }

    Example 4: Combined filters
    {
      "filters": {
        "conditions": [{"column": "variant_class", "operator": "eq", "value": "Missense_Mutation"}]
      },
      "genomic_filter": {
        "region": {"chromosome": "chr17", "start": 7577000, "end": 7579000}
      },
      "term": "R175",
      "sort_by": "start",
      "page": 1,
      "page_size": 50
    }
    """
    try:
        model_class = get_model_class(table_name)
        query = db.query(model_class)

        # ---------------------------------------------------------
        # 1. Apply Structured Filters (Context)
        # ---------------------------------------------------------
        query = apply_filters(query, model_class, request.filters)

        # ---------------------------------------------------------
        # 2. Apply Genomic Position Filters (NEW)
        # ---------------------------------------------------------
        query = _apply_genomic_position_filter(query, model_class, request.genomic_filter)

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
            genomic_filter_applied=request.genomic_filter is not None,
            results=[row_to_dict(row) for row in results],
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ==========================================
# USAGE EXAMPLES
# ==========================================

"""
Example 1: Search TP53 mutations in specific genomic range
-----------------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "filters": {
    "logic": "AND",
    "conditions": [
      {"column": "gene", "operator": "eq", "value": "TP53"}
    ]
  },
  "genomic_filter": {
    "region": {
      "chromosome": "chr17",
      "start": 7577000,
      "end": 7579000
    }
  },
  "sort_by": "start",
  "sort_order": "asc",
  "page": 1,
  "page_size": 100
}

Example 2: Search variants at multiple specific positions
----------------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "genomic_filter": {
    "positions": [
      {"chromosome": "chr11", "start": 534289},
      {"chromosome": "chr17", "start": 7578406},
      {"chromosome": "chr17", "start": 7577538},
      {"chromosome": "chr17", "start": 7577120}
    ]
  },
  "page": 1,
  "page_size": 100
}

Example 3: Search missense variants in PI3K-AKT pathway
--------------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "filters": {
    "conditions": [
      {"column": "variant_class", "operator": "eq", "value": "Missense_Mutation"}
    ]
  },
  "genomic_filter": {
    "pathway": "PI3K-AKT"
  },
  "sort_by": "gene",
  "sort_order": "asc",
  "page": 1,
  "page_size": 50
}

Example 4: Combined filters with text search
---------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "filters": {
    "conditions": [
      {"column": "variant_class", "operator": "eq", "value": "Missense_Mutation"}
    ]
  },
  "genomic_filter": {
    "region": {
      "chromosome": "17",
      "start": 7577000,
      "end": 7579000
    }
  },
  "term": "R175",
  "sort_by": "start",
  "page": 1,
  "page_size": 50
}

Example 5: Exact position search
---------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "genomic_filter": {
    "region": {
      "chromosome": "chr17",
      "start": 7577538
    }
  }
}

Example 6: Range search without gene filter
--------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "genomic_filter": {
    "region": {
      "chromosome": "1",
      "start": 915188,
      "end": 1015188
    }
  },
  "sort_by": "gene",
  "page": 1,
  "page_size": 100
}
"""
