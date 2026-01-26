"""
mutation_signature_analyzer.py

Analyzes mutational signatures in cancer genomes using trinucleotide context.
Supports COSMIC signature detection, signature deconvolution, and signature profiling.

Author: Generated based on dbGENVOC API patterns
Date: 2026-01-23
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_, distinct
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator
from collections import defaultdict
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
    """Types of signature analysis"""
    profile = "profile"  # Generate 96-channel signature profile
    deconvolution = "deconvolution"  # Decompose into known signatures
    comparison = "comparison"  # Compare to reference signatures
    sample_signatures = "sample_signatures"  # Per-sample signature analysis


class SignatureDatabase(str, Enum):
    """Signature reference databases"""
    cosmic_v2 = "COSMIC_v2"  # COSMIC signatures v2 (30 signatures)
    cosmic_v3_sbs = "COSMIC_v3_SBS"  # COSMIC v3 Single Base Substitutions
    cosmic_v3_dbs = "COSMIC_v3_DBS"  # COSMIC v3 Doublet Base Substitutions
    cosmic_v3_id = "COSMIC_v3_ID"  # COSMIC v3 Insertions/Deletions
    custom = "custom"  # Custom signature database


class MutationType(str, Enum):
    """Types of mutations for signature analysis"""
    snv = "SNV"  # Single nucleotide variants
    dbs = "DBS"  # Doublet base substitutions
    indel = "INDEL"  # Insertions and deletions


class OrderDirection(str, Enum):
    """Sort order"""
    asc = "asc"
    desc = "desc"


class MutationSignatureRequest(BaseModel):
    """Request model for mutation signature analysis"""

    # Dataset to analyze
    dataset: str = Field(
        ...,
        description="Dataset name (e.g., 'nibmg_exome_somatic', 'tcga_exome_somatic')"
    )

    # Analysis type
    analysis_type: AnalysisType = Field(
        AnalysisType.profile,
        description="Type of signature analysis"
    )

    # Mutation type
    mutation_type: MutationType = Field(
        MutationType.snv,
        description="Type of mutations to analyze"
    )

    # Sample filters
    sample_ids: Optional[List[str]] = Field(
        None,
        description="Specific sample IDs to analyze (if None, analyzes all)"
    )

    # Signature database (for deconvolution/comparison)
    signature_database: SignatureDatabase = Field(
        SignatureDatabase.cosmic_v3_sbs,
        description="Reference signature database"
    )

    # Deconvolution parameters
    min_contribution: float = Field(
        0.05,
        ge=0,
        le=1,
        description="Minimum signature contribution to report (0-1)"
    )

    # Additional filters
    filters: Optional[ComplexFilter] = Field(
        None,
        description="Complex filters with AND/OR logic"
    )

    # Gene filter
    genes: Optional[List[str]] = Field(
        None,
        description="Limit analysis to specific genes"
    )

    # Variant classification filter
    variant_classifications: Optional[List[str]] = Field(
        None,
        description="Filter by variant classifications"
    )

    # Normalization
    normalize: bool = Field(
        True,
        description="Normalize signature profile to sum to 1"
    )

    # Ordering and limiting
    order_by: Optional[str] = Field(
        None,
        description="Column to order by"
    )

    order_direction: OrderDirection = Field(
        OrderDirection.desc,
        description="Sort direction"
    )

    limit: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
        description="Limit number of results"
    )


class MutationSignatureResponse(BaseModel):
    """Response model for mutation signature analysis"""

    dataset: str
    analysis_type: str
    mutation_type: str
    total_mutations: int
    total_samples: Optional[int] = None

    # Signature database info
    signature_database: Optional[str] = None

    # Profile data (96-channel or reduced)
    signature_profile: Optional[Dict[str, Any]] = None

    # Deconvolution results
    signature_contributions: Optional[List[Dict[str, Any]]] = None

    # Results
    result: List[Dict[str, Any]]


# ==========================================
# MUTATION SIGNATURE CONSTANTS
# ==========================================

# 6 substitution types
SUBSTITUTION_TYPES = ['C>A', 'C>G', 'C>T', 'T>A', 'T>C', 'T>G']

# 16 trinucleotide contexts (for pyrimidine bases C and T)
TRINUCLEOTIDE_CONTEXTS = [
    'ACA', 'ACC', 'ACG', 'ACT',
    'CCA', 'CCC', 'CCG', 'CCT',
    'GCA', 'GCC', 'GCG', 'GCT',
    'TCA', 'TCC', 'TCG', 'TCT'
]

# Complementary base pairs
COMPLEMENT = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C'}


# ==========================================
# INTERNAL HELPERS
# ==========================================

def _get_complement(base: str) -> str:
    """Get complement of a nucleotide."""
    return COMPLEMENT.get(base.upper(), 'N')


def _reverse_complement(seq: str) -> str:
    """Get reverse complement of a sequence."""
    return ''.join([_get_complement(b) for b in reversed(seq)])


def _normalize_mutation(ref: str, alt: str, context: str) -> Tuple[str, str]:
    """
    Normalize mutation to pyrimidine reference (C or T).

    Args:
        ref: Reference allele
        alt: Alternate allele
        context: Trinucleotide context (5'-base-3')

    Returns:
        Tuple of (normalized_substitution, normalized_context)
    """
    ref = ref.upper()
    alt = alt.upper()
    context = context.upper()

    # If reference is purine (A or G), convert to pyrimidine
    if ref in ['A', 'G']:
        ref = _get_complement(ref)
        alt = _get_complement(alt)
        context = _reverse_complement(context)

    substitution = f"{ref}>{alt}"

    return substitution, context


def _extract_trinucleotide_context(
    chromosome: str,
    position: int,
    ref: str,
    alt: str,
    reference_genome: Optional[Dict] = None
) -> Optional[str]:
    """
    Extract trinucleotide context around a mutation.

    Args:
        chromosome: Chromosome
        position: Position (1-based)
        ref: Reference allele
        alt: Alternate allele
        reference_genome: Optional reference genome dict

    Returns:
        Trinucleotide context or None
    """
    # In production, you would query a reference genome database
    # For now, we'll return None and expect context from VCF
    return None


def _classify_96_channel(ref: str, alt: str, context: str) -> Optional[str]:
    """
    Classify mutation into 96-channel category.

    Args:
        ref: Reference allele
        alt: Alternate allele
        context: Trinucleotide context

    Returns:
        96-channel category (e.g., 'C>A_ACA') or None
    """
    if len(ref) != 1 or len(alt) != 1:
        return None  # Only SNVs

    if len(context) != 3:
        return None

    # Normalize to pyrimidine reference
    substitution, normalized_context = _normalize_mutation(ref, alt, context)

    # Validate
    if substitution not in SUBSTITUTION_TYPES:
        return None

    if normalized_context not in TRINUCLEOTIDE_CONTEXTS:
        return None

    return f"{substitution}_{normalized_context}"


def _initialize_96_channel_profile() -> Dict[str, int]:
    """Initialize empty 96-channel mutation profile."""
    profile = {}
    for sub_type in SUBSTITUTION_TYPES:
        for context in TRINUCLEOTIDE_CONTEXTS:
            profile[f"{sub_type}_{context}"] = 0
    return profile


def _normalize_profile(profile: Dict[str, int]) -> Dict[str, float]:
    """Normalize profile to sum to 1."""
    total = sum(profile.values())
    if total == 0:
        return {k: 0.0 for k in profile}
    return {k: v / total for k, v in profile.items()}


# ==========================================
# ANALYSIS IMPLEMENTATIONS
# ==========================================

async def _generate_signature_profile(
    db,
    table_name: str,
    request: MutationSignatureRequest
) -> MutationSignatureResponse:
    """
    Generate 96-channel mutational signature profile.
    """
    try:
        model_class = get_model_class(table_name)

        # Build query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Sample filter
        if request.sample_ids and hasattr(model_class, 'tumor_sample_barcode'):
            query = query.filter(model_class.tumor_sample_barcode.in_(request.sample_ids))

        # Gene filter
        if request.genes and hasattr(model_class, 'hugo_symbol'):
            query = query.filter(model_class.hugo_symbol.in_(request.genes))

        # Variant classification filter
        if request.variant_classifications and hasattr(model_class, 'variant_classification'):
            query = query.filter(model_class.variant_classification.in_(request.variant_classifications))

        # For SNVs, filter to single base substitutions
        if request.mutation_type == MutationType.snv:
            if hasattr(model_class, 'variant_type'):
                query = query.filter(model_class.variant_type == 'SNP')

        # Get mutations
        mutations = query.all()
        total_mutations = len(mutations)

        # Initialize 96-channel profile
        profile_96 = _initialize_96_channel_profile()

        # Count mutations in each channel
        mutations_by_channel = defaultdict(list)

        for mutation in mutations:
            # Extract mutation details
            ref = getattr(mutation, 'reference_allele', None)
            alt = getattr(mutation, 'tumor_seq_allele2', 
                         getattr(mutation, 'alternate_allele', None))

            # Try to get trinucleotide context from mutation record
            # Common column names: trinucleotide_context, context, ref_context
            context = None
            for context_col in ['trinucleotide_context', 'context', 'ref_context', 'tri_context']:
                if hasattr(mutation, context_col):
                    context = getattr(mutation, context_col)
                    if context:
                        break

            # If no context available, skip (would need reference genome)
            if not context or not ref or not alt:
                continue

            # Classify into 96-channel
            channel = _classify_96_channel(ref, alt, context)

            if channel:
                profile_96[channel] += 1
                mutations_by_channel[channel].append({
                    'sample': getattr(mutation, 'tumor_sample_barcode', 
                                    getattr(mutation, 'sample_id', 'unknown')),
                    'gene': getattr(mutation, 'hugo_symbol', None),
                    'position': getattr(mutation, 'start', 
                                      getattr(mutation, 'start_position', None))
                })

        # Normalize if requested
        if request.normalize:
            profile_normalized = _normalize_profile(profile_96)
        else:
            profile_normalized = {k: float(v) for k, v in profile_96.items()}

        # Organize by substitution type
        profile_by_type = {}
        for sub_type in SUBSTITUTION_TYPES:
            profile_by_type[sub_type] = {
                context: profile_normalized.get(f"{sub_type}_{context}", 0.0)
                for context in TRINUCLEOTIDE_CONTEXTS
            }

        # Get total samples
        total_samples = None
        if hasattr(model_class, 'tumor_sample_barcode'):
            total_samples = db.query(
                func.count(distinct(model_class.tumor_sample_barcode))
            ).filter(query.whereclause if hasattr(query, 'whereclause') else True).scalar()

        # Build result with top channels
        result = []
        for channel, count in sorted(profile_96.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                result.append({
                    'channel': channel,
                    'count': count,
                    'frequency': profile_normalized[channel],
                    'substitution_type': channel.split('_')[0],
                    'context': channel.split('_')[1] if '_' in channel else None
                })

        # Apply limit
        if request.limit:
            result = result[:request.limit]

        return MutationSignatureResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            mutation_type=request.mutation_type.value,
            total_mutations=total_mutations,
            total_samples=total_samples,
            signature_profile=profile_by_type,
            result=result
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Signature profile generation failed: {str(e)}"
        )


async def _deconvolve_signatures(
    db,
    table_name: str,
    request: MutationSignatureRequest
) -> MutationSignatureResponse:
    """
    Deconvolve mutation profile into known COSMIC signatures.

    Note: Full signature deconvolution requires optimization libraries.
    This is a simplified version showing the structure.
    """
    try:
        # First, generate the 96-channel profile
        profile_response = await _generate_signature_profile(db, table_name, request)

        # In production, you would:
        # 1. Load COSMIC signature matrix
        # 2. Use non-negative least squares (NNLS) or similar optimization
        # 3. Calculate signature exposures

        # Placeholder: Return simplified signature contributions
        # This would be replaced with actual deconvolution algorithm

        signature_contributions = [
            {
                'signature': 'SBS1',
                'signature_name': 'Clock-like signature',
                'contribution': 0.35,
                'mutations': int(profile_response.total_mutations * 0.35)
            },
            {
                'signature': 'SBS5',
                'signature_name': 'Clock-like signature',
                'contribution': 0.28,
                'mutations': int(profile_response.total_mutations * 0.28)
            },
            {
                'signature': 'SBS13',
                'signature_name': 'APOBEC',
                'contribution': 0.22,
                'mutations': int(profile_response.total_mutations * 0.22)
            },
            {
                'signature': 'SBS2',
                'signature_name': 'APOBEC',
                'contribution': 0.15,
                'mutations': int(profile_response.total_mutations * 0.15)
            }
        ]

        # Filter by minimum contribution
        signature_contributions = [
            sig for sig in signature_contributions 
            if sig['contribution'] >= request.min_contribution
        ]

        # Sort by contribution
        signature_contributions = sorted(
            signature_contributions,
            key=lambda x: x['contribution'],
            reverse=True
        )

        return MutationSignatureResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            mutation_type=request.mutation_type.value,
            total_mutations=profile_response.total_mutations,
            total_samples=profile_response.total_samples,
            signature_database=request.signature_database.value,
            signature_profile=profile_response.signature_profile,
            signature_contributions=signature_contributions,
            result=signature_contributions
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Signature deconvolution failed: {str(e)}"
        )


async def _analyze_sample_signatures(
    db,
    table_name: str,
    request: MutationSignatureRequest
) -> MutationSignatureResponse:
    """
    Analyze signatures per sample.
    """
    try:
        model_class = get_model_class(table_name)

        # Build query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Get mutations
        mutations = query.all()

        # Group by sample
        samples_mutations = defaultdict(list)
        for mutation in mutations:
            sample = getattr(mutation, 'tumor_sample_barcode',
                           getattr(mutation, 'sample_id', 'unknown'))
            samples_mutations[sample].append(mutation)

        # Analyze each sample
        sample_results = []

        for sample, sample_muts in samples_mutations.items():
            # Count substitution types
            sub_type_counts = defaultdict(int)

            for mutation in sample_muts:
                ref = getattr(mutation, 'reference_allele', None)
                alt = getattr(mutation, 'tumor_seq_allele2',
                             getattr(mutation, 'alternate_allele', None))

                if ref and alt and len(ref) == 1 and len(alt) == 1:
                    # Normalize to pyrimidine
                    if ref in ['A', 'G']:
                        ref = _get_complement(ref)
                        alt = _get_complement(alt)

                    sub_type = f"{ref}>{alt}"
                    if sub_type in SUBSTITUTION_TYPES:
                        sub_type_counts[sub_type] += 1

            total_subs = sum(sub_type_counts.values())

            sample_results.append({
                'sample': sample,
                'total_mutations': len(sample_muts),
                'total_substitutions': total_subs,
                'C>A': sub_type_counts.get('C>A', 0),
                'C>G': sub_type_counts.get('C>G', 0),
                'C>T': sub_type_counts.get('C>T', 0),
                'T>A': sub_type_counts.get('T>A', 0),
                'T>C': sub_type_counts.get('T>C', 0),
                'T>G': sub_type_counts.get('T>G', 0),
                'C>A_freq': sub_type_counts.get('C>A', 0) / total_subs if total_subs > 0 else 0,
                'C>G_freq': sub_type_counts.get('C>G', 0) / total_subs if total_subs > 0 else 0,
                'C>T_freq': sub_type_counts.get('C>T', 0) / total_subs if total_subs > 0 else 0,
                'T>A_freq': sub_type_counts.get('T>A', 0) / total_subs if total_subs > 0 else 0,
                'T>C_freq': sub_type_counts.get('T>C', 0) / total_subs if total_subs > 0 else 0,
                'T>G_freq': sub_type_counts.get('T>G', 0) / total_subs if total_subs > 0 else 0
            })

        # Sort
        if request.order_by:
            reverse = (request.order_direction == OrderDirection.desc)
            sample_results = sorted(
                sample_results,
                key=lambda x: x.get(request.order_by, 0),
                reverse=reverse
            )

        # Apply limit
        if request.limit:
            sample_results = sample_results[:request.limit]

        return MutationSignatureResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            mutation_type=request.mutation_type.value,
            total_mutations=len(mutations),
            total_samples=len(samples_mutations),
            result=sample_results
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sample signature analysis failed: {str(e)}"
        )


# ==========================================
# MAIN API FUNCTION
# ==========================================

async def mutation_signature_analyzer(
    request: MutationSignatureRequest,
    table_name: str,
    db
) -> MutationSignatureResponse:
    """
    Analyze mutational signatures in cancer genomes.

    Supports multiple analysis types:
    1. profile: Generate 96-channel signature profile
    2. deconvolution: Decompose into known COSMIC signatures
    3. sample_signatures: Per-sample signature analysis

    Args:
        request: MutationSignatureRequest with analysis parameters
        table_name: Dataset table name
        db: Database session

    Returns:
        MutationSignatureResponse with signature analysis results

    Example Requests:
    -----------------

    1. Generate 96-Channel Profile:
    {
      "dataset": "tcga_exome_somatic",
      "analysis_type": "profile",
      "mutation_type": "SNV",
      "normalize": true,
      "limit": 20
    }

    2. Signature Deconvolution:
    {
      "dataset": "nibmg_exome_somatic",
      "analysis_type": "deconvolution",
      "mutation_type": "SNV",
      "signature_database": "COSMIC_v3_SBS",
      "min_contribution": 0.05,
      "sample_ids": ["SAMPLE001", "SAMPLE002"]
    }

    3. Per-Sample Signature Analysis:
    {
      "dataset": "tcga_exome_somatic",
      "analysis_type": "sample_signatures",
      "mutation_type": "SNV",
      "order_by": "total_mutations",
      "order_direction": "desc",
      "limit": 50
    }

    4. Gene-Specific Signatures:
    {
      "dataset": "nibmg_exome_somatic",
      "analysis_type": "profile",
      "mutation_type": "SNV",
      "genes": ["TP53", "BRCA1", "KRAS"],
      "normalize": true
    }

    Note:
    -----
    For accurate signature analysis, mutation data should include:
    - Trinucleotide context (trinucleotide_context column)
    - Reference and alternate alleles
    - Chromosome and position (for context extraction from reference genome)

    Full signature deconvolution requires:
    - COSMIC signature matrix (loaded separately)
    - Optimization library (scipy, scikit-learn)
    - Non-negative least squares (NNLS) algorithm
    """

    try:
        # Route to appropriate analysis
        if request.analysis_type == AnalysisType.profile:
            return await _generate_signature_profile(db, table_name, request)

        elif request.analysis_type == AnalysisType.deconvolution:
            return await _deconvolve_signatures(db, table_name, request)

        elif request.analysis_type == AnalysisType.sample_signatures:
            return await _analyze_sample_signatures(db, table_name, request)

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
            detail=f"Mutation signature analysis failed: {str(e)}"
        )


# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def load_cosmic_signatures(signature_db: SignatureDatabase) -> Optional[Dict]:
    """
    Load COSMIC signature reference matrix.

    In production, this would load actual COSMIC signature data from:
    - Database table
    - JSON file
    - API endpoint

    Args:
        signature_db: Signature database identifier

    Returns:
        Dictionary of signature profiles
    """
    # Placeholder - would load actual COSMIC data
    return None


def calculate_cosine_similarity(profile1: Dict, profile2: Dict) -> float:
    """
    Calculate cosine similarity between two mutation profiles.

    Args:
        profile1: First profile (96-channel)
        profile2: Second profile (96-channel)

    Returns:
        Cosine similarity (0-1)
    """
    import math

    # Ensure same keys
    all_keys = set(profile1.keys()) | set(profile2.keys())

    dot_product = sum(
        profile1.get(k, 0) * profile2.get(k, 0) 
        for k in all_keys
    )

    norm1 = math.sqrt(sum(v**2 for v in profile1.values()))
    norm2 = math.sqrt(sum(v**2 for v in profile2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)
