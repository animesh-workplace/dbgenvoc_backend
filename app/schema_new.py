from typing import Any, List, Union, Literal
from pydantic import BaseModel, field_validator


class FilterCondition(BaseModel):
    value: Any
    column: str
    operator: Literal["eq", "neq", "gt", "lt", "in", "not_in", "like"] = "eq"


class ComplexFilter(BaseModel):
    logic: Literal["AND", "OR"] = "AND"
    conditions: List[Union[FilterCondition, "ComplexFilter"]]


class HavingCondition(BaseModel):
    """Condition to filter aggregated results (applies after GROUP BY)"""

    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte"] = "eq"
    value: Union[int, float]

    @field_validator("value")
    @classmethod
    def validate_value(cls, v):
        if not isinstance(v, (int, float)):
            raise ValueError("HAVING value must be a number")
        return v


class HavingClause(BaseModel):
    """
    HAVING clause for filtering aggregated results.
    Supports nested AND/OR logic similar to ComplexFilter.
    """

    logic: Literal["AND", "OR"] = "AND"
    conditions: List[Union[HavingCondition, "HavingClause"]]

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v):
        if not v:
            raise ValueError("HAVING clause must have at least one condition")
        return v
