from enum import Enum
from fastapi import HTTPException
from sqlalchemy import and_, or_
from app.schema_new import ComplexFilter
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.core import (
    row_to_dict,
    apply_filters,
    get_model_class,
)


# ==========================================
# SCHEMAS
# ==========================================


class ProximityDirection(str, Enum):
    """Direction for proximity search"""

    upstream = "upstream"  # Only upstream (5' direction)
    downstream = "downstream"  # Only downstream (3' direction)
    both = "both"  # Both directions


class DistanceMode(str, Enum):
    """Distance filter mode"""

    within = "within"  # Distance ≤ proximity_distance (default)
    beyond = "beyond"  # Distance ≥ proximity_distance
    exact = "exact"  # Distance = proximity_distance (±1bp tolerance)
    range = "range"  # Between min_distance and max_distance


class DistanceUnit(str, Enum):
    """Unit of distance measurement"""

    bp = "bp"  # Base pairs (default)
    kb = "kb"  # Kilobases (1kb = 1000bp)
    mb = "mb"  # Megabases (1mb = 1,000,000bp)
    codon = "codon"  # Codons (1 codon = 3bp, for coding regions)


class SortOrder(str, Enum):
    """Sort order"""

    asc = "asc"
    desc = "desc"


class ProximityVariantRequest(BaseModel):
    """Request model for proximity variant search"""

    # Reference variant definition (REQUIRED)
    reference_filters: ComplexFilter = Field(
        ...,
        description="Filters to identify reference variants",
    )

    # Distance parameters
    distance_mode: DistanceMode = Field(
        DistanceMode.within,
        description="Distance filter mode (within/beyond/exact/range)",
    )

    proximity_distance: int = Field(
        300,
        ge=1,
        le=10000000,
        description="Distance threshold (or min distance for 'range' mode)",
    )

    max_proximity_distance: Optional[int] = Field(
        None,
        ge=1,
        le=10000000,
        description="Maximum distance (required for 'range' mode)",
    )

    distance_unit: DistanceUnit = Field(
        DistanceUnit.bp,
        description="Unit of distance measurement (bp/kb/mb/codon)",
    )

    direction: ProximityDirection = Field(
        ProximityDirection.both,
        description="Direction to search (upstream/downstream/both)",
    )

    # Query variant filters (optional)
    query_filters: Optional[ComplexFilter] = Field(
        None,
        description="Additional filters for query variants",
    )

    exclude_reference: bool = Field(
        True,
        description="Exclude reference variants from results",
    )

    same_gene_only: bool = Field(
        False,
        description="Only find variants in the same gene as reference",
    )

    same_chromosome_only: bool = Field(
        True,
        description="Only search within the same chromosome",
    )

    # Chromosome filter (optional)
    chromosome: Optional[str] = Field(
        None,
        description="Limit search to specific chromosome",
    )

    # ===== AGGREGATION (HAVING-LIKE LOGIC) =====
    aggregate_by_reference: bool = Field(
        False,
        description="Group results by reference variant and calculate statistics",
    )

    min_nearby_variants: Optional[int] = Field(
        None,
        ge=1,
        description="HAVING: Minimum number of nearby variants per reference (requires aggregate_by_reference=true)",
    )

    max_nearby_variants: Optional[int] = Field(
        None,
        ge=1,
        description="HAVING: Maximum number of nearby variants per reference (requires aggregate_by_reference=true)",
    )

    min_avg_distance: Optional[float] = Field(
        None,
        ge=0,
        description="HAVING: Minimum average distance to nearby variants (requires aggregate_by_reference=true)",
    )

    max_avg_distance: Optional[float] = Field(
        None,
        ge=0,
        description="HAVING: Maximum average distance to nearby variants (requires aggregate_by_reference=true)",
    )

    # ===== MULTI-LEVEL LIMITS =====
    max_reference_variants: Optional[int] = Field(
        None,
        ge=1,
        le=100000,
        description="LIMIT: Maximum number of reference variants to process",
    )

    reference_sort_by: Optional[str] = Field(
        None,
        description="How to sort reference variants before limiting",
    )

    reference_sort_order: SortOrder = Field(
        SortOrder.asc,
        description="Sort order for reference variants",
    )

    max_nearby_per_reference: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="LIMIT: Maximum nearby variants per reference variant",
    )

    nearby_sort_by: Optional[str] = Field(
        "distance",
        description="How to sort nearby variants per reference (default: distance)",
    )

    nearby_sort_order: SortOrder = Field(
        SortOrder.asc,
        description="Sort order for nearby variants per reference",
    )

    # Sorting and pagination (final output)
    sort_by: Optional[str] = Field(
        "distance",
        description="Column to sort final results by",
    )

    sort_order: SortOrder = Field(
        SortOrder.asc,
        description="Sort direction for final results",
    )

    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(100, ge=1, le=10000, description="Results per page")

    # Validators
    @field_validator("max_proximity_distance")
    @classmethod
    def validate_max_distance(cls, v, info):
        """Validate max_proximity_distance for range mode"""
        distance_mode = info.data.get("distance_mode")
        proximity_distance = info.data.get("proximity_distance")

        if distance_mode == DistanceMode.range:
            if not v:
                raise ValueError("max_proximity_distance is required for 'range' mode")
            if v <= proximity_distance:
                raise ValueError(
                    "max_proximity_distance must be greater than proximity_distance"
                )
        return v

    @field_validator(
        "min_nearby_variants",
        "max_nearby_variants",
        "min_avg_distance",
        "max_avg_distance",
    )
    @classmethod
    def validate_having_requires_aggregation(cls, v, info):
        """HAVING clauses require aggregation"""
        if v is not None:
            aggregate_by_reference = info.data.get("aggregate_by_reference")
            if not aggregate_by_reference:
                raise ValueError(
                    "HAVING filters (min_nearby_variants, max_nearby_variants, etc.) "
                    "require aggregate_by_reference=true"
                )
        return v


class ProximityVariantResponse(BaseModel):
    """Response model for proximity variant search"""

    direction: str
    table_name: str
    distance_mode: str
    distance_unit: str
    proximity_distance: int
    aggregate_by_reference: bool
    max_proximity_distance: Optional[int] = None

    # Counts
    total_results: int
    total_query_variants: int
    total_reference_variants: int

    # Pagination
    page: int
    page_size: int

    # Sorting
    sort_order: str
    sort_by: Optional[str] = None

    # Results
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


def _convert_distance_to_bp(distance: int, unit: DistanceUnit) -> int:
    """Convert distance from specified unit to base pairs."""
    if unit == DistanceUnit.bp:
        return distance
    elif unit == DistanceUnit.kb:
        return distance * 1000
    elif unit == DistanceUnit.mb:
        return distance * 1000000
    elif unit == DistanceUnit.codon:
        return distance * 3
    return distance


def _calculate_distance(
    ref_pos: int, query_pos: int, direction: ProximityDirection
) -> Optional[int]:
    """Calculate distance based on direction."""
    if direction == ProximityDirection.upstream:
        if query_pos < ref_pos:
            return ref_pos - query_pos
        return None
    elif direction == ProximityDirection.downstream:
        if query_pos > ref_pos:
            return query_pos - ref_pos
        return None
    else:  # both
        return abs(ref_pos - query_pos)


def _validate_distance(
    distance: Optional[int],
    distance_mode: DistanceMode,
    min_distance_bp: int,
    max_distance_bp: Optional[int],
) -> bool:
    """Validate if a distance matches the distance mode criteria."""
    if distance is None:
        return False

    if distance_mode == DistanceMode.within:
        return distance <= min_distance_bp
    elif distance_mode == DistanceMode.beyond:
        return distance >= min_distance_bp
    elif distance_mode == DistanceMode.exact:
        return abs(distance - min_distance_bp) <= 1
    elif distance_mode == DistanceMode.range:
        if max_distance_bp is None:
            return False
        return min_distance_bp <= distance <= max_distance_bp
    return False


def _apply_having_filters(
    aggregated_data: Dict[str, Dict[str, Any]], request: ProximityVariantRequest
) -> Dict[str, Dict[str, Any]]:
    """
    Apply HAVING-like filters to aggregated data.

    Args:
        aggregated_data: Dict mapping reference key to aggregated stats
        request: Request with HAVING parameters

    Returns:
        Filtered aggregated data
    """
    filtered = {}

    for ref_key, ref_data in aggregated_data.items():
        nearby_count = ref_data["nearby_count"]
        avg_distance = ref_data["avg_distance"]

        # HAVING: min_nearby_variants
        if request.min_nearby_variants and nearby_count < request.min_nearby_variants:
            continue

        # HAVING: max_nearby_variants
        if request.max_nearby_variants and nearby_count > request.max_nearby_variants:
            continue

        # HAVING: min_avg_distance
        if request.min_avg_distance and avg_distance < request.min_avg_distance:
            continue

        # HAVING: max_avg_distance
        if request.max_avg_distance and avg_distance > request.max_avg_distance:
            continue

        # Passed all HAVING filters
        filtered[ref_key] = ref_data

    return filtered


# ==========================================
# MAIN API FUNCTION
# ==========================================


async def proximity_variant_finder(
    request: ProximityVariantRequest, table_name: str, db
) -> ProximityVariantResponse:
    """
    Find variants in proximity to reference variants with aggregation and multi-level limits.

    Enhanced Features:
    ------------------
    1. HAVING-like aggregation filters
    2. Multi-level limits (reference, per-reference, final)

    Example Requests:
    -----------------

    1. Find reference mutations with >5 nearby variants (HAVING logic):
    {
      "reference_filters": {
        "conditions": [
          {"column": "variant_class", "operator": "in",
           "value": ["Frame_Shift_Del", "Frame_Shift_Ins"]}
        ]
      },
      "proximity_distance": 300,
      "distance_unit": "bp",
      "aggregate_by_reference": true,
      "min_nearby_variants": 5,
      "max_avg_distance": 200
    }

    2. Top 10 references with most nearby variants (multi-level limits):
    {
      "reference_filters": {
        "conditions": [
          {"column": "gene", "operator": "eq", "value": "TP53"}
        ]
      },
      "proximity_distance": 500,
      "aggregate_by_reference": true,
      "max_reference_variants": 10,
      "reference_sort_by": "start",
      "max_nearby_per_reference": 5
    }

    3. Find variants within 300bp of specific mutation:
    {
      "reference_filters": {
        "logic": "AND",
        "conditions": [
          {"column": "gene", "operator": "eq", "value": "TP53"},
          {"column": "protein_change", "operator": "like", "value": "%W146fs%"}
        ]
      },
      "proximity_distance": 300,
      "distance_unit": "bp",
      "direction": "both",
      "exclude_reference": true
    }
    """

    try:
        model_class = get_model_class(table_name)

        pos_col = getattr(model_class, "start")
        chr_col = getattr(model_class, "chrom")

        # Gene column (optional)
        gene_col_name = "gene"
        for col_name in ["hugo_symbol", "gene", "gene_symbol"]:
            if hasattr(model_class, col_name):
                gene_col_name = col_name
                break

        # Convert distances to bp
        min_distance_bp = _convert_distance_to_bp(
            request.proximity_distance, request.distance_unit
        )
        max_distance_bp = None
        if request.max_proximity_distance:
            max_distance_bp = _convert_distance_to_bp(
                request.max_proximity_distance, request.distance_unit
            )

        # ===== STEP 1: GET REFERENCE VARIANTS WITH LIMITS =====
        ref_query = db.query(model_class)

        # Apply chromosome filter
        if request.chromosome:
            norm_chrom = _normalize_chromosome(request.chromosome)
            ref_query = ref_query.filter(
                or_(
                    chr_col == norm_chrom,
                    chr_col == f"chr{norm_chrom}",
                    chr_col == request.chromosome,
                )
            )

        # Apply reference filters
        ref_query = apply_filters(ref_query, model_class, request.reference_filters)

        # Sort reference variants (for limit)
        if request.reference_sort_by and hasattr(
            model_class, request.reference_sort_by
        ):
            sort_col = getattr(model_class, request.reference_sort_by)
            if request.reference_sort_order == SortOrder.desc:
                ref_query = ref_query.order_by(sort_col.desc())
            else:
                ref_query = ref_query.order_by(sort_col.asc())

        # Get total count
        total_reference_variants = ref_query.count()

        # Apply limit to reference variants if specified
        if request.max_reference_variants:
            reference_variants = ref_query.limit(request.max_reference_variants).all()
        else:
            reference_variants = ref_query.all()

        if len(reference_variants) == 0:
            return ProximityVariantResponse(
                results=[],
                total_results=0,
                page=request.page,
                table_name=table_name,
                total_query_variants=0,
                sort_by=request.sort_by,
                total_reference_variants=0,
                page_size=request.page_size,
                direction=request.direction.value,
                sort_order=request.sort_order.value,
                distance_mode=request.distance_mode.value,
                distance_unit=request.distance_unit.value,
                proximity_distance=request.proximity_distance,
                max_proximity_distance=request.max_proximity_distance,
                aggregate_by_reference=request.aggregate_by_reference,
            )

        # ===== STEP 2: FIND NEARBY VARIANTS FOR EACH REFERENCE =====
        nearby_variants = []
        aggregated_data = {}

        for ref_variant in reference_variants:
            ref_chrom = getattr(ref_variant, "chrom")

            # Get position
            ref_pos_raw = getattr(ref_variant, "start")
            try:
                ref_pos = int(ref_pos_raw)
            except (ValueError, TypeError):
                continue

            # Extract reference variant details (for aggregation)
            ref_gene = getattr(ref_variant, "gene")
            ref_variant_type = getattr(ref_variant, "variant_type")
            ref_genome_change = getattr(ref_variant, "genome_change")
            ref_variant_class = getattr(ref_variant, "variant_class")
            ref_protein_change = getattr(ref_variant, "protein_change")

            # Build query for nearby variants
            query_query = db.query(model_class)

            # Same chromosome
            if request.same_chromosome_only:
                query_query = query_query.filter(chr_col == ref_chrom)

            # Position filtering based on distance mode
            if request.distance_mode == DistanceMode.within:
                if request.direction == ProximityDirection.upstream:
                    query_query = query_query.filter(
                        and_(pos_col < ref_pos, pos_col >= ref_pos - min_distance_bp)
                    )
                elif request.direction == ProximityDirection.downstream:
                    query_query = query_query.filter(
                        and_(pos_col > ref_pos, pos_col <= ref_pos + min_distance_bp)
                    )
                else:
                    query_query = query_query.filter(
                        and_(
                            pos_col >= ref_pos - min_distance_bp,
                            pos_col <= ref_pos + min_distance_bp,
                        )
                    )

            elif request.distance_mode == DistanceMode.beyond:
                if request.direction == ProximityDirection.upstream:
                    query_query = query_query.filter(
                        pos_col <= ref_pos - min_distance_bp
                    )
                elif request.direction == ProximityDirection.downstream:
                    query_query = query_query.filter(
                        pos_col >= ref_pos + min_distance_bp
                    )
                else:
                    query_query = query_query.filter(
                        or_(
                            pos_col <= ref_pos - min_distance_bp,
                            pos_col >= ref_pos + min_distance_bp,
                        )
                    )

            elif request.distance_mode == DistanceMode.exact:
                if request.direction == ProximityDirection.upstream:
                    query_query = query_query.filter(
                        and_(
                            pos_col >= ref_pos - min_distance_bp - 1,
                            pos_col <= ref_pos - min_distance_bp + 1,
                        )
                    )
                elif request.direction == ProximityDirection.downstream:
                    query_query = query_query.filter(
                        and_(
                            pos_col >= ref_pos + min_distance_bp - 1,
                            pos_col <= ref_pos + min_distance_bp + 1,
                        )
                    )
                else:
                    query_query = query_query.filter(
                        or_(
                            and_(
                                pos_col >= ref_pos - min_distance_bp - 1,
                                pos_col <= ref_pos - min_distance_bp + 1,
                            ),
                            and_(
                                pos_col >= ref_pos + min_distance_bp - 1,
                                pos_col <= ref_pos + min_distance_bp + 1,
                            ),
                        )
                    )

            elif request.distance_mode == DistanceMode.range:
                if max_distance_bp is None:
                    continue

                if request.direction == ProximityDirection.upstream:
                    query_query = query_query.filter(
                        and_(
                            pos_col <= ref_pos - min_distance_bp,
                            pos_col >= ref_pos - max_distance_bp,
                        )
                    )
                elif request.direction == ProximityDirection.downstream:
                    query_query = query_query.filter(
                        and_(
                            pos_col >= ref_pos + min_distance_bp,
                            pos_col <= ref_pos + max_distance_bp,
                        )
                    )
                else:
                    query_query = query_query.filter(
                        or_(
                            and_(
                                pos_col <= ref_pos - min_distance_bp,
                                pos_col >= ref_pos - max_distance_bp,
                            ),
                            and_(
                                pos_col >= ref_pos + min_distance_bp,
                                pos_col <= ref_pos + max_distance_bp,
                            ),
                        )
                    )

            # Exclude reference
            if request.exclude_reference:
                query_query = query_query.filter(pos_col != ref_pos)

            # Same gene only
            if request.same_gene_only and ref_gene and gene_col_name:
                gene_col = getattr(model_class, gene_col_name)
                query_query = query_query.filter(gene_col == ref_gene)

            # Apply query filters
            if request.query_filters:
                query_query = apply_filters(
                    query_query, model_class, request.query_filters
                )

            # Sort nearby variants per reference
            if request.nearby_sort_by:
                if request.nearby_sort_by == "distance":
                    # Will sort by distance after calculation
                    pass
                elif hasattr(model_class, request.nearby_sort_by):
                    sort_col = getattr(model_class, request.nearby_sort_by)
                    if request.nearby_sort_order == SortOrder.desc:
                        query_query = query_query.order_by(sort_col.desc())
                    else:
                        query_query = query_query.order_by(sort_col.asc())

            # Execute query
            query_variants = query_query.all()

            # Calculate distances and create variant objects
            ref_nearby_variants = []
            for query_variant in query_variants:
                query_pos_raw = getattr(query_variant, "start")
                try:
                    query_pos = int(query_pos_raw)
                except (ValueError, TypeError):
                    continue

                distance_bp = _calculate_distance(ref_pos, query_pos, request.direction)

                if not _validate_distance(
                    distance_bp, request.distance_mode, min_distance_bp, max_distance_bp
                ):
                    continue

                variant_dict = row_to_dict(query_variant)

                # Convert distance to requested unit
                if request.distance_unit == DistanceUnit.kb:
                    distance_display = round(distance_bp / 1000, 3)
                elif request.distance_unit == DistanceUnit.mb:
                    distance_display = round(distance_bp / 1000000, 6)
                elif request.distance_unit == DistanceUnit.codon:
                    distance_display = distance_bp // 3
                else:
                    distance_display = distance_bp

                variant_dict["distance_bp"] = distance_bp
                variant_dict["reference_gene"] = ref_gene
                variant_dict["distance"] = distance_display
                variant_dict["reference_position"] = ref_pos
                variant_dict["reference_chromosome"] = ref_chrom
                variant_dict["distance_unit"] = request.distance_unit.value

                if query_pos < ref_pos:
                    variant_dict["relative_direction"] = "upstream"
                elif query_pos > ref_pos:
                    variant_dict["relative_direction"] = "downstream"
                else:
                    variant_dict["relative_direction"] = "same"

                ref_nearby_variants.append(variant_dict)

            # Sort by distance if requested
            if request.nearby_sort_by == "distance":
                ref_nearby_variants = sorted(
                    ref_nearby_variants,
                    key=lambda x: x["distance_bp"],
                    reverse=(request.nearby_sort_order == SortOrder.desc),
                )

            # Limit nearby per reference
            if request.max_nearby_per_reference:
                ref_nearby_variants = ref_nearby_variants[
                    : request.max_nearby_per_reference
                ]

            # Store for aggregation or add to results
            if request.aggregate_by_reference:
                # Aggregate by reference
                ref_key = f"{ref_chrom}:{ref_pos}"
                if ref_nearby_variants:
                    aggregated_data[ref_key] = {
                        "reference": {
                            "gene": ref_gene,
                            "position": ref_pos,
                            "chromosome": ref_chrom,
                            "variant_type": ref_variant_type,
                            "genome_change": ref_genome_change,
                            "variant_class": ref_variant_class,
                            "protein_change": ref_protein_change,
                        },
                        "nearby_count": len(ref_nearby_variants),
                        "avg_distance": sum(
                            v["distance_bp"] for v in ref_nearby_variants
                        )
                        / len(ref_nearby_variants),
                        "min_distance": min(
                            v["distance_bp"] for v in ref_nearby_variants
                        ),
                        "max_distance": max(
                            v["distance_bp"] for v in ref_nearby_variants
                        ),
                        "nearby_variants": ref_nearby_variants,
                    }
            else:
                # No aggregation - add all nearby variants
                nearby_variants.extend(ref_nearby_variants)

        # ===== STEP 3: APPLY HAVING FILTERS (IF AGGREGATED) =====
        if request.aggregate_by_reference:
            aggregated_data = _apply_having_filters(aggregated_data, request)

            # Convert aggregated data to result format
            nearby_variants = []
            for ref_key, ref_data in aggregated_data.items():
                nearby_variants.append(
                    {
                        "reference": ref_data["reference"],
                        "nearby_count": ref_data["nearby_count"],
                        "min_distance": ref_data["min_distance"],
                        "max_distance": ref_data["max_distance"],
                        "nearby_variants": ref_data["nearby_variants"],
                        "avg_distance": round(ref_data["avg_distance"], 2),
                    }
                )

        # ===== STEP 4: REMOVE DUPLICATES (IF NOT AGGREGATED) =====
        if not request.aggregate_by_reference:
            unique_variants = {}
            for variant in nearby_variants:
                key = f"{variant.get('chrom')}:{variant.get('start')}"
                if (
                    key not in unique_variants
                    or variant["distance_bp"] < unique_variants[key]["distance_bp"]
                ):
                    unique_variants[key] = variant
            nearby_variants = list(unique_variants.values())

        total_query_variants = len(nearby_variants)

        # ===== STEP 5: SORT FINAL RESULTS =====
        if request.sort_by and not request.aggregate_by_reference:
            reverse = request.sort_order == SortOrder.desc
            try:
                nearby_variants = sorted(
                    nearby_variants,
                    key=lambda x: (
                        x.get(request.sort_by, 0)
                        if x.get(request.sort_by) is not None
                        else 0
                    ),
                    reverse=reverse,
                )
            except Exception:
                nearby_variants = sorted(
                    nearby_variants, key=lambda x: x.get("distance_bp", 0)
                )
        elif request.aggregate_by_reference:
            # Sort aggregated results
            if request.sort_by == "nearby_count":
                nearby_variants = sorted(
                    nearby_variants,
                    key=lambda x: x["nearby_count"],
                    reverse=(request.sort_order == SortOrder.desc),
                )
            elif request.sort_by == "avg_distance":
                nearby_variants = sorted(
                    nearby_variants,
                    key=lambda x: x["avg_distance"],
                    reverse=(request.sort_order == SortOrder.desc),
                )

        # ===== STEP 6: PAGINATION =====
        offset = (request.page - 1) * request.page_size
        paginated_results = nearby_variants[offset : offset + request.page_size]

        return ProximityVariantResponse(
            page=request.page,
            table_name=table_name,
            sort_by=request.sort_by,
            results=paginated_results,
            page_size=request.page_size,
            direction=request.direction.value,
            total_results=total_query_variants,
            sort_order=request.sort_order.value,
            distance_mode=request.distance_mode.value,
            distance_unit=request.distance_unit.value,
            total_query_variants=total_query_variants,
            proximity_distance=request.proximity_distance,
            total_reference_variants=total_reference_variants,
            max_proximity_distance=request.max_proximity_distance,
            aggregate_by_reference=request.aggregate_by_reference,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(500, f"Proximity variant search failed: {str(e)}")


# ==========================================
# USAGE EXAMPLES
# ==========================================

"""
Example 1: HAVING Logic - Find frameshifts with >5 nearby variants
--------------------------------------------------------------------
{
  "reference_filters": {
    "logic": "AND",
    "conditions": [
      {"column": "variant_class", "operator": "in", 
       "value": ["Frame_Shift_Del", "Frame_Shift_Ins"]}
    ]
  },
  "proximity_distance": 300,
  "distance_unit": "bp",
  "aggregate_by_reference": true,
  "min_nearby_variants": 5,
  "max_avg_distance": 200,
  "sort_by": "nearby_count",
  "sort_order": "desc"
}

Example 2: Multi-Level Limits - Top 10 references, 5 nearest each
-------------------------------------------------------------------
{
  "reference_filters": {
    "conditions": [{"column": "gene", "operator": "eq", "value": "TP53"}]
  },
  "proximity_distance": 500,
  "max_reference_variants": 10,
  "reference_sort_by": "start",
  "max_nearby_per_reference": 5,
  "nearby_sort_by": "distance"
}

Example 3: Simple proximity - Variants within 300bp of specific mutation
--------------------------------------------------------------------------
{
  "reference_filters": {
    "logic": "AND",
    "conditions": [
      {"column": "gene", "operator": "eq", "value": "TP53"},
      {"column": "protein_change", "operator": "like", "value": "%W146fs%"}
    ]
  },
  "proximity_distance": 300,
  "distance_unit": "bp",
  "direction": "both",
  "exclude_reference": true,
  "sort_by": "distance",
  "sort_order": "asc"
}
"""
