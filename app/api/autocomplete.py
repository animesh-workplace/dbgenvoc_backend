from enum import Enum
from fastapi import HTTPException
from app.core import get_model_class
from sqlalchemy.orm import joinedload
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, or_, cast
from typing import List, Optional, Dict, Any, Union


class SuggestionType(str, Enum):
    GENE = "gene"
    PATHWAY = "pathway"
    GENOMIC_REGION = "genomic_region"


class SuggestionGeneItem(BaseModel):
    value: str
    type: SuggestionType = SuggestionType.GENE


class SuggestionPathwayItem(BaseModel):
    value: str
    pathway_genes: Optional[List[str]] = None
    type: SuggestionType = SuggestionType.PATHWAY


class SuggestionPositionItem(BaseModel):
    value: str
    end: Optional[int] = None
    start: Optional[int] = None
    chromosome: Optional[str] = None
    type: SuggestionType = SuggestionType.GENOMIC_REGION


class SuggestionSection(BaseModel):
    label: str
    items: Union[
        List[SuggestionGeneItem],
        List[SuggestionPathwayItem],
        List[SuggestionPositionItem],
    ]


async def unified_autocomplete(db, term: str, limit: int = 10):
    """Unified autocomplete for genes, pathways, and genomic regions"""
    try:
        if not term or len(term.strip()) < 2:
            raise HTTPException(
                status_code=400, detail="Search term must be at least 2 characters long"
            )

        # Fetching genes from the Genes DB
        Genelist = get_model_class("genelist")
        gene_results = (
            db.query(Genelist.gene)
            .filter(Genelist.gene.ilike(f"{term}%"))
            .order_by(Genelist.gene)
            .limit(limit)
            .all()
        )
        gene_suggestions = [SuggestionGeneItem(value=gene[0]) for gene in gene_results]

        # Fetching pathway from the Pathways DB
        Pathway = get_model_class("pathway")
        pathway_results = (
            db.query(Pathway)
            .options(joinedload(Pathway.genes))
            .filter(Pathway.pathway_name.ilike(f"{term}%"))
            .order_by(Pathway.pathway_name)
            .limit(limit)
            .all()
        )
        pathway_suggestion = [
            SuggestionPathwayItem(
                pathway_genes=[gene.gene for gene in pathway.genes],
                value=pathway.pathway_name,
                type=SuggestionType.PATHWAY,
            )
            for pathway in pathway_results
        ]

        # Fetching chromosome position from the genomic positions DB
        GenomicPosition = get_model_class("somatic_genomic_position")
        genomic_suggestions = []
        clean_term = term.strip()

        # If user provided a chrom:part
        if ":" in clean_term:
            chrom, coords_part = clean_term.split(":", 1)
            chrom = chrom.strip()
            coords_part = coords_part.strip()

            # Range input: "chr1:915188-1015188"
            if "-" in coords_part:
                try:
                    start_str, end_str = coords_part.split("-", 1)
                    start_q = int(start_str.replace(",", "").strip())
                    end_q = int(end_str.replace(",", "").strip())

                    # Swap if reversed
                    if end_q < start_q:
                        start_q, end_q = end_q, start_q

                    # Find records that overlap the queried range:
                    # record.end >= start_q AND record.start <= end_q
                    query = (
                        db.query(GenomicPosition)
                        .filter(
                            and_(
                                GenomicPosition.chromosome.ilike(f"{chrom}%"),
                                GenomicPosition.end >= start_q,
                                GenomicPosition.start <= end_q,
                            )
                        )
                        .order_by(GenomicPosition.start)
                        .limit(limit)
                    )
                    results = query.all()

                    genomic_suggestions = [
                        SuggestionPositionItem(
                            end=r.end,
                            start=r.start,
                            chromosome=r.chromosome,
                            value=f"{r.chromosome}:{r.start}-{r.end}",
                        )
                        for r in results
                    ]
                except ValueError:
                    # malformed numbers — return no suggestions for genomic region
                    genomic_suggestions = []

            # Single numeric coordinate: "chr1:915188" -> find records that contain this position
            else:
                # If coords_part looks numeric, treat as position. Otherwise fallback to prefix-match on start.
                digits = coords_part.replace(",", "").strip()
                if digits.isdigit():
                    pos_q = int(digits)
                    query = (
                        db.query(GenomicPosition)
                        .filter(
                            and_(
                                GenomicPosition.chromosome.ilike(f"{chrom}%"),
                                GenomicPosition.start <= pos_q,
                                GenomicPosition.end >= pos_q,
                            )
                        )
                        .order_by(GenomicPosition.start)
                        .limit(limit)
                    )
                    results = query.all()

                    genomic_suggestions = [
                        SuggestionPositionItem(
                            end=r.end,
                            start=r.start,
                            chromosome=r.chromosome,
                            value=f"{r.chromosome}:{r.start}-{r.end}",
                        )
                        for r in results
                    ]
                else:
                    # Fallback: user typed something like chr1:915 (partial) — do prefix-match on start
                    query = (
                        db.query(GenomicPosition)
                        .filter(GenomicPosition.chromosome.ilike(f"{chrom}%"))
                        .filter(
                            cast(GenomicPosition.start, String).like(f"{coords_part}%")
                        )
                        .order_by(GenomicPosition.start)
                        .limit(limit)
                    )
                    results = query.all()
                    genomic_suggestions = [
                        SuggestionPositionItem(
                            end=r.end,
                            start=r.start,
                            chromosome=r.chromosome,
                            value=f"{r.chromosome}:{r.start}-{r.end}",
                        )
                        for r in results
                    ]

        # Only chromosome prefix: "chr1"
        else:
            query = (
                db.query(GenomicPosition)
                .filter(GenomicPosition.chromosome.ilike(f"{clean_term}%"))
                .order_by(GenomicPosition.count)
                .limit(limit)
            )
            results = query.all()
            genomic_suggestions = [
                SuggestionPositionItem(
                    end=r.end,
                    start=r.start,
                    chromosome=r.chromosome,
                    value=f"{r.chromosome}:{r.start}-{r.end}",
                )
                for r in results
            ]

        return [
            SuggestionSection(label="Genes", items=gene_suggestions),
            SuggestionSection(label="Pathways", items=pathway_suggestion),
            SuggestionSection(label="Genomic Regions", items=genomic_suggestions),
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Autocomplete search failed: {str(e)}"
        )
