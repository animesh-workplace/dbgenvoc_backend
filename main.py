import json
from app.session import get_db
from typing import Optional, List
from sqlalchemy.orm import Session
from app.core import GERMLINE_TABLE_REGISTRY
from app.api.oncoplot import oncoplot_search
from fastapi.responses import StreamingResponse
from app.api.ask_ai import VocalResearchWorkflow
from fastapi.middleware.cors import CORSMiddleware
from app.api.interactions import interaction_search
from app.api.search import SearchRequest, SearchResponse, generic_search
from fastapi import FastAPI, Depends, Path, HTTPException, APIRouter, Query
from app.auth import verify_germline_token, TokenInfo, require_germline_access
from app.api.structure import get_protein_structure, StructureResponse, StructureRequest
from app.api.aggregate import generic_aggregate, AggregationRequest, AggregationResponse
from app.api.precomputed_metrics_retriever import (
    precomputed_metrics_retriever,
    PrecomputedMetricsRequest,
    PrecomputedMetricsResponse,
    get_tmb_statistics,
    get_high_tmb_samples,
)
from app.api.proximity_variant_finder import (
    ProximityVariantRequest,
    ProximityVariantResponse,
    proximity_variant_finder,
)
from app.api.aggregate_combination import (
    ConcatenatedAggregationRequest,
    ConcatenatedAggregationResponse,
    generic_concatenated_aggregate,
)
from app.api.autocomplete import (
    SuggestionSection,
    AutocompleteRequest,
    unified_autocomplete,
)

from app.schema import (
    OncoplotRequest,
)

# from app.api.oncoplot_data_retriever import (
#     oncoplot_data_retriever,
#     OncoplotRequest,
#     OncoplotResponse,
#     format_for_complexheatmap,
#     format_for_maftools,
# )
from app.api.cross_dataset_comparator import (
    cross_dataset_comparator,
    CrossDatasetRequest,
    CrossDatasetResponse,
)

api_router = APIRouter()
BASE_URL = "/dbgenvoc/api/v2"


@api_router.post("/{table_name}/search", response_model=SearchResponse)
async def TABLE_SEARCH_API(
    request: SearchRequest,
    db: Session = Depends(get_db),
    token_info: Optional[TokenInfo] = Depends(verify_germline_token),
    table_name: str = Path(..., description="Name of the table to search"),
):
    """Generic search across any table."""
    authenticated_user = require_germline_access(table_name, token_info)
    if table_name in GERMLINE_TABLE_REGISTRY and not authenticated_user:
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
    if table_name in GERMLINE_TABLE_REGISTRY and not authenticated_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied for germline tables without valid token",
        )
    return await generic_aggregate(request=request, db=db, table_name=table_name)


@api_router.post(
    "/{table_name}/aggregate-concatenated",
    response_model=ConcatenatedAggregationResponse,
)
async def TABLE_AGGREGATE_CONCATE_API(
    request: ConcatenatedAggregationRequest,
    db: Session = Depends(get_db),
    token_info: Optional[TokenInfo] = Depends(verify_germline_token),
    table_name: str = Path(..., description="Name of the table to aggregate"),
):
    """Generic concatenated aggregation (e.g., ref_allele>tumor_seq_allele2)."""
    authenticated_user = require_germline_access(table_name, token_info)
    if table_name in GERMLINE_TABLE_REGISTRY and not authenticated_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied for germline tables without valid token",
        )
    return await generic_concatenated_aggregate(
        request=request, table_name=table_name, db=db
    )


@api_router.post("/{table_name}/oncoplot")
async def TABLE_ONCOPLOT_API(
    request: OncoplotRequest,
    db: Session = Depends(get_db),
    token_info: Optional[TokenInfo] = Depends(verify_germline_token),
    table_name: str = Path(..., description="Name of the table to get oncoplot data"),
):
    """Oncoplot search supporting multiple gene terms."""
    authenticated_user = require_germline_access(table_name, token_info)
    if table_name in GERMLINE_TABLE_REGISTRY and not authenticated_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied for germline tables without valid token",
        )
    return await oncoplot_search(request=request, table_name=table_name, db=db)


@api_router.post("/{table_name}/interactions")
async def TABLE_INTERACTION_API(
    request: OncoplotRequest,
    db: Session = Depends(get_db),
    token_info: Optional[TokenInfo] = Depends(verify_germline_token),
    table_name: str = Path(
        ..., description="Name of the table to get interaction data"
    ),
):
    """Oncoplot search supporting multiple gene terms."""
    authenticated_user = require_germline_access(table_name, token_info)
    if table_name in GERMLINE_TABLE_REGISTRY and not authenticated_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied for germline tables without valid token",
        )
    return await interaction_search(request=request, table_name=table_name, db=db)


@api_router.post("/autocomplete", response_model=List[SuggestionSection])
async def autocomplete_unified(
    request: AutocompleteRequest, db: Session = Depends(get_db)
):
    """Unified autocomplete returning genes and pathways with pathway genes"""
    return await unified_autocomplete(term=request.term, limit=request.limit, db=db)


@api_router.post("/structure", response_model=StructureResponse)
async def fetch_structure(request: StructureRequest, db: Session = Depends(get_db)):
    """
    Get protein structure domains/regions dynamically by gene name.
    """
    return await get_protein_structure(request, db)


# @api_router.post(
#     "/precomputed_metrics_retriever", response_model=PrecomputedMetricsResponse
# )
# async def retrieve_metrics(
#     request: PrecomputedMetricsRequest, db: Session = Depends(get_db)
# ):
#     return await precomputed_metrics_retriever(request, db)


@api_router.post(
    "/{table_name}/proximity_variant_finder", response_model=ProximityVariantResponse
)
async def variant_finder(
    request: ProximityVariantRequest,
    db: Session = Depends(get_db),
    token_info: Optional[TokenInfo] = Depends(verify_germline_token),
    table_name: str = Path(
        ..., description="Name of the table to get interaction data"
    ),
):
    return await proximity_variant_finder(request=request, table_name=table_name, db=db)


# @api_router.post(
#     "/{table_name}/oncoplot_data_retriever", response_model=OncoplotResponse
# )
# async def retrieve_oncoplot_data(
#     table_name: str, request: OncoplotRequest, db: Session = Depends(get_db)
# ):
#     return await oncoplot_data_retriever(request, table_name, db)


# @api_router.post("/cross_dataset_comparator", response_model=CrossDatasetResponse)
# async def cross_dataset_comparator_endpoint(
#     request: CrossDatasetRequest,
#     db: Session = Depends(get_db),
# ):
#     return await cross_dataset_comparator(request, db)


@api_router.get("/ask")
async def ask_endpoint(
    query: str = Query(..., description="Natural language query"),
    stream: bool = Query(False, description="Enable streaming response"),
    db: Session = Depends(get_db),
):
    research_workflow = VocalResearchWorkflow(name="Parallel Research Pipeline")

    try:
        if stream:
            # Return streaming response
            async def event_generator():
                try:
                    async for event in research_workflow.run_stream(query, db):
                        # Format as Server-Sent Events
                        yield f"data: {json.dumps(event)}\n\n"
                except Exception as e:
                    error_event = {"type": "error", "data": {"error": str(e)}}
                    yield f"data: {json.dumps(error_event)}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                },
            )
        else:
            # Non-streaming response (backwards compatible)
            result = await research_workflow.run_async(query, db)
            return result

    except Exception as e:
        print(f"Workflow Critical Failure: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your research workflow.",
        )


app = FastAPI()
origins = ["http://10.10.6.80", "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
)
app.include_router(api_router, prefix=BASE_URL)
