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
    EsTcgaOncoplot,
    TargetedSomatic,
    TargetedGermline,
    WgSomaticOncoplot,
    ExomeSomaticOncoplot,
    EsTcgaSomaticVariation,
)
from fastapi import HTTPException
from typing import List, Dict, Any

# Table registry mapping table names to models
TABLE_REGISTRY = {
    "es_tcga": EsTcga,
    "pathway": Pathway,
    "genelist": Genelist,
    "es_journal": EsJournal,
    "wg_somatic": WgSomatic,
    "uniprot_fixed": Uniprot,
    "samplelist": Samplelist,
    "wg_germline": WgGermline,
    "exome_somatic": ExomeSomatic,
    "exome_germline": ExomeGermline,
    "es_tcga_oncoplot": EsTcgaOncoplot,
    "targeted_somatic": TargetedSomatic,
    "targeted_germline": TargetedGermline,
    "wg_somatic_oncoplot": WgSomaticOncoplot,
    "exome_somatic_oncoplot": ExomeSomaticOncoplot,
    "es_tcga_somatic_variation": EsTcgaSomaticVariation,
}

# Define searchable columns for each table type
SEARCHABLE_COLUMNS = {
    # Genomic tables (similar structure)
    "genomic_tables": {
        "secondary": [
            "dbsnp_rs",
            "sample_id",
            "genome_change",
            "protein_change",
            "tumor_sample_barcode",
        ],
        "all": [
            "gene",
            "end",
            "chrom",
            "start",
            "disease",
            "remarks",
            "dbsnp_rs",
            "sample_id",
            "ref_allele",
            "variant_type",
            "genome_change",
            "variant_class",
            "protein_change",
            "entrez_gene_id",
            "tumor_seq_allele2",
            "tumor_sample_barcode",
            "annotation_transcript",
        ],
        "primary": ["gene", "chrom", "disease", "variant_class", "variant_type"],
    },
    # Special tables
    "genelist": ["gene"],
    "samplelist": ["sample_id"],
    "uniprot_fixed": ["Hugo_Symbol", "Accession_Id"],
    "pathway": ["pathway_name", "path_gene", "disease"],
}

# Table categories for different handling
GENOMIC_TABLES = {
    "es_tcga",
    "es_journal",
    "wg_somatic",
    "wg_germline",
    "exome_somatic",
    "exome_germline",
    "targeted_somatic",
    "targeted_germline",
}

SPECIAL_TABLES = {"pathway", "genelist", "samplelist", "uniprot_fixed"}

GERMLINE_TABLES = {"exome_germline", "wg_germline", "targeted_germline"}


# Helper functions
def get_model_class(table_name: str):
    """Get the SQLAlchemy model class for a given table name."""
    if table_name not in TABLE_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found.",
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
