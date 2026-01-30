from typing import Optional
from fastapi import HTTPException
from sqlalchemy import func, and_, or_
from app.abstract import Genelist, Pathway, pathway_gene_association
from app.api.schema import (
    HavingClause,
    AggregationType,
    HavingCondition,
    GenomicPositionFilter,
)

_AGGREGATION_FUNCS = {
    AggregationType.sum: func.sum,
    AggregationType.avg: func.avg,
    AggregationType.min: func.min,
    AggregationType.max: func.max,
    AggregationType.count: func.count,
    AggregationType.distinct_count: lambda col: func.count(func.distinct(col)),
}


def _normalize_chromosome(chrom: str) -> str:
    """
    Normalize chromosome name for flexible matching.

    Examples:
        'chr1' -> '1'
        'CHR17' -> '17'
        '17' -> '17'
        'chrX' -> 'X'
    """
    if not chrom:
        return chrom
    chrom_str = str(chrom).upper()
    if chrom_str.startswith("CHR"):
        return chrom_str[3:]
    return chrom_str


def _apply_genomic_position_filter(
    query, model_class, genomic_filter: Optional[GenomicPositionFilter]
):
    """
    Apply genomic position filtering to query (unified approach).

    Features:
    1. Unified positions list - mix ranges and exact positions
    2. Flexible chromosome naming ('chr17' or '17')
    3. Overlap detection (if dataset has 'end' column)
    4. Exact position matching (if no 'end' column)
    5. Pathway filtering (if pathway column exists)
    6. OR logic - match ANY position/range

    Args:
        query: SQLAlchemy query
        model_class: Model class
        genomic_filter: GenomicPositionFilter object

    Returns:
        Filtered query
    """
    if not genomic_filter:
        return query

    # Detect chromosome and position column names in the dataset
    chr_col_name = "chrom"
    pos_col_name = "start"
    end_col_name = "end"

    if not chr_col_name or not pos_col_name:
        raise HTTPException(
            400,
            detail=(
                "Dataset must have chromosome and position columns for genomic filtering. "
                f"Found columns: {[c.name for c in model_class.__table__.columns]}"
            ),
        )

    chr_col = getattr(model_class, chr_col_name)
    pos_col = getattr(model_class, pos_col_name)
    end_col = getattr(model_class, end_col_name) if end_col_name else None

    # Build genomic position conditions
    conditions = []

    if genomic_filter.positions:
        for region in genomic_filter.positions:
            norm_chrom = _normalize_chromosome(region.chromosome)

            # Flexible chromosome matching
            chrom_cond = or_(
                chr_col == norm_chrom,
                chr_col == f"chr{norm_chrom}",
                chr_col == region.chromosome,
                chr_col == region.chromosome.upper(),
                chr_col == region.chromosome.lower(),
            )

            if region.end:
                # Range query
                if end_col:
                    # Overlap detection
                    pos_cond = and_(pos_col <= region.end, end_col >= region.start)
                else:
                    # Position within range
                    pos_cond = and_(pos_col >= region.start, pos_col <= region.end)
            else:
                # Exact position match
                pos_cond = pos_col == region.start

            conditions.append(and_(chrom_cond, pos_cond))

    # Apply all genomic conditions with OR logic
    if conditions:
        if len(conditions) == 1:
            query = query.filter(conditions[0])
        else:
            query = query.filter(or_(*conditions))

    # Apply pathway filter (independent of positions)
    if genomic_filter.pathway_names:
        query = (
            query.join(Genelist, model_class.gene == Genelist.gene)
            .join(
                pathway_gene_association,
                Genelist.gene == pathway_gene_association.c.gene,
            )
            .join(
                Pathway,
                pathway_gene_association.c.pathway_id == Pathway.id,
            )
            .filter(Pathway.pathway_name.in_(genomic_filter.pathway_names))
            .distinct()
        )

    # Apply pathway filter with exact ID matching
    if genomic_filter.pathway_ids:
        query = (
            query.join(Genelist, model_class.gene == Genelist.gene)
            .join(
                pathway_gene_association,
                Genelist.gene == pathway_gene_association.c.gene,
            )
            .filter(
                pathway_gene_association.c.pathway_id.in_(genomic_filter.pathway_ids)
            )
            .distinct()
        )

    return query


def _build_having_filter(having_clause: HavingClause, agg_expr):
    """Recursively builds SQLAlchemy HAVING conditions."""
    conditions = []

    for condition in having_clause.conditions:
        if isinstance(condition, HavingCondition):
            if condition.operator == "eq":
                conditions.append(agg_expr == condition.value)
            elif condition.operator == "neq":
                conditions.append(agg_expr != condition.value)
            elif condition.operator == "gt":
                conditions.append(agg_expr > condition.value)
            elif condition.operator == "gte":
                conditions.append(agg_expr >= condition.value)
            elif condition.operator == "lt":
                conditions.append(agg_expr < condition.value)
            elif condition.operator == "lte":
                conditions.append(agg_expr <= condition.value)
        else:
            conditions.append(_build_having_filter(condition, agg_expr))

    if having_clause.logic == "AND":
        return and_(*conditions)
    else:
        return or_(*conditions)
