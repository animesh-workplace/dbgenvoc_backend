from app.session import Base
from sqlalchemy.orm import relationship, declared_attr
from sqlalchemy import String, Column, Integer, Float, ForeignKey, Table, Text, Index

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

    pathway_name = Column(String(300))
    id = Column(String(12), primary_key=True)
    genes = relationship(
        "Genelist", secondary=pathway_gene_association, back_populates="pathways"
    )


class PatientBarcode(Base):
    __tablename__ = "patient_barcode"

    id = Column(String(200), primary_key=True)


class Uniprot(Base):
    __tablename__ = "uniprot_structure"

    structure = Column(Text)
    accession_id = Column(String(20))
    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20), ForeignKey("genelist.gene"), index=True)

    @declared_attr
    def genelist(cls):
        return relationship("Genelist", lazy="joined")


class BaseVariantModel(Base):
    __abstract__ = True

    end = Column(String(30))
    chrom = Column(String(6))
    start = Column(String(30))
    disease = Column(String(100))
    ncbi_build = Column(String(6))
    dbsnp_rs = Column(String(200))
    table_name = Column(String(50))
    ref_allele = Column(String(50))
    reference = Column(String(200))
    entrez_gene_id = Column(Integer)
    cDNA_change = Column(String(30))
    variant_type = Column(String(10))
    codon_change = Column(String(30))
    genome_change = Column(String(75))
    variant_class = Column(String(100))
    protein_change = Column(String(20))
    reference_url = Column(String(900))
    transcript_exon = Column(String(10))
    transcript_strand = Column(String(2))
    tumor_seq_allele2 = Column(String(50))
    transcript_position = Column(String(20))
    trinucleotide_context = Column(String(3))
    annotation_transcript = Column(String(20))
    tumor_sample_barcode = Column(
        String(20), ForeignKey("patient_barcode.id"), index=True
    )
    variant_id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(20), ForeignKey("genelist.gene"), index=True)

    @declared_attr
    def genelist(cls):
        return relationship("Genelist", lazy="joined")

    @declared_attr
    def barcode(cls):
        return relationship("PatientBarcode", lazy="joined")

    @declared_attr
    def __table_args__(cls):
        return (
            # 1️⃣ Dataset + Gene (most common statistical query)
            Index(f"idx_{cls.__tablename__}_dataset_gene", "table_name", "gene"),
            # 2️⃣ Dataset + Chrom + Start (range queries inside dataset)
            Index(
                f"idx_{cls.__tablename__}_dataset_chrom_start",
                "table_name",
                "chrom",
                "start",
            ),
            # 3️⃣ Chrom + Start + End (global range queries)
            Index(
                f"idx_{cls.__tablename__}_dataset_chrom_start_end",
                "table_name",
                "chrom",
                "start",
                "end",
            ),
            # 4️⃣ Dataset + Variant Type (useful for stats)
            Index(
                f"idx_{cls.__tablename__}_dataset_varianttype",
                "table_name",
                "variant_type",
            ),
        )


class BaseOncoplotModel(Base):
    __abstract__ = True

    code = Column(Integer)
    annotation = Column(String(255))
    id = Column(Integer, primary_key=True, autoincrement=True)
    tumor_sample_barcode = Column(
        String(20), ForeignKey("patient_barcode.id"), index=True
    )
    gene = Column(String(20), ForeignKey("genelist.gene"), index=True)

    @declared_attr
    def genelist(cls):
        return relationship("Genelist", lazy="joined")

    @declared_attr
    def barcode(cls):
        return relationship("PatientBarcode", lazy="joined")


class BaseGeneInteractionModel(Base):
    __abstract__ = True

    p_value = Column(Float)
    odds_ratio = Column(Float)
    neg_log10_pval = Column(Float)
    gene1 = Column(String(20), ForeignKey("genelist.gene"))
    gene2 = Column(String(20), ForeignKey("genelist.gene"))
    id = Column(Integer, primary_key=True, autoincrement=True)

    @declared_attr
    def gene1_obj(cls):
        return relationship("Genelist", foreign_keys=[cls.gene1], lazy="joined")

    @declared_attr
    def gene2_obj(cls):
        return relationship("Genelist", foreign_keys=[cls.gene2], lazy="joined")

    @declared_attr
    def __table_args__(cls):
        return (Index(f"index_{cls.__tablename__}_gene1_gene2", "gene1", "gene2"),)


class BaseSampleTMBModel(Base):
    __abstract__ = True

    count = Column(Integer)
    variant_class = Column(String(100))
    id = Column(Integer, primary_key=True, autoincrement=True)
    tumor_sample_barcode = Column(
        String(20), ForeignKey("patient_barcode.id"), index=True
    )

    @declared_attr
    def barcode(cls):
        return relationship("PatientBarcode", lazy="joined")


class BaseSampleTiTvModel(Base):
    __abstract__ = True

    count = Column(Integer)
    snv_class = Column(String(10))
    id = Column(Integer, primary_key=True, autoincrement=True)
    tumor_sample_barcode = Column(
        String(20), ForeignKey("patient_barcode.id"), index=True
    )

    @declared_attr
    def barcode(cls):
        return relationship("PatientBarcode", lazy="joined")
