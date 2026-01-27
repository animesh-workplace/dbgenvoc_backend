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


class ComputedField(BaseModel):
    """
    Derived/computed output field.

    Example:
    {
        "name": "mutation",
        "type": "concat",
        "columns": ["ref_allele", "tumor_seq_allele2"],
        "separator": ">"
    }
    """

    name: str = Field(..., description="Output field name")
    type: ComputedFieldType = Field(
        ComputedFieldType.concat, description="Type of computation"
    )
    columns: List[str] = Field(..., min_length=2, description="Source columns")
    separator: str = Field("", description="Separator for concat")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v.isidentifier():
            raise ValueError("Computed field name must be a valid identifier")
        return v


# ======================================================
# REQUEST / RESPONSE SCHEMAS
# ======================================================


class ConcatenatedAggregationRequest(BaseModel):
    """
    New combination aggregation request with computed fields.
    """

    limit: Optional[int] = None
    having: Optional[HavingClause] = None
    filters: Optional[ComplexFilter] = None
    order_by: Optional[Union[str, List[str]]] = None
    order_direction: OrderDirection = OrderDirection.desc
    aggregate_column: str = Field(..., description="Column to aggregate on")
    combination_columns: List[str] = Field(
        ..., min_length=1, description="Columns to GROUP BY"
    )
    aggregation_type: AggregationType = Field(
        AggregationType.count, description="Aggregation type"
    )
    computed_fields: Optional[List[ComputedField]] = Field(
        None, description="Derived/computed output fields"
    )
    percentage_by: Optional[List[str]] = Field(
        None, description="Subset of combination_columns for percentage denominator"
    )

    @field_validator("percentage_by")
    @classmethod
    def validate_percentage_by(cls, v, info):
        if v:
            combo_cols = info.data.get("combination_columns")
            if not combo_cols or not set(v).issubset(set(combo_cols)):
                raise ValueError(
                    "percentage_by must be a subset of combination_columns"
                )
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v < 1:
            raise ValueError("limit must be > 0")
        return v


class ConcatenatedAggregationResponse(BaseModel):
    table_name: str
    total_records: int
    aggregation_type: str
    aggregate_column: str
    total_combinations: int
    limit: Optional[int] = None
    results: List[Dict[str, Any]]
    combination_columns: List[str]
    order_direction: Optional[str] = None
    order_by: Optional[Union[str, List[str]]] = None


# ======================================================
# INTERNAL HELPERS
# ======================================================


def validate_computed_fields(
    computed_fields: Optional[List[ComputedField]],
    combination_columns: List[str],
):
    if not computed_fields:
        return

    for field in computed_fields:
        missing = set(field.columns) - set(combination_columns)
        if missing:
            raise ValueError(
                f"Computed field '{field.name}' references columns not in "
                f"combination_columns: {list(missing)}"
            )


def apply_computed_fields(
    rows: List[Dict[str, Any]],
    computed_fields: Optional[List[ComputedField]],
) -> List[Dict[str, Any]]:
    """
    Apply computed fields AFTER aggregation.
    """
    if not computed_fields:
        return rows

    for row in rows:
        for field in computed_fields:
            if field.type == ComputedFieldType.concat:
                parts = [
                    "" if row.get(col) is None else str(row.get(col))
                    for col in field.columns
                ]
                row[field.name] = field.separator.join(parts)

    return rows


def build_having_filter(having: HavingClause, agg_expr):
    conditions = []

    for cond in having.conditions:
        if isinstance(cond, HavingCondition):
            op = cond.operator
            val = cond.value
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
            conditions.append(build_having_filter(cond, agg_expr))

    return and_(*conditions) if having.logic == "AND" else or_(*conditions)


# ======================================================
# MAIN AGGREGATION FUNCTION
# ======================================================


async def generic_concatenated_aggregate(
    request: ConcatenatedAggregationRequest,
    db,
    table_name: str,
) -> ConcatenatedAggregationResponse:
    """
    Combination aggregation with derived/computed output fields.
    """

    try:
        model_class = get_model_class(table_name)

        # --- Validation ---
        validate_columns(model_class, request.combination_columns)
        validate_columns(model_class, [request.aggregate_column])
        if request.percentage_by:
            validate_columns(model_class, request.percentage_by)

        validate_computed_fields(
            request.computed_fields,
            request.combination_columns,
        )

        agg_col = getattr(model_class, request.aggregate_column)
        group_attrs = [getattr(model_class, c) for c in request.combination_columns]

        # --- Base Query ---
        query = db.query(model_class)
        query = apply_filters(query, model_class, request.filters)

        total_records = query.count()

        # --- Aggregation Expression ---
        if request.aggregation_type == AggregationType.count:
            agg_expr = func.count(agg_col)
        elif request.aggregation_type == AggregationType.sum:
            agg_expr = func.sum(agg_col)
        elif request.aggregation_type == AggregationType.avg:
            agg_expr = func.avg(agg_col)
        elif request.aggregation_type == AggregationType.min:
            agg_expr = func.min(agg_col)
        elif request.aggregation_type == AggregationType.max:
            agg_expr = func.max(agg_col)
        elif request.aggregation_type == AggregationType.distinct_count:
            agg_expr = func.count(func.distinct(agg_col))
        elif request.aggregation_type == AggregationType.percentage:
            if request.percentage_by:
                partition_cols = [
                    getattr(model_class, c) for c in request.percentage_by
                ]
                denom = func.sum(func.count(agg_col)).over(partition_by=partition_cols)
                agg_expr = (func.count(agg_col) * 100.0) / denom
            else:
                agg_expr = (func.count(agg_col) * 100.0) / (
                    total_records if total_records else 1
                )
        else:
            raise ValueError("Unsupported aggregation type")

        # --- Grouped Query ---
        grouped_query = query.with_entities(
            *group_attrs, agg_expr.label("aggregated_value")
        ).group_by(*group_attrs)

        total_combinations = (
            db.query(func.count()).select_from(grouped_query.subquery()).scalar() or 0
        )

        # --- HAVING ---
        if request.having:
            grouped_query = grouped_query.having(
                build_having_filter(request.having, agg_expr)
            )

        # --- ORDER BY ---
        if request.order_by:

            def order(expr):
                return (
                    expr.desc()
                    if request.order_direction == OrderDirection.desc
                    else expr.asc()
                )

            if isinstance(request.order_by, str):
                if request.order_by == "aggregated_value":
                    grouped_query = grouped_query.order_by(order(agg_expr))
                else:
                    idx = request.combination_columns.index(request.order_by)
                    grouped_query = grouped_query.order_by(order(group_attrs[idx]))
            else:
                for col in request.order_by:
                    if col == "aggregated_value":
                        grouped_query = grouped_query.order_by(order(agg_expr))
                    else:
                        idx = request.combination_columns.index(col)
                        grouped_query = grouped_query.order_by(order(group_attrs[idx]))

        # --- LIMIT ---
        if request.limit:
            grouped_query = grouped_query.limit(request.limit)

        # --- Execute ---
        rows = grouped_query.all()

        # --- Format Results ---
        results: List[Dict[str, Any]] = []

        for row in rows:
            item: Dict[str, Any] = {}
            for i, col in enumerate(request.combination_columns):
                item[col] = row[i]

            val = row[len(request.combination_columns)]
            if request.aggregation_type == AggregationType.percentage:
                val = round(float(val), 2)

            item["aggregated_value"] = val
            results.append(item)

        results = apply_computed_fields(results, request.computed_fields)

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
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Combination aggregation failed: {str(e)}",
        )
