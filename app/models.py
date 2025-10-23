from app.session import Base
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Boolean


class EsJournal(Base):
    __tablename__ = "es_journal"

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
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

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
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

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
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

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
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

    variant_id = Column(BigInteger, primary_key=True, autoincrement=True)
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

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
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

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
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

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
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


class ApiToken(Base):
    __tablename__ = "api_tokens"

    token_id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    user_identifier = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)  # Purpose of token
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=True)  # NULL means no expiration
    last_used_at = Column(DateTime, nullable=True)
    permissions = Column(Text, nullable=True)  # JSON string of permissions
    ip_whitelist = Column(Text, nullable=True)  # JSON array of allowed IPs


class EsTcgaOncoplot(Base):
    __tablename__ = "es_tcga_oncoplot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20))
    sample_id = Column(String(20))
    evalue = Column(Integer)
    annotation = Column(String(255))


class EsJournalOncoplot(Base):
    __tablename__ = "es_journal_oncoplot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20))
    sample_id = Column(String(20))
    evalue = Column(Integer)
    annotation = Column(String(255))


class ExomeGermlineOncoplot(Base):
    __tablename__ = "exome_germline_oncoplot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20))
    sample_id = Column(String(20))
    evalue = Column(Integer)
    annotation = Column(String(255))


class ExomeSomaticOncoplot(Base):
    __tablename__ = "exome_somatic_oncoplot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20))
    sample_id = Column(String(20))
    evalue = Column(Integer)
    annotation = Column(String(255))


class WgGermlineOncoplot(Base):
    __tablename__ = "wg_germline_oncoplot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20))
    sample_id = Column(String(20))
    evalue = Column(Integer)
    annotation = Column(String(255))


class WgSomaticOncoplot(Base):
    __tablename__ = "wg_somatic_oncoplot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20))
    sample_id = Column(String(20))
    evalue = Column(Integer)
    annotation = Column(String(255))
