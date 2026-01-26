"""
pathway_enrichment_analyzer.py

Analyzes pathway enrichment in mutated genes from genomic datasets.
Supports multiple analysis types: enrichment, pathway_genes, and gene_pathways.

Author: Generated based on dbGENVOC API patterns
Date: 2026-01-23
Updated: Uses actual Pathway and Genelist models with pathway_gene_association
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_, distinct
from typing import Any, Dict, List, Optional, Union
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

class AnalysisType(str, Enum):
    """Types of pathway analysis supported"""
    enrichment = "enrichment"  # Find enriched pathways in gene list
    pathway_genes = "pathway_genes"  # Get genes in specific pathways
    gene_pathways = "gene_pathways"  # Get pathways for specific genes


class OrderDirection(str, Enum):
    """Sort order"""
    asc = "asc"
    desc = "desc"


class PathwayEnrichmentRequest(BaseModel):
    """Request model for pathway enrichment analysis"""

    # Dataset to analyze
    dataset: str = Field(
        ..., 
        description="Dataset name (e.g., 'nibmg_exome_somatic', 'tcga_exome_somatic')"
    )

    # Analysis type
    analysis_type: AnalysisType = Field(
        AnalysisType.enrichment,
        description="Type of pathway analysis to perform"
    )

    # Gene list for enrichment analysis
    gene_list: Optional[List[str]] = Field(
        None,
        description="List of genes for enrichment analysis (required for 'enrichment' type)"
    )

    # Pathway filters
    pathway_id: Optional[str] = Field(
        None,
        description="Specific pathway ID to query (for 'pathway_genes' type)"
    )

    pathway_name_contains: Optional[str] = Field(
        None,
        description="Filter pathways by name substring (e.g., 'cancer', 'signaling')"
    )

    # Enrichment parameters
    min_genes: int = Field(
        2,
        ge=1,
        description="Minimum number of genes in pathway for enrichment"
    )

    p_value_threshold: float = Field(
        0.05,
        gt=0,
        le=1,
        description="P-value threshold for significance (default: 0.05)"
    )

    # Additional filters on variants
    filters: Optional[ComplexFilter] = Field(
        None,
        description="Complex filters to apply on variant data before pathway analysis"
    )

    # Ordering and limiting
    order_by: Optional[str] = Field(
        None,
        description="Column to order by ('p_value', 'gene_count', 'pathway_name', 'fold_enrichment')"
    )

    order_direction: OrderDirection = Field(
        OrderDirection.asc,
        description="Sort direction"
    )

    limit: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
        description="Limit number of results"
    )

    @field_validator("gene_list")
    @classmethod
    def validate_gene_list(cls, v, info):
        """Validate gene list is provided for enrichment analysis"""
        analysis_type = info.data.get("analysis_type")
        if analysis_type == AnalysisType.enrichment and not v:
            raise ValueError("gene_list is required for enrichment analysis")
        if analysis_type == AnalysisType.gene_pathways and not v:
            raise ValueError("gene_list is required for gene_pathways analysis")
        return v

    @field_validator("pathway_id")
    @classmethod
    def validate_pathway_id(cls, v, info):
        """Validate pathway_id is provided for pathway_genes analysis"""
        if info.data.get("analysis_type") == AnalysisType.pathway_genes and not v:
            raise ValueError("pathway_id is required for pathway_genes analysis")
        return v


class PathwayEnrichmentResponse(BaseModel):
    """Response model for pathway enrichment analysis"""

    dataset: str
    analysis_type: str
    total_pathways: int
    total_genes: Optional[int] = None
    input_genes: Optional[int] = None

    # Ordering and limiting info
    order_by: Optional[str] = None
    order_direction: Optional[str] = None
    limit: Optional[int] = None

    # Results
    result: List[Dict[str, Any]]


# ==========================================
# INTERNAL HELPERS
# ==========================================

def _get_mutated_genes_from_dataset(
    db, 
    table_name: str, 
    filters: Optional[ComplexFilter] = None
) -> List[str]:
    """
    Extract unique mutated genes from a dataset.

    Args:
        db: Database session
        table_name: Name of the variant table
        filters: Optional filters to apply

    Returns:
        List of unique gene symbols
    """
    try:
        model_class = get_model_class(table_name)

        # Build query
        query = db.query(distinct(model_class.hugo_symbol))

        # Apply filters if provided
        if filters:
            query = apply_filters(query, model_class, filters)

        # Execute and extract genes
        results = query.filter(model_class.hugo_symbol.isnot(None)).all()
        genes = [row[0] for row in results if row[0]]

        return genes

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract genes from dataset: {str(e)}"
        )


def _calculate_enrichment_statistics(
    total_genes: int,
    pathway_genes: int,
    input_genes_count: int,
    overlap_count: int
) -> Dict[str, float]:
    """
    Calculate enrichment statistics using Fisher's exact test approximation.

    Args:
        total_genes: Total genes in genome/background
        pathway_genes: Number of genes in the pathway
        input_genes_count: Number of genes in input list
        overlap_count: Number of overlapping genes

    Returns:
        Dictionary with p_value, fold_enrichment, etc.
    """
    try:
        from scipy.stats import fisher_exact

        # Build contingency table
        # | In pathway | Not in pathway |
        # | In input   | a              | b              |
        # | Not input  | c              | d              |

        a = overlap_count  # In both pathway and input
        b = input_genes_count - overlap_count  # In input, not in pathway
        c = pathway_genes - overlap_count  # In pathway, not in input
        d = total_genes - pathway_genes - input_genes_count + overlap_count  # Neither

        # Ensure no negative values
        if d < 0:
            d = 0

        # Fisher's exact test
        contingency_table = [[a, b], [c, d]]
        oddsratio, p_value = fisher_exact(contingency_table, alternative='greater')

        # Calculate fold enrichment
        expected = (input_genes_count * pathway_genes) / total_genes if total_genes > 0 else 0
        fold_enrichment = overlap_count / expected if expected > 0 else 0

        return {
            "p_value": float(p_value),
            "fold_enrichment": round(float(fold_enrichment), 3),
            "odds_ratio": round(float(oddsratio), 3)
        }

    except ImportError:
        # Fallback if scipy not available - use hypergeometric approximation
        import math

        # Simple hypergeometric p-value approximation
        expected = (input_genes_count * pathway_genes) / total_genes if total_genes > 0 else 0
        fold_enrichment = overlap_count / expected if expected > 0 else 0

        # Rough p-value estimate (not as accurate as Fisher's)
        if overlap_count > expected:
            p_value = 1.0 / (fold_enrichment + 1)
        else:
            p_value = 1.0

        return {
            "p_value": round(p_value, 4),
            "fold_enrichment": round(fold_enrichment, 3),
            "odds_ratio": round(fold_enrichment, 3),
            "note": "Approximation used (install scipy for accurate statistics)"
        }

    except Exception as e:
        # Complete fallback
        return {
            "p_value": 1.0,
            "fold_enrichment": 1.0,
            "odds_ratio": 1.0,
            "note": f"Statistical calculation failed: {str(e)}"
        }


def _apply_pathway_ordering(
    results: List[Dict[str, Any]],
    order_by: Optional[str],
    order_direction: OrderDirection
) -> List[Dict[str, Any]]:
    """
    Apply sorting to pathway results.

    Args:
        results: List of pathway result dictionaries
        order_by: Field to sort by
        order_direction: Direction (asc/desc)

    Returns:
        Sorted results
    """
    if not order_by or not results:
        return results

    # Validate order_by column exists
    if order_by not in results[0]:
        raise ValueError(
            f"Cannot order by '{order_by}'. Available columns: {list(results[0].keys())}"
        )

    # Sort
    reverse = (order_direction == OrderDirection.desc)
    try:
        sorted_results = sorted(
            results, 
            key=lambda x: x.get(order_by, 0) if x.get(order_by) is not None else 0, 
            reverse=reverse
        )
        return sorted_results
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sort by '{order_by}': {str(e)}"
        )


# ==========================================
# ANALYSIS IMPLEMENTATIONS
# ==========================================

async def _perform_enrichment_analysis(
    db,
    table_name: str,
    request: PathwayEnrichmentRequest
) -> PathwayEnrichmentResponse:
    """
    Perform pathway enrichment analysis on a gene list.

    This identifies which pathways are significantly enriched in the input gene list.
    Uses Fisher's exact test for statistical significance.
    """
    try:
        # Import models
        from app.models import Pathway, Genelist, pathway_gene_association

        # Get mutated genes from dataset (for background)
        background_genes = _get_mutated_genes_from_dataset(db, table_name, request.filters)
        total_genes_in_dataset = len(background_genes)

        # Input genes
        input_genes = set(request.gene_list)
        input_genes_count = len(input_genes)

        # Query all pathways with their genes
        query = db.query(
            Pathway.id,
            Pathway.pathway_name,
            func.count(pathway_gene_association.c.gene).label('pathway_gene_count'),
            func.group_concat(pathway_gene_association.c.gene).label('pathway_genes')
        ).join(
            pathway_gene_association,
            Pathway.id == pathway_gene_association.c.pathway_id
        ).group_by(
            Pathway.id,
            Pathway.pathway_name
        )

        # Apply pathway name filter if specified
        if request.pathway_name_contains:
            query = query.filter(
                Pathway.pathway_name.ilike(f"%{request.pathway_name_contains}%")
            )

        # Execute query
        pathways = query.all()

        # Calculate enrichment for each pathway
        enriched_pathways = []

        for pathway in pathways:
            pathway_id = pathway.id
            pathway_name = pathway.pathway_name
            pathway_gene_count = pathway.pathway_gene_count

            # Parse pathway genes (SQLite group_concat returns comma-separated string)
            pathway_genes_str = pathway.pathway_genes or ""
            pathway_genes = set(pathway_genes_str.split(',')) if pathway_genes_str else set()

            # Calculate overlap with input genes
            overlap = input_genes.intersection(pathway_genes)
            overlap_count = len(overlap)

            # Skip pathways below minimum gene threshold
            if overlap_count < request.min_genes:
                continue

            # Calculate enrichment statistics
            stats = _calculate_enrichment_statistics(
                total_genes=total_genes_in_dataset,
                pathway_genes=pathway_gene_count,
                input_genes_count=input_genes_count,
                overlap_count=overlap_count
            )

            # Filter by p-value threshold
            if stats["p_value"] <= request.p_value_threshold:
                enriched_pathways.append({
                    "pathway_id": pathway_id,
                    "pathway_name": pathway_name,
                    "total_genes_in_pathway": pathway_gene_count,
                    "genes_in_input": overlap_count,
                    "overlapping_genes": sorted(list(overlap)),
                    "p_value": stats["p_value"],
                    "fold_enrichment": stats["fold_enrichment"],
                    "odds_ratio": stats.get("odds_ratio", stats["fold_enrichment"])
                })

        # Apply ordering
        if request.order_by:
            enriched_pathways = _apply_pathway_ordering(
                enriched_pathways,
                request.order_by,
                request.order_direction
            )

        # Apply limit
        if request.limit:
            enriched_pathways = enriched_pathways[:request.limit]

        return PathwayEnrichmentResponse(
            dataset=table_name,
            analysis_type=request.analysis_type.value,
            total_pathways=len(enriched_pathways),
            total_genes=total_genes_in_dataset,
            input_genes=input_genes_count,
            order_by=request.order_by,
            order_direction=request.order_direction.value if request.order_direction else None,
            limit=request.limit,
            result=enriched_pathways
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Enrichment analysis failed: {str(e)}"
        )


async def _get_pathway_genes(
    db,
    request: PathwayEnrichmentRequest
) -> PathwayEnrichmentResponse:
    """
    Get all genes in a specific pathway.
    """
    try:
        from app.models import Pathway, Genelist, pathway_gene_association

        # Query the pathway and its genes
        pathway = db.query(Pathway).filter(Pathway.id == request.pathway_id).first()

        if not pathway:
            raise HTTPException(
                status_code=404,
                detail=f"Pathway '{request.pathway_id}' not found"
            )

        # Get genes associated with this pathway
        genes_query = db.query(
            pathway_gene_association.c.gene
        ).filter(
            pathway_gene_association.c.pathway_id == request.pathway_id
        )

        gene_results = genes_query.all()
        genes = [{"gene_symbol": row.gene} for row in gene_results]

        # Apply ordering
        if request.order_by:
            genes = _apply_pathway_ordering(
                genes,
                request.order_by,
                request.order_direction
            )

        # Apply limit
        if request.limit:
            genes = genes[:request.limit]

        return PathwayEnrichmentResponse(
            dataset="N/A",
            analysis_type=request.analysis_type.value,
            total_pathways=1,
            total_genes=len(genes),
            order_by=request.order_by,
            order_direction=request.order_direction.value if request.order_direction else None,
            limit=request.limit,
            result=genes
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve pathway genes: {str(e)}"
        )


async def _get_gene_pathways(
    db,
    request: PathwayEnrichmentRequest
) -> PathwayEnrichmentResponse:
    """
    Get all pathways for specific genes.
    """
    try:
        from app.models import Pathway, Genelist, pathway_gene_association

        # Query pathways for the gene list
        query = db.query(
            pathway_gene_association.c.gene,
            Pathway.id,
            Pathway.pathway_name
        ).join(
            Pathway,
            pathway_gene_association.c.pathway_id == Pathway.id
        ).filter(
            pathway_gene_association.c.gene.in_(request.gene_list)
        )

        # Apply pathway name filter if specified
        if request.pathway_name_contains:
            query = query.filter(
                Pathway.pathway_name.ilike(f"%{request.pathway_name_contains}%")
            )

        results = query.all()

        pathways = [
            {
                "gene_symbol": row.gene,
                "pathway_id": row.id,
                "pathway_name": row.pathway_name
            }
            for row in results
        ]

        # Apply ordering
        if request.order_by:
            pathways = _apply_pathway_ordering(
                pathways,
                request.order_by,
                request.order_direction
            )

        # Apply limit
        if request.limit:
            pathways = pathways[:request.limit]

        return PathwayEnrichmentResponse(
            dataset="N/A",
            analysis_type=request.analysis_type.value,
            total_pathways=len(set(p["pathway_id"] for p in pathways)),
            total_genes=len(set(p["gene_symbol"] for p in pathways)),
            input_genes=len(request.gene_list),
            order_by=request.order_by,
            order_direction=request.order_direction.value if request.order_direction else None,
            limit=request.limit,
            result=pathways
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve gene pathways: {str(e)}"
        )


# ==========================================
# MAIN API FUNCTION
# ==========================================

async def pathway_enrichment_analyzer(
    request: PathwayEnrichmentRequest,
    table_name: str,
    db
) -> PathwayEnrichmentResponse:
    """
    Main pathway enrichment analysis endpoint.

    Supports three analysis types:
    1. enrichment: Find enriched pathways in a gene list
    2. pathway_genes: Get genes in a specific pathway
    3. gene_pathways: Get pathways for specific genes

    Args:
        request: PathwayEnrichmentRequest with analysis parameters
        table_name: Dataset table name (for enrichment analysis)
        db: Database session

    Returns:
        PathwayEnrichmentResponse with analysis results

    Example Requests:
    -----------------

    1. Enrichment Analysis:
    {
      "dataset": "nibmg_exome_somatic",
      "analysis_type": "enrichment",
      "gene_list": ["TP53", "BRCA1", "KRAS", "PIK3CA", "PTEN"],
      "min_genes": 2,
      "p_value_threshold": 0.05,
      "filters": {
        "logic": "AND",
        "conditions": [
          {"column": "variant_classification", "operator": "in", 
           "value": ["Missense_Mutation", "Nonsense_Mutation"]}
        ]
      },
      "order_by": "p_value",
      "order_direction": "asc",
      "limit": 10
    }

    2. Get Pathway Genes:
    {
      "analysis_type": "pathway_genes",
      "pathway_id": "hsa05200",
      "limit": 50
    }

    3. Get Gene Pathways:
    {
      "analysis_type": "gene_pathways",
      "gene_list": ["TP53", "BRCA1", "KRAS"],
      "pathway_name_contains": "cancer"
    }
    """

    try:
        # Route to appropriate analysis
        if request.analysis_type == AnalysisType.enrichment:
            return await _perform_enrichment_analysis(db, table_name, request)

        elif request.analysis_type == AnalysisType.pathway_genes:
            return await _get_pathway_genes(db, request)

        elif request.analysis_type == AnalysisType.gene_pathways:
            return await _get_gene_pathways(db, request)

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
            detail=f"Pathway analysis failed: {str(e)}"
        )
