from fastapi import HTTPException
from app.core import get_model_class
from app.schema import AutocompleteSuggestion


async def unified_autocomplete(
    db,
    term: str,
    limit: int = 10,
):
    """Unified autocomplete returning genes and pathways with pathway_genes"""
    try:
        if not term or len(term.strip()) < 2:
            raise HTTPException(
                status_code=400, detail="Search term must be at least 2 characters long"
            )

        suggestions = []

        # Search in Genelist table (genes)
        Genelist = get_model_class("genelist")
        gene_results = (
            db.query(Genelist.gene)
            .filter(Genelist.gene.ilike(f"{term}%"))
            .order_by(Genelist.gene)
            .limit(limit)
            .all()
        )

        for gene in gene_results:
            suggestions.append(AutocompleteSuggestion(value=gene[0], type="gene"))

        # Search in Pathway table (pathway IDs only)
        Pathway = get_model_class("pathway")
        pathway_results = (
            db.query(Pathway.pathway_name, Pathway.path_gene)
            .filter(Pathway.pathway_name.ilike(f"{term}%"))
            .order_by(Pathway.path_id)
            .limit(limit)
            .all()
        )

        for pathway_name, path_gene in pathway_results:
            print(pathway_name, path_gene)
            suggestions.append(
                AutocompleteSuggestion(
                    value=pathway_name, type="pathway", pathway_genes=path_gene
                )
            )

        # Sort alphabetically and apply limit
        suggestions.sort(key=lambda x: x.value)
        return {"suggestions": suggestions}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Autocomplete search failed: {str(e)}"
        )
