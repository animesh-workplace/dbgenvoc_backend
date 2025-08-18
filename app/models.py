from app.session import Base
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime


class EsJournal(Base):
    __tablename__ = "es_journal"

    esj_id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20))
    entrez_gene_id = Column(Integer)
    ncbi_build = Column(String(6))
    chrom = Column(String(6), index=True)
    start = Column(String(30), index=True)
    end = Column(String(30), index=True)
    variant_class = Column(String(100))
    variant_type = Column(String(10))
    ref_allele = Column(String(50))
    tumor_seq_allele2 = Column(String(50))
    dbsnp_rs = Column(String(200))
    tumor_sample_barcode = Column(String(20), index=True)
    genome_change = Column(String(75))
    annotation_transcript = Column(String(20))
    transcript_strand = Column(String(2))
    transcript_exon = Column(String(10))
    transcript_position = Column(String(20))
    cDNA_change = Column(String(30))
    codon_change = Column(String(30))
    protein_change = Column(String(20))
    disease = Column(String(100))
    reference_url = Column(String(900))
    reference = Column(String(200))
    remarks = Column(String(500))


class EsTcga(Base):
    __tablename__ = "es_tcga"

    tcga_id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20), index=True)
    entrez_gene_id = Column(Integer)
    ncbi_build = Column(String(6))
    chrom = Column(String(6), index=True)
    start = Column(String(30), index=True)
    end = Column(String(30), index=True)
    variant_class = Column(String(100))
    variant_type = Column(String(10))
    ref_allele = Column(String(50))
    tumor_seq_allele2 = Column(String(50))
    dbsnp_rs = Column(String(200))
    tumor_sample_barcode = Column(String(20), index=True)
    genome_change = Column(String(75))
    annotation_transcript = Column(String(20))
    transcript_strand = Column(String(2))
    transcript_exon = Column(String(10))
    transcript_position = Column(String(20))
    cDNA_change = Column(String(30))
    codon_change = Column(String(30))
    protein_change = Column(String(20))
    disease = Column(String(100))
    reference_url = Column(String(900))
    reference = Column(String(200))


class ExomeGermline(Base):
    __tablename__ = "exome_germline"

    egm_id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20), index=True)
    entrez_gene_id = Column(Integer)
    ncbi_build = Column(String(3))
    chrom = Column(String(6), index=True)
    start = Column(String(30), index=True)
    end = Column(String(30), index=True)
    variant_class = Column(String(100))
    variant_type = Column(String(10))
    ref_allele = Column(String(50))
    tumor_seq_allele2 = Column(String(50))
    dbsnp_rs = Column(String(200))
    tumor_sample_barcode = Column(String(10))
    sample_id = Column(String(20), index=True)
    genome_change = Column(String(75))
    annotation_transcript = Column(String(20))
    transcript_strand = Column(String(2))
    transcript_exon = Column(String(10))
    transcript_position = Column(String(20))
    cDNA_change = Column(String(30))
    codon_change = Column(String(30))
    protein_change = Column(String(20))
    disease = Column(String(100))
    reference_url = Column(String(900))
    reference = Column(String(200))
    remarks = Column(String(500))


class ExomeSomatic(Base):
    __tablename__ = "exome_somatic"

    esm_id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20), index=True)
    entrez_gene_id = Column(Integer)
    ncbi_build = Column(String(3))
    chrom = Column(String(6), index=True)
    start = Column(String(30), index=True)
    end = Column(String(30), index=True)
    variant_class = Column(String(100))
    variant_type = Column(String(10))
    ref_allele = Column(String(50))
    tumor_seq_allele2 = Column(String(50))
    dbsnp_rs = Column(String(200))
    tumor_sample_barcode = Column(String(10))
    sample_id = Column(String(20), index=True)
    genome_change = Column(String(75))
    annotation_transcript = Column(String(20))
    transcript_strand = Column(String(2))
    transcript_exon = Column(String(10))
    transcript_position = Column(String(20))
    cDNA_change = Column(String(30))
    codon_change = Column(String(30))
    protein_change = Column(String(20))
    disease = Column(String(100))
    reference_url = Column(String(900))
    reference = Column(String(200))
    remarks = Column(String(500))


class WgGermline(Base):
    __tablename__ = "wg_germline"

    wgm_id = Column(BigInteger, primary_key=True, autoincrement=True)
    gene = Column(String(20), index=True)
    entrez_gene_id = Column(Integer)
    ncbi_build = Column(String(3))
    chrom = Column(String(6), index=True)
    start = Column(String(30), index=True)
    end = Column(String(30), index=True)
    variant_class = Column(String(100))
    variant_type = Column(String(10))
    ref_allele = Column(String(50))
    tumor_seq_allele2 = Column(String(50))
    dbsnp_rs = Column(String(200))
    tumor_sample_barcode = Column(String(10))
    sample_id = Column(String(20), index=True)
    genome_change = Column(String(75))
    annotation_transcript = Column(String(20))
    transcript_strand = Column(String(2))
    transcript_exon = Column(String(10))
    transcript_position = Column(String(20))
    cDNA_change = Column(String(30))
    codon_change = Column(String(30))
    protein_change = Column(String(20))
    disease = Column(String(100))
    reference_url = Column(String(900))
    reference = Column(String(200))
    remarks = Column(String(500))


class WgSomatic(Base):
    __tablename__ = "wg_somatic"

    wsm_id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20), index=True)
    entrez_gene_id = Column(Integer)
    ncbi_build = Column(String(3))
    chrom = Column(String(6), index=True)
    start = Column(String(30), index=True)
    end = Column(String(30), index=True)
    variant_class = Column(String(100))
    variant_type = Column(String(10))
    ref_allele = Column(String(50))
    tumor_seq_allele2 = Column(String(50))
    dbsnp_rs = Column(String(200))
    tumor_sample_barcode = Column(String(10))
    sample_id = Column(String(20), index=True)
    genome_change = Column(String(75))
    annotation_transcript = Column(String(20))
    transcript_strand = Column(String(2))
    transcript_exon = Column(String(10))
    transcript_position = Column(String(20))
    cDNA_change = Column(String(30))
    codon_change = Column(String(30))
    protein_change = Column(String(20))
    disease = Column(String(100))
    reference_url = Column(String(900))
    reference = Column(String(200))
    remarks = Column(String(500))


class TargetedGermline(Base):
    __tablename__ = "targeted_germline"

    tgm_id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20))
    entrez_gene_id = Column(Integer)
    ncbi_build = Column(String(3))
    chrom = Column(String(6))
    start = Column(String(30))
    end = Column(String(30))
    variant_class = Column(String(100))
    variant_type = Column(String(10))
    ref_allele = Column(String(50))
    tumor_seq_allele2 = Column(String(50))
    dbsnp_rs = Column(String(200))
    tumor_sample_barcode = Column(String(10))
    sample_id = Column(String(20))
    genome_change = Column(String(75))
    annotation_transcript = Column(String(20))
    transcript_strand = Column(String(2))
    transcript_exon = Column(String(10))
    transcript_position = Column(String(20))
    cDNA_change = Column(String(30))
    codon_change = Column(String(30))
    protein_change = Column(String(20))
    disease = Column(String(100))
    reference_url = Column(String(900))
    reference = Column(String(200))
    remarks = Column(String(500))


class TargetedSomatic(Base):
    __tablename__ = "targeted_somatic"

    tsm_id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20))
    entrez_gene_id = Column(Integer)
    ncbi_build = Column(String(3))
    chrom = Column(String(6))
    start = Column(String(30))
    end = Column(String(30))
    variant_class = Column(String(100))
    variant_type = Column(String(10))
    ref_allele = Column(String(50))
    tumor_seq_allele2 = Column(String(50))
    dbsnp_rs = Column(String(200))
    tumor_sample_barcode = Column(String(10))
    sample_id = Column(String(20))
    genome_change = Column(String(75))
    annotation_transcript = Column(String(20))
    transcript_strand = Column(String(2))
    transcript_exon = Column(String(10))
    transcript_position = Column(String(20))
    cDNA_change = Column(String(30))
    codon_change = Column(String(30))
    protein_change = Column(String(20))
    disease = Column(String(100))
    reference_url = Column(String(900))
    reference = Column(String(200))
    remarks = Column(String(500))


class Pathway(Base):
    __tablename__ = "pathway"

    path_id = Column(String(12), primary_key=True)
    pathway_name = Column(String(300))
    path_gene = Column(String(6000))
    disease = Column(String(100))


class Genelist(Base):
    __tablename__ = "genelist"

    gene = Column(String(200), primary_key=True)


class Samplelist(Base):
    __tablename__ = "samplelist"

    sample_id = Column(String(200), primary_key=True)


class Uniprot(Base):
    __tablename__ = "uniprot_fixed"

    Row_Index = Column(Integer, primary_key=True, autoincrement=True)
    Hugo_Symbol = Column(String(20))
    Accession_Id = Column(String(20))
    Structure = Column(Text)
