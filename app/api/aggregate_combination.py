from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.abstract import Genelist, Pathway, pathway_gene_association
from app.core import get_model_class, apply_filters, validate_columns
from app.schema_new import ComplexFilter, HavingClause, HavingCondition


# ======================================================
# AGGREGATION SCHEMAS
# ======================================================


class AggregationType(str, Enum):
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"
    count = "count"
    percentage = "percentage"
    distinct_count = "distinct_count"


class OrderDirection(str, Enum):
    asc = "asc"
    desc = "desc"


class ComputedFieldType(str, Enum):
    concat = "concat"


class GenomicRegion(BaseModel):
    chromosome: str
    start: int = Field(..., ge=1)
    end: Optional[int] = Field(None, ge=1)

    @field_validator("end")
    @classmethod
    def validate_end(cls, v, info):
        if v is not None and v < info.data.get("start"):
            raise ValueError("end must be >= start")
        return v


class GenomicPositionFilter(BaseModel):
    """
    Genomic position filtering - unified approach.
    """

    positions: Optional[List[GenomicRegion]] = Field(
        None,
        description=(
            "List of genomic positions or ranges. "
            "Can mix exact positions (start only) and ranges (start + end). "
            "All conditions combined with OR logic - matches ANY position/range."
        ),
    )

    pathway_ids: Optional[List[str]] = Field(
        None,
        description=(
            "Filter by exact pathway IDs from autocomplete. "
            "Example: ['hsa04151', 'hsa04115'] for KEGG pathways"
        ),
    )

    pathway_names: Optional[List[str]] = Field(
        None,
        description=(
            "Filter by pathway names (case-insensitive partial match). "
            "Returns variants in genes associated with ANY of the specified pathways. "
            "Examples: ['PI3K-AKT signaling', 'TP53 pathway'] or ['DNA repair']"
        ),
    )

    @field_validator("pathway_names")
    @classmethod
    def validate_pathway_names_not_empty(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("pathway_names list cannot be empty")
        return v


class ComputedField(BaseModel):
    name: str
    type: ComputedFieldType = ComputedFieldType.concat
    columns: List[str]
    separator: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v.isidentifier():
            raise ValueError("Computed field name must be a valid identifier")
        return v


class ConcatenatedAggregationRequest(BaseModel):
    aggregate_column: str
    limit: Optional[int] = None
    combination_columns: List[str]
    having: Optional[HavingClause] = None
    filters: Optional[ComplexFilter] = None
    percentage_by: Optional[List[str]] = None
    order_by: Optional[Union[str, List[str]]] = None
    order_direction: OrderDirection = OrderDirection.desc
    computed_fields: Optional[List[ComputedField]] = None
    genomic_filter: Optional[GenomicPositionFilter] = None
    aggregation_type: AggregationType = AggregationType.count

    @field_validator("percentage_by")
    @classmethod
    def validate_percentage_by(cls, v, info):
        if v:
            combo = info.data.get("combination_columns")
            if not combo or not set(v).issubset(combo):
                raise ValueError("percentage_by must be subset of combination_columns")
        return v


class ConcatenatedAggregationResponse(BaseModel):
    table_name: str
    total_records: int
    limit: Optional[int]
    aggregation_type: str
    aggregate_column: str
    total_combinations: int
    results: List[Dict[str, Any]]
    combination_columns: List[str]
    order_direction: Optional[str]
    order_by: Optional[Union[str, List[str]]]


# ======================================================
# INTERNAL HELPERS
# ======================================================


def _normalize_chromosome(chrom: str) -> str:
    chrom = chrom.upper()
    return chrom[3:] if chrom.startswith("CHR") else chrom


def _apply_genomic_position_filter(
    query, model_class, genomic_filter: Optional[GenomicPositionFilter]
):
    """
    Apply genomic position filtering to query.

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

    Examples:
        # Query matches variants that satisfy ANY of:
        # - In chr17:7571000-7572000 (regulatory region)
        # - At chr17:7577538 (R175H hotspot)
        # - At chr17:7578406 (R248Q hotspot)
    """
    if not genomic_filter:
        return query

    # Detect chromosome and position column names in the dataset
    chr_col_name = "chrom"
    pos_col_name = "start"
    end_col_name = "end"

    # Validate required columns exist
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
            # Handles: 'chr17', '17', 'CHR17' all match chromosome '17' or 'chr17' in DB
            chrom_cond = or_(
                chr_col == norm_chrom,
                chr_col == f"chr{norm_chrom}",
                chr_col == region.chromosome,
                chr_col == region.chromosome.upper(),
                chr_col == region.chromosome.lower(),
            )

            if region.end:
                # Range query: find overlapping variants
                if end_col:
                    # Dataset has end column - check for overlap
                    # Variants overlap region if: variant.start <= region.end AND variant.end >= region.start
                    pos_cond = and_(pos_col <= region.end, end_col >= region.start)
                else:
                    # Dataset only has start position - check if start is within range
                    pos_cond = and_(pos_col >= region.start, pos_col <= region.end)
            else:
                # Exact position match
                pos_cond = pos_col == region.start

            # Combine chromosome and position conditions
            conditions.append(and_(chrom_cond, pos_cond))

    # Apply all genomic conditions with OR logic
    if conditions:
        if len(conditions) == 1:
            query = query.filter(conditions[0])
        else:
            # Match ANY position/range
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


def _build_having_filter(having: HavingClause, agg_expr):
    conditions = []

    for c in having.conditions:
        if isinstance(c, HavingCondition):
            op = c.operator
            val = c.value
            if op == "eq":
                conditions.append(agg_expr == val)
            elif op == "neq":
                conditions.append(agg_expr != val)
            elif op == "gt":
                conditions.append(agg_expr > val)
            elif op == "gte":
                conditions.append(agg_expr >= val)
            elif op == "lt":
                conditions.append(agg_expr < val)
            elif op == "lte":
                conditions.append(agg_expr <= val)
        else:
            conditions.append(_build_having_filter(c, agg_expr))

    return and_(*conditions) if having.logic == "AND" else or_(*conditions)


def _apply_computed_fields(rows, computed_fields):
    if not computed_fields:
        return rows

    for row in rows:
        for field in computed_fields:
            if field.type == ComputedFieldType.concat:
                row[field.name] = field.separator.join(
                    "" if row.get(c) is None else str(row.get(c)) for c in field.columns
                )
    return rows


# ======================================================
# MAIN API
# ======================================================


async def generic_concatenated_aggregate(
    request: ConcatenatedAggregationRequest,
    db,
    table_name: str,
) -> ConcatenatedAggregationResponse:
    try:
        model = get_model_class(table_name)

        validate_columns(model, request.combination_columns)
        validate_columns(model, [request.aggregate_column])

        agg_col = getattr(model, request.aggregate_column)
        group_attrs = [getattr(model, c) for c in request.combination_columns]

        query = db.query(model)
        query = apply_filters(query, model, request.filters)
        query = _apply_genomic_position_filter(query, model, request.genomic_filter)

        total_records = query.count()

        # Aggregation expression
        if request.aggregation_type == AggregationType.count:
            agg_expr = func.count(agg_col)
        elif request.aggregation_type == AggregationType.distinct_count:
            agg_expr = func.count(func.distinct(agg_col))
        elif request.aggregation_type == AggregationType.percentage:
            agg_expr = (func.count(agg_col) * 100.0) / (
                total_records if total_records else 1
            )
        else:
            raise HTTPException(400, "Unsupported aggregation type")

        grouped_query = query.with_entities(
            *group_attrs,
            agg_expr.label("aggregated_value"),
        ).group_by(*group_attrs)

        total_combinations = (
            db.query(func.count()).select_from(grouped_query.subquery()).scalar() or 0
        )

        if request.having:
            grouped_query = grouped_query.having(
                _build_having_filter(request.having, agg_expr)
            )

        if request.order_by:

            def order(x):
                return (
                    x.desc()
                    if request.order_direction == OrderDirection.desc
                    else x.asc()
                )

            if request.order_by == "aggregated_value":
                grouped_query = grouped_query.order_by(order(agg_expr))
            else:
                idx = request.combination_columns.index(request.order_by)
                grouped_query = grouped_query.order_by(order(group_attrs[idx]))

        if request.limit:
            grouped_query = grouped_query.limit(request.limit)

        rows = grouped_query.all()

        results = []
        for row in rows:
            item = {}
            for i, col in enumerate(request.combination_columns):
                item[col] = row[i]
            item["aggregated_value"] = row[-1]
            results.append(item)

        results = _apply_computed_fields(results, request.computed_fields)

        return ConcatenatedAggregationResponse(
            results=results,
            limit=request.limit,
            table_name=table_name,
            order_by=request.order_by,
            total_records=total_records,
            total_combinations=total_combinations,
            aggregate_column=request.aggregate_column,
            order_direction=request.order_direction.value,
            aggregation_type=request.aggregation_type.value,
            combination_columns=request.combination_columns,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Combination aggregation failed: {str(e)}")
