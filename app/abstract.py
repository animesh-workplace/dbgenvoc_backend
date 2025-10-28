from app.session import Base
from sqlalchemy.orm import relationship, declared_attr
from sqlalchemy import String, Column, Integer, Float, ForeignKey, Table, Text

# Association table
pathway_gene_association = Table(
    "pathway_gene_association",
    Base.metadata,
    Column("gene", String(200), ForeignKey("genelist.gene")),
    Column("pathway_id", String(12), ForeignKey("pathway.id")),
)


class Genelist(Base):
    __tablename__ = "genelist"

    gene = Column(String(200), primary_key=True)
    # Relationship to pathways
    pathways = relationship(
        "Pathway", secondary=pathway_gene_association, back_populates="genes"
    )


class Pathway(Base):
    __tablename__ = "pathway"

    id = Column(String(12), primary_key=True)
    pathway_name = Column(String(300))
    genes = relationship(
        "Genelist", secondary=pathway_gene_association, back_populates="pathways"
    )


class PatientBarcode(Base):
    __tablename__ = "patient_barcode"

    id = Column(String(200), primary_key=True)


class Uniprot(Base):
    __tablename__ = "uniprot_structure"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20), ForeignKey("genelist.gene"), index=True)
    accession_id = Column(String(20))
    structure = Column(Text)

    @declared_attr
    def genelist(cls):
        return relationship("Genelist", lazy="joined")


class BaseVariantModel(Base):
    __abstract__ = True

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20), ForeignKey("genelist.gene"), index=True)
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
    tumor_sample_barcode = Column(
        String(20), ForeignKey("patient_barcode.id"), index=True
    )
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

    @declared_attr
    def genelist(cls):
        return relationship("Genelist", lazy="joined")

    @declared_attr
    def barcode(cls):
        return relationship("PatientBarcode", lazy="joined")


class BaseOncoplotModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20), ForeignKey("genelist.gene"), index=True)
    tumor_sample_barcode = Column(
        String(20), ForeignKey("patient_barcode.id"), index=True
    )
    code = Column(Integer)
    annotation = Column(String(255))

    @declared_attr
    def genelist(cls):
        return relationship("Genelist", lazy="joined")

    @declared_attr
    def barcode(cls):
        return relationship("PatientBarcode", lazy="joined")


class BaseGeneInteractionModel(Base):
    # Requires index when creating Model from this
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    gene1 = Column(String(20), ForeignKey("genelist.gene"), index=True)
    gene2 = Column(String(20), ForeignKey("genelist.gene"), index=True)
    p_value = Column(Float)
    odds_ratio = Column(Float)
    neg_log10_pval = Column(Float)

    @declared_attr
    def gene1_obj(cls):
        return relationship("Genelist", foreign_keys=[cls.gene1], lazy="joined")

    @declared_attr
    def gene2_obj(cls):
        return relationship("Genelist", foreign_keys=[cls.gene2], lazy="joined")


class BaseSampleTMBModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    tumor_sample_barcode = Column(
        String(20), ForeignKey("patient_barcode.id"), index=True
    )
    variant_class = Column(String(100))
    count = Column(Integer)

    @declared_attr
    def barcode(cls):
        return relationship("PatientBarcode", lazy="joined")


class BaseSampleTiTvModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    tumor_sample_barcode = Column(
        String(20), ForeignKey("patient_barcode.id"), index=True
    )
    snv_class = Column(String(10))
    count = Column(Integer)

    @declared_attr
    def barcode(cls):
        return relationship("PatientBarcode", lazy="joined")
