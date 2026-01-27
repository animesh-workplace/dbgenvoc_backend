"""
aggregate_combination.py

Enhanced concatenated aggregation API with genomic position and pathway filtering.

Features:
- Concatenate multiple columns (e.g., Ref→Alt for TiTv analysis)
- Count, percentage, distinct_count aggregations
- Genomic position filtering (ranges and specific positions)
- Pathway filtering
- Scoped percentages (percentage_by)
- HAVING clause for post-aggregation filtering
- Multi-column ORDER BY
- LIMIT support

Author: Generated for dbGENVOC API
Date: 2026-01-27
Version: 2.0 (With Genomic Position Filtering)
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.schema_new import ComplexFilter, HavingClause, HavingCondition
from app.core import (
    apply_filters,
    get_model_class,
    validate_columns,
    _build_filter_expression,
)


# ==========================================
# GENOMIC POSITION SCHEMAS
# ==========================================

class GenomicRegion(BaseModel):
    """Single genomic region specification"""
    chromosome: str = Field(..., description="Chromosome (e.g., 'chr1', '1', 'X')")
    start: int = Field(..., ge=1, description="Start position (1-based, inclusive)")
    end: Optional[int] = Field(None, ge=1, description="End position (1-based, inclusive)")

    @field_validator("end")
    @classmethod
    def validate_end_after_start(cls, v, info):
        if v is not None:
            start = info.data.get("start")
            if start and v < start:
                raise ValueError("end must be >= start")
        return v


class GenomicPositionFilter(BaseModel):
    """Genomic position filtering - supports ranges and specific positions"""

    # Option 1: Single range [chr1:915188-1015188]
    region: Optional[GenomicRegion] = Field(
        None,
        description="Single genomic region (chr + start + optional end)"
    )

    # Option 2: Multiple specific positions [chr11:534289, chr17:7578406]
    positions: Optional[List[GenomicRegion]] = Field(
        None,
        description="List of specific genomic positions or regions"
    )

    # Pathway filter (optional)
    pathway: Optional[str] = Field(
        None,
        description="Filter by pathway name (e.g., 'PI3K-AKT', 'TP53 pathway')"
    )

    @field_validator("positions")
    @classmethod
    def validate_positions_or_region(cls, v, info):
        region = info.data.get("region")
        if v is not None and region is not None:
            raise ValueError("Cannot specify both 'region' and 'positions'")
        if v is None and region is None and not info.data.get("pathway"):
            return None  # All filters are optional
        return v


# ==========================================
# CONCATENATED AGGREGATION SCHEMAS
# ==========================================

class AggregationType(str, Enum):
    count = "count"
    percentage = "percentage"
    distinct_count = "distinct_count"


class OrderDirection(str, Enum):
    asc = "asc"
    desc = "desc"


class ConcatenatedAggregationRequest(BaseModel):
    separator: str = Field(", ", description="Separator for concatenation (e.g. ' > ')")
    columns: List[str] = Field(..., description="List of columns to concatenate")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")

    # New Field: percentage_by
    # Usage: If group_by=['disease', 'gene'], percentage_by=['disease']
    # Result: Gene mutation combo % within that Disease.
    percentage_by: Optional[List[str]] = Field(
        None, description="Columns to calculate percentage against (denominator scope)"
    )

    filters: Optional[ComplexFilter] = Field(
        None,
        description="Filters to apply before concatenation (applied before GROUP BY)",
    )

    # --- Genomic Position Filters (NEW) ---
    genomic_filter: Optional[GenomicPositionFilter] = Field(
        None,
        description="Filter by genomic position/range or pathway (applied before GROUP BY)",
    )

    aggregation_type: AggregationType = Field(
        AggregationType.count,
        description="Type of aggregation (count, percentage, or distinct_count)",
    )

    having: Optional[HavingClause] = Field(
        None,
        description="HAVING clause to filter aggregated results (applied after GROUP BY)",
    )

    order_by: Optional[Union[str, List[str]]] = Field(
        None,
        description="Column(s) to order results by. Use 'aggregated_value' for ordering by the aggregation result or 'concatenated_value' for ordering by the concatenated string. For multiple columns, provide as list.",
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
        if v is not None:
            group_by = info.data.get("group_by")
            if not group_by:
                # For non-grouped aggregations, only allow ordering by aggregated_value or concatenated_value
                allowed = ["aggregated_value", "concatenated_value"]
                if isinstance(v, str) and v not in allowed:
                    raise ValueError(
                        f"For non-grouped aggregations, order_by must be one of {allowed} or None"
                    )
                elif isinstance(v, list):
                    raise ValueError(
                        "For non-grouped aggregations, order_by cannot be a list"
                    )
            else:
                # For grouped aggregations, validate order_by columns
                if isinstance(v, str):
                    allowed = ["aggregated_value", "concatenated_value"] + group_by
                    if v not in allowed:
                        raise ValueError(
                            f"For grouped aggregations, order_by must be one of {allowed}"
                        )
                elif isinstance(v, list):
                    for col in v:
                        allowed = ["aggregated_value", "concatenated_value"] + group_by
                        if col not in allowed:
                            raise ValueError(
                                f"Invalid order_by column '{col}'. Must be one of {allowed}"
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
    having_applied: bool = False  # Whether HAVING clause was used
    groups_after_having: Optional[int] = None  # Number of groups after HAVING
    groups_before_having: Optional[int] = None  # Number of groups before HAVING
    genomic_filter_applied: bool = False  # NEW: Whether genomic filter was used

    # New Key: Group Totals
    group_totals: Optional[Dict[str, int]] = None

    # Ordering and limiting information
    order_by: Optional[Union[str, List[str]]] = None
    order_direction: Optional[str] = None
    limit: Optional[int] = None

    result: Union[Dict[str, Any], List[Dict[str, Any]]]


# ==========================================
# INTERNAL HELPERS
# ==========================================

def _normalize_chromosome(chrom: str) -> str:
    """Normalize chromosome name (remove 'chr' prefix)"""
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
    Apply genomic position filtering to query.

    Supports:
    1. Single range: chr1:915188-1015188
    2. Multiple positions: chr11:534289, chr17:7578406, chr17:7577538
    3. Pathway filtering (if pathway column exists)

    Args:
        query: SQLAlchemy query
        model_class: Model class
        genomic_filter: GenomicPositionFilter object

    Returns:
        Filtered query
    """
    if not genomic_filter:
        return query

    # Determine chromosome and position column names
    chr_col_name = None
    for col in ["chrom", "chromosome", "chr"]:
        if hasattr(model_class, col):
            chr_col_name = col
            break

    pos_col_name = None
    for col in ["start", "start_position", "pos", "position"]:
        if hasattr(model_class, col):
            pos_col_name = col
            break

    end_col_name = None
    for col in ["end", "end_position"]:
        if hasattr(model_class, col):
            end_col_name = col
            break

    if not chr_col_name or not pos_col_name:
        raise HTTPException(
            400, 
            "Dataset must have chromosome and position columns for genomic filtering"
        )

    chr_col = getattr(model_class, chr_col_name)
    pos_col = getattr(model_class, pos_col_name)
    end_col = getattr(model_class, end_col_name) if end_col_name else None

    # Apply filters
    conditions = []

    # Option 1: Single region filter
    if genomic_filter.region:
        region = genomic_filter.region
        norm_chrom = _normalize_chromosome(region.chromosome)

        # Chromosome match (flexible - handles both 'chr1' and '1')
        chrom_cond = or_(
            chr_col == norm_chrom,
            chr_col == f"chr{norm_chrom}",
            chr_col == region.chromosome
        )

        if region.end:
            # Range query: variants overlapping [start, end]
            if end_col:
                # If dataset has end column, check for overlap
                # Overlap: variant.start <= region.end AND variant.end >= region.start
                pos_cond = and_(
                    pos_col <= region.end,
                    end_col >= region.start
                )
            else:
                # No end column, just check if position is within range
                pos_cond = and_(
                    pos_col >= region.start,
                    pos_col <= region.end
                )
        else:
            # Exact position match
            pos_cond = pos_col == region.start

        conditions.append(and_(chrom_cond, pos_cond))

    # Option 2: Multiple specific positions
    elif genomic_filter.positions:
        for pos_spec in genomic_filter.positions:
            norm_chrom = _normalize_chromosome(pos_spec.chromosome)

            chrom_cond = or_(
                chr_col == norm_chrom,
                chr_col == f"chr{norm_chrom}",
                chr_col == pos_spec.chromosome
            )

            if pos_spec.end:
                # Range for this position
                if end_col:
                    pos_cond = and_(
                        pos_col <= pos_spec.end,
                        end_col >= pos_spec.start
                    )
                else:
                    pos_cond = and_(
                        pos_col >= pos_spec.start,
                        pos_col <= pos_spec.end
                    )
            else:
                # Exact position
                pos_cond = pos_col == pos_spec.start

            conditions.append(and_(chrom_cond, pos_cond))

    # Apply genomic conditions (OR logic for multiple positions)
    if conditions:
        if len(conditions) == 1:
            query = query.filter(conditions[0])
        else:
            query = query.filter(or_(*conditions))

    # Option 3: Pathway filter (if column exists)
    if genomic_filter.pathway:
        pathway_col_name = None
        for col in ["pathway", "pathway_name", "kegg_pathway", "reactome_pathway"]:
            if hasattr(model_class, col):
                pathway_col_name = col
                break

        if pathway_col_name:
            pathway_col = getattr(model_class, pathway_col_name)
            query = query.filter(pathway_col.ilike(f"%{genomic_filter.pathway}%"))

    return query


def _build_having_filter(having_clause: HavingClause, agg_expr):
    """
    Recursively builds SQLAlchemy HAVING conditions.

    Args:
        having_clause: The HavingClause to process
        agg_expr: The aggregation expression to apply conditions to

    Returns:
        SQLAlchemy BinaryExpression for HAVING clause
    """
    conditions = []

    for condition in having_clause.conditions:
        if isinstance(condition, HavingCondition):
            # Base case: single condition
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
            # Recursive case: nested HavingClause
            conditions.append(_build_having_filter(condition, agg_expr))

    # Combine with appropriate logic
    if having_clause.logic == "AND":
        return and_(*conditions)
    else:  # OR
        return or_(*conditions)


def _apply_ordering_concatenated(
    query,
    order_by,
    order_direction,
    group_attrs,
    agg_expr,
    group_by_columns,
    concatenated_col,
):
    """
    Apply ordering to the concatenated aggregation query.

    Args:
        query: The SQLAlchemy query to order
        order_by: String or list of strings specifying what to order by
        order_direction: 'asc' or 'desc'
        group_attrs: List of SQLAlchemy column attributes for group_by columns
        agg_expr: The aggregation expression
        group_by_columns: List of group_by column names
        concatenated_col: The concatenated column expression

    Returns:
        Ordered query
    """
    order_clauses = []

    def add_order_clause(column_expr):
        """Helper to add order clause with direction."""
        if order_direction == OrderDirection.desc:
            return column_expr.desc()
        else:
            return column_expr.asc()

    if order_by:
        if isinstance(order_by, str):
            # Single order by column
            if order_by == "aggregated_value":
                order_clauses.append(add_order_clause(agg_expr))
            elif order_by == "concatenated_value":
                order_clauses.append(add_order_clause(concatenated_col))
            elif order_by in group_by_columns:
                idx = group_by_columns.index(order_by)
                order_clauses.append(add_order_clause(group_attrs[idx]))
            else:
                raise ValueError(
                    f"Cannot order by '{order_by}'. Must be 'aggregated_value', 'concatenated_value', or one of group_by columns: {group_by_columns}"
                )
        else:
            # Multiple order by columns
            for order_col in order_by:
                if order_col == "aggregated_value":
                    order_clauses.append(add_order_clause(agg_expr))
                elif order_col == "concatenated_value":
                    order_clauses.append(add_order_clause(concatenated_col))
                elif order_col in group_by_columns:
                    idx = group_by_columns.index(order_col)
                    order_clauses.append(add_order_clause(group_attrs[idx]))
                else:
                    raise ValueError(
                        f"Cannot order by '{order_col}'. Must be 'aggregated_value', 'concatenated_value', or one of group_by columns: {group_by_columns}"
                    )

    # Apply ordering to query
    if order_clauses:
        query = query.order_by(*order_clauses)

    return query


# ==========================================
# MAIN API FUNCTION
# ==========================================

async def generic_concatenated_aggregate(
    request: ConcatenatedAggregationRequest, table_name: str, db
) -> AggregationResponse:
    """
    Enhanced concatenated aggregation with genomic position filtering.

    Concatenates values from multiple columns (e.g., "Ref>Alt") and aggregates them.
    Supports Scoped Percentages (percentage_by), Group Totals, HAVING clause, 
    ORDER BY, LIMIT, and genomic position filtering.

    Query execution order:
    1. FROM table_name
    2. WHERE (filters)
    3. WHERE (genomic_filter) ← NEW
    4. GROUP BY (group_by + concatenated_value)
    5. HAVING (having clause on aggregated results)
    6. ORDER BY (order_by)
    7. LIMIT (limit)
    8. SELECT (final result)

    Examples:
    ---------

    Example 1: TiTv ratio in genomic range
    {
      "columns": ["ref_allele", "tumor_seq_allele2"],
      "separator": "→",
      "aggregation_type": "count",
      "genomic_filter": {
        "region": {"chromosome": "chr17", "start": 7577000, "end": 7579000}
      },
      "order_by": "aggregated_value",
      "order_direction": "desc"
    }

    Example 2: Ref→Alt patterns at specific positions
    {
      "columns": ["ref_allele", "tumor_seq_allele2"],
      "separator": "→",
      "aggregation_type": "count",
      "genomic_filter": {
        "positions": [
          {"chromosome": "chr17", "start": 7577538},
          {"chromosome": "chr17", "start": 7577548},
          {"chromosome": "chr17", "start": 7578406}
        ]
      },
      "order_by": "aggregated_value",
      "order_direction": "desc"
    }

    Example 3: Gene + Protein change patterns in pathway
    {
      "columns": ["gene", "protein_change"],
      "separator": " : ",
      "aggregation_type": "count",
      "group_by": ["gene"],
      "genomic_filter": {"pathway": "PI3K-AKT"},
      "having": {
        "logic": "AND",
        "conditions": [{"operator": "gt", "value": 5}]
      },
      "limit": 10
    }

    Example 4: TiTv by gene in region
    {
      "columns": ["ref_allele", "tumor_seq_allele2"],
      "separator": "→",
      "aggregation_type": "count",
      "group_by": ["gene"],
      "genomic_filter": {
        "region": {"chromosome": "1", "start": 915188, "end": 1015188}
      },
      "order_by": "aggregated_value",
      "order_direction": "desc"
    }
    """
    try:
        model_class = get_model_class(table_name)

        # 1. Validation
        allowed_types = [
            AggregationType.count,
            AggregationType.distinct_count,
            AggregationType.percentage,
        ]
        if request.aggregation_type not in allowed_types:
            raise HTTPException(
                400, "Supported types: count, distinct_count, percentage"
            )

        validate_columns(model_class, request.columns)
        if request.group_by:
            validate_columns(model_class, request.group_by)
        if request.percentage_by:
            validate_columns(model_class, request.percentage_by)

        # 2. Build Concatenated Expression (with NULL Safety)
        col_attrs = [getattr(model_class, col) for col in request.columns]
        concatenated_col = func.coalesce(col_attrs[0], "")
        for i in range(1, len(col_attrs)):
            concatenated_col = func.concat(
                concatenated_col, request.separator, func.coalesce(col_attrs[i], "")
            )

        # 3. Base Query & Apply WHERE Filters
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        # 3b. Apply Genomic Position Filters (NEW)
        query = _apply_genomic_position_filter(query, model_class, request.genomic_filter)

        # 4. Capture Total Records (After WHERE + genomic filters, Before GROUP BY)
        total_records = query.count()

        # 5. Aggregation Logic
        formatted_results = []
        final_result = None
        group_totals_map = {}
        groups_before_having = None
        groups_after_having = None

        # Re-build filter expression for the specific aggregation query
        filter_expr = (
            _build_filter_expression(model_class, request.filters)
            if request.filters
            else True
        )

        if request.group_by:
            # === GROUPED AGGREGATION WITH CONCATENATION ===
            group_attrs = [getattr(model_class, c) for c in request.group_by]
            group_by_columns = request.group_by
            extra_selects = []

            if request.aggregation_type in [
                AggregationType.count,
                AggregationType.percentage,
            ]:
                if (
                    request.aggregation_type == AggregationType.percentage
                    and request.percentage_by
                ):
                    # --- SCOPED PERCENTAGE (Window Function) ---
                    partition_attrs = [
                        getattr(model_class, c) for c in request.percentage_by
                    ]
                    denominator = func.sum(func.count(concatenated_col)).over(
                        partition_by=partition_attrs
                    )
                    count_col = func.count(concatenated_col)
                    # For HAVING, we use the count expression
                    agg_expr = count_col
                    extra_selects = [
                        count_col.label("count"),
                        denominator.label("group_total"),
                    ]
                elif request.aggregation_type == AggregationType.percentage:
                    # --- GLOBAL PERCENTAGE ---
                    count_col = func.count(concatenated_col)
                    agg_expr = count_col
                    extra_selects = [count_col.label("count")]
                else:
                    # Standard Count
                    count_col = func.count(concatenated_col)
                    agg_expr = count_col
                    extra_selects = [count_col.label("count")]

                # Build Grouped Query
                grouped_query = (
                    db.query(
                        *group_attrs,
                        concatenated_col.label("concatenated_value"),
                        *extra_selects,
                    )
                    .filter(filter_expr)
                    .group_by(*group_attrs, concatenated_col)
                )

                # Apply genomic filter to grouped query as well
                grouped_query = _apply_genomic_position_filter(
                    grouped_query, model_class, request.genomic_filter
                )

                # Count groups before HAVING
                groups_before_having = (
                    db.query(func.count())
                    .select_from(grouped_query.subquery())
                    .scalar()
                )

                # Apply HAVING clause if present
                if request.having:
                    having_filter = _build_having_filter(request.having, agg_expr)
                    grouped_query = grouped_query.having(having_filter)

                # Apply ORDER BY if specified
                if request.order_by:
                    grouped_query = _apply_ordering_concatenated(
                        grouped_query,
                        request.order_by,
                        request.order_direction,
                        group_attrs,
                        agg_expr,
                        group_by_columns,
                        concatenated_col,
                    )

                # Apply LIMIT if specified
                if request.limit:
                    grouped_query = grouped_query.limit(request.limit)

                # Execute Query
                results = grouped_query.all()
                groups_after_having = len(results)

                # Indices Helper for percentage_by
                pct_indices = []
                if request.percentage_by:
                    pct_indices = [
                        request.group_by.index(c) for c in request.percentage_by
                    ]

                for res in results:
                    item = {}

                    # 1. Map Group Columns
                    for i, g_col in enumerate(request.group_by):
                        item[g_col] = res[i]

                    # 2. Map Concat Value (It's at index len(group_by))
                    concat_idx = len(request.group_by)
                    item["concatenated_value"] = res[concat_idx]

                    # 3. Extract Count and Total
                    count_val = res[concat_idx + 1]
                    if request.aggregation_type == AggregationType.percentage:
                        if request.percentage_by:
                            group_total = res[concat_idx + 2]
                            val = (
                                (count_val / group_total * 100)
                                if group_total > 0
                                else 0.0
                            )
                            item["aggregated_value"] = round(val, 2)

                            # Add to Totals Map
                            key_parts = [str(res[idx]) for idx in pct_indices]
                            key = "|".join(key_parts)
                            group_totals_map[key] = int(group_total)
                        else:
                            # Global %
                            val = (
                                (count_val / total_records * 100)
                                if total_records > 0
                                else 0.0
                            )
                            item["aggregated_value"] = round(val, 2)
                            group_totals_map["global"] = total_records
                    else:
                        item["aggregated_value"] = count_val

                    formatted_results.append(item)

                final_result = formatted_results

            elif request.aggregation_type == AggregationType.distinct_count:
                # Distinct count logic
                agg_expr = func.count(func.distinct(concatenated_col))

                grouped_query = (
                    db.query(
                        *group_attrs,
                        agg_expr.label("distinct_cnt"),
                    )
                    .filter(filter_expr)
                    .group_by(*group_attrs)
                )

                # Apply genomic filter
                grouped_query = _apply_genomic_position_filter(
                    grouped_query, model_class, request.genomic_filter
                )

                # Count groups before HAVING
                groups_before_having = (
                    db.query(func.count())
                    .select_from(grouped_query.subquery())
                    .scalar()
                )

                # Apply HAVING clause if present
                if request.having:
                    having_filter = _build_having_filter(request.having, agg_expr)
                    grouped_query = grouped_query.having(having_filter)

                # Apply ORDER BY if specified
                if request.order_by:
                    grouped_query = _apply_ordering_concatenated(
                        grouped_query,
                        request.order_by,
                        request.order_direction,
                        group_attrs,
                        agg_expr,
                        group_by_columns,
                        concatenated_col,
                    )

                # Apply LIMIT if specified
                if request.limit:
                    grouped_query = grouped_query.limit(request.limit)

                results = grouped_query.all()
                groups_after_having = len(results)

                for res in results:
                    item = {}
                    for i, g_col in enumerate(request.group_by):
                        item[g_col] = res[i]
                    item["concatenated_value"] = "N/A"
                    item["aggregated_value"] = res[-1]
                    formatted_results.append(item)

                final_result = formatted_results

        else:
            # === NO GROUPING (Global Distribution) ===
            if request.aggregation_type in [
                AggregationType.count,
                AggregationType.percentage,
            ]:
                count_col = func.count(concatenated_col)
                agg_expr = count_col

                agg_query = (
                    db.query(
                        concatenated_col.label("concatenated_value"),
                        count_col.label("count"),
                    )
                    .filter(filter_expr)
                    .group_by(concatenated_col)
                )

                # Apply genomic filter
                agg_query = _apply_genomic_position_filter(
                    agg_query, model_class, request.genomic_filter
                )

                # Count groups before HAVING
                groups_before_having = (
                    db.query(func.count()).select_from(agg_query.subquery()).scalar()
                )

                # Apply HAVING clause if present
                if request.having:
                    having_filter = _build_having_filter(request.having, agg_expr)
                    agg_query = agg_query.having(having_filter)

                # Apply ORDER BY if specified (for non-grouped)
                if request.order_by:
                    if isinstance(request.order_by, str):
                        if request.order_by == "aggregated_value":
                            order_attr = count_col
                        elif request.order_by == "concatenated_value":
                            order_attr = concatenated_col
                        else:
                            raise ValueError(
                                f"Invalid order_by for non-grouped: {request.order_by}"
                            )

                        if request.order_direction == OrderDirection.desc:
                            agg_query = agg_query.order_by(order_attr.desc())
                        else:
                            agg_query = agg_query.order_by(order_attr.asc())

                # Apply LIMIT if specified
                if request.limit:
                    agg_query = agg_query.limit(request.limit)

                results = agg_query.all()
                groups_after_having = len(results)

                for row in results:
                    count_val = row.count
                    if request.aggregation_type == AggregationType.percentage:
                        val = (
                            (count_val / total_records * 100)
                            if total_records > 0
                            else 0.0
                        )
                        formatted_results.append(
                            {
                                "concatenated_value": row.concatenated_value,
                                "aggregated_value": round(val, 2),
                            }
                        )
                        group_totals_map["global"] = total_records
                    else:
                        formatted_results.append(
                            {
                                "concatenated_value": row.concatenated_value,
                                "aggregated_value": count_val,
                            }
                        )

                final_result = formatted_results

            elif request.aggregation_type == AggregationType.distinct_count:
                cnt = (
                    db.query(func.count(func.distinct(concatenated_col)))
                    .filter(filter_expr)
                    .scalar()
                    or 0
                )
                final_result = {"value": cnt}

        # 6. Return Response
        return AggregationResponse(
            table_name=table_name,
            column="+".join(request.columns),
            aggregation_type=request.aggregation_type.value,
            result=final_result,
            total_records=total_records,
            groups_before_having=groups_before_having,
            groups_after_having=groups_after_having,
            having_applied=request.having is not None,
            genomic_filter_applied=request.genomic_filter is not None,
            group_totals=group_totals_map if group_totals_map else None,
            order_by=request.order_by,
            order_direction=request.order_direction.value,
            limit=request.limit,
        )

    except HTTPException as he:
        raise he
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Concatenated aggregation failed: {str(e)}"
        )


# ==========================================
# USAGE EXAMPLES
# ==========================================

"""
Example 1: TiTv ratio in TP53 genomic range
--------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "columns": ["ref_allele", "tumor_seq_allele2"],
  "separator": "→",
  "aggregation_type": "count",
  "genomic_filter": {
    "region": {
      "chromosome": "chr17",
      "start": 7577000,
      "end": 7579000
    }
  },
  "order_by": "aggregated_value",
  "order_direction": "desc"
}

Response:
{
  "column": "ref_allele+tumor_seq_allele2",
  "table_name": "nibmg_exome_somatic_variants",
  "aggregation_type": "count",
  "total_records": 156,
  "genomic_filter_applied": true,
  "result": [
    {"concatenated_value": "C→T", "aggregated_value": 45},
    {"concatenated_value": "G→A", "aggregated_value": 38},
    {"concatenated_value": "C→A", "aggregated_value": 22},
    {"concatenated_value": "G→T", "aggregated_value": 18}
  ]
}

Example 2: Ref→Alt patterns at hotspot positions
-------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "columns": ["ref_allele", "tumor_seq_allele2"],
  "separator": "→",
  "aggregation_type": "count",
  "genomic_filter": {
    "positions": [
      {"chromosome": "chr17", "start": 7577538},
      {"chromosome": "chr17", "start": 7577548},
      {"chromosome": "chr17", "start": 7578406}
    ]
  },
  "order_by": "aggregated_value",
  "order_direction": "desc"
}

Example 3: Gene + Protein change patterns with HAVING
------------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "columns": ["gene", "protein_change"],
  "separator": " : ",
  "aggregation_type": "count",
  "group_by": ["gene"],
  "genomic_filter": {
    "pathway": "PI3K-AKT"
  },
  "having": {
    "logic": "AND",
    "conditions": [
      {"operator": "gt", "value": 5}
    ]
  },
  "order_by": "aggregated_value",
  "order_direction": "desc",
  "limit": 10
}

Example 4: TiTv by gene in wide genomic range
----------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "columns": ["ref_allele", "tumor_seq_allele2"],
  "separator": "→",
  "aggregation_type": "count",
  "group_by": ["gene"],
  "genomic_filter": {
    "region": {
      "chromosome": "1",
      "start": 915188,
      "end": 1015188
    }
  },
  "order_by": "aggregated_value",
  "order_direction": "desc"
}

Example 5: cDNA change patterns at specific position
-----------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "columns": ["ref_allele", "tumor_seq_allele2", "cdna_change"],
  "separator": " | ",
  "aggregation_type": "count",
  "genomic_filter": {
    "region": {
      "chromosome": "chr17",
      "start": 7577538
    }
  },
  "order_by": "concatenated_value",
  "order_direction": "asc"
}

Example 6: Percentage of substitution types in pathway
-------------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "columns": ["ref_allele", "tumor_seq_allele2"],
  "separator": "→",
  "aggregation_type": "percentage",
  "genomic_filter": {
    "pathway": "DNA repair"
  },
  "order_by": "aggregated_value",
  "order_direction": "desc"
}
"""
