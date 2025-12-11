import app.models  # Needs to be there for ALL_TABLE_REGISTRY to work
import numpy as np
from app.session import Base
from sqlalchemy import and_, or_
from sqlalchemy.orm import Query
from fastapi import HTTPException
from typing import List, Dict, Any, Union
from app.schema_new import ComplexFilter, FilterCondition
from sqlalchemy.sql.sqltypes import Numeric, Float, Integer, DECIMAL

# Table registry mapping table names to models
ALL_TABLE_REGISTRY = {
    mapper.class_.__tablename__: mapper.class_
    for mapper in Base.registry.mappers
    if hasattr(mapper.class_, "__tablename__")
}

# Table registry for germline tables that will require authentication to get access to
GERMLINE_TABLE_REGISTRY = [
    table_name
    for table_name, model_class in ALL_TABLE_REGISTRY.items()
    if "germline" in table_name
]


# Helper functions
def get_model_class(table_name: str):
    """Get the SQLAlchemy model class for a given table name."""
    if table_name not in ALL_TABLE_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found.",
        )
    return ALL_TABLE_REGISTRY[table_name]


def get_searchable_columns(table_name: str) -> List[str]:
    """Get searchable columns for a table."""
    model_class = get_model_class(table_name)
    return [col.name for col in model_class.__table__.columns]


def validate_columns(model_class, column_names: List[str]) -> List[str]:
    """Validate that columns exist in the model."""
    valid_columns = []
    invalid_columns = []

    for col_name in column_names:
        if hasattr(model_class, col_name):
            valid_columns.append(col_name)
        else:
            invalid_columns.append(col_name)

    if invalid_columns:
        available_columns = [col.name for col in model_class.__table__.columns]
        raise HTTPException(
            status_code=400,
            # Need to remove available columns
            detail=f"Invalid columns: {invalid_columns}. Available columns: {available_columns}",
        )

    return valid_columns


def row_to_dict(row) -> Dict[str, Any]:
    """
    Convert SQLAlchemy row to dictionary with safe numeric conversion for all numeric columns.
    - 'inf' -> 999
    - '-inf' -> -999
    - Invalid numbers -> np.nan
    """
    result = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)

        # Handle numeric columns
        if isinstance(column.type, (Numeric, Float, Integer, DECIMAL)):
            try:
                f = float(value)
                if np.isposinf(f):
                    f = 999
                elif np.isneginf(f):
                    f = -999
                elif np.isnan(f):
                    f = np.nan  # or 0 if you prefer
                result[column.name] = f
            except (ValueError, TypeError):
                result[column.name] = np.nan  # fallback for invalid strings
        else:
            # Non-numeric columns stay as-is
            result[column.name] = value
    return result


def _build_filter_expression(
    model_class, filter_data: Union[ComplexFilter, FilterCondition]
):
    """Recursively builds SQLAlchemy filter expressions with AND/OR logic."""

    # Case 1: Leaf Node (Actual Condition)
    if isinstance(filter_data, FilterCondition):
        if not hasattr(model_class, filter_data.column):
            return None  # Ignore invalid columns or raise error

        attr = getattr(model_class, filter_data.column)
        val = filter_data.value

        ops = {
            "eq": lambda: attr == val,
            "neq": lambda: attr != val,
            "gt": lambda: attr > val,
            "lt": lambda: attr < val,
            "in": lambda: attr.in_(val) if isinstance(val, list) else attr.in_([val]),
            "not_in": lambda: ~attr.in_(val)
            if isinstance(val, list)
            else ~attr.in_([val]),
            "like": lambda: attr.like(f"%{val}%"),
        }
        return ops.get(filter_data.operator, lambda: attr == val)()

    # Case 2: Branch Node (AND/OR Logic)
    if isinstance(filter_data, ComplexFilter):
        conditions = [
            _build_filter_expression(model_class, cond)
            for cond in filter_data.conditions
        ]
        # Filter out None values
        conditions = [c for c in conditions if c is not None]

        if not conditions:
            return None

        if filter_data.logic == "OR":
            return or_(*conditions)
        return and_(*conditions)

    return None


def apply_filters(query: Query, model_class, filters: ComplexFilter) -> Query:
    if not filters:
        return query
    expression = _build_filter_expression(model_class, filters)
    if expression is not None:
        return query.filter(expression)
    return query
