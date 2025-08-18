from pydantic import BaseModel, Field
from typing import Optional


# Base schemas for common genomic variant fields
class GenomicVariantBase(BaseModel):
    gene: Optional[str] = None
    entrez_gene_id: Optional[int] = None
    ncbi_build: Optional[str] = None
    chrom: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    variant_class: Optional[str] = None
    variant_type: Optional[str] = None
    ref_allele: Optional[str] = None
    tumor_seq_allele2: Optional[str] = None
    dbsnp_rs: Optional[str] = None
    genome_change: Optional[str] = None
    annotation_transcript: Optional[str] = None
    transcript_strand: Optional[str] = None
    transcript_exon: Optional[str] = None
    transcript_position: Optional[str] = None
    cDNA_change: Optional[str] = None
    codon_change: Optional[str] = None
    protein_change: Optional[str] = None
    disease: Optional[str] = None
    reference_url: Optional[str] = None
    reference: Optional[str] = None


# ES Journal Schemas
class EsJournalCreate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    remarks: Optional[str] = None


class EsJournalUpdate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    remarks: Optional[str] = None


class EsJournalResponse(GenomicVariantBase):
    esj_id: int
    tumor_sample_barcode: Optional[str] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


# ES TCGA Schemas
class EsTcgaCreate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None


class EsTcgaUpdate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None


class EsTcgaResponse(GenomicVariantBase):
    tcga_id: int
    tumor_sample_barcode: Optional[str] = None

    class Config:
        from_attributes = True


# Exome Germline Schemas
class ExomeGermlineCreate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class ExomeGermlineUpdate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class ExomeGermlineResponse(GenomicVariantBase):
    egm_id: int
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


# Exome Somatic Schemas
class ExomeSomaticCreate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class ExomeSomaticUpdate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class ExomeSomaticResponse(GenomicVariantBase):
    esm_id: int
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


# WG Germline Schemas
class WgGermlineCreate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class WgGermlineUpdate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class WgGermlineResponse(GenomicVariantBase):
    wgm_id: int
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


# WG Somatic Schemas
class WgSomaticCreate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class WgSomaticUpdate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class WgSomaticResponse(GenomicVariantBase):
    wsm_id: int
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


# Targeted Germline Schemas
class TargetedGermlineCreate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class TargetedGermlineResponse(GenomicVariantBase):
    tgm_id: int
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


# Targeted Somatic Schemas
class TargetedSomaticCreate(GenomicVariantBase):
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None


class TargetedSomaticResponse(GenomicVariantBase):
    tsm_id: int
    tumor_sample_barcode: Optional[str] = None
    sample_id: Optional[str] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


# Pathway Schemas
class PathwayCreate(BaseModel):
    path_id: str = Field(..., max_length=12)
    pathway_name: Optional[str] = Field(None, max_length=300)
    path_gene: Optional[str] = Field(None, max_length=6000)
    disease: Optional[str] = Field(None, max_length=100)


class PathwayResponse(BaseModel):
    path_id: str
    pathway_name: Optional[str] = None
    path_gene: Optional[str] = None
    disease: Optional[str] = None

    class Config:
        from_attributes = True


# Simple List Schemas
class GenelistCreate(BaseModel):
    gene: str = Field(..., max_length=200)


class GenelistResponse(BaseModel):
    gene: str

    class Config:
        from_attributes = True


class SamplelistCreate(BaseModel):
    sample_id: str = Field(..., max_length=200)


class SamplelistResponse(BaseModel):
    sample_id: str

    class Config:
        from_attributes = True


# Uniprot Schemas
class UniprotCreate(BaseModel):
    Row_Index: str = Field(..., max_length=10)
    Hugo_Symbol: Optional[str] = Field(None, max_length=20)
    Accession_Id: Optional[str] = Field(None, max_length=20)
    Structure: str


class UniprotResponse(BaseModel):
    Row_Index: str
    Hugo_Symbol: Optional[str] = None
    Accession_Id: Optional[str] = None
    Structure: str

    class Config:
        from_attributes = True


class UniprotFixedCreate(BaseModel):
    Hugo_Symbol: Optional[str] = Field(None, max_length=20)
    Accession_Id: Optional[str] = Field(None, max_length=20)
    Structure: str


class UniprotFixedResponse(BaseModel):
    Row_Index: int
    Hugo_Symbol: Optional[str] = None
    Accession_Id: Optional[str] = None
    Structure: str

    class Config:
        from_attributes = True


# Search and Filter Schemas
class GenomicSearchParams(BaseModel):
    gene: Optional[str] = None
    chrom: Optional[str] = None
    variant_class: Optional[str] = None
    variant_type: Optional[str] = None
    disease: Optional[str] = None
    sample_id: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class GenomicRangeSearch(BaseModel):
    chrom: str
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None
    gene: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
