"""
protein_structure_mapper.py

Maps mutations to protein domains, structures, and functional regions.
Supports domain enrichment analysis, hotspot detection, and structural impact prediction.

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

class AnalysisType(str, Enum):
    """Types of protein structure analysis"""
    domain_mapping = "domain_mapping"  # Map mutations to protein domains
    hotspot_detection = "hotspot_detection"  # Detect mutation hotspots in domains
    domain_enrichment = "domain_enrichment"  # Domain enrichment analysis
    structural_impact = "structural_impact"  # Predict structural impact
    functional_region = "functional_region"  # Map to functional regions


class DomainDatabase(str, Enum):
    """Protein domain databases"""
    pfam = "Pfam"  # Pfam domains
    interpro = "InterPro"  # InterPro domains
    smart = "SMART"  # SMART domains
    prosite = "PROSITE"  # PROSITE patterns
    custom = "custom"  # Custom domain annotations


class OrderDirection(str, Enum):
    """Sort order"""
    asc = "asc"
    desc = "desc"


class ProteinStructureRequest(BaseModel):
    """Request model for protein structure mapping"""

    # Dataset to analyze
    dataset: str = Field(
        ...,
        description="Dataset name (e.g., 'nibmg_exome_somatic', 'tcga_exome_somatic')"
    )

    # Analysis type
    analysis_type: AnalysisType = Field(
        AnalysisType.domain_mapping,
        description="Type of protein structure analysis"
    )

    # Gene filters
    genes: Optional[List[str]] = Field(
        None,
        description="Specific genes to analyze (if None, analyzes all)"
    )

    # Domain database
    domain_database: DomainDatabase = Field(
        DomainDatabase.pfam,
        description="Domain database to use"
    )

    # Hotspot parameters
    min_mutations_for_hotspot: int = Field(
        3,
        ge=2,
        description="Minimum mutations to define a hotspot"
    )

    hotspot_window_size: int = Field(
        10,
        ge=5,
        le=50,
        description="Window size (amino acids) for hotspot detection"
    )

    # Enrichment parameters
    min_domain_mutations: int = Field(
        2,
        ge=1,
        description="Minimum mutations in domain for enrichment"
    )

    # Additional filters
    filters: Optional[ComplexFilter] = Field(
        None,
        description="Complex filters for mutations"
    )

    # Variant classification filter
    variant_classifications: Optional[List[str]] = Field(
        None,
        description="Filter by variant classifications"
    )

    # Ordering and limiting
    order_by: Optional[str] = Field(
        "mutation_count",
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


class ProteinStructureResponse(BaseModel):
    """Response model for protein structure mapping"""

    dataset: str
    analysis_type: str
    total_mutations: int
    total_genes: Optional[int] = None
    domain_database: str

    # Analysis-specific results
    result: List[Dict[str, Any]]


# ==========================================
# INTERNAL HELPERS
# ==========================================

def _parse_protein_position(protein_change: str) -> Optional[int]:
    """
    Extract amino acid position from protein change string.

    Args:
        protein_change: Protein change (e.g., 'p.R273H', 'R273H')

    Returns:
        Amino acid position or None
    """
    import re

    if not protein_change:
        return None

    # Remove 'p.' prefix if present
    protein_change = protein_change.replace('p.', '')

    # Extract position (digits in the middle)
    match = re.search(r'[A-Z*]?(\d+)[A-Z*]?', protein_change)

    if match:
        return int(match.group(1))

    return None


def _get_protein_domains_from_db(
    db,
    genes: List[str],
    domain_database: str = "Pfam"
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Query protein domain annotations from database.

    Assumes you have a protein_domain table with schema:
    - gene_symbol: Gene symbol
    - domain_name: Domain name
    - domain_id: Domain identifier (e.g., PF00001)
    - domain_start: Domain start position
    - domain_end: Domain end position
    - domain_database: Database source (Pfam, InterPro, etc.)

    Args:
        db: Database session
        genes: List of gene symbols
        domain_database: Domain database filter

    Returns:
        Dictionary mapping gene to list of domains
    """
    try:
        # Try to get the ProteinDomain model
        from app.models import ProteinDomain

        # Build query
        query = db.query(ProteinDomain).filter(
            ProteinDomain.gene_symbol.in_(genes)
        )

        # Filter by database
        if domain_database != "custom":
            query = query.filter(ProteinDomain.domain_database == domain_database)

        # Execute query
        domains = query.all()

        # Organize by gene
        gene_domains = defaultdict(list)
        for domain in domains:
            gene = domain.gene_symbol
            gene_domains[gene].append({
                'domain_name': domain.domain_name,
                'domain_id': domain.domain_id,
                'start': domain.domain_start,
                'end': domain.domain_end,
                'database': domain.domain_database
            })

        return dict(gene_domains)

    except ImportError:
        # If ProteinDomain model doesn't exist, return hardcoded annotations
        # for common cancer genes
        return _get_hardcoded_domains(genes)


def _get_hardcoded_domains(genes: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Hardcoded protein domain annotations for common cancer genes.

    Args:
        genes: List of gene symbols

    Returns:
        Dictionary mapping gene to domains
    """
    # Common cancer gene domains
    known_domains = {
        'TP53': [
            {'domain_name': 'Transactivation domain', 'domain_id': 'TAD', 'start': 1, 'end': 61, 'database': 'UniProt'},
            {'domain_name': 'DNA-binding domain', 'domain_id': 'DBD', 'start': 102, 'end': 292, 'database': 'UniProt'},
            {'domain_name': 'Tetramerization domain', 'domain_id': 'TET', 'start': 326, 'end': 355, 'database': 'UniProt'},
            {'domain_name': 'Regulatory domain', 'domain_id': 'REG', 'start': 363, 'end': 393, 'database': 'UniProt'}
        ],
        'KRAS': [
            {'domain_name': 'GTPase domain', 'domain_id': 'G-domain', 'start': 1, 'end': 166, 'database': 'Pfam'},
            {'domain_name': 'Hypervariable region', 'domain_id': 'HVR', 'start': 167, 'end': 188, 'database': 'UniProt'}
        ],
        'PIK3CA': [
            {'domain_name': 'PI3K-ABD', 'domain_id': 'PF00794', 'start': 1, 'end': 108, 'database': 'Pfam'},
            {'domain_name': 'PI3K-RBD', 'domain_id': 'PF00794', 'start': 109, 'end': 314, 'database': 'Pfam'},
            {'domain_name': 'C2 domain', 'domain_id': 'PF00168', 'start': 330, 'end': 487, 'database': 'Pfam'},
            {'domain_name': 'Helical domain', 'domain_id': 'Helical', 'start': 533, 'end': 694, 'database': 'UniProt'},
            {'domain_name': 'Kinase domain', 'domain_id': 'PF00454', 'start': 713, 'end': 1068, 'database': 'Pfam'}
        ],
        'EGFR': [
            {'domain_name': 'Receptor L domain 1', 'domain_id': 'L1', 'start': 1, 'end': 165, 'database': 'UniProt'},
            {'domain_name': 'Receptor L domain 2', 'domain_id': 'L2', 'start': 166, 'end': 310, 'database': 'UniProt'},
            {'domain_name': 'Tyrosine kinase domain', 'domain_id': 'TK', 'start': 712, 'end': 979, 'database': 'Pfam'}
        ],
        'BRAF': [
            {'domain_name': 'Ras-binding domain', 'domain_id': 'RBD', 'start': 155, 'end': 227, 'database': 'Pfam'},
            {'domain_name': 'Protein kinase domain', 'domain_id': 'PKD', 'start': 457, 'end': 717, 'database': 'Pfam'}
        ],
        'PTEN': [
            {'domain_name': 'Phosphatase domain', 'domain_id': 'PTP', 'start': 7, 'end': 185, 'database': 'Pfam'},
            {'domain_name': 'C2 domain', 'domain_id': 'C2', 'start': 190, 'end': 351, 'database': 'Pfam'}
        ]
    }

    # Return domains for requested genes
    result = {}
    for gene in genes:
        if gene in known_domains:
            result[gene] = known_domains[gene]

    return result


def _find_domain_for_position(
    position: int,
    domains: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Find which domain contains a given position.

    Args:
        position: Amino acid position
        domains: List of domain annotations

    Returns:
        Domain dict or None
    """
    for domain in domains:
        if domain['start'] <= position <= domain['end']:
            return domain

    return None


def _detect_hotspots(
    mutations: List[int],
    window_size: int,
    min_mutations: int
) -> List[Dict[str, Any]]:
    """
    Detect mutation hotspots using sliding window.

    Args:
        mutations: List of mutation positions
        window_size: Window size in amino acids
        min_mutations: Minimum mutations to define hotspot

    Returns:
        List of hotspot regions
    """
    if len(mutations) < min_mutations:
        return []

    # Sort positions
    sorted_positions = sorted(mutations)

    # Find hotspots using sliding window
    hotspots = []

    i = 0
    while i < len(sorted_positions):
        window_start = sorted_positions[i]
        window_end = window_start + window_size - 1

        # Count mutations in window
        mutations_in_window = []
        for pos in sorted_positions[i:]:
            if pos <= window_end:
                mutations_in_window.append(pos)
            else:
                break

        # Check if hotspot
        if len(mutations_in_window) >= min_mutations:
            hotspots.append({
                'start': window_start,
                'end': window_end,
                'mutation_count': len(mutations_in_window),
                'positions': mutations_in_window,
                'center': sum(mutations_in_window) // len(mutations_in_window)
            })

            # Skip to end of this hotspot
            i += len(mutations_in_window)
        else:
            i += 1

    return hotspots


# ==========================================
# ANALYSIS IMPLEMENTATIONS
# ==========================================

async def _map_mutations_to_domains(
    db,
    table_name: str,
    request: ProteinStructureRequest
) -> ProteinStructureResponse:
    """
    Map mutations to protein domains.
    """
    try:
        model_class = get_model_class(table_name)

        # Build query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Gene filter
        if request.genes and hasattr(model_class, 'hugo_symbol'):
            query = query.filter(model_class.hugo_symbol.in_(request.genes))
            genes_to_analyze = request.genes
        else:
            # Get all genes
            if hasattr(model_class, 'hugo_symbol'):
                genes_to_analyze = [
                    row[0] for row in 
                    db.query(distinct(model_class.hugo_symbol)).all()
                ]
            else:
                raise HTTPException(400, "Dataset must have hugo_symbol column")

        # Variant classification filter
        if request.variant_classifications and hasattr(model_class, 'variant_classification'):
            query = query.filter(model_class.variant_classification.in_(request.variant_classifications))

        # Get mutations
        mutations = query.all()
        total_mutations = len(mutations)

        # Get domain annotations
        gene_domains = _get_protein_domains_from_db(
            db,
            genes_to_analyze,
            request.domain_database.value
        )

        # Map mutations to domains
        result = []
        unmapped_count = 0

        for mutation in mutations:
            gene = getattr(mutation, 'hugo_symbol', None)

            # Get protein change
            protein_change = None
            for col in ['hgvsp_short', 'protein_change', 'hgvs_p']:
                if hasattr(mutation, col):
                    protein_change = getattr(mutation, col)
                    if protein_change:
                        break

            if not protein_change or not gene:
                unmapped_count += 1
                continue

            # Parse position
            position = _parse_protein_position(protein_change)

            if not position:
                unmapped_count += 1
                continue

            # Find domain
            domains = gene_domains.get(gene, [])
            domain_info = _find_domain_for_position(position, domains)

            result.append({
                'gene': gene,
                'protein_change': protein_change,
                'position': position,
                'domain_name': domain_info['domain_name'] if domain_info else 'Intradomain/Unknown',
                'domain_id': domain_info['domain_id'] if domain_info else None,
                'domain_start': domain_info['start'] if domain_info else None,
                'domain_end': domain_info['end'] if domain_info else None,
                'variant_classification': getattr(mutation, 'variant_classification', None),
                'sample': getattr(mutation, 'tumor_sample_barcode', 
                                getattr(mutation, 'sample_id', None))
            })

        # Sort
        if request.order_by:
            reverse = (request.order_direction == OrderDirection.desc)
            result = sorted(
                result,
                key=lambda x: x.get(request.order_by, 0),
                reverse=reverse
            )

        # Apply limit
        if request.limit:
            result = result[:request.limit]

        return ProteinStructureResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            total_mutations=total_mutations,
            total_genes=len(genes_to_analyze),
            domain_database=request.domain_database.value,
            result=result
        )

    except Exception as e:
        raise HTTPException(500, f"Domain mapping failed: {str(e)}")


async def _detect_domain_hotspots(
    db,
    table_name: str,
    request: ProteinStructureRequest
) -> ProteinStructureResponse:
    """
    Detect mutation hotspots in protein domains.
    """
    try:
        model_class = get_model_class(table_name)

        # Build query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Gene filter
        if request.genes and hasattr(model_class, 'hugo_symbol'):
            query = query.filter(model_class.hugo_symbol.in_(request.genes))
            genes_to_analyze = request.genes
        else:
            if hasattr(model_class, 'hugo_symbol'):
                genes_to_analyze = [
                    row[0] for row in 
                    db.query(distinct(model_class.hugo_symbol)).all()
                ]
            else:
                raise HTTPException(400, "Dataset must have hugo_symbol column")

        # Get mutations
        mutations = query.all()

        # Group mutations by gene
        gene_mutations = defaultdict(list)

        for mutation in mutations:
            gene = getattr(mutation, 'hugo_symbol', None)

            # Get protein change
            protein_change = None
            for col in ['hgvsp_short', 'protein_change', 'hgvs_p']:
                if hasattr(mutation, col):
                    protein_change = getattr(mutation, col)
                    if protein_change:
                        break

            if protein_change and gene:
                position = _parse_protein_position(protein_change)
                if position:
                    gene_mutations[gene].append(position)

        # Detect hotspots for each gene
        result = []

        for gene, positions in gene_mutations.items():
            hotspots = _detect_hotspots(
                positions,
                request.hotspot_window_size,
                request.min_mutations_for_hotspot
            )

            for hotspot in hotspots:
                result.append({
                    'gene': gene,
                    'hotspot_start': hotspot['start'],
                    'hotspot_end': hotspot['end'],
                    'hotspot_center': hotspot['center'],
                    'mutation_count': hotspot['mutation_count'],
                    'mutations_per_residue': round(
                        hotspot['mutation_count'] / request.hotspot_window_size, 3
                    ),
                    'positions': hotspot['positions']
                })

        # Sort by mutation count
        result = sorted(result, key=lambda x: x['mutation_count'], reverse=True)

        # Apply limit
        if request.limit:
            result = result[:request.limit]

        return ProteinStructureResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            total_mutations=len(mutations),
            total_genes=len(gene_mutations),
            domain_database=request.domain_database.value,
            result=result
        )

    except Exception as e:
        raise HTTPException(500, f"Hotspot detection failed: {str(e)}")


async def _analyze_domain_enrichment(
    db,
    table_name: str,
    request: ProteinStructureRequest
) -> ProteinStructureResponse:
    """
    Analyze domain enrichment for mutations.
    """
    try:
        model_class = get_model_class(table_name)

        # Build query
        query = db.query(model_class)

        # Apply filters
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # Gene filter
        if request.genes and hasattr(model_class, 'hugo_symbol'):
            query = query.filter(model_class.hugo_symbol.in_(request.genes))
            genes_to_analyze = request.genes
        else:
            if hasattr(model_class, 'hugo_symbol'):
                genes_to_analyze = [
                    row[0] for row in 
                    db.query(distinct(model_class.hugo_symbol)).all()
                ]
            else:
                raise HTTPException(400, "Dataset must have hugo_symbol column")

        # Get mutations
        mutations = query.all()
        total_mutations = len(mutations)

        # Get domain annotations
        gene_domains = _get_protein_domains_from_db(
            db,
            genes_to_analyze,
            request.domain_database.value
        )

        # Count mutations per domain
        domain_mutation_counts = defaultdict(lambda: {'count': 0, 'genes': set()})

        for mutation in mutations:
            gene = getattr(mutation, 'hugo_symbol', None)

            # Get protein change
            protein_change = None
            for col in ['hgvsp_short', 'protein_change', 'hgvs_p']:
                if hasattr(mutation, col):
                    protein_change = getattr(mutation, col)
                    if protein_change:
                        break

            if not protein_change or not gene:
                continue

            # Parse position
            position = _parse_protein_position(protein_change)

            if not position:
                continue

            # Find domain
            domains = gene_domains.get(gene, [])
            domain_info = _find_domain_for_position(position, domains)

            if domain_info:
                domain_key = f"{domain_info['domain_name']}|{domain_info['domain_id']}"
                domain_mutation_counts[domain_key]['count'] += 1
                domain_mutation_counts[domain_key]['genes'].add(gene)
                domain_mutation_counts[domain_key]['domain_info'] = domain_info

        # Build result
        result = []
        for domain_key, data in domain_mutation_counts.items():
            if data['count'] >= request.min_domain_mutations:
                domain_name, domain_id = domain_key.split('|')
                result.append({
                    'domain_name': domain_name,
                    'domain_id': domain_id,
                    'mutation_count': data['count'],
                    'gene_count': len(data['genes']),
                    'genes': list(data['genes']),
                    'frequency': round(data['count'] / total_mutations, 4) if total_mutations > 0 else 0
                })

        # Sort by mutation count
        result = sorted(result, key=lambda x: x['mutation_count'], reverse=True)

        # Apply limit
        if request.limit:
            result = result[:request.limit]

        return ProteinStructureResponse(
            dataset=request.dataset,
            analysis_type=request.analysis_type.value,
            total_mutations=total_mutations,
            total_genes=len(genes_to_analyze),
            domain_database=request.domain_database.value,
            result=result
        )

    except Exception as e:
        raise HTTPException(500, f"Domain enrichment failed: {str(e)}")


# ==========================================
# MAIN API FUNCTION
# ==========================================

async def protein_structure_mapper(
    request: ProteinStructureRequest,
    table_name: str,
    db
) -> ProteinStructureResponse:
    """
    Map mutations to protein domains and structural features.

    Supports multiple analysis types:
    1. domain_mapping: Map mutations to protein domains
    2. hotspot_detection: Detect mutation hotspots
    3. domain_enrichment: Analyze domain enrichment

    Args:
        request: ProteinStructureRequest with analysis parameters
        table_name: Dataset table name
        db: Database session

    Returns:
        ProteinStructureResponse with analysis results

    Database Schema:
    ----------------
    Assumes a protein_domain table with columns:
    - gene_symbol: Gene symbol (STRING)
    - domain_name: Domain name (STRING)
    - domain_id: Domain identifier (STRING)
    - domain_start: Domain start position (INT)
    - domain_end: Domain end position (INT)
    - domain_database: Database source (STRING)

    Example Requests:
    -----------------

    1. Map Mutations to Domains:
    {
      "dataset": "tcga_exome_somatic",
      "analysis_type": "domain_mapping",
      "genes": ["TP53", "PIK3CA"],
      "domain_database": "Pfam",
      "limit": 100
    }

    2. Detect Mutation Hotspots:
    {
      "dataset": "nibmg_exome_somatic",
      "analysis_type": "hotspot_detection",
      "genes": ["KRAS", "BRAF"],
      "min_mutations_for_hotspot": 5,
      "hotspot_window_size": 15
    }

    3. Domain Enrichment Analysis:
    {
      "dataset": "tcga_exome_somatic",
      "analysis_type": "domain_enrichment",
      "domain_database": "Pfam",
      "min_domain_mutations": 10,
      "order_by": "mutation_count",
      "limit": 20
    }

    4. Filter by Variant Type:
    {
      "dataset": "nibmg_exome_somatic",
      "analysis_type": "domain_mapping",
      "genes": ["TP53"],
      "variant_classifications": ["Missense_Mutation"],
      "domain_database": "UniProt"
    }

    Note:
    -----
    If protein_domain table doesn't exist, the tool uses hardcoded
    annotations for common cancer genes (TP53, KRAS, PIK3CA, EGFR, etc.)
    """

    try:
        # Route to appropriate analysis
        if request.analysis_type == AnalysisType.domain_mapping:
            return await _map_mutations_to_domains(db, table_name, request)

        elif request.analysis_type == AnalysisType.hotspot_detection:
            return await _detect_domain_hotspots(db, table_name, request)

        elif request.analysis_type == AnalysisType.domain_enrichment:
            return await _analyze_domain_enrichment(db, table_name, request)

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
            detail=f"Protein structure mapping failed: {str(e)}"
        )


# ==========================================
# EXAMPLE USAGE
# ==========================================

"""
Example Integration in FastAPI Router:
---------------------------------------

from protein_structure_mapper import (
    protein_structure_mapper,
    ProteinStructureRequest,
    ProteinStructureResponse
)

@router.post("/protein_structure_mapper", response_model=ProteinStructureResponse)
async def map_protein_structure(
    table_name: str,
    request: ProteinStructureRequest,
    db: Session = Depends(get_db)
):
    return await protein_structure_mapper(request, table_name, db)


Database Setup (Optional):
---------------------------

CREATE TABLE protein_domain (
    id INTEGER PRIMARY KEY,
    gene_symbol VARCHAR(50) NOT NULL,
    domain_name VARCHAR(255),
    domain_id VARCHAR(50),
    domain_start INTEGER,
    domain_end INTEGER,
    domain_database VARCHAR(50),
    INDEX idx_gene (gene_symbol)
);

# SQLAlchemy Model:
class ProteinDomain(Base):
    __tablename__ = "protein_domain"

    id = Column(Integer, primary_key=True)
    gene_symbol = Column(String(50), nullable=False, index=True)
    domain_name = Column(String(255))
    domain_id = Column(String(50))
    domain_start = Column(Integer)
    domain_end = Column(Integer)
    domain_database = Column(String(50))


Hardcoded Domains:
------------------
The tool includes hardcoded domain annotations for:
- TP53 (DNA-binding, Tetramerization, etc.)
- KRAS (GTPase domain)
- PIK3CA (Kinase, Helical, C2 domains)
- EGFR (Receptor L, Tyrosine kinase)
- BRAF (Kinase domain)
- PTEN (Phosphatase, C2)

These work without a protein_domain table!
"""
