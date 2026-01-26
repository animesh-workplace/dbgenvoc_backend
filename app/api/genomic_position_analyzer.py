"""
genomic_position_analyzer.py

Analyzes mutations by genomic position to identify hotspots, mutation density,
and regional mutation patterns.

Author: Generated based on dbGENVOC API patterns
Date: 2026-01-23
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_, between
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator
from app.schema_new import ComplexFilter
from app.core import (
    apply_filters,
    get_model_class,
    validate_columns,
)


# ==========================================
# SCHEMAS
# ==========================================

class AnalysisType(str, Enum):
    """Types of position-based analysis"""
    hotspot_detection = "hotspot_detection"  # Find mutation hotspots
    position_density = "position_density"  # Mutation density per position
    region_analysis = "region_analysis"  # Analyze specific genomic region
    codon_analysis = "codon_analysis"  # Analyze mutations by codon position


class WindowType(str, Enum):
    """Type of window for hotspot detection"""
    fixed = "fixed"  # Fixed window size (e.g., 100bp)
    sliding = "sliding"  # Sliding window
    gene_based = "gene_based"  # Gene boundaries


class OrderDirection(str, Enum):
    """Sort order"""
    asc = "asc"
    desc = "desc"


class GenomicPositionRequest(BaseModel):
    """Request model for genomic position analysis"""

    # Dataset to analyze
    dataset: str = Field(
        ...,
        description="Dataset name (e.g., 'nibmg_exome_somatic', 'tcga_exome_somatic')"
    )

    # Analysis type
    analysis_type: AnalysisType = Field(
        AnalysisType.hotspot_detection,
        description="Type of position-based analysis"
    )

    # Genomic region filters
    chromosome: Optional[str] = Field(
        None,
        description="Chromosome to analyze (e.g., '1', '2', 'X', 'Y')"
    )

    start_position: Optional[int] = Field(
        None,
        ge=0,
        description="Start position (1-based coordinate)"
    )

    end_position: Optional[int] = Field(
        None,
        ge=0,
        description="End position (1-based coordinate)"
    )

    # Gene-based filtering
    gene: Optional[str] = Field(
        None,
        description="Gene symbol to analyze (alternative to chromosome/position)"
    )

    # Hotspot detection parameters
    window_size: int = Field(
        100,
        ge=1,
        le=10000,
        description="Window size in base pairs for hotspot detection"
    )

    window_type: WindowType = Field(
        WindowType.fixed,
        description="Type of window for analysis"
    )

    min_mutations: int = Field(
        3,
        ge=1,
        description="Minimum mutations in window to be considered a hotspot"
    )

    # Position density parameters
    bin_size: int = Field(
        1000,
        ge=1,
        le=1000000,
        description="Bin size for density calculation (in base pairs)"
    )

    # Additional filters
    filters: Optional[ComplexFilter] = Field(
        None,
        description="Complex filters with AND/OR logic"
    )

    # Variant type filtering
    variant_types: Optional[List[str]] = Field(
        None,
        description="Filter by variant types (e.g., ['SNP', 'DEL', 'INS'])"
    )

    variant_classifications: Optional[List[str]] = Field(
        None,
        description="Filter by variant classifications (e.g., ['Missense_Mutation'])"
    )

    # Ordering and limiting
    order_by: Optional[str] = Field(
        None,
        description="Column to order by (e.g., 'mutation_count', 'position', 'density')"
    )

    order_direction: OrderDirection = Field(
        OrderDirection.desc,
        description="Sort direction"
    )

    limit: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="Limit number of results"
    )

    @field_validator("end_position")
    @classmethod
    def validate_position_range(cls, v, info):
        """Validate position range is valid"""
        start_pos = info.data.get("start_position")
        if v is not None and start_pos is not None and v < start_pos:
            raise ValueError("end_position must be greater than or equal to start_position")
        return v

    @field_validator("chromosome")
    @classmethod
    def validate_chromosome_or_gene(cls, v, info):
        """Validate that either chromosome or gene is provided for region analysis"""
        analysis_type = info.data.get("analysis_type")
        gene = info.data.get("gene")

        if analysis_type == AnalysisType.region_analysis:
            if not v and not gene:
                raise ValueError(
                    "Either chromosome (with positions) or gene must be specified for region_analysis"
                )
        return v


class GenomicPositionResponse(BaseModel):
    """Response model for genomic position analysis"""

    dataset: str
    analysis_type: str
    chromosome: Optional[str] = None
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    gene: Optional[str] = None
    total_mutations: int
    total_results: int

    # Analysis parameters
    window_size: Optional[int] = None
    bin_size: Optional[int] = None

    # Ordering info
    order_by: Optional[str] = None
    order_direction: Optional[str] = None
    limit: Optional[int] = None

    # Results
    result: List[Dict[str, Any]]


# ==========================================
# INTERNAL HELPERS
# ==========================================

def _normalize_chromosome(chrom: str) -> str:
    """
    Normalize chromosome name (remove 'chr' prefix if present).

    Args:
        chrom: Chromosome identifier

    Returns:
        Normalized chromosome name
    """
    if chrom is None:
        return None

    chrom_str = str(chrom).upper()
    if chrom_str.startswith('CHR'):
        return chrom_str[3:]
    return chrom_str


def _get_gene_coordinates(db, gene_symbol: str) -> Optional[Tuple[str, int, int]]:
    """
    Get genomic coordinates for a gene.

    Args:
        db: Database session
        gene_symbol: Gene symbol

    Returns:
        Tuple of (chromosome, start, end) or None if not found
    """
    try:
        from app.models import Genelist

        gene = db.query(Genelist).filter(Genelist.gene == gene_symbol).first()

        if gene and hasattr(gene, 'chrom') and hasattr(gene, 'start') and hasattr(gene, 'end'):
            return (gene.chrom, gene.start, gene.end)

        return None

    except Exception:
        return None


def _apply_position_filters(
    query,
    model_class,
    chromosome: Optional[str],
    start_pos: Optional[int],
    end_pos: Optional[int]
):
    """
    Apply genomic position filters to query.

    Args:
        query: SQLAlchemy query
        model_class: Model class
        chromosome: Chromosome filter
        start_pos: Start position
        end_pos: End position

    Returns:
        Filtered query
    """
    # Chromosome filter
    if chromosome:
        norm_chrom = _normalize_chromosome(chromosome)

        if hasattr(model_class, 'chrom'):
            # Try both with and without 'chr' prefix
            query = query.filter(
                or_(
                    model_class.chrom == norm_chrom,
                    model_class.chrom == f'chr{norm_chrom}',
                    model_class.chrom == chromosome
                )
            )
        elif hasattr(model_class, 'chromosome'):
            query = query.filter(
                or_(
                    model_class.chromosome == norm_chrom,
                    model_class.chromosome == f'chr{norm_chrom}',
                    model_class.chromosome == chromosome
                )
            )

    # Position range filters
    if start_pos is not None or end_pos is not None:
        if hasattr(model_class, 'start') and hasattr(model_class, 'end'):
            # Use start/end columns for range overlap
            if start_pos is not None and end_pos is not None:
                # Variants that overlap with the region
                query = query.filter(
                    and_(
                        model_class.start <= end_pos,
                        model_class.end >= start_pos
                    )
                )
            elif start_pos is not None:
                query = query.filter(model_class.end >= start_pos)
            elif end_pos is not None:
                query = query.filter(model_class.start <= end_pos)
        elif hasattr(model_class, 'start_position'):
            if start_pos is not None:
                query = query.filter(model_class.start_position >= start_pos)
            if end_pos is not None:
                query = query.filter(model_class.start_position <= end_pos)

    return query


def _apply_variant_filters(
    query,
    model_class,
    variant_types: Optional[List[str]],
    variant_classifications: Optional[List[str]]
):
    """
    Apply variant type and classification filters.

    Args:
        query: SQLAlchemy query
        model_class: Model class
        variant_types: List of variant types to include
        variant_classifications: List of variant classifications to include

    Returns:
        Filtered query
    """
    if variant_types and hasattr(model_class, 'variant_type'):
        query = query.filter(model_class.variant_type.in_(variant_types))

    if variant_classifications and hasattr(model_class, 'variant_classification'):
        query = query.filter(model_class.variant_classification.in_(variant_classifications))

    return query


# ==========================================
# ANALYSIS IMPLEMENTATIONS
# ==========================================

async def _detect_hotspots(
    db,
    table_name: str,
    request: GenomicPositionRequest
) -> GenomicPositionResponse:
    """
    Detect mutation hotspots using windowed analysis.

    Identifies genomic positions with high mutation density.
    """
    try:
        model_class = get_model_class(table_name)

        # Build base query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Apply position filters
        chromosome = request.chromosome
        start_pos = request.start_position
        end_pos = request.end_position

        # If gene specified, get its coordinates
        if request.gene:
            gene_coords = _get_gene_coordinates(db, request.gene)
            if gene_coords:
                chromosome, start_pos, end_pos = gene_coords
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Gene '{request.gene}' not found or has no coordinates"
                )

        query = _apply_position_filters(query, model_class, chromosome, start_pos, end_pos)
        query = _apply_variant_filters(query, model_class, request.variant_types, request.variant_classifications)

        # Get total mutations in region
        total_mutations = query.count()

        # Group by position windows
        # We'll use start position and create bins
        if hasattr(model_class, 'start'):
            position_col = model_class.start
        elif hasattr(model_class, 'start_position'):
            position_col = model_class.start_position
        else:
            raise HTTPException(
                status_code=400,
                detail="Model does not have position column (start or start_position)"
            )

        # Calculate window bin for each position
        window_bin = (position_col / request.window_size).cast(func.integer()) * request.window_size

        # Aggregate by window
        hotspot_query = query.with_entities(
            window_bin.label('window_start'),
            func.count().label('mutation_count'),
            func.min(position_col).label('min_position'),
            func.max(position_col).label('max_position'),
            func.group_concat(model_class.hugo_symbol).label('genes') if hasattr(model_class, 'hugo_symbol') else func.count().label('genes')
        ).group_by(window_bin)

        # Filter by minimum mutations
        hotspot_query = hotspot_query.having(func.count() >= request.min_mutations)

        # Execute
        results = hotspot_query.all()

        # Format results
        hotspots = []
        for row in results:
            window_start = int(row.window_start)
            window_end = window_start + request.window_size

            hotspot = {
                'chromosome': chromosome or 'N/A',
                'window_start': window_start,
                'window_end': window_end,
                'mutation_count': row.mutation_count,
                'min_position': row.min_position,
                'max_position': row.max_position
            }

            # Add genes if available
            if hasattr(row, 'genes') and row.genes:
                genes = set(str(row.genes).split(','))
                hotspot['genes'] = sorted([g for g in genes if g and g != 'None'])

            hotspots.append(hotspot)

        # Sort by mutation count (descending) by default
        if request.order_by:
            reverse = (request.order_direction == OrderDirection.desc)
            hotspots = sorted(
                hotspots,
                key=lambda x: x.get(request.order_by, 0),
                reverse=reverse
            )
        else:
            hotspots = sorted(hotspots, key=lambda x: x['mutation_count'], reverse=True)

        # Apply limit
        if request.limit:
            hotspots = hotspots[:request.limit]

        return GenomicPositionResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            chromosome=chromosome,
            start_position=start_pos,
            end_position=end_pos,
            gene=request.gene,
            total_mutations=total_mutations,
            total_results=len(hotspots),
            window_size=request.window_size,
            order_by=request.order_by,
            order_direction=request.order_direction.value,
            limit=request.limit,
            result=hotspots
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Hotspot detection failed: {str(e)}"
        )


async def _calculate_position_density(
    db,
    table_name: str,
    request: GenomicPositionRequest
) -> GenomicPositionResponse:
    """
    Calculate mutation density across genomic positions.
    """
    try:
        model_class = get_model_class(table_name)

        # Build query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Get gene coordinates if specified
        chromosome = request.chromosome
        start_pos = request.start_position
        end_pos = request.end_position

        if request.gene:
            gene_coords = _get_gene_coordinates(db, request.gene)
            if gene_coords:
                chromosome, start_pos, end_pos = gene_coords

        query = _apply_position_filters(query, model_class, chromosome, start_pos, end_pos)
        query = _apply_variant_filters(query, model_class, request.variant_types, request.variant_classifications)

        total_mutations = query.count()

        # Get position column
        if hasattr(model_class, 'start'):
            position_col = model_class.start
        elif hasattr(model_class, 'start_position'):
            position_col = model_class.start_position
        else:
            raise HTTPException(
                status_code=400,
                detail="Model does not have position column"
            )

        # Create bins
        bin_number = (position_col / request.bin_size).cast(func.integer())

        # Aggregate by bin
        density_query = query.with_entities(
            bin_number.label('bin'),
            func.count().label('mutation_count'),
            func.min(position_col).label('bin_start'),
            func.max(position_col).label('bin_end')
        ).group_by(bin_number)

        results = density_query.all()

        # Format results
        density_data = []
        for row in results:
            bin_start = int(row.bin) * request.bin_size
            bin_end = bin_start + request.bin_size

            density_data.append({
                'chromosome': chromosome or 'N/A',
                'bin_start': bin_start,
                'bin_end': bin_end,
                'mutation_count': row.mutation_count,
                'density': round(row.mutation_count / request.bin_size * 1000, 3)  # per kb
            })

        # Sort
        if request.order_by:
            reverse = (request.order_direction == OrderDirection.desc)
            density_data = sorted(
                density_data,
                key=lambda x: x.get(request.order_by, 0),
                reverse=reverse
            )

        # Apply limit
        if request.limit:
            density_data = density_data[:request.limit]

        return GenomicPositionResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            chromosome=chromosome,
            start_position=start_pos,
            end_position=end_pos,
            gene=request.gene,
            total_mutations=total_mutations,
            total_results=len(density_data),
            bin_size=request.bin_size,
            order_by=request.order_by,
            order_direction=request.order_direction.value,
            limit=request.limit,
            result=density_data
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Position density calculation failed: {str(e)}"
        )


async def _analyze_region(
    db,
    table_name: str,
    request: GenomicPositionRequest
) -> GenomicPositionResponse:
    """
    Analyze mutations in a specific genomic region.
    """
    try:
        model_class = get_model_class(table_name)

        # Build query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Get gene coordinates if specified
        chromosome = request.chromosome
        start_pos = request.start_position
        end_pos = request.end_position

        if request.gene:
            gene_coords = _get_gene_coordinates(db, request.gene)
            if gene_coords:
                chromosome, start_pos, end_pos = gene_coords

        query = _apply_position_filters(query, model_class, chromosome, start_pos, end_pos)
        query = _apply_variant_filters(query, model_class, request.variant_types, request.variant_classifications)

        # Get position column for grouping
        if hasattr(model_class, 'start'):
            position_col = model_class.start
        elif hasattr(model_class, 'start_position'):
            position_col = model_class.start_position
        else:
            position_col = None

        # Group by position
        if position_col:
            region_query = query.with_entities(
                position_col.label('position'),
                func.count().label('mutation_count'),
                func.group_concat(model_class.hugo_symbol).label('genes') if hasattr(model_class, 'hugo_symbol') else None,
                func.group_concat(model_class.variant_classification).label('variant_classifications') if hasattr(model_class, 'variant_classification') else None
            ).group_by(position_col)

            results = region_query.all()

            # Format results
            region_data = []
            for row in results:
                item = {
                    'position': row.position,
                    'mutation_count': row.mutation_count
                }

                if hasattr(row, 'genes') and row.genes:
                    genes = set(str(row.genes).split(','))
                    item['genes'] = sorted([g for g in genes if g and g != 'None'])

                if hasattr(row, 'variant_classifications') and row.variant_classifications:
                    classifications = set(str(row.variant_classifications).split(','))
                    item['variant_classifications'] = sorted([c for c in classifications if c and c != 'None'])

                region_data.append(item)
        else:
            # Just count total
            total = query.count()
            region_data = [{'total_mutations': total}]

        # Sort
        if request.order_by and region_data and request.order_by in region_data[0]:
            reverse = (request.order_direction == OrderDirection.desc)
            region_data = sorted(
                region_data,
                key=lambda x: x.get(request.order_by, 0),
                reverse=reverse
            )

        # Apply limit
        if request.limit:
            region_data = region_data[:request.limit]

        return GenomicPositionResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            chromosome=chromosome,
            start_position=start_pos,
            end_position=end_pos,
            gene=request.gene,
            total_mutations=query.count(),
            total_results=len(region_data),
            order_by=request.order_by,
            order_direction=request.order_direction.value,
            limit=request.limit,
            result=region_data
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Region analysis failed: {str(e)}"
        )


async def _analyze_codons(
    db,
    table_name: str,
    request: GenomicPositionRequest
) -> GenomicPositionResponse:
    """
    Analyze mutations by codon position.
    """
    try:
        model_class = get_model_class(table_name)

        # Ensure codon column exists
        if not hasattr(model_class, 'protein_position'):
            raise HTTPException(
                status_code=400,
                detail="Codon analysis requires protein_position column in dataset"
            )

        # Build query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Gene filter is important for codon analysis
        if request.gene:
            if hasattr(model_class, 'hugo_symbol'):
                query = query.filter(model_class.hugo_symbol == request.gene)

        query = _apply_variant_filters(query, model_class, request.variant_types, request.variant_classifications)

        # Group by protein position
        codon_query = query.with_entities(
            model_class.protein_position,
            func.count().label('mutation_count'),
            func.group_concat(model_class.hgvsp_short).label('protein_changes') if hasattr(model_class, 'hgvsp_short') else None
        ).group_by(model_class.protein_position)

        results = codon_query.all()

        # Format results
        codon_data = []
        for row in results:
            item = {
                'protein_position': row.protein_position,
                'mutation_count': row.mutation_count
            }

            if hasattr(row, 'protein_changes') and row.protein_changes:
                changes = set(str(row.protein_changes).split(','))
                item['protein_changes'] = sorted([c for c in changes if c and c != 'None'])

            codon_data.append(item)

        # Sort
        if request.order_by:
            reverse = (request.order_direction == OrderDirection.desc)
            codon_data = sorted(
                codon_data,
                key=lambda x: x.get(request.order_by, 0),
                reverse=reverse
            )

        # Apply limit
        if request.limit:
            codon_data = codon_data[:request.limit]

        return GenomicPositionResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            gene=request.gene,
            chromosome=None,
            start_position=None,
            end_position=None,
            total_mutations=query.count(),
            total_results=len(codon_data),
            order_by=request.order_by,
            order_direction=request.order_direction.value,
            limit=request.limit,
            result=codon_data
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Codon analysis failed: {str(e)}"
        )


# ==========================================
# MAIN API FUNCTION
# ==========================================

async def genomic_position_analyzer(
    request: GenomicPositionRequest,
    table_name: str,
    db
) -> GenomicPositionResponse:
    """
    Analyze mutations by genomic position.

    Supports multiple analysis types:
    1. hotspot_detection: Find mutation hotspots using windowed analysis
    2. position_density: Calculate mutation density across genomic regions
    3. region_analysis: Detailed analysis of specific genomic region
    4. codon_analysis: Analyze mutations by codon/protein position

    Args:
        request: GenomicPositionRequest with analysis parameters
        table_name: Dataset table name
        db: Database session

    Returns:
        GenomicPositionResponse with analysis results

    Example Requests:
    -----------------

    1. Detect TP53 Hotspots:
    {
      "dataset": "tcga_exome_somatic",
      "analysis_type": "hotspot_detection",
      "gene": "TP53",
      "window_size": 50,
      "min_mutations": 5,
      "order_by": "mutation_count",
      "order_direction": "desc",
      "limit": 10
    }

    2. Mutation Density on Chromosome 17:
    {
      "dataset": "nibmg_exome_somatic",
      "analysis_type": "position_density",
      "chromosome": "17",
      "start_position": 7500000,
      "end_position": 8000000,
      "bin_size": 10000
    }

    3. Analyze Specific Region:
    {
      "dataset": "tcga_exome_somatic",
      "analysis_type": "region_analysis",
      "chromosome": "17",
      "start_position": 7571720,
      "end_position": 7590863,
      "variant_classifications": ["Missense_Mutation", "Nonsense_Mutation"]
    }

    4. Codon-Level Analysis:
    {
      "dataset": "tcga_exome_somatic",
      "analysis_type": "codon_analysis",
      "gene": "KRAS",
      "order_by": "mutation_count",
      "order_direction": "desc",
      "limit": 20
    }
    """

    try:
        # Route to appropriate analysis
        if request.analysis_type == AnalysisType.hotspot_detection:
            return await _detect_hotspots(db, table_name, request)

        elif request.analysis_type == AnalysisType.position_density:
            return await _calculate_position_density(db, table_name, request)

        elif request.analysis_type == AnalysisType.region_analysis:
            return await _analyze_region(db, table_name, request)

        elif request.analysis_type == AnalysisType.codon_analysis:
            return await _analyze_codons(db, table_name, request)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported analysis type: {request.analysis_type}"
            )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Genomic position analysis failed: {str(e)}"
        )
