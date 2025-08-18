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
from app.db.session import get_db
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, and_
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any, Union
from fastapi import FastAPI, Depends, Query, HTTPException, Path


app = FastAPI()
origins = ["http://localhost:3011", "http://10.10.6.80"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
)
BASE_URL = "/dbgenvoc/api/"


# Table registry mapping table names to models
TABLE_REGISTRY = {
    "es_journal": EsJournal,
    "es_tcga": EsTcga,
    "exome_germline": ExomeGermline,
    "exome_somatic": ExomeSomatic,
    "wg_germline": WgGermline,
    "wg_somatic": WgSomatic,
    "targeted_germline": TargetedGermline,
    "targeted_somatic": TargetedSomatic,
    "pathway": Pathway,
    "genelist": Genelist,
    "samplelist": Samplelist,
    "uniprot_fixed": Uniprot,
}

# Define searchable columns for each table type
SEARCHABLE_COLUMNS = {
    # Genomic tables (similar structure)
    "genomic_tables": {
        "primary": ["gene", "chrom", "disease", "variant_class", "variant_type"],
        "secondary": [
            "dbsnp_rs",
            "protein_change",
            "genome_change",
            "tumor_sample_barcode",
            "sample_id",
        ],
        "all": [
            "gene",
            "entrez_gene_id",
            "chrom",
            "start",
            "end",
            "variant_class",
            "variant_type",
            "ref_allele",
            "tumor_seq_allele2",
            "dbsnp_rs",
            "tumor_sample_barcode",
            "sample_id",
            "genome_change",
            "annotation_transcript",
            "protein_change",
            "disease",
            "remarks",
        ],
    },
    # Special tables
    "pathway": ["pathway_name", "path_gene", "disease"],
    "genelist": ["gene"],
    "samplelist": ["sample_id"],
    "uniprot_fixed": ["Hugo_Symbol", "Accession_Id"],
}

# Table categories for different handling
GENOMIC_TABLES = {
    "es_journal",
    "es_tcga",
    "exome_germline",
    "exome_somatic",
    "wg_germline",
    "wg_somatic",
    "targeted_germline",
    "targeted_somatic",
}

SPECIAL_TABLES = {"pathway", "genelist", "samplelist", "uniprot_fixed"}


# Pydantic models
class AggregationType(str, Enum):
    count = "count"
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"
    distinct_count = "distinct_count"


class GenericSearchResponse(BaseModel):
    table_name: str
    total_results: int
    page: int
    page_size: int
    results: List[Dict[str, Any]]


class GenericAggregationRequest(BaseModel):
    column: str = Field(..., description="Column name to aggregate")
    aggregation_type: AggregationType = Field(..., description="Type of aggregation")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")
    filters: Optional[Dict[str, Any]] = Field(
        None, description="Filters to apply before aggregation"
    )


class GenericAggregationResponse(BaseModel):
    table_name: str
    column: str
    aggregation_type: str
    result: Union[Dict[str, Any], List[Dict[str, Any]]]
    total_records: int


class ConcatenatedAggregationRequest(BaseModel):
    columns: List[str] = Field(..., description="Columns to concatenate")
    separator: str = Field(default=">", description="Separator for concatenation")
    aggregation_type: AggregationType = Field(..., description="Type of aggregation")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")
    filters: Optional[Dict[str, Any]] = Field(
        None, description="Filters to apply before aggregation"
    )


# Helper functions
def get_model_class(table_name: str):
    """Get the SQLAlchemy model class for a given table name."""
    if table_name not in TABLE_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found. Available tables: {list(TABLE_REGISTRY.keys())}",
        )
    return TABLE_REGISTRY[table_name]


def get_searchable_columns(table_name: str) -> List[str]:
    """Get searchable columns for a table."""
    if table_name in GENOMIC_TABLES:
        return (
            SEARCHABLE_COLUMNS["genomic_tables"]["primary"]
            + SEARCHABLE_COLUMNS["genomic_tables"]["secondary"]
        )
    elif table_name in SEARCHABLE_COLUMNS:
        return SEARCHABLE_COLUMNS[table_name]
    else:
        # Fallback: get all string columns
        model_class = get_model_class(table_name)
        return [
            col.name
            for col in model_class.__table__.columns
            if str(col.type).startswith("VARCHAR")
        ]


def validate_columns(model_class, column_names: List[str]) -> List[str]:
    """Validate that columns exist in the model."""
    valid_columns = []
    invalid_columns = []

    for col_name in column_names:
        if hasattr(model_class, col_name):
            valid_columns.append(col_name)
        else:
            invalid_columns.append(col_name)

    if invalid_columns:
        available_columns = [col.name for col in model_class.__table__.columns]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid columns: {invalid_columns}. Available columns: {available_columns}",
        )

    return valid_columns


def row_to_dict(row) -> Dict[str, Any]:
    """Convert SQLAlchemy row to dictionary."""
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


# Database dependency
def get_db():
    # Replace with your actual database session
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# API Endpoints
@app.get("/tables")
async def get_available_tables():
    """Get list of available tables and their searchable columns."""
    table_info = {}
    for table_name, model_class in TABLE_REGISTRY.items():
        columns = [col.name for col in model_class.__table__.columns]
        searchable = get_searchable_columns(table_name)
        table_info[table_name] = {
            "columns": columns,
            "searchable_columns": searchable,
            "primary_key": [
                col.name for col in model_class.__table__.primary_key.columns
            ],
        }
    return {"tables": table_info}


@app.get("/{table_name}/search", response_model=GenericSearchResponse)
async def generic_search(
    table_name: str = Path(..., description="Name of the table to search"),
    term: str = Query(..., description="Search term"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Results per page"),
    exact_match: bool = Query(False, description="Exact match or partial match"),
    search_columns: Optional[List[str]] = Query(
        None, description="Specific columns to search"
    ),
    db: Session = Depends(get_db),
):
    """Generic search across any table."""
    try:
        model_class = get_model_class(table_name)

        # Get searchable columns
        if search_columns:
            columns_to_search = validate_columns(model_class, search_columns)
        else:
            columns_to_search = get_searchable_columns(table_name)
            # Filter to only existing columns
            columns_to_search = [
                col for col in columns_to_search if hasattr(model_class, col)
            ]

        # Build query
        query = db.query(model_class)

        # Create search conditions
        search_conditions = []
        for column in columns_to_search:
            col_attr = getattr(model_class, column)
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

        # Convert to dictionaries
        result_dicts = [row_to_dict(row) for row in results]

        return GenericSearchResponse(
            table_name=table_name,
            total_results=total_results,
            page=page,
            page_size=page_size,
            results=result_dicts,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/{table_name}/aggregate", response_model=GenericAggregationResponse)
async def generic_aggregate(
    request: GenericAggregationRequest,
    table_name: str = Path(..., description="Name of the table to aggregate"),
    db: Session = Depends(get_db),
):
    """Generic aggregation for any table."""
    try:
        model_class = get_model_class(table_name)

        # Validate column
        validate_columns(model_class, [request.column])
        col_attr = getattr(model_class, request.column)

        # Validate group_by columns if provided
        if request.group_by:
            validate_columns(model_class, request.group_by)

        # Start building query
        query = db.query(model_class)

        # Apply filters
        filter_conditions = []
        if request.filters:
            for filter_col, filter_value in request.filters.items():
                if hasattr(model_class, filter_col):
                    filter_attr = getattr(model_class, filter_col)
                    if isinstance(filter_value, list):
                        filter_conditions.append(filter_attr.in_(filter_value))
                    else:
                        filter_conditions.append(filter_attr == filter_value)

            if filter_conditions:
                query = query.filter(and_(*filter_conditions))

        # Get total records
        total_records = query.count()

        # Perform aggregation
        if request.group_by:
            # Group by aggregation
            group_columns = [getattr(model_class, col) for col in request.group_by]

            # Build aggregation function
            agg_functions = {
                AggregationType.count: func.count(col_attr),
                AggregationType.sum: func.sum(col_attr),
                AggregationType.avg: func.avg(col_attr),
                AggregationType.min: func.min(col_attr),
                AggregationType.max: func.max(col_attr),
                AggregationType.distinct_count: func.count(func.distinct(col_attr)),
            }

            agg_func = agg_functions[request.aggregation_type]
            agg_query = db.query(
                *group_columns, agg_func.label("aggregated_value")
            ).group_by(*group_columns)

            # Apply filters to aggregation query
            if filter_conditions:
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

            return GenericAggregationResponse(
                table_name=table_name,
                column=request.column,
                aggregation_type=request.aggregation_type.value,
                result=formatted_results,
                total_records=total_records,
            )

        else:
            # Simple aggregation
            agg_functions = {
                AggregationType.count: query.count(),
                AggregationType.sum: db.query(func.sum(col_attr))
                .filter(*filter_conditions)
                .scalar()
                or 0
                if filter_conditions
                else db.query(func.sum(col_attr)).scalar() or 0,
                AggregationType.avg: db.query(func.avg(col_attr))
                .filter(*filter_conditions)
                .scalar()
                or 0
                if filter_conditions
                else db.query(func.avg(col_attr)).scalar() or 0,
                AggregationType.min: db.query(func.min(col_attr))
                .filter(*filter_conditions)
                .scalar()
                if filter_conditions
                else db.query(func.min(col_attr)).scalar(),
                AggregationType.max: db.query(func.max(col_attr))
                .filter(*filter_conditions)
                .scalar()
                if filter_conditions
                else db.query(func.max(col_attr)).scalar(),
                AggregationType.distinct_count: db.query(
                    func.count(func.distinct(col_attr))
                )
                .filter(*filter_conditions)
                .scalar()
                or 0
                if filter_conditions
                else db.query(func.count(func.distinct(col_attr))).scalar() or 0,
            }

            result = agg_functions[request.aggregation_type]

            return GenericAggregationResponse(
                table_name=table_name,
                column=request.column,
                aggregation_type=request.aggregation_type.value,
                result={"value": result},
                total_records=total_records,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")


@app.post(
    "/{table_name}/aggregate-concatenated", response_model=GenericAggregationResponse
)
async def generic_concatenated_aggregate(
    request: ConcatenatedAggregationRequest,
    table_name: str = Path(..., description="Name of the table to aggregate"),
    db: Session = Depends(get_db),
):
    """Generic concatenated aggregation (e.g., ref_allele>tumor_seq_allele2)."""
    try:
        model_class = get_model_class(table_name)

        # Validate columns
        validate_columns(model_class, request.columns)
        col_attrs = [getattr(model_class, col_name) for col_name in request.columns]

        # Validate group_by columns
        if request.group_by:
            validate_columns(model_class, request.group_by)

        # Create concatenated column expression
        concatenated_col = col_attrs[0]
        for i in range(1, len(col_attrs)):
            concatenated_col = func.concat(
                concatenated_col, request.separator, col_attrs[i]
            )

        # Build query with filters
        query = db.query(model_class)
        filter_conditions = []

        if request.filters:
            for filter_col, filter_value in request.filters.items():
                if hasattr(model_class, filter_col):
                    filter_attr = getattr(model_class, filter_col)
                    if isinstance(filter_value, list):
                        filter_conditions.append(filter_attr.in_(filter_value))
                    else:
                        filter_conditions.append(filter_attr == filter_value)

        if filter_conditions:
            query = query.filter(and_(*filter_conditions))

        total_records = query.count()

        # Perform aggregation
        if request.group_by:
            group_columns = [getattr(model_class, col) for col in request.group_by]

            if request.aggregation_type in [
                AggregationType.count,
                AggregationType.distinct_count,
            ]:
                if request.aggregation_type == AggregationType.count:
                    agg_func = func.count(concatenated_col)
                else:
                    agg_func = func.count(func.distinct(concatenated_col))

                agg_query = db.query(
                    *group_columns,
                    concatenated_col.label("concatenated_value"),
                    agg_func.label("count"),
                ).group_by(*group_columns, concatenated_col)

                if filter_conditions:
                    agg_query = agg_query.filter(and_(*filter_conditions))

                results = agg_query.all()

                formatted_results = []
                for result in results:
                    result_dict = {}
                    for i, group_col in enumerate(request.group_by):
                        result_dict[group_col] = result[i]
                    result_dict["concatenated_value"] = result[-2]
                    result_dict["count"] = result[-1]
                    formatted_results.append(result_dict)

                return GenericAggregationResponse(
                    table_name=table_name,
                    column=f"{'+'.join(request.columns)}",
                    aggregation_type=request.aggregation_type.value,
                    result=formatted_results,
                    total_records=total_records,
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Only count and distinct_count are supported for concatenated columns with grouping",
                )

        else:
            # Simple concatenated aggregation
            if request.aggregation_type == AggregationType.count:
                agg_query = db.query(
                    concatenated_col.label("concatenated_value"),
                    func.count(concatenated_col).label("count"),
                ).group_by(concatenated_col)

                if filter_conditions:
                    agg_query = agg_query.filter(and_(*filter_conditions))

                results = agg_query.all()
                formatted_results = [
                    {
                        "concatenated_value": result.concatenated_value,
                        "count": result.count,
                    }
                    for result in results
                ]

                return GenericAggregationResponse(
                    table_name=table_name,
                    column=f"{'+'.join(request.columns)}",
                    aggregation_type=request.aggregation_type.value,
                    result=formatted_results,
                    total_records=total_records,
                )

            elif request.aggregation_type == AggregationType.distinct_count:
                result = db.query(func.count(func.distinct(concatenated_col)))
                if filter_conditions:
                    result = result.filter(and_(*filter_conditions))
                result = result.scalar() or 0

                return GenericAggregationResponse(
                    table_name=table_name,
                    column=f"{'+'.join(request.columns)}",
                    aggregation_type=request.aggregation_type.value,
                    result={"distinct_count": result},
                    total_records=total_records,
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail="Only count and distinct_count are supported for concatenated columns",
                )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Concatenated aggregation failed: {str(e)}"
        )
