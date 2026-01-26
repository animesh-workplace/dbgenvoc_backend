"""
oncoplot_data_retriever.py

Retrieves data formatted for oncoplot/OncoPrint visualizations.
Generates mutation matrix (genes × samples) with alteration annotations.

Author: Generated based on dbGENVOC API patterns
Date: 2026-01-23
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_, distinct
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field, field_validator
from collections import defaultdict
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

class AlterationType(str, Enum):
    """Types of alterations to include"""
    mutation = "mutation"  # All mutations
    missense = "missense"  # Missense mutations only
    truncating = "truncating"  # Truncating mutations (nonsense, frameshift)
    inframe = "inframe"  # Inframe indels
    splice_site = "splice_site"  # Splice site mutations
    all = "all"  # All alteration types


class SampleSortOrder(str, Enum):
    """Sample sorting methods"""
    mutation_count = "mutation_count"  # By total mutations
    alphabetical = "alphabetical"  # Alphabetical by sample ID
    clinical_annotation = "clinical_annotation"  # By clinical variable
    custom = "custom"  # Custom order provided


class GeneSortOrder(str, Enum):
    """Gene sorting methods"""
    mutation_frequency = "mutation_frequency"  # By mutation frequency
    alphabetical = "alphabetical"  # Alphabetical
    custom = "custom"  # Custom order provided


class OncoplotRequest(BaseModel):
    """Request model for oncoplot data retrieval"""

    # Dataset to query
    dataset: str = Field(
        ...,
        description="Dataset name (e.g., 'nibmg_exome_somatic', 'tcga_exome_somatic')"
    )

    # Genes to include
    genes: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Gene symbols to include in oncoplot (1-100 genes)"
    )

    # Sample filters
    sample_ids: Optional[List[str]] = Field(
        None,
        description="Specific sample IDs to include (if None, includes all)"
    )

    # Alteration type
    alteration_types: List[AlterationType] = Field(
        [AlterationType.all],
        description="Types of alterations to include"
    )

    # Sorting
    gene_sort_order: GeneSortOrder = Field(
        GeneSortOrder.mutation_frequency,
        description="How to sort genes"
    )

    sample_sort_order: SampleSortOrder = Field(
        SampleSortOrder.mutation_count,
        description="How to sort samples"
    )

    custom_gene_order: Optional[List[str]] = Field(
        None,
        description="Custom gene order (for gene_sort_order='custom')"
    )

    custom_sample_order: Optional[List[str]] = Field(
        None,
        description="Custom sample order (for sample_sort_order='custom')"
    )

    # Clinical annotation
    clinical_annotation: Optional[str] = Field(
        None,
        description="Clinical variable for annotation track (e.g., 'cancer_type', 'stage')"
    )

    # Additional filters
    filters: Optional[ComplexFilter] = Field(
        None,
        description="Complex filters with AND/OR logic"
    )

    # Include mutation details
    include_mutation_details: bool = Field(
        False,
        description="Include detailed mutation information in response"
    )

    # Limits
    max_samples: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="Maximum number of samples to include"
    )

    @field_validator("custom_gene_order")
    @classmethod
    def validate_custom_gene_order(cls, v, info):
        """Validate custom gene order matches genes"""
        if v is not None:
            genes = info.data.get("genes", [])
            gene_sort = info.data.get("gene_sort_order")

            if gene_sort == GeneSortOrder.custom and set(v) != set(genes):
                raise ValueError("custom_gene_order must contain exactly the same genes as 'genes'")
        return v


class OncoplotResponse(BaseModel):
    """Response model for oncoplot data"""

    dataset: str
    total_genes: int
    total_samples: int
    total_alterations: int

    # Matrix dimensions
    genes: List[str]  # Ordered list of genes
    samples: List[str]  # Ordered list of samples

    # Mutation matrix (genes × samples)
    # Each cell contains alteration type(s)
    alteration_matrix: Dict[str, Dict[str, List[str]]]  # gene -> sample -> [alteration_types]

    # Summary statistics
    gene_alteration_frequency: Dict[str, float]  # gene -> frequency
    sample_alteration_count: Dict[str, int]  # sample -> count

    # Clinical annotation track (optional)
    clinical_annotation: Optional[Dict[str, Any]] = None

    # Detailed mutations (optional)
    mutation_details: Optional[List[Dict[str, Any]]] = None


# ==========================================
# INTERNAL HELPERS
# ==========================================

def _classify_alteration_type(mutation: Any) -> str:
    """
    Classify mutation into alteration category.

    Args:
        mutation: Mutation object

    Returns:
        Alteration type string
    """
    variant_class = getattr(mutation, 'variant_classification', None)

    if not variant_class:
        return 'mutation'

    # Truncating mutations
    truncating = [
        'Nonsense_Mutation',
        'Frame_Shift_Del',
        'Frame_Shift_Ins',
        'Frameshift_Deletion',
        'Frameshift_Insertion',
        'Splice_Site'
    ]

    # Inframe mutations
    inframe = [
        'In_Frame_Del',
        'In_Frame_Ins'
    ]

    # Missense
    if variant_class == 'Missense_Mutation':
        return 'missense'
    elif variant_class in truncating:
        return 'truncating'
    elif variant_class in inframe:
        return 'inframe'
    elif 'Splice' in variant_class:
        return 'splice_site'
    else:
        return 'mutation'


def _filter_by_alteration_type(
    mutations: List[Any],
    alteration_types: List[AlterationType]
) -> List[Any]:
    """
    Filter mutations by alteration type.

    Args:
        mutations: List of mutation objects
        alteration_types: List of alteration types to include

    Returns:
        Filtered mutation list
    """
    if AlterationType.all in alteration_types:
        return mutations

    filtered = []
    for mutation in mutations:
        alt_type = _classify_alteration_type(mutation)

        # Check if this alteration type is requested
        if any(alt_type == at.value for at in alteration_types if at != AlterationType.all):
            filtered.append(mutation)

    return filtered


def _get_clinical_annotations(
    db,
    model_class,
    sample_ids: List[str],
    annotation_column: str
) -> Dict[str, Any]:
    """
    Get clinical annotations for samples.

    Args:
        db: Database session
        model_class: Model class
        sample_ids: List of sample IDs
        annotation_column: Column name for annotation

    Returns:
        Dictionary mapping sample to annotation value
    """
    try:
        if not hasattr(model_class, annotation_column):
            return {}

        # Get sample column name
        sample_col_name = None
        for col in ['tumor_sample_barcode', 'sample_id', 'sample']:
            if hasattr(model_class, col):
                sample_col_name = col
                break

        if not sample_col_name:
            return {}

        sample_col = getattr(model_class, sample_col_name)
        annotation_col = getattr(model_class, annotation_column)

        # Query annotations
        results = db.query(
            sample_col,
            annotation_col
        ).filter(
            sample_col.in_(sample_ids)
        ).distinct().all()

        # Build dictionary
        annotations = {}
        for row in results:
            sample = row[0]
            value = row[1]
            if sample and value:
                annotations[sample] = value

        return annotations

    except Exception:
        return {}


# ==========================================
# MAIN API FUNCTION
# ==========================================

async def oncoplot_data_retriever(
    request: OncoplotRequest,
    table_name: str,
    db
) -> OncoplotResponse:
    """
    Retrieve data formatted for oncoplot/OncoPrint visualization.

    Generates a mutation matrix (genes × samples) with alteration types,
    suitable for visualization in oncoplot/OncoPrint format.

    Args:
        request: OncoplotRequest with query parameters
        table_name: Dataset table name
        db: Database session

    Returns:
        OncoplotResponse with oncoplot data

    Example Requests:
    -----------------

    1. Basic Oncoplot for Top Cancer Genes:
    {
      "dataset": "tcga_exome_somatic",
      "genes": ["TP53", "KRAS", "PIK3CA", "PTEN", "EGFR", "BRAF"],
      "alteration_types": ["all"],
      "gene_sort_order": "mutation_frequency",
      "sample_sort_order": "mutation_count",
      "max_samples": 100
    }

    2. Oncoplot with Clinical Annotation:
    {
      "dataset": "tcga_exome_somatic",
      "genes": ["TP53", "BRCA1", "BRCA2", "ATM", "CHEK2"],
      "clinical_annotation": "cancer_type",
      "gene_sort_order": "alphabetical",
      "sample_sort_order": "clinical_annotation"
    }

    3. Truncating Mutations Only:
    {
      "dataset": "nibmg_exome_somatic",
      "genes": ["TP53", "APC", "BRCA1", "PTEN"],
      "alteration_types": ["truncating", "splice_site"],
      "include_mutation_details": true
    }

    4. Custom Gene/Sample Order:
    {
      "dataset": "tcga_exome_somatic",
      "genes": ["TP53", "KRAS", "EGFR"],
      "gene_sort_order": "custom",
      "custom_gene_order": ["TP53", "KRAS", "EGFR"],
      "sample_ids": ["TCGA-A1-A0SB", "TCGA-A1-A0SD", "TCGA-A1-A0SE"]
    }

    Response Format:
    ----------------
    {
      "dataset": "tcga_exome_somatic",
      "total_genes": 6,
      "total_samples": 523,
      "total_alterations": 1547,
      "genes": ["TP53", "KRAS", "PIK3CA", "PTEN", "EGFR", "BRAF"],
      "samples": ["TCGA-A1-A0SB", "TCGA-A1-A0SD", ...],
      "alteration_matrix": {
        "TP53": {
          "TCGA-A1-A0SB": ["missense"],
          "TCGA-A1-A0SD": ["truncating"],
          ...
        },
        "KRAS": {
          "TCGA-A1-A0SB": ["missense"],
          ...
        }
      },
      "gene_alteration_frequency": {
        "TP53": 0.548,
        "KRAS": 0.298,
        ...
      },
      "sample_alteration_count": {
        "TCGA-A1-A0SB": 3,
        "TCGA-A1-A0SD": 2,
        ...
      }
    }
    """

    try:
        model_class = get_model_class(table_name)

        # Build base query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Filter by genes
        if hasattr(model_class, 'hugo_symbol'):
            query = query.filter(model_class.hugo_symbol.in_(request.genes))
        else:
            raise HTTPException(
                status_code=400,
                detail="Dataset must have 'hugo_symbol' column for oncoplot generation"
            )

        # Filter by samples if specified
        sample_col_name = None
        for col in ['tumor_sample_barcode', 'sample_id', 'sample']:
            if hasattr(model_class, col):
                sample_col_name = col
                break

        if not sample_col_name:
            raise HTTPException(
                status_code=400,
                detail="Dataset must have sample identifier column"
            )

        sample_col = getattr(model_class, sample_col_name)

        if request.sample_ids:
            query = query.filter(sample_col.in_(request.sample_ids))

        # Get all mutations
        mutations = query.all()

        # Filter by alteration type
        mutations = _filter_by_alteration_type(mutations, request.alteration_types)

        # Build alteration matrix
        alteration_matrix = defaultdict(lambda: defaultdict(list))
        all_samples = set()
        gene_mutation_counts = defaultdict(int)
        sample_mutation_counts = defaultdict(int)

        mutation_details_list = []

        for mutation in mutations:
            gene = getattr(mutation, 'hugo_symbol')
            sample = getattr(mutation, sample_col_name)
            alt_type = _classify_alteration_type(mutation)

            if gene and sample:
                # Add to matrix
                if alt_type not in alteration_matrix[gene][sample]:
                    alteration_matrix[gene][sample].append(alt_type)
                    gene_mutation_counts[gene] += 1

                all_samples.add(sample)
                sample_mutation_counts[sample] += 1

                # Store mutation details if requested
                if request.include_mutation_details:
                    mutation_details_list.append({
                        'gene': gene,
                        'sample': sample,
                        'alteration_type': alt_type,
                        'variant_classification': getattr(mutation, 'variant_classification', None),
                        'protein_change': getattr(mutation, 'hgvsp_short', 
                                                 getattr(mutation, 'protein_change', None)),
                        'chromosome': getattr(mutation, 'chrom', 
                                            getattr(mutation, 'chromosome', None)),
                        'position': getattr(mutation, 'start', 
                                          getattr(mutation, 'start_position', None))
                    })

        # Get all samples (including those with no mutations in selected genes)
        if not request.sample_ids:
            # Query all samples in dataset
            all_samples_query = db.query(distinct(sample_col))
            if request.filters:
                all_samples_query = apply_filters(all_samples_query, model_class, request.filters)
            all_samples_result = all_samples_query.all()
            all_samples = set(row[0] for row in all_samples_result if row[0])

        all_samples = list(all_samples)

        # Apply max_samples limit
        if request.max_samples and len(all_samples) > request.max_samples:
            # Sort by mutation count and take top N
            sorted_samples = sorted(
                all_samples,
                key=lambda s: sample_mutation_counts.get(s, 0),
                reverse=True
            )
            all_samples = sorted_samples[:request.max_samples]

        # Sort genes
        if request.gene_sort_order == GeneSortOrder.mutation_frequency:
            sorted_genes = sorted(
                request.genes,
                key=lambda g: gene_mutation_counts.get(g, 0),
                reverse=True
            )
        elif request.gene_sort_order == GeneSortOrder.alphabetical:
            sorted_genes = sorted(request.genes)
        elif request.gene_sort_order == GeneSortOrder.custom:
            sorted_genes = request.custom_gene_order or request.genes
        else:
            sorted_genes = request.genes

        # Sort samples
        if request.sample_sort_order == SampleSortOrder.mutation_count:
            sorted_samples = sorted(
                all_samples,
                key=lambda s: sample_mutation_counts.get(s, 0),
                reverse=True
            )
        elif request.sample_sort_order == SampleSortOrder.alphabetical:
            sorted_samples = sorted(all_samples)
        elif request.sample_sort_order == SampleSortOrder.custom:
            sorted_samples = request.custom_sample_order or all_samples
        else:
            sorted_samples = all_samples

        # Calculate gene alteration frequencies
        total_samples = len(all_samples)
        gene_alteration_frequency = {
            gene: gene_mutation_counts.get(gene, 0) / total_samples if total_samples > 0 else 0
            for gene in sorted_genes
        }

        # Get clinical annotations if requested
        clinical_annotation_data = None
        if request.clinical_annotation:
            clinical_annotation_data = _get_clinical_annotations(
                db,
                model_class,
                all_samples,
                request.clinical_annotation
            )

            # Sort by clinical annotation if requested
            if request.sample_sort_order == SampleSortOrder.clinical_annotation and clinical_annotation_data:
                sorted_samples = sorted(
                    all_samples,
                    key=lambda s: clinical_annotation_data.get(s, '')
                )

        # Convert alteration_matrix to regular dict for JSON serialization
        alteration_matrix_dict = {
            gene: dict(alteration_matrix[gene])
            for gene in sorted_genes
        }

        return OncoplotResponse(
            dataset=request.dataset,
            total_genes=len(sorted_genes),
            total_samples=len(sorted_samples),
            total_alterations=len(mutations),
            genes=sorted_genes,
            samples=sorted_samples,
            alteration_matrix=alteration_matrix_dict,
            gene_alteration_frequency=gene_alteration_frequency,
            sample_alteration_count=dict(sample_mutation_counts),
            clinical_annotation=clinical_annotation_data,
            mutation_details=mutation_details_list if request.include_mutation_details else None
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Oncoplot data retrieval failed: {str(e)}"
        )


# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def format_for_complexheatmap(response: OncoplotResponse) -> Dict[str, Any]:
    """
    Format oncoplot data for R ComplexHeatmap package.

    Args:
        response: OncoplotResponse object

    Returns:
        Dictionary formatted for ComplexHeatmap
    """
    # Create alteration matrix in wide format
    matrix = []
    for sample in response.samples:
        row = []
        for gene in response.genes:
            alterations = response.alteration_matrix.get(gene, {}).get(sample, [])
            if alterations:
                # Combine multiple alteration types
                row.append(';'.join(alterations))
            else:
                row.append('')
        matrix.append(row)

    return {
        'genes': response.genes,
        'samples': response.samples,
        'matrix': matrix,
        'gene_frequencies': response.gene_alteration_frequency,
        'sample_counts': response.sample_alteration_count,
        'clinical_annotation': response.clinical_annotation
    }


def format_for_maftools(response: OncoplotResponse) -> List[Dict[str, Any]]:
    """
    Format oncoplot data for maftools (R package).

    Args:
        response: OncoplotResponse object

    Returns:
        List of mutation records
    """
    records = []

    for gene in response.genes:
        for sample in response.samples:
            alterations = response.alteration_matrix.get(gene, {}).get(sample, [])
            if alterations:
                for alt_type in alterations:
                    records.append({
                        'Hugo_Symbol': gene,
                        'Tumor_Sample_Barcode': sample,
                        'Variant_Classification': alt_type,
                        'Variant_Type': 'SNP'  # Simplified
                    })

    return records


# ==========================================
# EXAMPLE USAGE
# ==========================================

"""
Example Integration in FastAPI Router:
---------------------------------------

from oncoplot_data_retriever import (
    oncoplot_data_retriever,
    OncoplotRequest,
    OncoplotResponse,
    format_for_complexheatmap,
    format_for_maftools
)

@router.post("/oncoplot_data_retriever", response_model=OncoplotResponse)
async def retrieve_oncoplot_data(
    table_name: str,
    request: OncoplotRequest,
    db: Session = Depends(get_db)
):
    return await oncoplot_data_retriever(request, table_name, db)


@router.post("/oncoplot_data_retriever/complexheatmap")
async def get_complexheatmap_format(
    table_name: str,
    request: OncoplotRequest,
    db: Session = Depends(get_db)
):
    response = await oncoplot_data_retriever(request, table_name, db)
    return format_for_complexheatmap(response)


Visualization Examples:
-----------------------

1. Using JavaScript (D3.js or custom):
   - Parse alteration_matrix
   - Create SVG/Canvas grid
   - Color cells by alteration type
   - Add frequency bars

2. Using Python (matplotlib/seaborn):
   import matplotlib.pyplot as plt
   import seaborn as sns

   # Create binary matrix
   matrix = []
   for sample in samples:
       row = []
       for gene in genes:
           has_mutation = len(alteration_matrix[gene].get(sample, [])) > 0
           row.append(1 if has_mutation else 0)
       matrix.append(row)

   # Plot
   sns.heatmap(matrix, cmap='RdBu_r', cbar=False)

3. Using R (ComplexHeatmap):
   library(ComplexHeatmap)

   mat = read.csv("matrix.csv", row.names=1)
   oncoPrint(mat, alter_fun = list(...))
"""
