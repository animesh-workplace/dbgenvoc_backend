from enum import Enum
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union


class AggregationType(str, Enum):
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"
    count = "count"
    distinct_count = "distinct_count"


class SearchRequest(BaseModel):
    term: str
    page: int
    db: Session
    page_size: int
    table_name: str
    exact_match: bool
    search_columns: Optional[List[str]]


class SearchResponse(BaseModel):
    page: int
    page_size: int
    table_name: str
    total_results: int
    results: List[Dict[str, Any]]


class AggregationRequest(BaseModel):
    column: str
    group_by: Optional[List[str]]
    filters: Optional[Dict[str, Any]]
    aggregation_type: AggregationType


class AggregationResponse(BaseModel):
    column: str
    table_name: str
    total_records: int
    aggregation_type: str
    result: Union[Dict[str, Any], List[Dict[str, Any]]]


class ConcatenatedAggregationRequest(BaseModel):
    separator: str
    columns: List[str]
    group_by: Optional[List[str]]
    filters: Optional[Dict[str, Any]]
    aggregation_type: AggregationType
