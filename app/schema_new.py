from pydantic import BaseModel
from typing import Any, List, Union, Literal


class FilterCondition(BaseModel):
    value: Any
    column: str
    operator: Literal["eq", "neq", "gt", "lt", "in", "not_in", "like"] = "eq"


class ComplexFilter(BaseModel):
    logic: Literal["AND", "OR"] = "AND"
    conditions: List[Union[FilterCondition, "ComplexFilter"]]
