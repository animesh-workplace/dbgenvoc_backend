"""
gene_interaction_retriever.py

Retrieves gene-gene and protein-protein interactions from interaction databases.
Supports network analysis, pathway-based interactions, and interaction filtering.

Author: Generated based on dbGENVOC API patterns
Date: 2026-01-23
"""

from enum import Enum
from fastapi import HTTPException
from collections import defaultdict
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


class InteractionType(str, Enum):
    """Types of gene/protein interactions"""

    physical = "physical"  # Physical protein-protein interactions
    regulatory = "regulatory"  # Regulatory interactions
    pathway = "pathway"  # Pathway-based interactions
    genetic = "genetic"  # Genetic interactions
    all = "all"  # All interaction types


class InteractionDatabase(str, Enum):
    """Interaction databases"""

    string = "STRING"  # STRING database
    biogrid = "BioGRID"  # BioGRID database
    intact = "IntAct"  # IntAct database
    reactome = "Reactome"  # Reactome pathways
    custom = "custom"  # Custom interaction database


class NetworkAnalysisType(str, Enum):
    """Types of network analysis"""

    direct_partners = "direct_partners"  # Direct interaction partners
    network_neighbors = "network_neighbors"  # Network neighborhood
    shortest_path = "shortest_path"  # Shortest path between genes
    common_partners = "common_partners"  # Common interaction partners
    subnetwork = "subnetwork"  # Subnetwork extraction


class OrderDirection(str, Enum):
    """Sort order"""

    asc = "asc"
    desc = "desc"


class GeneInteractionRequest(BaseModel):
    """Request model for gene interaction retrieval"""

    # Query genes
    genes: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Gene symbols to query (1-100 genes)",
    )

    # Analysis type
    analysis_type: NetworkAnalysisType = Field(
        NetworkAnalysisType.direct_partners, description="Type of network analysis"
    )

    # Interaction filters
    interaction_type: InteractionType = Field(
        InteractionType.all, description="Type of interactions to retrieve"
    )

    interaction_database: InteractionDatabase = Field(
        InteractionDatabase.string, description="Interaction database to query"
    )

    # Confidence filtering
    min_confidence: Optional[float] = Field(
        None, ge=0, le=1, description="Minimum interaction confidence score (0-1)"
    )

    # Network parameters
    max_distance: int = Field(
        1, ge=1, le=3, description="Maximum network distance (1=direct, 2=2-hop, etc.)"
    )

    include_experimental: bool = Field(
        True, description="Include experimentally validated interactions"
    )

    include_predicted: bool = Field(
        False, description="Include predicted/computational interactions"
    )

    # Partner gene filters
    partner_genes: Optional[List[str]] = Field(
        None,
        description="Specific partner genes to search for (for shortest_path/common_partners)",
    )

    # Additional filters
    filters: Optional[ComplexFilter] = Field(
        None, description="Complex filters for interaction properties"
    )

    # Ordering and limiting
    order_by: Optional[str] = Field(
        "confidence_score",
        description="Column to order by (e.g., 'confidence_score', 'interaction_count')",
    )

    order_direction: OrderDirection = Field(
        OrderDirection.desc, description="Sort direction"
    )

    limit: Optional[int] = Field(
        None, ge=1, le=10000, description="Limit number of results"
    )

    @field_validator("partner_genes")
    @classmethod
    def validate_partner_genes(cls, v, info):
        """Validate partner_genes for specific analysis types"""
        analysis_type = info.data.get("analysis_type")
        if analysis_type in [
            NetworkAnalysisType.shortest_path,
            NetworkAnalysisType.common_partners,
        ]:
            if not v:
                raise ValueError(
                    f"partner_genes is required for {analysis_type.value} analysis"
                )
        return v


class GeneInteractionResponse(BaseModel):
    """Response model for gene interaction retrieval"""

    analysis_type: str
    query_genes: List[str]
    interaction_database: str
    total_interactions: int
    total_partners: Optional[int] = None

    # Network statistics
    network_stats: Optional[Dict[str, Any]] = None

    # Ordering info
    order_by: Optional[str] = None
    order_direction: Optional[str] = None
    limit: Optional[int] = None

    # Results
    result: List[Dict[str, Any]]


# ==========================================
# INTERNAL HELPERS
# ==========================================


def _get_gene_interactions_from_db(
    db,
    genes: List[str],
    interaction_type: Optional[str] = None,
    min_confidence: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Query gene interactions from database.

    Assumes you have a gene_interaction table with schema:
    - gene_a: Gene symbol
    - gene_b: Gene symbol (interaction partner)
    - interaction_type: Type of interaction
    - confidence_score: Confidence (0-1)
    - source_database: Database source
    - experimental_evidence: Boolean

    Args:
        db: Database session
        genes: List of gene symbols
        interaction_type: Filter by interaction type
        min_confidence: Minimum confidence threshold

    Returns:
        List of interaction dictionaries
    """
    try:
        # Try to get the GeneInteraction model
        # This assumes you have a gene_interaction table
        from app.models import GeneInteraction

        # Build query - get interactions where gene_a or gene_b is in our gene list
        query = db.query(GeneInteraction).filter(
            or_(GeneInteraction.gene_a.in_(genes), GeneInteraction.gene_b.in_(genes))
        )

        # Apply interaction type filter
        if interaction_type and interaction_type != "all":
            if hasattr(GeneInteraction, "interaction_type"):
                query = query.filter(
                    GeneInteraction.interaction_type == interaction_type
                )

        # Apply confidence filter
        if min_confidence is not None and hasattr(GeneInteraction, "confidence_score"):
            query = query.filter(GeneInteraction.confidence_score >= min_confidence)

        # Execute query
        interactions = query.all()

        # Convert to dictionaries
        return [row_to_dict(interaction) for interaction in interactions]

    except ImportError:
        # If GeneInteraction model doesn't exist, return empty
        raise HTTPException(
            status_code=404,
            detail="Gene interaction table not found. Please ensure gene_interaction table exists.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to query gene interactions: {str(e)}"
        )


def _build_interaction_network(
    interactions: List[Dict[str, Any]],
) -> Tuple[Dict[str, Set[str]], Dict[Tuple[str, str], Dict]]:
    """
    Build interaction network from interaction list.

    Args:
        interactions: List of interaction dictionaries

    Returns:
        Tuple of (adjacency_dict, edge_properties)
    """
    network = defaultdict(set)
    edge_props = {}

    for interaction in interactions:
        gene_a = interaction.get("gene_a")
        gene_b = interaction.get("gene_b")

        if gene_a and gene_b:
            # Add edges (undirected)
            network[gene_a].add(gene_b)
            network[gene_b].add(gene_a)

            # Store edge properties
            edge_key = tuple(sorted([gene_a, gene_b]))
            if edge_key not in edge_props:
                edge_props[edge_key] = []
            edge_props[edge_key].append(interaction)

    return dict(network), edge_props


def _find_shortest_path(
    network: Dict[str, Set[str]], source: str, target: str, max_distance: int = 3
) -> Optional[List[str]]:
    """
    Find shortest path between two genes using BFS.

    Args:
        network: Adjacency dictionary
        source: Source gene
        target: Target gene
        max_distance: Maximum path length

    Returns:
        List of genes in path, or None if no path found
    """
    if source == target:
        return [source]

    if source not in network:
        return None

    # BFS
    from collections import deque

    queue = deque([(source, [source])])
    visited = {source}

    while queue:
        current, path = queue.popleft()

        if len(path) > max_distance:
            continue

        for neighbor in network.get(current, []):
            if neighbor == target:
                return path + [neighbor]

            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return None


def _find_common_partners(
    network: Dict[str, Set[str]], genes: List[str]
) -> Dict[str, List[str]]:
    """
    Find common interaction partners for a set of genes.

    Args:
        network: Adjacency dictionary
        genes: List of gene symbols

    Returns:
        Dictionary mapping common partners to genes they interact with
    """
    # Get partners for each gene
    partners_per_gene = {}
    for gene in genes:
        partners_per_gene[gene] = network.get(gene, set())

    # Find intersection
    if not partners_per_gene:
        return {}

    common = (
        set.intersection(*partners_per_gene.values()) if partners_per_gene else set()
    )

    # Build result
    result = {}
    for partner in common:
        result[partner] = [gene for gene in genes if partner in network.get(gene, [])]

    return result


# ==========================================
# ANALYSIS IMPLEMENTATIONS
# ==========================================


async def _get_direct_partners(
    db, request: GeneInteractionRequest
) -> GeneInteractionResponse:
    """
    Get direct interaction partners for query genes.
    """
    try:
        # Get interactions from database
        interactions = _get_gene_interactions_from_db(
            db,
            request.genes,
            request.interaction_type.value
            if request.interaction_type != InteractionType.all
            else None,
            request.min_confidence,
        )

        # Organize by query gene
        partners_by_gene = defaultdict(list)
        all_partners = set()

        for interaction in interactions:
            gene_a = interaction.get("gene_a")
            gene_b = interaction.get("gene_b")

            # Determine which is the query gene and which is the partner
            if gene_a in request.genes:
                query_gene = gene_a
                partner_gene = gene_b
            elif gene_b in request.genes:
                query_gene = gene_b
                partner_gene = gene_a
            else:
                continue

            partners_by_gene[query_gene].append(
                {
                    "partner_gene": partner_gene,
                    "confidence_score": interaction.get("confidence_score", 0),
                    "interaction_type": interaction.get("interaction_type"),
                    "source_database": interaction.get("source_database"),
                    "experimental_evidence": interaction.get(
                        "experimental_evidence", False
                    ),
                }
            )

            all_partners.add(partner_gene)

        # Build result list
        result = []
        for query_gene in request.genes:
            partners = partners_by_gene.get(query_gene, [])

            # Sort partners by confidence
            partners = sorted(
                partners, key=lambda x: x.get("confidence_score", 0), reverse=True
            )

            result.append(
                {
                    "query_gene": query_gene,
                    "partner_count": len(partners),
                    "partners": partners[: request.limit]
                    if request.limit
                    else partners,
                }
            )

        # Calculate network statistics
        network_stats = {
            "total_query_genes": len(request.genes),
            "total_unique_partners": len(all_partners),
            "avg_partners_per_gene": len(all_partners) / len(request.genes)
            if request.genes
            else 0,
        }

        return GeneInteractionResponse(
            analysis_type=request.analysis_type.value,
            query_genes=request.genes,
            interaction_database=request.interaction_database.value,
            total_interactions=len(interactions),
            total_partners=len(all_partners),
            network_stats=network_stats,
            order_by=request.order_by,
            order_direction=request.order_direction.value,
            limit=request.limit,
            result=result,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Direct partners analysis failed: {str(e)}"
        )


async def _get_network_neighbors(
    db, request: GeneInteractionRequest
) -> GeneInteractionResponse:
    """
    Get network neighborhood (multi-hop interactions).
    """
    try:
        from collections import defaultdict

        # Get all interactions
        all_interactions = _get_gene_interactions_from_db(
            db,
            request.genes,
            request.interaction_type.value
            if request.interaction_type != InteractionType.all
            else None,
            request.min_confidence,
        )

        # Build network
        network, edge_props = _build_interaction_network(all_interactions)

        # Find neighbors at each distance
        neighbors_by_distance = defaultdict(set)
        neighbors_by_distance[0] = set(request.genes)

        # Expand network iteratively
        for distance in range(1, request.max_distance + 1):
            new_neighbors = set()
            for gene in neighbors_by_distance[distance - 1]:
                if gene in network:
                    new_neighbors.update(network[gene])

            # Remove genes already seen at closer distances
            for d in range(distance):
                new_neighbors -= neighbors_by_distance[d]

            neighbors_by_distance[distance] = new_neighbors

            # If no new neighbors, stop
            if not new_neighbors:
                break

        # Build result
        result = []
        for distance in sorted(neighbors_by_distance.keys()):
            if distance == 0:
                continue  # Skip query genes themselves

            for neighbor in sorted(neighbors_by_distance[distance]):
                result.append(
                    {
                        "gene": neighbor,
                        "distance": distance,
                        "is_query_gene": neighbor in request.genes,
                    }
                )

        # Sort
        if request.order_by:
            reverse = request.order_direction == OrderDirection.desc
            result = sorted(
                result, key=lambda x: x.get(request.order_by, 0), reverse=reverse
            )

        # Apply limit
        if request.limit:
            result = result[: request.limit]

        # Calculate statistics
        total_neighbors = sum(
            len(neighbors_by_distance[d]) for d in neighbors_by_distance if d > 0
        )

        network_stats = {
            "max_distance": request.max_distance,
            "total_neighbors": total_neighbors,
            "neighbors_by_distance": {
                str(d): len(neighbors_by_distance[d])
                for d in sorted(neighbors_by_distance.keys())
                if d > 0
            },
        }

        return GeneInteractionResponse(
            analysis_type=request.analysis_type.value,
            query_genes=request.genes,
            interaction_database=request.interaction_database.value,
            total_interactions=len(all_interactions),
            total_partners=total_neighbors,
            network_stats=network_stats,
            order_by=request.order_by,
            order_direction=request.order_direction.value,
            limit=request.limit,
            result=result,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Network neighbors analysis failed: {str(e)}"
        )


async def _find_shortest_paths(
    db, request: GeneInteractionRequest
) -> GeneInteractionResponse:
    """
    Find shortest paths between query genes and partner genes.
    """
    try:
        # Get all interactions (need larger network for path finding)
        # Expand search to include intermediate genes
        expanded_genes = list(set(request.genes + (request.partner_genes or [])))

        interactions = _get_gene_interactions_from_db(
            db,
            expanded_genes,
            request.interaction_type.value
            if request.interaction_type != InteractionType.all
            else None,
            request.min_confidence,
        )

        # Build network
        network, edge_props = _build_interaction_network(interactions)

        # Find paths
        result = []
        for query_gene in request.genes:
            for partner_gene in request.partner_genes or []:
                if query_gene == partner_gene:
                    continue

                path = _find_shortest_path(
                    network, query_gene, partner_gene, request.max_distance
                )

                if path:
                    result.append(
                        {
                            "source_gene": query_gene,
                            "target_gene": partner_gene,
                            "path": path,
                            "path_length": len(path) - 1,
                            "intermediate_genes": path[1:-1] if len(path) > 2 else [],
                        }
                    )

        # Sort by path length
        result = sorted(result, key=lambda x: x["path_length"])

        # Apply limit
        if request.limit:
            result = result[: request.limit]

        network_stats = {
            "paths_found": len(result),
            "max_path_length": max([r["path_length"] for r in result]) if result else 0,
            "min_path_length": min([r["path_length"] for r in result]) if result else 0,
        }

        return GeneInteractionResponse(
            analysis_type=request.analysis_type.value,
            query_genes=request.genes,
            interaction_database=request.interaction_database.value,
            total_interactions=len(interactions),
            network_stats=network_stats,
            limit=request.limit,
            result=result,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Shortest path analysis failed: {str(e)}"
        )


async def _find_common_interaction_partners(
    db, request: GeneInteractionRequest
) -> GeneInteractionResponse:
    """
    Find common interaction partners for query genes.
    """
    try:
        # Get interactions
        interactions = _get_gene_interactions_from_db(
            db,
            request.genes,
            request.interaction_type.value
            if request.interaction_type != InteractionType.all
            else None,
            request.min_confidence,
        )

        # Build network
        network, edge_props = _build_interaction_network(interactions)

        # Find common partners
        common_partners_dict = _find_common_partners(network, request.genes)

        # Build result
        result = []
        for partner, connected_genes in common_partners_dict.items():
            result.append(
                {
                    "common_partner": partner,
                    "shared_by": connected_genes,
                    "shared_count": len(connected_genes),
                }
            )

        # Sort by number of connections
        result = sorted(result, key=lambda x: x["shared_count"], reverse=True)

        # Apply limit
        if request.limit:
            result = result[: request.limit]

        network_stats = {
            "total_common_partners": len(common_partners_dict),
            "query_genes": request.genes,
        }

        return GeneInteractionResponse(
            analysis_type=request.analysis_type.value,
            query_genes=request.genes,
            interaction_database=request.interaction_database.value,
            total_interactions=len(interactions),
            total_partners=len(common_partners_dict),
            network_stats=network_stats,
            limit=request.limit,
            result=result,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Common partners analysis failed: {str(e)}"
        )


# ==========================================
# MAIN API FUNCTION
# ==========================================


async def gene_interaction_retriever(
    request: GeneInteractionRequest, db
) -> GeneInteractionResponse:
    """
    Retrieve gene-gene and protein-protein interactions.

    Supports multiple analysis types:
    1. direct_partners: Get direct interaction partners
    2. network_neighbors: Multi-hop network neighborhood
    3. shortest_path: Find shortest path between genes
    4. common_partners: Find shared interaction partners

    Args:
        request: GeneInteractionRequest with analysis parameters
        db: Database session

    Returns:
        GeneInteractionResponse with interaction data

    Database Schema:
    ----------------
    Assumes a gene_interaction table with columns:
    - gene_a: Gene symbol (STRING)
    - gene_b: Gene symbol (STRING)
    - interaction_type: Type of interaction (STRING)
    - confidence_score: Confidence (0-1) (FLOAT)
    - source_database: Database source (STRING)
    - experimental_evidence: Boolean (BOOLEAN)

    Example Requests:
    -----------------

    1. Get Direct Partners for TP53:
    {
      "genes": ["TP53"],
      "analysis_type": "direct_partners",
      "interaction_type": "physical",
      "min_confidence": 0.7,
      "limit": 50
    }

    2. Find Network Neighborhood:
    {
      "genes": ["TP53", "MDM2", "CDKN1A"],
      "analysis_type": "network_neighbors",
      "max_distance": 2,
      "interaction_type": "all",
      "limit": 100
    }

    3. Shortest Path Between Genes:
    {
      "genes": ["TP53"],
      "partner_genes": ["BRCA1", "ATM"],
      "analysis_type": "shortest_path",
      "max_distance": 3
    }

    4. Common Interaction Partners:
    {
      "genes": ["TP53", "BRCA1", "ATM"],
      "analysis_type": "common_partners",
      "min_confidence": 0.5,
      "limit": 20
    }
    """

    try:
        # Route to appropriate analysis
        if request.analysis_type == NetworkAnalysisType.direct_partners:
            return await _get_direct_partners(db, request)

        elif request.analysis_type == NetworkAnalysisType.network_neighbors:
            return await _get_network_neighbors(db, request)

        elif request.analysis_type == NetworkAnalysisType.shortest_path:
            return await _find_shortest_paths(db, request)

        elif request.analysis_type == NetworkAnalysisType.common_partners:
            return await _find_common_interaction_partners(db, request)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported analysis type: {request.analysis_type}",
            )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gene interaction retrieval failed: {str(e)}"
        )


# ==========================================
# EXAMPLE USAGE
# ==========================================

"""
Example Integration in FastAPI Router:
---------------------------------------

from gene_interaction_retriever import (
    gene_interaction_retriever,
    GeneInteractionRequest,
    GeneInteractionResponse
)

@router.post("/gene_interaction_retriever", response_model=GeneInteractionResponse)
async def retrieve_interactions(
    request: GeneInteractionRequest,
    db: Session = Depends(get_db)
):
    return await gene_interaction_retriever(request, db)


Database Setup:
---------------

CREATE TABLE gene_interaction (
    id INTEGER PRIMARY KEY,
    gene_a VARCHAR(50) NOT NULL,
    gene_b VARCHAR(50) NOT NULL,
    interaction_type VARCHAR(50),
    confidence_score FLOAT,
    source_database VARCHAR(50),
    experimental_evidence BOOLEAN DEFAULT FALSE,
    INDEX idx_gene_a (gene_a),
    INDEX idx_gene_b (gene_b)
);

# SQLAlchemy Model:
class GeneInteraction(Base):
    __tablename__ = "gene_interaction"

    id = Column(Integer, primary_key=True)
    gene_a = Column(String(50), nullable=False, index=True)
    gene_b = Column(String(50), nullable=False, index=True)
    interaction_type = Column(String(50))
    confidence_score = Column(Float)
    source_database = Column(String(50))
    experimental_evidence = Column(Boolean, default=False)
"""
