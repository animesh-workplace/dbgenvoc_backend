"""
aggregate_combination.py

Enhanced multi-column combination aggregation API with unified genomic position filtering.

Features:
- Multi-column combinations (e.g., gene + variant_class)
- Standard aggregations on combination groups
- Unified genomic position filtering (ranges and exact positions)
- Pathway filtering
- HAVING clause for post-aggregation filtering
- Multi-column ORDER BY
- LIMIT support
- Percentage calculations (global and scoped)

Author: Generated for dbGENVOC API
Date: 2026-01-27
Version: 2.1 (Unified Genomic Position Filtering)
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import func, and_, or_
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from app.schema_new import ComplexFilter, HavingClause, HavingCondition


# ==========================================
# GENOMIC POSITION SCHEMAS
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


# ==========================================
# AGGREGATION SCHEMAS
# ==========================================


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


class CombinationAggregationRequest(BaseModel):
    """
    Multi-column combination aggregation request.

    Generates all unique combinations of specified columns and aggregates on target column.

    Example:
        combination_columns: ["gene", "variant_class", "impact"]
        aggregate_column: "sample_id"
        aggregation_type: "count"

        Result: Count of samples for each (gene, variant_class, impact) combination
    """

    combination_columns: List[str] = Field(
        ...,
        description="Columns to combine (generate all unique combinations)",
        min_length=1,
    )

    aggregate_column: str = Field(
        ..., description="Column to aggregate on for each combination"
    )

    aggregation_type: AggregationType = Field(
        AggregationType.count, description="Type of aggregation"
    )

    filters: Optional[ComplexFilter] = Field(
        None, description="Complex filters with AND/OR logic (applied before GROUP BY)"
    )

    # --- Genomic Position Filters (UNIFIED) ---
    genomic_filter: Optional[GenomicPositionFilter] = Field(
        None,
        description="Filter by genomic positions/ranges or pathway (applied before GROUP BY)",
    )

    percentage_by: Optional[List[str]] = Field(
        None,
        description="Subset of combination_columns to calculate percentage against",
    )

    having: Optional[HavingClause] = Field(
        None,
        description="HAVING clause to filter aggregated results (applied after GROUP BY)",
    )

    order_by: Optional[Union[str, List[str]]] = Field(
        None,
        description="Column(s) to order by. Use 'aggregated_value' for ordering by aggregation result.",
    )

    order_direction: OrderDirection = Field(
        OrderDirection.desc, description="Order direction: asc or desc"
    )

    limit: Optional[int] = Field(
        None, description="Limit the number of results returned"
    )

    @field_validator("percentage_by")
    @classmethod
    def validate_percentage_by(cls, v, info):
        if v:
            combo_cols = info.data.get("combination_columns")
            if not combo_cols or not set(v).issubset(set(combo_cols)):
                raise ValueError(
                    "percentage_by columns must be subset of combination_columns"
                )
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v < 1:
            raise ValueError("Limit must be greater than 0")
        return v


class CombinationAggregationResponse(BaseModel):
    """Response for combination aggregation"""

    table_name: str
    aggregate_column: str
    aggregation_type: str
    combination_columns: List[str]

    total_records: int
    total_combinations: int

    having_applied: bool = False
    combinations_before_having: Optional[int] = None
    combinations_after_having: Optional[int] = None

    genomic_filter_applied: bool = False
    genomic_positions_count: Optional[int] = Field(
        None, description="Number of genomic positions/ranges in the filter"
    )

    group_totals: Optional[Dict[str, int]] = None

    order_by: Optional[Union[str, List[str]]] = None
    order_direction: Optional[str] = None
    limit: Optional[int] = None

    results: List[Dict[str, Any]]


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

    # Detect chromosome and position column names
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
    query, order_by, order_direction, group_attrs, agg_expr, combination_columns
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
            elif order_by in combination_columns:
                idx = combination_columns.index(order_by)
                order_clauses.append(add_order_clause(group_attrs[idx]))
            else:
                raise ValueError(
                    f"Cannot order by '{order_by}'. Must be 'aggregated_value' or one of combination_columns: {combination_columns}"
                )
        else:
            for order_col in order_by:
                if order_col == "aggregated_value":
                    order_clauses.append(add_order_clause(agg_expr))
                elif order_col in combination_columns:
                    idx = combination_columns.index(order_col)
                    order_clauses.append(add_order_clause(group_attrs[idx]))
                else:
                    raise ValueError(
                        f"Cannot order by '{order_col}'. Must be 'aggregated_value' or one of combination_columns: {combination_columns}"
                    )

    if order_clauses:
        query = query.order_by(*order_clauses)

    return query


# ==========================================
# MAIN COMBINATION AGGREGATION API
# ==========================================


async def combination_aggregate(
    request: CombinationAggregationRequest, db, table_name: str
) -> CombinationAggregationResponse:
    """
    Multi-column combination aggregation with unified genomic position filtering.

    Generates all unique combinations of specified columns and performs aggregation
    on a target column for each combination.

    Query execution order:
    1. FROM table_name
    2. WHERE (filters)
    3. WHERE (genomic_filter - unified positions/ranges)
    4. GROUP BY (combination_columns)
    5. HAVING (having clause on aggregated results)
    6. ORDER BY (order_by)
    7. LIMIT (limit)
    8. SELECT (final result)

    Examples:
    ---------

    Example 1: Gene + Variant Class combinations in genomic range
    {
      "combination_columns": ["gene", "variant_class"],
      "aggregate_column": "sample_id",
      "aggregation_type": "count",
      "genomic_filter": {
        "positions": [
          {"chromosome": "chr17", "start": 7577000, "end": 7579000}
        ]
      },
      "order_by": "aggregated_value",
      "order_direction": "desc"
    }

    Example 2: Mixed positions - regulatory + hotspots (NEW!)
    {
      "combination_columns": ["gene", "variant_class", "impact"],
      "aggregate_column": "sample_id",
      "aggregation_type": "distinct_count",
      "genomic_filter": {
        "positions": [
          {"chromosome": "chr17", "start": 7571000, "end": 7572000},
          {"chromosome": "chr17", "start": 7577538},
          {"chromosome": "chr17", "start": 7578406}
        ]
      }
    }

    Example 3: Multi-gene panel combinations (NEW!)
    {
      "combination_columns": ["gene", "variant_class"],
      "aggregate_column": "variant_id",
      "aggregation_type": "count",
      "genomic_filter": {
        "positions": [
          {"chromosome": "chr17", "start": 7577000, "end": 7579000},
          {"chromosome": "chr13", "start": 32889611, "end": 32973805},
          {"chromosome": "chr17", "start": 43044295, "end": 43170245}
        ]
      }
    }

    Example 4: Exon + splice sites (NEW!)
    {
      "combination_columns": ["gene", "consequence"],
      "aggregate_column": "variant_id",
      "aggregation_type": "count",
      "genomic_filter": {
        "positions": [
          {"chromosome": "chr17", "start": 7577019, "end": 7577155},
          {"chromosome": "chr17", "start": 7577156},
          {"chromosome": "chr17", "start": 7577018}
        ]
      }
    }

    Example 5: Percentage by combination
    {
      "combination_columns": ["gene", "variant_class"],
      "aggregate_column": "sample_id",
      "aggregation_type": "percentage",
      "percentage_by": ["gene"],
      "genomic_filter": {
        "positions": [
          {"chromosome": "chr17", "start": 7577000, "end": 7579000}
        ]
      }
    }
    """
    try:
        from app.core import get_model_class, validate_columns, apply_filters

        model_class = get_model_class(table_name)

        # 1. Validation
        validate_columns(model_class, request.combination_columns)
        validate_columns(model_class, [request.aggregate_column])
        if request.percentage_by:
            validate_columns(model_class, request.percentage_by)

        agg_col_attr = getattr(model_class, request.aggregate_column)

        # 2. Build Query & Apply WHERE Filters
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        # 2b. Apply Genomic Position Filters (UNIFIED)
        query = _apply_genomic_position_filter(
            query, model_class, request.genomic_filter
        )

        # 3. Capture Total Records
        total_records = query.count()

        # Calculate genomic positions count
        genomic_positions_count = None
        if request.genomic_filter and request.genomic_filter.positions:
            genomic_positions_count = len(request.genomic_filter.positions)

        # 4. Build GROUP BY combinations
        group_attrs = [getattr(model_class, col) for col in request.combination_columns]

        # 5. Determine aggregation expression
        extra_selects = []
        group_totals_map = {}

        if request.aggregation_type == AggregationType.percentage:
            if request.percentage_by:
                partition_attrs = [
                    getattr(model_class, col) for col in request.percentage_by
                ]
                denominator = func.sum(func.count(agg_col_attr)).over(
                    partition_by=partition_attrs
                )
                agg_expr = (func.count(agg_col_attr) * 100.0) / denominator
                extra_selects.append(denominator.label("group_total"))
            else:
                agg_expr = (func.count(agg_col_attr) * 100.0) / (
                    total_records if total_records > 0 else 1
                )
        else:
            funcs_map = {
                AggregationType.count: func.count(agg_col_attr),
                AggregationType.sum: func.sum(agg_col_attr),
                AggregationType.avg: func.avg(agg_col_attr),
                AggregationType.min: func.min(agg_col_attr),
                AggregationType.max: func.max(agg_col_attr),
                AggregationType.distinct_count: func.count(func.distinct(agg_col_attr)),
            }
            agg_expr = funcs_map.get(request.aggregation_type)

        # 6. Build grouped query
        grouped_query = query.with_entities(
            *group_attrs, agg_expr.label("val"), *extra_selects
        ).group_by(*group_attrs)

        # Count combinations before HAVING
        combinations_before_having = (
            db.query(func.count()).select_from(grouped_query.subquery()).scalar()
        )

        # 7. Apply HAVING
        if request.having:
            having_filter = _build_having_filter(request.having, agg_expr)
            grouped_query = grouped_query.having(having_filter)

        # 8. Apply ORDER BY
        if request.order_by:
            grouped_query = _apply_ordering(
                grouped_query,
                request.order_by,
                request.order_direction,
                group_attrs,
                agg_expr,
                request.combination_columns,
            )

        # 9. Apply LIMIT
        if request.limit:
            grouped_query = grouped_query.limit(request.limit)

        # 10. Execute Query
        results = grouped_query.all()
        combinations_after_having = len(results)

        # 11. Format Results
        formatted_results = []
        pct_indices = []
        if request.percentage_by:
            pct_indices = [
                request.combination_columns.index(c) for c in request.percentage_by
            ]

        for result in results:
            result_dict = {}

            # Add combination column values
            for i, col in enumerate(request.combination_columns):
                result_dict[col] = result[i]

            # Add aggregated value
            val_index = len(request.combination_columns)
            val = result[val_index]
            if (
                request.aggregation_type == AggregationType.percentage
                and val is not None
            ):
                val = round(float(val), 2)
            result_dict["aggregated_value"] = val

            # Handle percentage group totals
            if request.aggregation_type == AggregationType.percentage:
                if request.percentage_by:
                    total_val = result[val_index + 1]
                    key_parts = [str(result[idx]) for idx in pct_indices]
                    key = "|".join(key_parts)
                    group_totals_map[key] = int(total_val) if total_val else 0
                else:
                    group_totals_map["global"] = total_records

            formatted_results.append(result_dict)

        return CombinationAggregationResponse(
            table_name=table_name,
            aggregate_column=request.aggregate_column,
            aggregation_type=request.aggregation_type.value,
            combination_columns=request.combination_columns,
            total_records=total_records,
            total_combinations=combinations_before_having or 0,
            combinations_before_having=combinations_before_having,
            combinations_after_having=combinations_after_having,
            having_applied=request.having is not None,
            genomic_filter_applied=request.genomic_filter is not None,
            genomic_positions_count=genomic_positions_count,
            group_totals=group_totals_map if group_totals_map else None,
            order_by=request.order_by,
            order_direction=request.order_direction.value,
            limit=request.limit,
            results=formatted_results,
        )

    except HTTPException as he:
        raise he
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Combination aggregation failed: {str(e)}"
        )


# ==========================================
# USAGE EXAMPLES
# ==========================================

"""
Example 1: Gene + Variant Class in TP53 region
-----------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "combination_columns": ["gene", "variant_class"],
  "aggregate_column": "sample_id",
  "aggregation_type": "count",
  "genomic_filter": {
    "positions": [
      {"chromosome": "chr17", "start": 7577000, "end": 7579000}
    ]
  },
  "order_by": "aggregated_value",
  "order_direction": "desc",
  "limit": 20
}

Example 2: Mixed - regulatory + hotspots (NEW!)
------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "combination_columns": ["gene", "variant_class", "impact"],
  "aggregate_column": "sample_id",
  "aggregation_type": "distinct_count",
  "genomic_filter": {
    "positions": [
      {"chromosome": "chr17", "start": 7571000, "end": 7572000},
      {"chromosome": "chr17", "start": 7577538},
      {"chromosome": "chr17", "start": 7578406}
    ]
  },
  "having": {
    "logic": "AND",
    "conditions": [{"operator": "gte", "value": 3}]
  }
}

Example 3: Multi-gene panel (NEW!)
-----------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "combination_columns": ["gene", "variant_class"],
  "aggregate_column": "variant_id",
  "aggregation_type": "count",
  "genomic_filter": {
    "positions": [
      {"chromosome": "chr17", "start": 7577000, "end": 7579000},
      {"chromosome": "chr13", "start": 32889611, "end": 32973805},
      {"chromosome": "chr17", "start": 43044295, "end": 43170245}
    ]
  },
  "order_by": ["gene", "aggregated_value"],
  "order_direction": "desc"
}

Example 4: Exon + splice sites (NEW!)
--------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "combination_columns": ["gene", "consequence"],
  "aggregate_column": "variant_id",
  "aggregation_type": "count",
  "genomic_filter": {
    "positions": [
      {"chromosome": "chr17", "start": 7577019, "end": 7577155},
      {"chromosome": "chr17", "start": 7577156},
      {"chromosome": "chr17", "start": 7577018}
    ]
  }
}

Example 5: Multi-chromosome impact analysis (NEW!)
---------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "combination_columns": ["gene", "impact"],
  "aggregate_column": "variant_id",
  "aggregation_type": "count",
  "genomic_filter": {
    "positions": [
      {"chromosome": "1", "start": 915188, "end": 1015188},
      {"chromosome": "17", "start": 7577000, "end": 7579000},
      {"chromosome": "X", "start": 123456}
    ]
  },
  "filters": {
    "logic": "AND",
    "conditions": [
      {"column": "variant_class", "operator": "in", "value": ["Missense_Mutation", "Nonsense_Mutation"]}
    ]
  }
}

Example 6: Percentage by gene (scoped percentage)
--------------------------------------------------
{
  "table": "nibmg_exome_somatic_variants",
  "combination_columns": ["gene", "variant_class"],
  "aggregate_column": "sample_id",
  "aggregation_type": "percentage",
  "percentage_by": ["gene"],
  "genomic_filter": {
    "positions": [
      {"chromosome": "chr17", "start": 7577000, "end": 7579000}
    ]
  },
  "order_by": ["gene", "aggregated_value"],
  "order_direction": "desc"
}
"""
