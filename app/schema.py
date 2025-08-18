from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union


class AggregationType(str, Enum):
    sum = "sum"  # Sum of values
    avg = "avg"  # Average of values
    min = "min"  # Minimum value
    max = "max"  # Maximum value
    count = "count"  # Count of records
    distinct_count = "distinct_count"  # Count of distinct values


class SearchRequest(BaseModel):
    term: str = Field(..., description="Search term")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Results per page")
    exact_match: bool = Field(False, description="Exact match or partial match")
    search_columns: Optional[List[str]] = Field(
        None, description="Specific columns to search"
    )


class SearchResponse(BaseModel):
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of results per page")
    table_name: str = Field(..., description="Name of the table searched")
    total_results: int = Field(..., description="Total number of results found")
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
