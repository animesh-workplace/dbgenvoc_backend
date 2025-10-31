from fastapi import HTTPException
from app.utils import (
    # parse_genomic_region,
    # search_genomic_regions,
    search_genes_and_pathways,
    # search_partial_genomic_region,
)


async def unified_autocomplete(db, term: str, limit: int = 10):
    """Unified autocomplete for genes, pathways, and genomic regions"""
    try:
        if not term or len(term.strip()) < 2:
            raise HTTPException(
                status_code=400, detail="Search term must be at least 2 characters long"
            )

        suggestions = []

        # First, check if it's a genomic region
        # parsed_region = parse_genomic_region(term)
        # print(parsed_region)
        # if parsed_region:
        #     # Search for genomic regions
        #     genomic_suggestions = await search_genomic_regions(parsed_region, limit, db)
        #     print(genomic_suggestions)
        #     suggestions.extend(genomic_suggestions)
        # else:
        #     # Search for partial genomic regions (chromosome names)
        #     partial_genomic_suggestions = await search_partial_genomic_region(
        #         term, limit, db
        #     )
        #     suggestions.extend(partial_genomic_suggestions)

        # Always search for genes and pathways
        gene_pathway_suggestions = await search_genes_and_pathways(term, limit, db)
        suggestions.extend(gene_pathway_suggestions)

        # Sort alphabetically and apply limit
        suggestions.sort(key=lambda x: x.value)
        return {"suggestions": suggestions}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Autocomplete search failed: {str(e)}"
        )
