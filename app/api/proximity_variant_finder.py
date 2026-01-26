"""
proximity_variant_finder.py

Finds variants that are in proximity to reference variants or genomic features.
Useful for identifying co-occurring mutations, clustered variants, and variants
near specific mutation types.

Author: Generated based on dbGENVOC API patterns
Date: 2026-01-23
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_, between, case
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator
from app.schema_new import ComplexFilter
from app.core import (
    apply_filters,
    get_model_class,
    validate_columns,
    row_to_dict,
)


# ==========================================
# SCHEMAS
# ==========================================


class ProximityDirection(str, Enum):
    """Direction for proximity search"""

    upstream = "upstream"  # Only upstream (5' direction)
    downstream = "downstream"  # Only downstream (3' direction)
    both = "both"  # Both directions


class ReferenceVariantType(str, Enum):
    """Type of reference variants to search near"""

    frameshift = "frameshift"  # Near frameshift mutations
    nonsense = "nonsense"  # Near nonsense mutations
    splice_site = "splice_site"  # Near splice site mutations
    missense = "missense"  # Near missense mutations
    specific_gene = "specific_gene"  # Near variants in specific gene
    custom_filter = "custom_filter"  # Use custom filters for reference


class SortOrder(str, Enum):
    """Sort order"""

    ASC = "asc"
    DESC = "desc"


class ProximityVariantRequest(BaseModel):
    """Request model for proximity variant search"""

    # Dataset to search
    dataset: str = Field(
        ...,
        description="Dataset name (e.g., 'nibmg_exome_somatic', 'tcga_exome_somatic')",
    )

    # Reference variant definition
    reference_variant_type: ReferenceVariantType = Field(
        ReferenceVariantType.frameshift,
        description="Type of reference variants to search near",
    )

    reference_gene: Optional[str] = Field(
        None,
        description="Gene symbol for reference variants (for 'specific_gene' type)",
    )

    reference_filters: Optional[ComplexFilter] = Field(
        None,
        description="Custom filters for reference variants (for 'custom_filter' type)",
    )

    # Proximity parameters
    proximity_bp: int = Field(
        300, ge=1, le=100000, description="Proximity distance in base pairs"
    )

    direction: ProximityDirection = Field(
        ProximityDirection.both,
        description="Direction to search (upstream, downstream, or both)",
    )

    # Query variant filters
    query_filters: Optional[ComplexFilter] = Field(
        None, description="Filters for query variants (variants to find near reference)"
    )

    exclude_reference: bool = Field(
        True, description="Exclude reference variants from results"
    )

    same_gene_only: bool = Field(
        False, description="Only find variants in the same gene as reference"
    )

    # Chromosome filter (optional - for performance)
    chromosome: Optional[str] = Field(
        None, description="Limit search to specific chromosome"
    )

    # Sorting and limiting
    sort_by: Optional[str] = Field(
        "distance", description="Column to sort by (e.g., 'distance', 'hugo_symbol')"
    )

    sort_order: SortOrder = Field(SortOrder.ASC, description="Sort direction")

    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(100, ge=1, le=10000, description="Results per page")

    @field_validator("reference_gene")
    @classmethod
    def validate_reference_gene(cls, v, info):
        """Validate reference_gene is provided when needed"""
        ref_type = info.data.get("reference_variant_type")
        if ref_type == ReferenceVariantType.specific_gene and not v:
            raise ValueError("reference_gene is required for 'specific_gene' type")
        return v

    @field_validator("reference_filters")
    @classmethod
    def validate_reference_filters(cls, v, info):
        """Validate reference_filters is provided when needed"""
        ref_type = info.data.get("reference_variant_type")
        if ref_type == ReferenceVariantType.custom_filter and not v:
            raise ValueError("reference_filters is required for 'custom_filter' type")
        return v


class ProximityVariantResponse(BaseModel):
    """Response model for proximity variant search"""

    dataset: str
    reference_variant_type: str
    reference_gene: Optional[str] = None
    proximity_bp: int
    direction: str
    total_reference_variants: int
    total_query_variants: int
    page: int
    page_size: int
    sort_by: Optional[str] = None
    sort_order: str
    results: List[Dict[str, Any]]


# ==========================================
# INTERNAL HELPERS
# ==========================================


def _normalize_chromosome(chrom: str) -> str:
    """Normalize chromosome name (remove 'chr' prefix if present)."""
    if chrom is None:
        return None
    chrom_str = str(chrom).upper()
    if chrom_str.startswith("CHR"):
        return chrom_str[3:]
    return chrom_str


def _build_reference_filter(
    model_class,
    reference_variant_type: ReferenceVariantType,
    reference_gene: Optional[str],
    reference_filters: Optional[ComplexFilter],
):
    """
    Build filter expression for reference variants.

    Args:
        model_class: SQLAlchemy model class
        reference_variant_type: Type of reference variants
        reference_gene: Gene symbol (if applicable)
        reference_filters: Custom filters (if applicable)

    Returns:
        SQLAlchemy filter expression
    """
    from app.core import _build_filter_expression

    conditions = []

    if reference_variant_type == ReferenceVariantType.frameshift:
        if hasattr(model_class, "variant_classification"):
            conditions.append(
                model_class.variant_classification.in_(
                    [
                        "Frame_Shift_Del",
                        "Frame_Shift_Ins",
                        "Frameshift_Deletion",
                        "Frameshift_Insertion",
                    ]
                )
            )

    elif reference_variant_type == ReferenceVariantType.nonsense:
        if hasattr(model_class, "variant_classification"):
            conditions.append(
                model_class.variant_classification.in_(
                    ["Nonsense_Mutation", "Nonstop_Mutation"]
                )
            )

    elif reference_variant_type == ReferenceVariantType.splice_site:
        if hasattr(model_class, "variant_classification"):
            conditions.append(
                model_class.variant_classification.in_(["Splice_Site", "Splice_Region"])
            )

    elif reference_variant_type == ReferenceVariantType.missense:
        if hasattr(model_class, "variant_classification"):
            conditions.append(model_class.variant_classification == "Missense_Mutation")

    elif reference_variant_type == ReferenceVariantType.specific_gene:
        if hasattr(model_class, "gene") and reference_gene:
            conditions.append(model_class.gene == reference_gene)

    elif reference_variant_type == ReferenceVariantType.custom_filter:
        if reference_filters:
            custom_expr = _build_filter_expression(model_class, reference_filters)
            if custom_expr is not None:
                conditions.append(custom_expr)

    if not conditions:
        # Default: return True (no filtering)
        return True

    return and_(*conditions) if len(conditions) > 1 else conditions[0]


def _calculate_distance(
    ref_pos: int, query_pos: int, direction: ProximityDirection
) -> Optional[int]:
    """
    Calculate distance based on direction.

    Args:
        ref_pos: Reference position
        query_pos: Query position
        direction: Direction constraint

    Returns:
        Distance (positive) or None if direction doesn't match
    """
    if direction == ProximityDirection.upstream:
        # Query must be upstream (lower position)
        if query_pos < ref_pos:
            return ref_pos - query_pos
        return None

    elif direction == ProximityDirection.downstream:
        # Query must be downstream (higher position)
        if query_pos > ref_pos:
            return query_pos - ref_pos
        return None

    else:  # both
        return abs(ref_pos - query_pos)


# ==========================================
# MAIN API FUNCTION
# ==========================================


async def proximity_variant_finder(
    request: ProximityVariantRequest, table_name: str, db
) -> ProximityVariantResponse:
    """
    Find variants in proximity to reference variants.

    This tool identifies variants that are within a specified distance of
    reference variants (e.g., find SNPs near frameshift mutations).

    Algorithm:
    1. Identify reference variants based on filters
    2. For each reference variant, find query variants within proximity
    3. Calculate distance and filter by direction
    4. Return results with distance information

    Args:
        request: ProximityVariantRequest with search parameters
        table_name: Dataset table name
        db: Database session

    Returns:
        ProximityVariantResponse with nearby variants

    Example Requests:
    -----------------

    1. Find Variants Near Frameshift Mutations:
    {
      "dataset": "nibmg_exome_somatic",
      "reference_variant_type": "frameshift",
      "proximity_bp": 300,
      "direction": "both",
      "exclude_reference": true,
      "sort_by": "distance",
      "sort_order": "asc"
    }

    2. Find Variants Near TP53 Mutations:
    {
      "dataset": "tcga_exome_somatic",
      "reference_variant_type": "specific_gene",
      "reference_gene": "TP53",
      "proximity_bp": 500,
      "direction": "both",
      "same_gene_only": true
    }

    3. Find Variants Upstream of Splice Sites:
    {
      "dataset": "nibmg_exome_somatic",
      "reference_variant_type": "splice_site",
      "proximity_bp": 50,
      "direction": "upstream",
      "query_filters": {
        "logic": "AND",
        "conditions": [
          {"column": "variant_type", "operator": "eq", "value": "SNP"}
        ]
      }
    }

    4. Custom Reference Filter:
    {
      "dataset": "tcga_exome_somatic",
      "reference_variant_type": "custom_filter",
      "reference_filters": {
        "logic": "AND",
        "conditions": [
          {"column": "hugo_symbol", "operator": "in", "value": ["BRCA1", "BRCA2"]},
          {"column": "variant_classification", "operator": "eq", "value": "Missense_Mutation"}
        ]
      },
      "proximity_bp": 200,
      "direction": "both"
    }
    """

    try:
        model_class = get_model_class(table_name)

        # Validate required columns
        required_cols = ["start", "chrom"]
        if not all(hasattr(model_class, col) for col in required_cols):
            # Try alternative column names
            if not hasattr(model_class, "start") and not hasattr(
                model_class, "start_position"
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Model must have 'start' or 'start_position' column",
                )
            if not hasattr(model_class, "chrom") and not hasattr(
                model_class, "chromosome"
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Model must have 'chrom' or 'chromosome' column",
                )

        # Determine column names
        pos_col = (
            model_class.start
            if hasattr(model_class, "start")
            else model_class.start_position
        )
        chrom_col = (
            model_class.chrom
            if hasattr(model_class, "chrom")
            else model_class.chromosome
        )

        # Step 1: Get reference variants
        ref_query = db.query(model_class)

        # Apply chromosome filter if specified
        if request.chromosome:
            norm_chrom = _normalize_chromosome(request.chromosome)
            ref_query = ref_query.filter(
                or_(
                    chrom_col == norm_chrom,
                    chrom_col == f"chr{norm_chrom}",
                    chrom_col == request.chromosome,
                )
            )

        # Apply reference filters
        ref_filter = _build_reference_filter(
            model_class,
            request.reference_variant_type,
            request.reference_gene,
            request.reference_filters,
        )

        if ref_filter is not True:
            ref_query = ref_query.filter(ref_filter)

        # Get reference variants
        reference_variants = ref_query.all()
        total_reference_variants = len(reference_variants)

        if total_reference_variants == 0:
            return ProximityVariantResponse(
                dataset=request.dataset,
                reference_variant_type=request.reference_variant_type.value,
                reference_gene=request.reference_gene,
                proximity_bp=request.proximity_bp,
                direction=request.direction.value,
                total_reference_variants=0,
                total_query_variants=0,
                page=request.page,
                page_size=request.page_size,
                sort_by=request.sort_by,
                sort_order=request.sort_order.value,
                results=[],
            )

        # Step 2: Find query variants near each reference
        nearby_variants = []

        for ref_variant in reference_variants:
            ref_chrom = getattr(
                ref_variant, "chrom" if hasattr(ref_variant, "chrom") else "chromosome"
            )
            # Get position value
            ref_pos_raw = getattr(
                ref_variant,
                "start" if hasattr(ref_variant, "start") else "start_position",
            )

            # Convert to integer (handle string or numeric types)
            try:
                ref_pos = int(ref_pos_raw)
            except (ValueError, TypeError):
                # Skip this reference variant if position is invalid
                continue

            ref_gene = (
                getattr(ref_variant, "gene", None)
                if hasattr(ref_variant, "gene")
                else None
            )

            # Build query for nearby variants
            query_query = db.query(model_class)

            # Same chromosome
            query_query = query_query.filter(chrom_col == ref_chrom)

            # Position proximity based on direction
            if request.direction == ProximityDirection.upstream:
                # Query variants upstream (lower position)
                query_query = query_query.filter(
                    and_(pos_col < ref_pos, pos_col >= ref_pos - request.proximity_bp)
                )
            elif request.direction == ProximityDirection.downstream:
                # Query variants downstream (higher position)
                query_query = query_query.filter(
                    and_(pos_col > ref_pos, pos_col <= ref_pos + request.proximity_bp)
                )
            else:  # both
                query_query = query_query.filter(
                    and_(
                        pos_col >= ref_pos - request.proximity_bp,
                        pos_col <= ref_pos + request.proximity_bp,
                    )
                )

            # Exclude reference variant itself if requested
            if request.exclude_reference:
                # Exclude exact position match
                query_query = query_query.filter(pos_col != ref_pos)

            # Same gene only
            if request.same_gene_only and ref_gene and hasattr(model_class, "gene"):
                query_query = query_query.filter(model_class.gene == ref_gene)

            # Apply query filters
            if request.query_filters:
                query_query = apply_filters(
                    query_query, model_class, request.query_filters
                )

            # Execute query
            query_variants = query_query.all()

            # Calculate distances and add to results
            for query_variant in query_variants:
                query_pos_raw = getattr(
                    query_variant,
                    "start" if hasattr(query_variant, "start") else "start_position",
                )

                # Convert to integer (handle string or numeric types)
                try:
                    query_pos = int(query_pos_raw)
                except (ValueError, TypeError):
                    # Skip this query variant if position is invalid
                    continue

                # Calculate distance based on direction
                distance = _calculate_distance(ref_pos, query_pos, request.direction)

                if distance is not None and distance <= request.proximity_bp:
                    variant_dict = row_to_dict(query_variant)

                    # Add proximity metadata
                    variant_dict["distance"] = distance
                    variant_dict["reference_position"] = ref_pos
                    variant_dict["reference_gene"] = ref_gene

                    # Add relative direction
                    if query_pos < ref_pos:
                        variant_dict["relative_direction"] = "upstream"
                    elif query_pos > ref_pos:
                        variant_dict["relative_direction"] = "downstream"
                    else:
                        variant_dict["relative_direction"] = "same"

                    nearby_variants.append(variant_dict)

        # Remove duplicates (same variant near multiple references)
        # Keep the one with smallest distance
        unique_variants = {}
        for variant in nearby_variants:
            # Create unique key (chromosome + position)
            key = f"{variant.get('chrom', variant.get('chromosome'))}:{variant.get('start', variant.get('start_position'))}"

            if (
                key not in unique_variants
                or variant["distance"] < unique_variants[key]["distance"]
            ):
                unique_variants[key] = variant

        nearby_variants = list(unique_variants.values())
        total_query_variants = len(nearby_variants)

        # Step 3: Sort results
        if request.sort_by:
            reverse = request.sort_order == SortOrder.DESC
            try:
                nearby_variants = sorted(
                    nearby_variants,
                    key=lambda x: x.get(request.sort_by, 0)
                    if x.get(request.sort_by) is not None
                    else 0,
                    reverse=reverse,
                )
            except Exception as e:
                # Fallback to distance sorting
                nearby_variants = sorted(
                    nearby_variants, key=lambda x: x.get("distance", 0)
                )

        # Step 4: Pagination
        offset = (request.page - 1) * request.page_size
        paginated_results = nearby_variants[offset : offset + request.page_size]

        return ProximityVariantResponse(
            dataset=request.dataset,
            reference_variant_type=request.reference_variant_type.value,
            reference_gene=request.reference_gene,
            proximity_bp=request.proximity_bp,
            direction=request.direction.value,
            total_reference_variants=total_reference_variants,
            total_query_variants=total_query_variants,
            page=request.page,
            page_size=request.page_size,
            sort_by=request.sort_by,
            sort_order=request.sort_order.value,
            results=paginated_results,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Proximity variant search failed: {str(e)}"
        )


# ==========================================
# EXAMPLE USAGE
# ==========================================

"""
Example Integration in FastAPI Router:
---------------------------------------

from proximity_variant_finder import (
    proximity_variant_finder,
    ProximityVariantRequest,
    ProximityVariantResponse
)

@router.post("/proximity_variant_finder", response_model=ProximityVariantResponse)
async def find_nearby_variants(
    table_name: str,
    request: ProximityVariantRequest,
    db: Session = Depends(get_db)
):
    return await proximity_variant_finder(request, table_name, db)


Example cURL Requests:
----------------------

1. Find SNPs near frameshift mutations in TP53:
curl -X POST "http://localhost:8000/proximity_variant_finder?table_name=tcga_exome_somatic_variants" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "tcga_exome_somatic",
    "reference_variant_type": "frameshift",
    "proximity_bp": 300,
    "direction": "both",
    "query_filters": {
      "logic": "AND",
      "conditions": [
        {"column": "hugo_symbol", "operator": "eq", "value": "TP53"},
        {"column": "variant_type", "operator": "eq", "value": "SNP"}
      ]
    },
    "same_gene_only": true,
    "sort_by": "distance",
    "sort_order": "asc",
    "page_size": 50
  }'

2. Find variants within 50bp upstream of splice sites:
curl -X POST "http://localhost:8000/proximity_variant_finder?table_name=nibmg_exome_somatic_variants" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "nibmg_exome_somatic",
    "reference_variant_type": "splice_site",
    "proximity_bp": 50,
    "direction": "upstream",
    "exclude_reference": true,
    "page_size": 100
  }'

3. Find clustered variants (variants near other variants):
curl -X POST "http://localhost:8000/proximity_variant_finder?table_name=tcga_exome_somatic_variants" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "tcga_exome_somatic",
    "reference_variant_type": "custom_filter",
    "reference_filters": {
      "logic": "AND",
      "conditions": [
        {"column": "variant_classification", "operator": "in", 
         "value": ["Missense_Mutation", "Nonsense_Mutation"]}
      ]
    },
    "proximity_bp": 100,
    "direction": "both",
    "exclude_reference": true,
    "chromosome": "17"
  }'

Expected Response:
-----------------
{
  "dataset": "tcga_exome_somatic",
  "reference_variant_type": "frameshift",
  "reference_gene": null,
  "proximity_bp": 300,
  "direction": "both",
  "total_reference_variants": 42,
  "total_query_variants": 187,
  "page": 1,
  "page_size": 50,
  "sort_by": "distance",
  "sort_order": "asc",
  "results": [
    {
      "chrom": "17",
      "start": 7577548,
      "hugo_symbol": "TP53",
      "variant_type": "SNP",
      "variant_classification": "Missense_Mutation",
      "distance": 15,
      "reference_position": 7577533,
      "reference_gene": "TP53",
      "relative_direction": "downstream"
    },
    {
      "chrom": "17",
      "start": 7577520,
      "hugo_symbol": "TP53",
      "variant_type": "SNP",
      "variant_classification": "Missense_Mutation",
      "distance": 13,
      "reference_position": 7577533,
      "reference_gene": "TP53",
      "relative_direction": "upstream"
    }
  ]
}
"""
