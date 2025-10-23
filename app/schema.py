from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union


class AggregationType(str, Enum):
    sum = "sum"  # Sum of values
    avg = "avg"  # Average of values
    min = "min"  # Minimum value
    max = "max"  # Maximum value
    count = "count"  # Count of records
    distinct_count = "distinct_count"  # Count of distinct values


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SearchMode(str, Enum):
    ANY = "any"
    ALL = "all"


class SearchRequest(BaseModel):
    term: Union[str, List[str]] = Field(
        ..., description="Search term(s) - single string or array of strings"
    )
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Results per page")
    exact_match: bool = Field(False, description="Exact match or partial match")
    search_columns: Optional[List[str]] = Field(
        None, description="Specific columns to search"
    )
    search_mode: SearchMode = Field(
        SearchMode.ANY,
        description="Search mode: 'any' (OR logic) or 'all' (AND logic) for multiple terms",
    )
    sort_by: Optional[str] = Field(
        None, description="Column name to sort the results by"
    )
    sort_order: SortOrder = Field(
        SortOrder.ASC,
        description="Sort order: 'asc' for ascending, 'desc' for descending",
    )

    @validator("sort_by")
    def validate_sort_by(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class SearchResponse(BaseModel):
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of results per page")
    table_name: str = Field(..., description="Name of the table searched")
    total_results: int = Field(..., description="Total number of results found")
    search_terms: List[str] = Field(..., description="Terms that were searched")
    search_mode: str = Field(..., description="Search mode used")
    sort_by: Optional[str] = Field(..., description="Column used for sorting")
    sort_order: str = Field(..., description="Sort order applied")
    results: List[Dict[str, Any]] = Field(
        ..., description="List of search results as dictionaries"
    )


class AggregationRequest(BaseModel):
    column: str = Field(..., description="Column to aggregate")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")
    filters: Optional[Dict[str, Any]] = Field(
        None, description="Filters to apply before aggregation"
    )
    aggregation_type: AggregationType = Field(
        AggregationType.count, description="Type of aggregation to perform"
    )


class AggregationResponse(BaseModel):
    column: str = Field(..., description="Column that was aggregated")
    table_name: str = Field(..., description="Name of the table aggregated")
    total_records: int = Field(..., description="Total number of records considered")
    aggregation_type: str = Field(
        ..., description="Type of aggregation performed (e.g., sum, avg, count)"
    )
    result: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(
        ...,
        description="Result of the aggregation, either a single value or a list of grouped results",
    )


class ConcatenatedAggregationRequest(BaseModel):
    separator: str = Field(", ", description="Separator for concatenated values")
    columns: List[str] = Field(..., description="List of columns to concatenate")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")
    filters: Optional[Dict[str, Any]] = Field(
        None, description="Filters to apply before concatenation"
    )
    aggregation_type: AggregationType = Field(
        AggregationType.count, description="Type of aggregation to perform"
    )


class TokenCreateRequest(BaseModel):
    user_identifier: str
    description: Optional[str] = None
    expires_in_days: Optional[int] = None  # None means no expiration
    permissions: Optional[List[str]] = None
    ip_whitelist: Optional[List[str]] = None


class TokenResponse(BaseModel):
    token: str
    token_id: int
    user_identifier: str
    created_at: datetime
    description: Optional[str]
    expires_at: Optional[datetime]


class SuggestionType(str, Enum):
    GENE = "gene"
    PATHWAY = "pathway"
    GENOMIC_REGION = "genomic_region"


class AutocompleteSuggestion(BaseModel):
    value: str
    type: SuggestionType
    pathway_genes: Optional[str] = None  # For pathway type
    table: Optional[str] = None  # For genomic_region type
    chromosome: Optional[str] = None  # For genomic_region type
    start: Optional[int] = None  # For genomic_region type
    end: Optional[int] = None  # For genomic_region type


class AutocompleteResponse(BaseModel):
    suggestions: List[AutocompleteSuggestion]


class AutocompleteRequest(BaseModel):
    term: str
    limit: int = 10


class GenomicRegionSuggestion(BaseModel):
    value: str
    type: str = "genomic_region"
    table: str
    chromosome: str
    start: int
    end: Optional[int] = None


class GenomicRegionResponse(BaseModel):
    suggestions: List[GenomicRegionSuggestion]


class GenomicRegionRequest(BaseModel):
    term: str
    limit: int = 10


class OncoplotRequest(BaseModel):
    genes: Optional[List[str]]


class OncoplotResponse(BaseModel):
    yAxis: List[str]
    xAxis: List[str]
    heatmap: List[List[Union[int, float]]]
