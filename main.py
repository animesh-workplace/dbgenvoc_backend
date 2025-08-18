from enum import Enum
from app.models import (
    EsTcga,
    Pathway,
    Uniprot,
    Genelist,
    EsJournal,
    WgSomatic,
    Samplelist,
    WgGermline,
    ExomeSomatic,
    ExomeGermline,
    TargetedSomatic,
    TargetedGermline,
)
from app.session import get_db
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, and_
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any, Union
from fastapi import FastAPI, Depends, Query, HTTPException, Path
from app.api.search import generic_search
from app.api.aggregate import generic_aggregate
from app.api.concate_aggregate import generic_concatenated_aggregate
from app.schema import (
    SearchRequest,
    SearchResponse,
    AggregationRequest,
    AggregationResponse,
    ConcatenatedAggregationRequest,
)

app = FastAPI()
origins = ["http://localhost:3011", "http://10.10.6.80"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
)
BASE_URL = "/dbgenvoc/api/"


@app.get("/{table_name}/search", response_model=SearchResponse)
async def TABLE_SEARCH_API(
    request: SearchRequest,
    db: Session = Depends(get_db),
    table_name: str = Path(..., description="Name of the table to search"),
):
    """Generic search across any table."""
    return await generic_search(table_name=table_name, request=request, db=db)


@app.post("/{table_name}/aggregate", response_model=AggregationResponse)
async def TABLE_AGGREGATE_API(
    request: AggregationRequest,
    db: Session = Depends(get_db),
    table_name: str = Path(..., description="Name of the table to aggregate"),
):
    """Generic aggregation for any table."""
    return await generic_aggregate(request=request, db=db, table_name=table_name)


@app.post("/{table_name}/aggregate-concatenated", response_model=AggregationResponse)
async def TABLE_AGGREGATE_CONCATE_API(
    request: ConcatenatedAggregationRequest,
    table_name: str = Path(..., description="Name of the table to aggregate"),
    db: Session = Depends(get_db),
):
    """Generic concatenated aggregation (e.g., ref_allele>tumor_seq_allele2)."""
    return await generic_concatenated_aggregate(
        request=request, table_name=table_name, db=db
    )
