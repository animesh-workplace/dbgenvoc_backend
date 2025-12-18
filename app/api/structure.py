import ast
from typing import Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core import get_model_class
from pydantic import BaseModel, Field

# ==========================================
#               SCHEMAS
# ==========================================


class StructureRequest(BaseModel):
    gene: str = Field(..., description="Target Gene Name (e.g. TP53)")
    # You can add more filters here later if needed (e.g., transcript_id)


class StructureResponse(BaseModel):
    gene: str
    accession_id: Optional[str]
    structure: Any  # Returns the raw structure JSON/Text


# ==========================================
#           MAIN API FUNCTION
# ==========================================


async def get_protein_structure(
    request: StructureRequest, db: Session
) -> StructureResponse:
    """
    Fetches the protein structure (domains, regions) for a specific gene
    from a dynamically specified table.
    """
    try:
        # 1. Resolve the Model Class dynamically
        model_class = get_model_class("uniprot_structure")

        # 2. Query the database
        # We assume the model has 'gene', 'accession_id', and 'structure' columns
        record = db.query(model_class).filter(model_class.gene == request.gene).first()

        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"No protein structure found for gene '{request.gene}' in table '{'uniprot_structure'}'",
            )

        # 3. Return the formatted response
        return StructureResponse(
            gene=record.gene,
            accession_id=record.accession_id,
            structure=ast.literal_eval(record.structure),
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch protein structure: {str(e)}"
        )
