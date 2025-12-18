from app.core import get_model_class
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Any
import re

# ==========================================
#               SCHEMAS
# ==========================================


class BulkValidateRequest(BaseModel):
    items: List[str] = Field(
        ..., description="List of raw strings (genes, regions, pathways) to validate"
    )


class SearchItem(BaseModel):
    label: str
    type: str  # 'gene', 'pathway', or 'region'
    value: str
    pathway_genes: Optional[List[str]] = Field(
        None, description="List of genes if type is 'pathway'"
    )


# ==========================================
#               MAIN API FUNCTION
# ==========================================

# Pre-compile Regex for performance
REGION_PATTERN = re.compile(r"^chr([0-9]{1,2}|[XYM]):[0-9]+(-[0-9]+)?$", re.IGNORECASE)


async def validate_bulk_items(
    request: BulkValidateRequest, db: Session
) -> List[SearchItem]:
    """
    Validates a list of input strings against Genes, Pathways, and Genomic Regions.
    Returns a list of valid, structured objects.
    """
    try:
        # 1. Resolve Model Classes dynamically
        # keys match your get_model_class registry logic
        GeneModel = get_model_class("genelist")
        PathwayModel = get_model_class("pathway")

        # 2. Pre-process Input
        # Deduplicate and strip whitespace
        raw_items = list(set([item.strip() for item in request.items if item.strip()]))

        valid_results = []
        items_to_query_db = []

        # 3. Fast Validation: Check for Genomic Regions (No DB needed)
        for item in raw_items:
            if REGION_PATTERN.match(item):
                valid_results.append(SearchItem(label=item, value=item, type="region"))
            else:
                # If not a region, queue it for DB lookup (convert to Upper for consistency)
                items_to_query_db.append(item.upper())

        if not items_to_query_db:
            return valid_results

        # 4. Query Database - Genes
        # We check if the items exist in the Genelist table
        found_genes = (
            db.query(GeneModel).filter(GeneModel.gene.in_(items_to_query_db)).all()
        )

        # Add found genes to results
        for record in found_genes:
            valid_results.append(
                SearchItem(label=record.gene, value=record.gene, type="gene")
            )

        # 5. Query Database - Pathways
        # We check if the items exist in the Pathway table
        # Note: Assuming PathwayModel has a 'name' column and 'genes' relationship
        found_pathways = (
            db.query(PathwayModel)
            .filter(PathwayModel.name.in_(items_to_query_db))
            .all()
        )

        # Add found pathways to results
        for record in found_pathways:
            # Extract related genes for the frontend logic
            associated_genes = [g.gene for g in record.genes]

            valid_results.append(
                SearchItem(
                    label=record.name,
                    value=record.name,
                    type="pathway",
                    pathway_genes=associated_genes,
                )
            )

        return valid_results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to validate bulk items: {str(e)}"
        )
