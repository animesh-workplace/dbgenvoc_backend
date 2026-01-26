"""
cross_dataset_comparator.py

Compares mutation data across multiple datasets to identify unique mutations,
shared mutations, differential mutation rates, and enrichment patterns.

Author: Generated based on dbGENVOC API patterns
Date: 2026-01-23
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_, distinct
from typing import Any, Dict, List, Optional, Set, Tuple
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

class ComparisonType(str, Enum):
    """Types of dataset comparison"""
    mutation_frequency = "mutation_frequency"  # Compare mutation frequencies
    gene_mutation_rate = "gene_mutation_rate"  # Compare gene-level mutation rates
    variant_overlap = "variant_overlap"  # Find shared/unique variants
    sample_comparison = "sample_comparison"  # Compare sample-level statistics
    hotspot_comparison = "hotspot_comparison"  # Compare mutation hotspots


class StatisticalTest(str, Enum):
    """Statistical tests for comparison"""
    fisher_exact = "fisher_exact"  # Fisher's exact test
    chi_square = "chi_square"  # Chi-square test
    none = "none"  # No statistical test


class OrderDirection(str, Enum):
    """Sort order"""
    asc = "asc"
    desc = "desc"


class DatasetConfig(BaseModel):
    """Configuration for a single dataset"""

    dataset: str = Field(
        ...,
        description="Dataset name (e.g., 'nibmg_exome_somatic', 'tcga_exome_somatic')"
    )

    label: Optional[str] = Field(
        None,
        description="Human-readable label for this dataset (defaults to dataset name)"
    )

    filters: Optional[ComplexFilter] = Field(
        None,
        description="Filters to apply to this dataset"
    )


class CrossDatasetRequest(BaseModel):
    """Request model for cross-dataset comparison"""

    # Datasets to compare
    datasets: List[DatasetConfig] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="List of datasets to compare (2-10 datasets)"
    )

    # Comparison type
    comparison_type: ComparisonType = Field(
        ComparisonType.mutation_frequency,
        description="Type of comparison to perform"
    )

    # Gene filter (optional)
    genes: Optional[List[str]] = Field(
        None,
        description="Limit comparison to specific genes"
    )

    # Variant classification filter
    variant_classifications: Optional[List[str]] = Field(
        None,
        description="Filter by variant classifications"
    )

    # Statistical testing
    statistical_test: StatisticalTest = Field(
        StatisticalTest.fisher_exact,
        description="Statistical test to apply"
    )

    p_value_threshold: float = Field(
        0.05,
        gt=0,
        le=1,
        description="P-value threshold for significance"
    )

    # Overlap analysis parameters
    min_datasets: int = Field(
        2,
        ge=1,
        description="Minimum number of datasets a variant must appear in (for overlap analysis)"
    )

    # Ordering and limiting
    order_by: Optional[str] = Field(
        None,
        description="Column to order by (e.g., 'p_value', 'mutation_count', 'frequency_difference')"
    )

    order_direction: OrderDirection = Field(
        OrderDirection.asc,
        description="Sort direction"
    )

    limit: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="Limit number of results"
    )

    @field_validator("datasets")
    @classmethod
    def validate_datasets(cls, v):
        """Validate datasets list"""
        if len(v) < 2:
            raise ValueError("At least 2 datasets are required for comparison")
        if len(v) > 10:
            raise ValueError("Maximum 10 datasets allowed for comparison")

        # Check for duplicate dataset names
        dataset_names = [d.dataset for d in v]
        if len(dataset_names) != len(set(dataset_names)):
            raise ValueError("Duplicate dataset names found")

        return v

    @field_validator("min_datasets")
    @classmethod
    def validate_min_datasets(cls, v, info):
        """Validate min_datasets"""
        datasets = info.data.get("datasets", [])
        if v > len(datasets):
            raise ValueError("min_datasets cannot exceed number of datasets")
        return v


class CrossDatasetResponse(BaseModel):
    """Response model for cross-dataset comparison"""

    comparison_type: str
    datasets: List[str]
    total_results: int

    # Statistical info
    statistical_test: Optional[str] = None
    p_value_threshold: Optional[float] = None

    # Ordering info
    order_by: Optional[str] = None
    order_direction: Optional[str] = None
    limit: Optional[int] = None

    # Summary statistics per dataset
    dataset_summaries: Dict[str, Dict[str, Any]]

    # Results
    result: List[Dict[str, Any]]


# ==========================================
# INTERNAL HELPERS
# ==========================================

def _get_dataset_label(config: DatasetConfig) -> str:
    """Get label for dataset (use provided label or dataset name)."""
    return config.label if config.label else config.dataset


def _calculate_fisher_exact(
    dataset1_mutated: int,
    dataset1_total: int,
    dataset2_mutated: int,
    dataset2_total: int
) -> Dict[str, float]:
    """
    Calculate Fisher's exact test for 2x2 contingency table.

    Args:
        dataset1_mutated: Mutated samples in dataset 1
        dataset1_total: Total samples in dataset 1
        dataset2_mutated: Mutated samples in dataset 2
        dataset2_total: Total samples in dataset 2

    Returns:
        Dictionary with odds_ratio and p_value
    """
    try:
        from scipy.stats import fisher_exact

        # Build contingency table
        dataset1_wild = dataset1_total - dataset1_mutated
        dataset2_wild = dataset2_total - dataset2_mutated

        table = [
            [dataset1_mutated, dataset1_wild],
            [dataset2_mutated, dataset2_wild]
        ]

        odds_ratio, p_value = fisher_exact(table)

        return {
            "odds_ratio": round(float(odds_ratio), 4),
            "p_value": float(p_value)
        }

    except ImportError:
        # Fallback if scipy not available
        return {
            "odds_ratio": 1.0,
            "p_value": 1.0,
            "note": "scipy not available for statistical testing"
        }
    except Exception as e:
        return {
            "odds_ratio": 1.0,
            "p_value": 1.0,
            "error": str(e)
        }


def _calculate_chi_square(observed_counts: List[int], expected_counts: List[int]) -> float:
    """
    Calculate chi-square statistic.

    Args:
        observed_counts: Observed counts for each category
        expected_counts: Expected counts for each category

    Returns:
        P-value
    """
    try:
        from scipy.stats import chisquare

        stat, p_value = chisquare(observed_counts, expected_counts)
        return float(p_value)

    except ImportError:
        return 1.0
    except Exception:
        return 1.0


def _get_dataset_mutations(
    db,
    config: DatasetConfig,
    genes: Optional[List[str]] = None,
    variant_classifications: Optional[List[str]] = None
) -> Tuple[List[Any], int, Set[str]]:
    """
    Get mutations and metadata for a dataset.

    Args:
        db: Database session
        config: Dataset configuration
        genes: Optional gene filter
        variant_classifications: Optional variant classification filter

    Returns:
        Tuple of (mutations, total_samples, unique_genes)
    """
    try:
        model_class = get_model_class(config.dataset)

        # Build query
        query = db.query(model_class)

        # Apply dataset-specific filters
        if config.filters:
            query = apply_filters(query, model_class, config.filters)

        # Apply gene filter
        if genes and hasattr(model_class, 'hugo_symbol'):
            query = query.filter(model_class.hugo_symbol.in_(genes))

        # Apply variant classification filter
        if variant_classifications and hasattr(model_class, 'variant_classification'):
            query = query.filter(model_class.variant_classification.in_(variant_classifications))

        # Get mutations
        mutations = query.all()

        # Get total samples
        if hasattr(model_class, 'tumor_sample_barcode'):
            total_samples = db.query(
                func.count(distinct(model_class.tumor_sample_barcode))
            ).filter(query.whereclause if hasattr(query, 'whereclause') else True).scalar() or 0
        else:
            total_samples = len(mutations)

        # Get unique genes
        unique_genes = set()
        if hasattr(model_class, 'hugo_symbol'):
            for m in mutations:
                if m.hugo_symbol:
                    unique_genes.add(m.hugo_symbol)

        return mutations, total_samples, unique_genes

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query dataset '{config.dataset}': {str(e)}"
        )


# ==========================================
# COMPARISON IMPLEMENTATIONS
# ==========================================

async def _compare_mutation_frequency(
    db,
    request: CrossDatasetRequest
) -> CrossDatasetResponse:
    """
    Compare mutation frequencies across datasets.

    Calculates mutation frequency per gene and compares across datasets.
    """
    dataset_data = {}
    dataset_summaries = {}

    # Collect data from each dataset
    for config in request.datasets:
        mutations, total_samples, unique_genes = _get_dataset_mutations(
            db, config, request.genes, request.variant_classifications
        )

        label = _get_dataset_label(config)

        # Calculate gene-level statistics
        gene_counts = {}
        for mutation in mutations:
            gene = getattr(mutation, 'hugo_symbol', None)
            if gene:
                gene_counts[gene] = gene_counts.get(gene, 0) + 1

        dataset_data[label] = {
            'mutations': mutations,
            'total_samples': total_samples,
            'gene_counts': gene_counts,
            'unique_genes': unique_genes
        }

        dataset_summaries[label] = {
            'total_mutations': len(mutations),
            'total_samples': total_samples,
            'unique_genes': len(unique_genes),
            'mutation_rate': round(len(mutations) / total_samples, 4) if total_samples > 0 else 0
        }

    # Get all genes across all datasets
    all_genes = set()
    for data in dataset_data.values():
        all_genes.update(data['unique_genes'])

    # Compare frequencies
    comparison_results = []

    for gene in all_genes:
        gene_result = {'gene': gene}

        # Collect counts for each dataset
        for label, data in dataset_data.items():
            count = data['gene_counts'].get(gene, 0)
            total = data['total_samples']
            frequency = count / total if total > 0 else 0

            gene_result[f'{label}_count'] = count
            gene_result[f'{label}_frequency'] = round(frequency, 4)

        # Statistical comparison (pairwise for first two datasets)
        if len(request.datasets) >= 2 and request.statistical_test != StatisticalTest.none:
            label1 = _get_dataset_label(request.datasets[0])
            label2 = _get_dataset_label(request.datasets[1])

            count1 = dataset_data[label1]['gene_counts'].get(gene, 0)
            total1 = dataset_data[label1]['total_samples']
            count2 = dataset_data[label2]['gene_counts'].get(gene, 0)
            total2 = dataset_data[label2]['total_samples']

            if request.statistical_test == StatisticalTest.fisher_exact:
                stats = _calculate_fisher_exact(count1, total1, count2, total2)
                gene_result.update(stats)

            # Calculate frequency difference
            freq1 = count1 / total1 if total1 > 0 else 0
            freq2 = count2 / total2 if total2 > 0 else 0
            gene_result['frequency_difference'] = round(abs(freq1 - freq2), 4)

        comparison_results.append(gene_result)

    # Filter by p-value if statistical test was applied
    if request.statistical_test != StatisticalTest.none and request.p_value_threshold:
        comparison_results = [
            r for r in comparison_results 
            if r.get('p_value', 1.0) <= request.p_value_threshold
        ]

    # Sort results
    if request.order_by:
        reverse = (request.order_direction == OrderDirection.desc)
        comparison_results = sorted(
            comparison_results,
            key=lambda x: x.get(request.order_by, 0) if x.get(request.order_by) is not None else 0,
            reverse=reverse
        )

    # Apply limit
    if request.limit:
        comparison_results = comparison_results[:request.limit]

    return CrossDatasetResponse(
        comparison_type=request.comparison_type.value,
        datasets=[_get_dataset_label(c) for c in request.datasets],
        total_results=len(comparison_results),
        statistical_test=request.statistical_test.value if request.statistical_test != StatisticalTest.none else None,
        p_value_threshold=request.p_value_threshold,
        order_by=request.order_by,
        order_direction=request.order_direction.value,
        limit=request.limit,
        dataset_summaries=dataset_summaries,
        result=comparison_results
    )


async def _analyze_variant_overlap(
    db,
    request: CrossDatasetRequest
) -> CrossDatasetResponse:
    """
    Analyze variant overlap across datasets.

    Identifies variants that are shared across multiple datasets or unique to specific datasets.
    """
    dataset_data = {}
    dataset_summaries = {}

    # Collect variants from each dataset
    for config in request.datasets:
        mutations, total_samples, unique_genes = _get_dataset_mutations(
            db, config, request.genes, request.variant_classifications
        )

        label = _get_dataset_label(config)

        # Create variant keys (chromosome:position:ref:alt or chromosome:position)
        variant_keys = set()
        variant_details = {}

        for mutation in mutations:
            # Try to build unique variant key
            chrom = getattr(mutation, 'chrom', getattr(mutation, 'chromosome', None))
            pos = getattr(mutation, 'start', getattr(mutation, 'start_position', None))
            ref = getattr(mutation, 'reference_allele', None)
            alt = getattr(mutation, 'tumor_seq_allele2', getattr(mutation, 'alternate_allele', None))
            gene = getattr(mutation, 'hugo_symbol', None)

            if chrom and pos:
                if ref and alt:
                    key = f"{chrom}:{pos}:{ref}:{alt}"
                else:
                    key = f"{chrom}:{pos}"

                variant_keys.add(key)
                variant_details[key] = {
                    'chromosome': chrom,
                    'position': pos,
                    'gene': gene,
                    'reference': ref,
                    'alternate': alt
                }

        dataset_data[label] = {
            'variant_keys': variant_keys,
            'variant_details': variant_details,
            'total_samples': total_samples
        }

        dataset_summaries[label] = {
            'total_variants': len(variant_keys),
            'total_samples': total_samples
        }

    # Analyze overlaps
    all_variants = set()
    for data in dataset_data.values():
        all_variants.update(data['variant_keys'])

    overlap_results = []

    for variant_key in all_variants:
        # Count how many datasets have this variant
        datasets_with_variant = []
        for label, data in dataset_data.items():
            if variant_key in data['variant_keys']:
                datasets_with_variant.append(label)

        # Filter by min_datasets
        if len(datasets_with_variant) >= request.min_datasets:
            # Get variant details (from first dataset that has it)
            details = None
            for label in datasets_with_variant:
                if variant_key in dataset_data[label]['variant_details']:
                    details = dataset_data[label]['variant_details'][variant_key]
                    break

            if details:
                overlap_results.append({
                    'variant_key': variant_key,
                    'chromosome': details['chromosome'],
                    'position': details['position'],
                    'gene': details['gene'],
                    'reference_allele': details['reference'],
                    'alternate_allele': details['alternate'],
                    'present_in_datasets': datasets_with_variant,
                    'dataset_count': len(datasets_with_variant),
                    'is_shared': len(datasets_with_variant) > 1,
                    'is_unique': len(datasets_with_variant) == 1
                })

    # Sort results
    if request.order_by:
        reverse = (request.order_direction == OrderDirection.desc)
        overlap_results = sorted(
            overlap_results,
            key=lambda x: x.get(request.order_by, 0) if x.get(request.order_by) is not None else 0,
            reverse=reverse
        )

    # Apply limit
    if request.limit:
        overlap_results = overlap_results[:request.limit]

    return CrossDatasetResponse(
        comparison_type=request.comparison_type.value,
        datasets=[_get_dataset_label(c) for c in request.datasets],
        total_results=len(overlap_results),
        order_by=request.order_by,
        order_direction=request.order_direction.value,
        limit=request.limit,
        dataset_summaries=dataset_summaries,
        result=overlap_results
    )


async def _compare_sample_statistics(
    db,
    request: CrossDatasetRequest
) -> CrossDatasetResponse:
    """
    Compare sample-level statistics across datasets.
    """
    dataset_summaries = {}
    comparison_results = []

    for config in request.datasets:
        mutations, total_samples, unique_genes = _get_dataset_mutations(
            db, config, request.genes, request.variant_classifications
        )

        label = _get_dataset_label(config)

        # Calculate sample-level statistics
        sample_mutation_counts = {}
        for mutation in mutations:
            sample = getattr(mutation, 'tumor_sample_barcode', 
                           getattr(mutation, 'sample_id', 'unknown'))
            sample_mutation_counts[sample] = sample_mutation_counts.get(sample, 0) + 1

        # Calculate statistics
        if sample_mutation_counts:
            counts = list(sample_mutation_counts.values())
            mean_mutations = sum(counts) / len(counts)
            max_mutations = max(counts)
            min_mutations = min(counts)
        else:
            mean_mutations = max_mutations = min_mutations = 0

        dataset_summaries[label] = {
            'total_samples': total_samples,
            'total_mutations': len(mutations),
            'samples_with_mutations': len(sample_mutation_counts),
            'mean_mutations_per_sample': round(mean_mutations, 2),
            'max_mutations_per_sample': max_mutations,
            'min_mutations_per_sample': min_mutations,
            'unique_genes': len(unique_genes)
        }

        comparison_results.append({
            'dataset': label,
            **dataset_summaries[label]
        })

    return CrossDatasetResponse(
        comparison_type=request.comparison_type.value,
        datasets=[_get_dataset_label(c) for c in request.datasets],
        total_results=len(comparison_results),
        dataset_summaries=dataset_summaries,
        result=comparison_results
    )


# ==========================================
# MAIN API FUNCTION
# ==========================================

async def cross_dataset_comparator(
    request: CrossDatasetRequest,
    db
) -> CrossDatasetResponse:
    """
    Compare mutation data across multiple datasets.

    Supports multiple comparison types:
    1. mutation_frequency: Compare mutation frequencies per gene
    2. variant_overlap: Find shared and unique variants
    3. sample_comparison: Compare sample-level statistics

    Args:
        request: CrossDatasetRequest with comparison parameters
        db: Database session

    Returns:
        CrossDatasetResponse with comparison results

    Example Requests:
    -----------------

    1. Compare Mutation Frequencies (TCGA vs NIBMG):
    {
      "datasets": [
        {"dataset": "tcga_exome_somatic", "label": "TCGA"},
        {"dataset": "nibmg_exome_somatic", "label": "NIBMG"}
      ],
      "comparison_type": "mutation_frequency",
      "genes": ["TP53", "BRCA1", "KRAS", "PIK3CA"],
      "statistical_test": "fisher_exact",
      "p_value_threshold": 0.05,
      "order_by": "p_value",
      "order_direction": "asc",
      "limit": 50
    }

    2. Find Shared Variants:
    {
      "datasets": [
        {"dataset": "tcga_exome_somatic", "label": "TCGA"},
        {"dataset": "nibmg_exome_somatic", "label": "NIBMG"},
        {"dataset": "icgc_exome_somatic", "label": "ICGC"}
      ],
      "comparison_type": "variant_overlap",
      "min_datasets": 2,
      "variant_classifications": ["Missense_Mutation", "Nonsense_Mutation"],
      "order_by": "dataset_count",
      "order_direction": "desc"
    }

    3. Compare Sample Statistics:
    {
      "datasets": [
        {"dataset": "tcga_exome_somatic", "label": "TCGA"},
        {"dataset": "nibmg_exome_somatic", "label": "NIBMG"}
      ],
      "comparison_type": "sample_comparison",
      "genes": ["TP53", "KRAS", "EGFR"]
    }

    4. Compare with Filters:
    {
      "datasets": [
        {
          "dataset": "tcga_exome_somatic",
          "label": "TCGA-LUAD",
          "filters": {
            "logic": "AND",
            "conditions": [
              {"column": "cancer_type", "operator": "eq", "value": "LUAD"}
            ]
          }
        },
        {
          "dataset": "tcga_exome_somatic",
          "label": "TCGA-LUSC",
          "filters": {
            "logic": "AND",
            "conditions": [
              {"column": "cancer_type", "operator": "eq", "value": "LUSC"}
            ]
          }
        }
      ],
      "comparison_type": "mutation_frequency",
      "statistical_test": "fisher_exact",
      "order_by": "frequency_difference",
      "order_direction": "desc",
      "limit": 100
    }
    """

    try:
        # Route to appropriate comparison
        if request.comparison_type == ComparisonType.mutation_frequency:
            return await _compare_mutation_frequency(db, request)

        elif request.comparison_type == ComparisonType.variant_overlap:
            return await _analyze_variant_overlap(db, request)

        elif request.comparison_type == ComparisonType.sample_comparison:
            return await _compare_sample_statistics(db, request)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported comparison type: {request.comparison_type}"
            )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cross-dataset comparison failed: {str(e)}"
        )
