from enum import Enum
from typing import Any, List, Union, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class ComputedFieldType(str, Enum):
    concat = "concat"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class AggregationType(str, Enum):
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"
    count = "count"
    percentage = "percentage"
    distinct_count = "distinct_count"


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


class FilterCondition(BaseModel):
    value: Any
    column: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "like"] = (
        "eq"
    )


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
