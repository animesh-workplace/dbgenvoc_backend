from enum import Enum
from db.session import get_db
from models import ExomeGermline
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from fastapi import Depends, HTTPException, Query


# Pydantic models for API responses
class ExomeGermlineResponse(BaseModel):
    egm_id: int
    gene: Optional[str]
    entrez_gene_id: Optional[int]
    ncbi_build: Optional[str]
    chrom: Optional[str]
    start: Optional[str]
    end: Optional[str]
    variant_class: Optional[str]
    variant_type: Optional[str]
    ref_allele: Optional[str]
    tumor_seq_allele2: Optional[str]
    dbsnp_rs: Optional[str]
    tumor_sample_barcode: Optional[str]
    sample_id: Optional[str]
    genome_change: Optional[str]
    annotation_transcript: Optional[str]
    transcript_strand: Optional[str]
    transcript_exon: Optional[str]
    transcript_position: Optional[str]
    cDNA_change: Optional[str]
    codon_change: Optional[str]
    protein_change: Optional[str]
    disease: Optional[str]
    reference_url: Optional[str]
    reference: Optional[str]
    remarks: Optional[str]

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    total_results: int
    page: int
    page_size: int
    results: List[ExomeGermlineResponse]


class AggregationType(str, Enum):
    count = "count"
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"
    distinct_count = "distinct_count"


class AggregationRequest(BaseModel):
    column: str = Field(..., description="Column name to aggregate")
    aggregation_type: AggregationType = Field(..., description="Type of aggregation")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")
    filters: Optional[Dict[str, Any]] = Field(
        None, description="Filters to apply before aggregation"
    )


class AggregationResponse(BaseModel):
    column: str
    aggregation_type: str
    result: Union[Dict[str, Any], List[Dict[str, Any]]]
    total_records: int


@app.get("/search", response_model=SearchResponse)
async def search_exome_germline(
    term: str = Query(
        ..., description="Search term to look for across multiple columns"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of results per page"),
    exact_match: bool = Query(
        False, description="Whether to perform exact match or partial match"
    ),
    search_columns: Optional[List[str]] = Query(
        None, description="Specific columns to search in"
    ),
    db: Session = Depends(get_db),
):
    """
    Search the ExomeGermline table for records matching the given term.
    Searches across multiple key columns by default.
    """
    try:
        # Define searchable columns (prioritizing indexed and commonly searched fields)
        default_search_columns = [
            "gene",
            "chrom",
            "sample_id",
            "disease",
            "variant_class",
            "variant_type",
            "dbsnp_rs",
            "protein_change",
            "genome_change",
        ]

        columns_to_search = search_columns if search_columns else default_search_columns

        # Build the query
        query = db.query(ExomeGermline)

        # Create search conditions
        search_conditions = []
        for column in columns_to_search:
            if hasattr(ExomeGermline, column):
                col_attr = getattr(ExomeGermline, column)
                if exact_match:
                    search_conditions.append(col_attr == term)
                else:
                    search_conditions.append(col_attr.ilike(f"%{term}%"))

        if search_conditions:
            query = query.filter(or_(*search_conditions))

        # Get total count
        total_results = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        return SearchResponse(
            total_results=total_results,
            page=page,
            page_size=page_size,
            results=[ExomeGermlineResponse.from_orm(result) for result in results],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/aggregate", response_model=AggregationResponse)
async def aggregate_column_data(
    request: AggregationRequest, db: Session = Depends(get_db)
):
    """
    Perform aggregation on specified column with optional grouping and filtering.
    """
    try:
        # Verify column exists
        if not hasattr(ExomeGermline, request.column):
            raise HTTPException(
                status_code=400, detail=f"Column '{request.column}' does not exist"
            )

        col_attr = getattr(ExomeGermline, request.column)

        # Start building query
        query = db.query(ExomeGermline)

        # Apply filters if provided
        if request.filters:
            filter_conditions = []
            for filter_col, filter_value in request.filters.items():
                if hasattr(ExomeGermline, filter_col):
                    filter_attr = getattr(ExomeGermline, filter_col)
                    if isinstance(filter_value, list):
                        filter_conditions.append(filter_attr.in_(filter_value))
                    else:
                        filter_conditions.append(filter_attr == filter_value)

            if filter_conditions:
                query = query.filter(and_(*filter_conditions))

        # Get total records count (before aggregation)
        total_records = query.count()

        # Perform aggregation
        if request.group_by:
            # Group by aggregation
            group_columns = []
            for group_col in request.group_by:
                if hasattr(ExomeGermline, group_col):
                    group_columns.append(getattr(ExomeGermline, group_col))

            if not group_columns:
                raise HTTPException(status_code=400, detail="Invalid group_by columns")

            # Build aggregation query
            if request.aggregation_type == AggregationType.count:
                agg_func = func.count(col_attr)
            elif request.aggregation_type == AggregationType.sum:
                agg_func = func.sum(col_attr)
            elif request.aggregation_type == AggregationType.avg:
                agg_func = func.avg(col_attr)
            elif request.aggregation_type == AggregationType.min:
                agg_func = func.min(col_attr)
            elif request.aggregation_type == AggregationType.max:
                agg_func = func.max(col_attr)
            elif request.aggregation_type == AggregationType.distinct_count:
                agg_func = func.count(func.distinct(col_attr))

            agg_query = db.query(
                *group_columns, agg_func.label("aggregated_value")
            ).group_by(*group_columns)

            # Apply same filters to aggregation query
            if request.filters:
                agg_query = agg_query.filter(and_(*filter_conditions))

            results = agg_query.all()

            # Format results
            formatted_results = []
            for result in results:
                result_dict = {}
                for i, group_col in enumerate(request.group_by):
                    result_dict[group_col] = result[i]
                result_dict["aggregated_value"] = result[-1]
                formatted_results.append(result_dict)

            return AggregationResponse(
                column=request.column,
                aggregation_type=request.aggregation_type.value,
                result=formatted_results,
                total_records=total_records,
            )

        else:
            # Simple aggregation without grouping
            if request.aggregation_type == AggregationType.count:
                result = query.count()
            elif request.aggregation_type == AggregationType.sum:
                result = (
                    db.query(func.sum(col_attr)).filter(query.whereclause).scalar() or 0
                )
            elif request.aggregation_type == AggregationType.avg:
                result = (
                    db.query(func.avg(col_attr)).filter(query.whereclause).scalar() or 0
                )
            elif request.aggregation_type == AggregationType.min:
                result = db.query(func.min(col_attr)).filter(query.whereclause).scalar()
            elif request.aggregation_type == AggregationType.max:
                result = db.query(func.max(col_attr)).filter(query.whereclause).scalar()
            elif request.aggregation_type == AggregationType.distinct_count:
                result = (
                    db.query(func.count(func.distinct(col_attr)))
                    .filter(query.whereclause)
                    .scalar()
                    or 0
                )

            return AggregationResponse(
                column=request.column,
                aggregation_type=request.aggregation_type.value,
                result={"value": result},
                total_records=total_records,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
