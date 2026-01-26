"""
precomputed_metrics_retriever.py

Retrieves precomputed metrics from summary tables (TMB, mutation counts, etc.).
Provides fast access to pre-calculated sample-level statistics.

Author: Generated based on dbGENVOC API patterns
Date: 2026-01-23
"""

from enum import Enum
from fastapi import HTTPException
from sqlalchemy import or_, asc, desc, and_
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.schema_new import ComplexFilter
from app.core import (
    row_to_dict,
    apply_filters,
    get_model_class,
    validate_columns,
)


# ==========================================
# SCHEMAS
# ==========================================

class MetricType(str, Enum):
    """Types of precomputed metrics available"""
    tmb = "tmb"  # Tumor Mutation Burden
    mutation_count = "mutation_count"  # Total mutation counts
    sample_summary = "sample_summary"  # Sample-level summaries


class SortOrder(str, Enum):
    """Sort order"""
    ASC = "asc"
    DESC = "desc"


class PrecomputedMetricsRequest(BaseModel):
    """Request model for retrieving precomputed metrics"""

    # Dataset to query
    dataset: str = Field(
        ...,
        description="Dataset name (e.g., 'nibmg_exome_somatic', 'tcga_exome_somatic')"
    )

    # Metric type
    metric_type: MetricType = Field(
        MetricType.tmb,
        description="Type of metric to retrieve (tmb, mutation_count, sample_summary)"
    )

    # Sample filters
    sample_ids: Optional[List[str]] = Field(
        None,
        description="Specific sample IDs to retrieve (if None, returns all)"
    )

    # TMB-specific filters
    tmb_min: Optional[float] = Field(
        None,
        ge=0,
        description="Minimum TMB threshold (mutations per Mb)"
    )

    tmb_max: Optional[float] = Field(
        None,
        ge=0,
        description="Maximum TMB threshold (mutations per Mb)"
    )

    # Mutation count filters
    mutation_count_min: Optional[int] = Field(
        None,
        ge=0,
        description="Minimum mutation count"
    )

    mutation_count_max: Optional[int] = Field(
        None,
        description="Maximum mutation count"
    )

    # Advanced filters (using ComplexFilter structure)
    filters: Optional[ComplexFilter] = Field(
        None,
        description="Complex filters with AND/OR logic"
    )

    # Sorting
    sort_by: Optional[str] = Field(
        None,
        description="Column to sort by (e.g., 'tmb', 'mutation_count', 'sample_id')"
    )

    sort_order: SortOrder = Field(
        SortOrder.DESC,
        description="Sort direction"
    )

    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(100, ge=1, le=10000, description="Results per page")

    @field_validator("tmb_max")
    @classmethod
    def validate_tmb_range(cls, v, info):
        """Validate TMB range is valid"""
        tmb_min = info.data.get("tmb_min")
        if v is not None and tmb_min is not None and v < tmb_min:
            raise ValueError("tmb_max must be greater than or equal to tmb_min")
        return v

    @field_validator("mutation_count_max")
    @classmethod
    def validate_mutation_count_range(cls, v, info):
        """Validate mutation count range is valid"""
        mutation_count_min = info.data.get("mutation_count_min")
        if v is not None and mutation_count_min is not None and v < mutation_count_min:
            raise ValueError(
                "mutation_count_max must be greater than or equal to mutation_count_min"
            )
        return v


class PrecomputedMetricsResponse(BaseModel):
    """Response model for precomputed metrics"""

    dataset: str
    metric_type: str
    table_name: str
    total_results: int
    page: int
    page_size: int
    sort_by: Optional[str] = None
    sort_order: str
    results: List[Dict[str, Any]]


# ==========================================
# INTERNAL HELPERS
# ==========================================

def _get_metric_table_name(dataset: str, metric_type: MetricType) -> str:
    """
    Construct the table name for the metric type.

    Args:
        dataset: Base dataset name (e.g., 'nibmg_exome_somatic')
        metric_type: Type of metric

    Returns:
        Full table name
    """
    if metric_type == MetricType.tmb:
        return f"{dataset}_sample_tmb"
    elif metric_type == MetricType.mutation_count:
        return f"{dataset}_sample_mutation_count"
    elif metric_type == MetricType.sample_summary:
        return f"{dataset}_sample_summary"
    else:
        raise ValueError(f"Unknown metric type: {metric_type}")


def _apply_metric_filters(
    query,
    model_class,
    request: PrecomputedMetricsRequest
):
    """
    Apply metric-specific filters to the query.

    Args:
        query: SQLAlchemy query
        model_class: The model class
        request: Request with filter parameters

    Returns:
        Filtered query
    """
    # Apply sample ID filter
    if request.sample_ids:
        # Try common sample ID column names
        if hasattr(model_class, 'tumor_sample_barcode'):
            query = query.filter(model_class.tumor_sample_barcode.in_(request.sample_ids))
        elif hasattr(model_class, 'sample_id'):
            query = query.filter(model_class.sample_id.in_(request.sample_ids))
        elif hasattr(model_class, 'sample'):
            query = query.filter(model_class.sample.in_(request.sample_ids))

    # Apply TMB filters
    if request.metric_type == MetricType.tmb:
        if hasattr(model_class, 'tmb'):
            if request.tmb_min is not None:
                query = query.filter(model_class.tmb >= request.tmb_min)
            if request.tmb_max is not None:
                query = query.filter(model_class.tmb <= request.tmb_max)

    # Apply mutation count filters
    if request.mutation_count_min is not None:
        if hasattr(model_class, 'mutation_count'):
            query = query.filter(model_class.mutation_count >= request.mutation_count_min)
        elif hasattr(model_class, 'total_mutations'):
            query = query.filter(model_class.total_mutations >= request.mutation_count_min)

    if request.mutation_count_max is not None:
        if hasattr(model_class, 'mutation_count'):
            query = query.filter(model_class.mutation_count <= request.mutation_count_max)
        elif hasattr(model_class, 'total_mutations'):
            query = query.filter(model_class.total_mutations <= request.mutation_count_max)

    return query


def _apply_sorting(
    query,
    model_class,
    sort_by: Optional[str],
    sort_order: SortOrder
):
    """
    Apply sorting to the query.

    Args:
        query: SQLAlchemy query
        model_class: Model class
        sort_by: Column to sort by
        sort_order: Sort direction

    Returns:
        Sorted query
    """
    if not sort_by:
        return query

    if not hasattr(model_class, sort_by):
        raise HTTPException(
            status_code=400,
            detail=f"Column '{sort_by}' does not exist in table"
        )

    col_attr = getattr(model_class, sort_by)

    if sort_order == SortOrder.DESC:
        return query.order_by(desc(col_attr))
    else:
        return query.order_by(asc(col_attr))


# ==========================================
# MAIN API FUNCTION
# ==========================================

async def precomputed_metrics_retriever(
    request: PrecomputedMetricsRequest,
    db
) -> PrecomputedMetricsResponse:
    """
    Retrieve precomputed metrics from summary tables.

    This function provides fast access to pre-calculated sample-level statistics
    like TMB (Tumor Mutation Burden), mutation counts, and other summary metrics.

    The function automatically determines the correct table based on the dataset
    and metric_type, then applies filters, sorting, and pagination.

    Args:
        request: PrecomputedMetricsRequest with query parameters
        db: Database session

    Returns:
        PrecomputedMetricsResponse with metric data

    Example Requests:
    -----------------

    1. Get High TMB Samples:
    {
      "dataset": "nibmg_exome_somatic",
      "metric_type": "tmb",
      "tmb_min": 10,
      "sort_by": "tmb",
      "sort_order": "desc",
      "page": 1,
      "page_size": 50
    }

    2. Get Specific Samples:
    {
      "dataset": "tcga_exome_somatic",
      "metric_type": "tmb",
      "sample_ids": ["TCGA-A1-A0SB", "TCGA-A1-A0SD"],
      "sort_by": "tmb",
      "sort_order": "asc"
    }

    3. Get Samples in TMB Range:
    {
      "dataset": "nibmg_exome_somatic",
      "metric_type": "tmb",
      "tmb_min": 5,
      "tmb_max": 20,
      "mutation_count_min": 100,
      "sort_by": "mutation_count",
      "sort_order": "desc"
    }

    4. Use Complex Filters:
    {
      "dataset": "tcga_exome_somatic",
      "metric_type": "tmb",
      "filters": {
        "logic": "AND",
        "conditions": [
          {"column": "tmb", "operator": "gt", "value": 10},
          {"column": "mutation_count", "operator": "gte", "value": 200}
        ]
      },
      "sort_by": "tmb",
      "sort_order": "desc",
      "limit": 100
    }
    """

    try:
        # 1. Determine table name
        table_name = _get_metric_table_name(request.dataset, request.metric_type)

        # 2. Get model class
        try:
            model_class = get_model_class(table_name)
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"Metric table '{table_name}' not found. "
                       f"Ensure precomputed metrics exist for dataset '{request.dataset}'. "
                       f"Error: {str(e)}"
            )

        # 3. Build base query
        query = db.query(model_class)

        # 4. Apply complex filters (if provided)
        if request.filters:
            query = apply_filters(query, model_class, request.filters)

        # 5. Apply metric-specific filters
        query = _apply_metric_filters(query, model_class, request)

        # 6. Apply sorting
        query = _apply_sorting(query, model_class, request.sort_by, request.sort_order)

        # 7. Get total count (before pagination)
        total_results = query.count()

        # 8. Apply pagination
        offset = (request.page - 1) * request.page_size
        results = query.offset(offset).limit(request.page_size).all()

        # 9. Format response
        return PrecomputedMetricsResponse(
            dataset=request.dataset,
            metric_type=request.metric_type.value,
            table_name=table_name,
            total_results=total_results,
            page=request.page,
            page_size=request.page_size,
            sort_by=request.sort_by,
            sort_order=request.sort_order.value,
            results=[row_to_dict(row) for row in results]
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )


# ==========================================
# UTILITY FUNCTIONS
# ==========================================

async def get_tmb_statistics(dataset: str, db) -> Dict[str, Any]:
    """
    Get summary statistics for TMB in a dataset.

    Args:
        dataset: Dataset name
        db: Database session

    Returns:
        Dictionary with min, max, mean, median TMB
    """
    from sqlalchemy import func

    try:
        table_name = f"{dataset}_sample_tmb"
        model_class = get_model_class(table_name)

        stats = db.query(
            func.min(model_class.tmb).label('min_tmb'),
            func.max(model_class.tmb).label('max_tmb'),
            func.avg(model_class.tmb).label('mean_tmb'),
            func.count(model_class.tmb).label('sample_count')
        ).first()

        return {
            "dataset": dataset,
            "min_tmb": float(stats.min_tmb) if stats.min_tmb else 0,
            "max_tmb": float(stats.max_tmb) if stats.max_tmb else 0,
            "mean_tmb": float(stats.mean_tmb) if stats.mean_tmb else 0,
            "sample_count": int(stats.sample_count) if stats.sample_count else 0
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate TMB statistics: {str(e)}"
        )


async def get_high_tmb_samples(
    dataset: str,
    threshold: float,
    db,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get samples with TMB above a threshold (convenience function).

    Args:
        dataset: Dataset name
        threshold: TMB threshold
        db: Database session
        limit: Maximum number of results

    Returns:
        List of samples with high TMB
    """
    request = PrecomputedMetricsRequest(
        dataset=dataset,
        metric_type=MetricType.tmb,
        tmb_min=threshold,
        sort_by="tmb",
        sort_order=SortOrder.DESC,
        page=1,
        page_size=limit
    )

    response = await precomputed_metrics_retriever(request, db)
    return response.results


# ==========================================
# EXAMPLE USAGE
# ==========================================

"""
Example Integration in FastAPI Router:
---------------------------------------

from precomputed_metrics_retriever import (
    precomputed_metrics_retriever,
    PrecomputedMetricsRequest,
    PrecomputedMetricsResponse,
    get_tmb_statistics,
    get_high_tmb_samples
)

@router.post("/precomputed_metrics_retriever", response_model=PrecomputedMetricsResponse)
async def retrieve_metrics(
    request: PrecomputedMetricsRequest,
    db: Session = Depends(get_db)
):
    return await precomputed_metrics_retriever(request, db)


@router.get("/tmb_statistics/{dataset}")
async def tmb_stats(
    dataset: str,
    db: Session = Depends(get_db)
):
    return await get_tmb_statistics(dataset, db)


@router.get("/high_tmb_samples/{dataset}")
async def high_tmb(
    dataset: str,
    threshold: float = 10.0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return await get_high_tmb_samples(dataset, threshold, db, limit)


Example Requests:
----------------

1. MSI-H Detection (TMB > 10):
curl -X POST "http://localhost:8000/precomputed_metrics_retriever" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "nibmg_exome_somatic",
    "metric_type": "tmb",
    "tmb_min": 10,
    "sort_by": "tmb",
    "sort_order": "desc",
    "page_size": 50
  }'

2. Low Mutation Burden Samples:
curl -X POST "http://localhost:8000/precomputed_metrics_retriever" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "tcga_exome_somatic",
    "metric_type": "tmb",
    "tmb_max": 1,
    "mutation_count_max": 50,
    "sort_by": "mutation_count",
    "sort_order": "asc"
  }'

3. Specific Sample TMB:
curl -X POST "http://localhost:8000/precomputed_metrics_retriever" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "nibmg_exome_somatic",
    "metric_type": "tmb",
    "sample_ids": ["SAMPLE001", "SAMPLE002", "SAMPLE003"]
  }'

Expected Response:
-----------------
{
  "dataset": "nibmg_exome_somatic",
  "metric_type": "tmb",
  "table_name": "nibmg_exome_somatic_sample_tmb",
  "total_results": 42,
  "page": 1,
  "page_size": 50,
  "sort_by": "tmb",
  "sort_order": "desc",
  "results": [
    {
      "tumor_sample_barcode": "SAMPLE001",
      "tmb": 15.7,
      "mutation_count": 471,
      "genome_size_mb": 30.0
    },
    {
      "tumor_sample_barcode": "SAMPLE005",
      "tmb": 12.3,
      "mutation_count": 369,
      "genome_size_mb": 30.0
    }
  ]
}
"""
