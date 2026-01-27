from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.schema_new import ComplexFilter, HavingClause, HavingCondition


# ==========================================
# AGGREGATION SCHEMAS
# ==========================================


class GenomicRegion(BaseModel):
    """
    Single genomic region specification.

    Can represent either:
    - Exact position: Provide chromosome + start only
    - Range: Provide chromosome + start + end

    Examples:
        Exact position: {"chromosome": "chr17", "start": 7577538}
        Range: {"chromosome": "chr17", "start": 7577000, "end": 7579000}
    """

    chromosome: str = Field(
        ..., description="Chromosome name (e.g., 'chr1', '1', 'X', 'Y', 'MT')"
    )
    start: int = Field(..., ge=1, description="Start position (1-based, inclusive)")
    end: Optional[int] = Field(
        None,
        ge=1,
        description="End position (1-based, inclusive). Omit for exact position match.",
    )

    @field_validator("end")
    @classmethod
    def validate_end_after_start(cls, v, info):
        if v is not None:
            start = info.data.get("start")
            if start and v < start:
                raise ValueError("end must be >= start")
        return v


class GenomicPositionFilter(BaseModel):
    """
    Genomic position filtering - unified approach.

    All genomic locations (ranges and exact positions) are specified in the
    'positions' field. All conditions are combined with OR logic.

    Features:
    - Mix ranges and exact positions freely
    - Multiple chromosomes in one query
    - Natural OR logic (match ANY position/range)
    - Optional pathway filtering

    Examples:
        # Single range
        {"positions": [{"chromosome": "chr17", "start": 7577000, "end": 7579000}]}

        # Multiple exact positions
        {"positions": [
            {"chromosome": "chr17", "start": 7577538},
            {"chromosome": "chr17", "start": 7578406}
        ]}

        # Mixed ranges and positions
        {"positions": [
            {"chromosome": "chr17", "start": 7571000, "end": 7572000},  # Regulatory region
            {"chromosome": "chr17", "start": 7577538},                   # R175H hotspot
            {"chromosome": "chr17", "start": 7578406}                    # R248Q hotspot
        ]}
    """

    positions: Optional[List[GenomicRegion]] = Field(
        None,
        description=(
            "List of genomic positions or ranges. "
            "Can mix exact positions (start only) and ranges (start + end). "
            "All conditions combined with OR logic - matches ANY position/range."
        ),
    )

    pathway: Optional[str] = Field(
        None,
        description=(
            "Filter by pathway name (case-insensitive partial match). "
            "Examples: 'PI3K-AKT', 'TP53 pathway', 'DNA repair'"
        ),
    )

    @field_validator("positions")
    @classmethod
    def validate_positions_not_empty(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("positions list cannot be empty")
        return v


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


class AggregationRequest(BaseModel):
    column: str = Field(..., description="Target column for aggregation")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")

    percentage_by: Optional[List[str]] = Field(
        None, description="Columns to calculate percentage against (denominator scope)"
    )

    filters: Optional[ComplexFilter] = Field(
        None, description="Complex filters with AND/OR logic (applied before GROUP BY)"
    )

    # --- Genomic Position Filters (UNIFIED) ---
    genomic_filter: Optional[GenomicPositionFilter] = Field(
        None,
        description="Filter by genomic positions/ranges or pathway (applied before GROUP BY)",
    )

    aggregation_type: AggregationType = Field(
        AggregationType.count, description="Type of aggregation"
    )

    having: Optional[HavingClause] = Field(
        None,
        description="HAVING clause to filter aggregated results (applied after GROUP BY)",
    )

    order_by: Optional[Union[str, List[str]]] = Field(
        None,
        description="Column(s) to order results by. Use 'aggregated_value' for ordering by the aggregation result.",
    )

    order_direction: OrderDirection = Field(
        OrderDirection.desc, description="Order direction: asc or desc"
    )

    limit: Optional[int] = Field(
        None, description="Limit the number of results returned"
    )

    @field_validator("having")
    @classmethod
    def validate_having_requires_group_by(cls, v, info):
        if v is not None and not info.data.get("group_by"):
            raise ValueError("HAVING clause requires group_by to be specified")
        return v

    @field_validator("percentage_by")
    @classmethod
    def validate_percentage_by(cls, v, info):
        if v:
            group_by = info.data.get("group_by")
            if not group_by or not set(v).issubset(set(group_by)):
                raise ValueError(
                    "percentage_by columns must be present in group_by columns"
                )
        return v

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, v, info):
        if v is not None and not info.data.get("group_by"):
            if isinstance(v, str) and v != "aggregated_value":
                raise ValueError(
                    "For scalar aggregations (without group_by), order_by must be 'aggregated_value' or None"
                )
            elif isinstance(v, list):
                raise ValueError(
                    "For scalar aggregations (without group_by), order_by cannot be a list"
                )
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v < 1:
            raise ValueError("Limit must be greater than 0")
        return v


class AggregationResponse(BaseModel):
    column: str
    table_name: str
    total_records: int
    aggregation_type: str
    limit: Optional[int] = None
    order_direction: Optional[str] = None
    groups_after_having: Optional[int] = None
    groups_before_having: Optional[int] = None
    group_totals: Optional[Dict[str, int]] = None
    order_by: Optional[Union[str, List[str]]] = None
    result: Union[Dict[str, Any], List[Dict[str, Any]]]


# ==========================================
# INTERNAL HELPERS
# ==========================================


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

    # Apply pathway filter
    if genomic_filter.pathway:
        pathway_col_name = None
        for col in ["pathway", "pathway_name", "kegg_pathway", "reactome_pathway"]:
            if hasattr(model_class, col):
                pathway_col_name = col
                break

        if pathway_col_name:
            pathway_col = getattr(model_class, pathway_col_name)
            query = query.filter(pathway_col.ilike(f"%{genomic_filter.pathway}%"))
        else:
            import warnings

            warnings.warn(
                f"Pathway filter '{genomic_filter.pathway}' specified but no pathway column found"
            )

    return query


async def _calculate_standard_agg(query, col_attr, agg_type: AggregationType):
    """Handles standard scalar aggregations."""
    funcs = {
        AggregationType.sum: func.sum(col_attr),
        AggregationType.avg: func.avg(col_attr),
        AggregationType.min: func.min(col_attr),
        AggregationType.max: func.max(col_attr),
        AggregationType.count: func.count(col_attr),
        AggregationType.distinct_count: func.count(func.distinct(col_attr)),
    }
    return query.with_entities(funcs[agg_type]).scalar() or 0


async def _calculate_global_percentage(query, db, model_class, col_attr):
    """Calculates percentage for non-grouped queries."""
    numerator = query.with_entities(func.count(col_attr)).scalar() or 0
    denominator = db.query(func.count(col_attr)).select_from(model_class).scalar() or 1
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


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


def _apply_ordering(
    query, order_by, order_direction, group_attrs, agg_expr, group_by_columns
):
    """Apply ordering to the query."""
    order_clauses = []

    def add_order_clause(column_expr):
        if order_direction == OrderDirection.desc:
            return column_expr.desc()
        else:
            return column_expr.asc()

    if order_by:
        if isinstance(order_by, str):
            if order_by == "aggregated_value":
                order_clauses.append(add_order_clause(agg_expr))
            elif order_by in group_by_columns:
                idx = group_by_columns.index(order_by)
                order_clauses.append(add_order_clause(group_attrs[idx]))
            else:
                raise ValueError(
                    f"Cannot order by '{order_by}'. Must be 'aggregated_value' or one of group_by columns: {group_by_columns}"
                )
        else:
            for order_col in order_by:
                if order_col == "aggregated_value":
                    order_clauses.append(add_order_clause(agg_expr))
                elif order_col in group_by_columns:
                    idx = group_by_columns.index(order_col)
                    order_clauses.append(add_order_clause(group_attrs[idx]))
                else:
                    raise ValueError(
                        f"Cannot order by '{order_col}'. Must be 'aggregated_value' or one of group_by columns: {group_by_columns}"
                    )

    if order_clauses:
        query = query.order_by(*order_clauses)

    return query


# ==========================================
# MAIN AGGREGATION API
# ==========================================


async def generic_aggregate(
    request: AggregationRequest, db, table_name: str
) -> AggregationResponse:
    """
    Enhanced generic aggregation endpoint with unified genomic position filtering.

    Query execution order:
    1. FROM table_name
    2. WHERE (filters)
    3. WHERE (genomic_filter - unified positions/ranges)
    4. GROUP BY (group_by)
    5. HAVING (having clause on aggregated results)
    6. ORDER BY (order_by)
    7. LIMIT (limit)
    8. SELECT (final result)
    """
    try:
        from app.core import get_model_class, validate_columns, apply_filters

        model_class = get_model_class(table_name)

        # 1. Validation
        validate_columns(model_class, [request.column])
        if request.group_by:
            validate_columns(model_class, request.group_by)
        if request.percentage_by:
            validate_columns(model_class, request.percentage_by)

        col_attr = getattr(model_class, request.column)

        # 2. Build Query & Apply WHERE Filters
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        # 2b. Apply Genomic Position Filters (UNIFIED)
        query = _apply_genomic_position_filter(
            query, model_class, request.genomic_filter
        )

        # 3. Capture Total Records
        total_records = query.count()

        # 4. Perform Aggregation
        final_result = None
        group_totals_map = {}
        groups_before_having = None
        groups_after_having = None

        if request.group_by:
            # === GROUPED AGGREGATION ===
            group_attrs = [getattr(model_class, c) for c in request.group_by]
            group_by_columns = request.group_by
            extra_selects = []

            # Determine aggregation expression
            if request.aggregation_type == AggregationType.percentage:
                if request.percentage_by:
                    partition_attrs = [
                        getattr(model_class, c) for c in request.percentage_by
                    ]
                    denominator = func.sum(func.count(col_attr)).over(
                        partition_by=partition_attrs
                    )
                    agg_expr = (func.count(col_attr) * 100.0) / denominator
                    extra_selects.append(denominator.label("group_total"))
                else:
                    agg_expr = (func.count(col_attr) * 100.0) / (
                        total_records if total_records > 0 else 1
                    )
            else:
                funcs_map = {
                    AggregationType.count: func.count(col_attr),
                    AggregationType.sum: func.sum(col_attr),
                    AggregationType.avg: func.avg(col_attr),
                    AggregationType.min: func.min(col_attr),
                    AggregationType.max: func.max(col_attr),
                    AggregationType.distinct_count: func.count(func.distinct(col_attr)),
                }
                agg_expr = funcs_map.get(request.aggregation_type)

            # Build grouped query
            grouped_query = query.with_entities(
                *group_attrs, agg_expr.label("val"), *extra_selects
            ).group_by(*group_attrs)

            # Count groups before HAVING
            groups_before_having = (
                db.query(func.count()).select_from(grouped_query.subquery()).scalar()
            )

            # Apply HAVING
            if request.having:
                having_filter = _build_having_filter(request.having, agg_expr)
                grouped_query = grouped_query.having(having_filter)

            # Apply ORDER BY
            if request.order_by:
                grouped_query = _apply_ordering(
                    grouped_query,
                    request.order_by,
                    request.order_direction,
                    group_attrs,
                    agg_expr,
                    group_by_columns,
                )

            # Apply LIMIT
            if request.limit:
                grouped_query = grouped_query.limit(request.limit)

            # Execute Query
            results = grouped_query.all()
            groups_after_having = len(results)

            # Format Results
            formatted_results = []
            pct_indices = []
            if request.percentage_by:
                pct_indices = [group_by_columns.index(c) for c in request.percentage_by]

            for result in results:
                result_dict = {}

                for i, group_col in enumerate(group_by_columns):
                    result_dict[group_col] = result[i]

                val_index = len(group_by_columns)
                val = result[val_index]
                if (
                    request.aggregation_type == AggregationType.percentage
                    and val is not None
                ):
                    val = round(float(val), 2)
                result_dict["aggregated_value"] = val

                if request.aggregation_type == AggregationType.percentage:
                    if request.percentage_by:
                        total_val = result[val_index + 1]
                        key_parts = [str(result[idx]) for idx in pct_indices]
                        key = "|".join(key_parts)
                        group_totals_map[key] = int(total_val) if total_val else 0
                    else:
                        group_totals_map["global"] = total_records

                formatted_results.append(result_dict)

            final_result = formatted_results

        else:
            # === SCALAR AGGREGATION ===
            if request.aggregation_type == AggregationType.percentage:
                val = await _calculate_global_percentage(
                    query, db, model_class, col_attr
                )
                final_result = {"value": val}
                group_totals_map["global"] = total_records
            else:
                val = await _calculate_standard_agg(
                    query, col_attr, request.aggregation_type
                )
                final_result = {"value": val}

        return AggregationResponse(
            result=final_result,
            limit=request.limit,
            table_name=table_name,
            column=request.column,
            order_by=request.order_by,
            total_records=total_records,
            groups_after_having=groups_after_having,
            groups_before_having=groups_before_having,
            order_direction=request.order_direction.value,
            aggregation_type=request.aggregation_type.value,
            group_totals=group_totals_map if group_totals_map else None,
        )

    except HTTPException as he:
        raise he
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
