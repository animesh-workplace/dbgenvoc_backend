from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
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
    Unified genomic filter:
    - Multiple positions and/or ranges
    - OR logic across positions
    - Optional pathway filter
    """

    positions: Optional[List[GenomicRegion]] = None
    pathway: Optional[str] = None

    @field_validator("positions")
    @classmethod
    def validate_positions(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("positions cannot be empty")
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


def _apply_genomic_position_filter(query, model, genomic_filter):
    if not genomic_filter:
        return query

    chr_col = getattr(model, "chrom", None)
    pos_col = getattr(model, "start", None)
    end_col = getattr(model, "end", None)

    if not chr_col or not pos_col:
        raise HTTPException(
            400,
            "Dataset must contain 'chrom' and 'start' columns for genomic filtering",
        )

    conditions = []

    if genomic_filter.positions:
        for region in genomic_filter.positions:
            norm = _normalize_chromosome(region.chromosome)

            chrom_cond = or_(
                chr_col == norm,
                chr_col == f"chr{norm}",
                chr_col == region.chromosome,
            )

            if region.end:
                if end_col:
                    pos_cond = and_(
                        pos_col <= region.end,
                        end_col >= region.start,
                    )
                else:
                    pos_cond = and_(
                        pos_col >= region.start,
                        pos_col <= region.end,
                    )
            else:
                pos_cond = pos_col == region.start

            conditions.append(and_(chrom_cond, pos_cond))

    if conditions:
        query = query.filter(or_(*conditions))

    if genomic_filter.pathway:
        for col in ["pathway", "pathway_name", "kegg_pathway", "reactome_pathway"]:
            if hasattr(model, col):
                query = query.filter(
                    getattr(model, col).ilike(f"%{genomic_filter.pathway}%")
                )
                break

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
