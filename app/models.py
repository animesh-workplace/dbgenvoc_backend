from sqlalchemy import (
    Text,
    Index,
    String,
    Column,
    Boolean,
    Integer,
    ForeignKey,
    DateTime,
)
from app.abstract import (
    BaseVariantModel,
    BaseOncoplotModel,
    BaseSampleTMBModel,
    BaseSampleTiTvModel,
    BaseGeneInteractionModel,
)
from app.session import Base
from sqlalchemy.sql import func


class SomaticGenomicPosition(Base):
    __tablename__ = "somatic_genomic_position"

    count = Column(Integer)
    end = Column(Integer, index=True, nullable=False)
    start = Column(Integer, index=True, nullable=False)
    id = Column(Integer, primary_key=True, autoincrement=True)
    chromosome = Column(String(20), index=True, nullable=False)
    # gene_name = Column(String(100), index=True, nullable=True) # Might be added later

    __table_args__ = (
        Index("index_somatic_genomic_position_chrom_start", "chromosome", "start"),
        Index(
            "index_somatic_genomic_position_chrom_start_end",
            "chromosome",
            "start",
            "end",
        ),
    )


class ApiToken(Base):
    __tablename__ = "api_tokens"

    last_used_at = Column(DateTime, nullable=True)
    user_identifier = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    token_id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    token = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(String(500), nullable=True)  # Purpose of token
    permissions = Column(Text, nullable=True)  # JSON string of permissions
    ip_whitelist = Column(Text, nullable=True)  # JSON array of allowed IPs
    expires_at = Column(DateTime, nullable=True)  # NULL means no expiration


class VariantData(BaseVariantModel):
    __tablename__ = "variant_data"

    remarks = Column(String(500))


class TranscriptData(Base):
    __tablename__ = "transcript_data"

    gene_id = Column(String(20))
    refseq_id = Column(String(20))
    protein_id = Column(String(20))
    uniprot_id = Column(String(20))
    protein_length = Column(Integer)
    transcript_id = Column(String(50), primary_key=True)
    gene = Column(String(20), ForeignKey("genelist.gene"), index=True)


class ExonData(Base):
    __tablename__ = "exon_data"

    end = Column(Integer)
    rank = Column(Integer)
    start = Column(Integer)
    strand = Column(Integer)
    version = Column(Integer)
    exon_id = Column(String(20))
    transcript_id = Column(
        String(20),
        ForeignKey("transcript_data.transcript_id"),
        index=True,
        primary_key=True,
    )


class DomainData(Base):
    __tablename__ = "domain_data"

    end = Column(Integer)
    start = Column(Integer)
    name = Column(String(100))
    domain_name = Column(String(20))
    description = Column(String(200))
    transcript_id = Column(
        String(20),
        ForeignKey("transcript_data.transcript_id"),
        index=True,
        primary_key=True,
    )


# # Section for Journal Models
# class JournalExomeSomaticVariant(BaseVariantModel):
#     __tablename__ = "journal_exome_somatic_variants"

#     remarks = Column(String(500))


# class JournalExomeSomaticVariantOncoplot(BaseOncoplotModel):
#     __tablename__ = "journal_exome_somatic_variant_oncoplot"


# class JournalExomeSomaticGeneInteraction(BaseGeneInteractionModel):
#     __tablename__ = "journal_exome_somatic_gene_interaction"


# class JournalExomeSomaticSampleTMB(BaseSampleTMBModel):
#     __tablename__ = "journal_exome_somatic_sample_tmb"


# class JournalExomeSomaticSampleTiTv(BaseSampleTiTvModel):
#     __tablename__ = "journal_exome_somatic_sample_titv"


# # Section for TCGA Models
# class TCGAExomeSomaticVariant(BaseVariantModel):
#     __tablename__ = "tcga_exome_somatic_variants"

#     remarks = Column(String(500))


# class TCGAExomeSomaticVariantOncoplot(BaseOncoplotModel):
#     __tablename__ = "tcga_exome_somatic_variant_oncoplot"


# class TCGAExomeSomaticGeneInteraction(BaseGeneInteractionModel):
#     __tablename__ = "tcga_exome_somatic_gene_interaction"


# class TCGAExomeSomaticSampleTMB(BaseSampleTMBModel):
#     __tablename__ = "tcga_exome_somatic_sample_tmb"


# class TCGAExomeSomaticSampleTiTv(BaseSampleTiTvModel):
#     __tablename__ = "tcga_exome_somatic_sample_titv"


# # Section for NIBMG Exome Somatic Tables
# class NIBMGExomeSomaticVariant(BaseVariantModel):
#     __tablename__ = "nibmg_exome_somatic_variants"

#     remarks = Column(String(500))


# class NIBMGExomeSomaticVariantOncoplot(BaseOncoplotModel):
#     __tablename__ = "nibmg_exome_somatic_variant_oncoplot"


# class NIBMGExomeSomaticGeneInteraction(BaseGeneInteractionModel):
#     __tablename__ = "nibmg_exome_somatic_gene_interaction"


# class NIBMGExomeSomaticSampleTMB(BaseSampleTMBModel):
#     __tablename__ = "nibmg_exome_somatic_sample_tmb"


# class NIBMGExomeSomaticSampleTiTv(BaseSampleTiTvModel):
#     __tablename__ = "nibmg_exome_somatic_sample_titv"


# # Section for NIBMG Whole Genome Somatic Tables
# class NIBMGWgSomaticVariant(BaseVariantModel):
#     __tablename__ = "nibmg_wg_somatic_variants"

#     remarks = Column(String(500))


# class NIBMGWgSomaticVariantOncoplot(BaseOncoplotModel):
#     __tablename__ = "nibmg_wg_somatic_variant_oncoplot"


# class NIBMGWgSomaticGeneInteraction(BaseGeneInteractionModel):
#     __tablename__ = "nibmg_wg_somatic_gene_interaction"


# class NIBMGWgSomaticSampleTMB(BaseSampleTMBModel):
#     __tablename__ = "nibmg_wg_somatic_sample_tmb"


# class NIBMGWgSomaticSampleTiTv(BaseSampleTiTvModel):
#     __tablename__ = "nibmg_wg_somatic_sample_titv"


# # Section for NIBMG Exome Germline Tables
# class NIBMGExomeGermlineVariant(BaseVariantModel):
#     __tablename__ = "nibmg_exome_germline_variants"

#     remarks = Column(String(500))


# class NIBMGExomeGermlineVariantOncoplot(BaseOncoplotModel):
#     __tablename__ = "nibmg_exome_germline_variant_oncoplot"


# class NIBMGExomeGermlineGeneInteraction(BaseGeneInteractionModel):
#     __tablename__ = "nibmg_exome_germline_gene_interaction"


# class NIBMGExomeGermlineSampleTMB(BaseSampleTMBModel):
#     __tablename__ = "nibmg_exome_germline_sample_tmb"


# class NIBMGExomeGermlineSampleTiTv(BaseSampleTiTvModel):
#     __tablename__ = "nibmg_exome_germline_sample_titv"


# # Section for NIBMG Whole Genome Germline Tables
# class NIBMGWgGermlineVariant(BaseVariantModel):
#     __tablename__ = "nibmg_wg_germline_variants"

#     remarks = Column(String(500))


# class NIBMGWgGermlineVariantOncoplot(BaseOncoplotModel):
#     __tablename__ = "nibmg_wg_germline_variant_oncoplot"


# class NIBMGWgGermlineGeneInteraction(BaseGeneInteractionModel):
#     __tablename__ = "nibmg_wg_germline_gene_interaction"


# class NIBMGWgGermlineSampleTMB(BaseSampleTMBModel):
#     __tablename__ = "nibmg_wg_germline_sample_tmb"


# class NIBMGWgGermlineSampleTiTv(BaseSampleTiTvModel):
#     __tablename__ = "nibmg_wg_germline_sample_titv"
