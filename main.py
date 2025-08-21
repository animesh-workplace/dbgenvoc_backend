from typing import Optional
from app.session import get_db
from sqlalchemy.orm import Session
from app.core import GERMLINE_TABLES
from app.api.search import generic_search
from app.api.aggregate import generic_aggregate
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, Path, HTTPException, APIRouter
from app.auth import verify_germline_token, TokenInfo, require_germline_access
from app.api.concate_aggregate import generic_concatenated_aggregate
from app.schema import (
    SearchRequest,
    SearchResponse,
    AggregationRequest,
    AggregationResponse,
    ConcatenatedAggregationRequest,
)

api_router = APIRouter()
BASE_URL = "/dbgenvoc/api/v2"


@api_router.get("/{table_name}/search", response_model=SearchResponse)
async def TABLE_SEARCH_API(
    request: SearchRequest,
    db: Session = Depends(get_db),
    token_info: Optional[TokenInfo] = Depends(verify_germline_token),
    table_name: str = Path(..., description="Name of the table to search"),
):
    """Generic search across any table."""
    authenticated_user = require_germline_access(table_name, token_info)
    if table_name in GERMLINE_TABLES and not authenticated_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied for germline tables without valid token",
        )
    return await generic_search(table_name=table_name, request=request, db=db)


@api_router.post("/{table_name}/aggregate", response_model=AggregationResponse)
async def TABLE_AGGREGATE_API(
    request: AggregationRequest,
    db: Session = Depends(get_db),
    token_info: Optional[TokenInfo] = Depends(verify_germline_token),
    table_name: str = Path(..., description="Name of the table to aggregate"),
):
    """Generic aggregation for any table."""
    authenticated_user = require_germline_access(table_name, token_info)
    if table_name in GERMLINE_TABLES and not authenticated_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied for germline tables without valid token",
        )
    return await generic_aggregate(request=request, db=db, table_name=table_name)


@api_router.post(
    "/{table_name}/aggregate-concatenated", response_model=AggregationResponse
)
async def TABLE_AGGREGATE_CONCATE_API(
    request: ConcatenatedAggregationRequest,
    db: Session = Depends(get_db),
    token_info: Optional[TokenInfo] = Depends(verify_germline_token),
    table_name: str = Path(..., description="Name of the table to aggregate"),
):
    """Generic concatenated aggregation (e.g., ref_allele>tumor_seq_allele2)."""
    authenticated_user = require_germline_access(table_name, token_info)
    if table_name in GERMLINE_TABLES and not authenticated_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied for germline tables without valid token",
        )
    return await generic_concatenated_aggregate(
        request=request, table_name=table_name, db=db
    )


app = FastAPI()
origins = ["http://localhost:3011", "http://10.10.6.80"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
)
app.include_router(api_router, prefix=BASE_URL)
