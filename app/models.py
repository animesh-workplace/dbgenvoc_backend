from sqlalchemy import (
    Text,
    Index,
    String,
    Column,
    Boolean,
    Integer,
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


# Section for Journal Models
class JournalExomeSomaticVariant(BaseVariantModel):
    __tablename__ = "journal_exome_somatic_variants"

    remarks = Column(String(500))


class JournalExomeSomaticVariantOncoplot(BaseOncoplotModel):
    __tablename__ = "journal_exome_somatic_variant_oncoplot"


class JournalExomeSomaticGeneInteraction(BaseGeneInteractionModel):
    __tablename__ = "journal_exome_somatic_gene_interaction"

    __table_args__ = (
        Index("index_journal_exome_somatic_gene_interation", "gene1", "gene2"),
    )


class JournalExomeSomaticSampleTMB(BaseSampleTMBModel):
    __tablename__ = "journal_exome_somatic_sample_tmb"


class JournalExomeSomaticSampleTiTv(BaseSampleTiTvModel):
    __tablename__ = "journal_exome_somatic_sample_titv"


# Section for TCGA Models
class TCGAExomeSomaticVariant(BaseVariantModel):
    __tablename__ = "tcga_exome_somatic_variants"

    remarks = Column(String(500))


class TCGAExomeSomaticVariantOncoplot(BaseOncoplotModel):
    __tablename__ = "tcga_exome_somatic_variant_oncoplot"


class TCGAExomeSomaticGeneInteraction(BaseGeneInteractionModel):
    __tablename__ = "tcga_exome_somatic_gene_interaction"

    __table_args__ = (
        Index("index_tcga_exome_somatic_gene_interation", "gene1", "gene2"),
    )


class TCGAExomeSomaticSampleTMB(BaseSampleTMBModel):
    __tablename__ = "tcga_exome_somatic_sample_tmb"


class TCGAExomeSomaticSampleTiTv(BaseSampleTiTvModel):
    __tablename__ = "tcga_exome_somatic_sample_titv"


# Section for NIBMG Exome Somatic Tables
class NIBMGExomeSomaticVariant(BaseVariantModel):
    __tablename__ = "nibmg_exome_somatic_variants"

    remarks = Column(String(500))


class NIBMGExomeSomaticVariantOncoplot(BaseOncoplotModel):
    __tablename__ = "nibmg_exome_somatic_variant_oncoplot"


class NIBMGExomeSomaticGeneInteraction(BaseGeneInteractionModel):
    __tablename__ = "nibmg_exome_somatic_gene_interaction"

    __table_args__ = (
        Index("index_nibmg_exome_somatic_gene_interation", "gene1", "gene2"),
    )


class NIBMGExomeSomaticSampleTMB(BaseSampleTMBModel):
    __tablename__ = "nibmg_exome_somatic_sample_tmb"


class NIBMGExomeSomaticSampleTiTv(BaseSampleTiTvModel):
    __tablename__ = "nibmg_exome_somatic_sample_titv"


# Section for NIBMG Whole Genome Somatic Tables
class NIBMGWgSomaticVariant(BaseVariantModel):
    __tablename__ = "nibmg_wg_somatic_variants"

    remarks = Column(String(500))


class NIBMGWgSomaticVariantOncoplot(BaseOncoplotModel):
    __tablename__ = "nibmg_wg_somatic_variant_oncoplot"


class NIBMGWgSomaticGeneInteraction(BaseGeneInteractionModel):
    __tablename__ = "nibmg_wg_somatic_gene_interaction"

    __table_args__ = (
        Index("index_nibmg_wg_somatic_gene_interation", "gene1", "gene2"),
    )


class NIBMGWgSomaticSampleTMB(BaseSampleTMBModel):
    __tablename__ = "nibmg_wg_somatic_sample_tmb"


class NIBMGWgSomaticSampleTiTv(BaseSampleTiTvModel):
    __tablename__ = "nibmg_wg_somatic_sample_titv"


# Section for NIBMG Exome Germline Tables
class NIBMGExomeGermlineVariant(BaseVariantModel):
    __tablename__ = "nibmg_exome_germline_variants"

    remarks = Column(String(500))


class NIBMGExomeGermlineVariantOncoplot(BaseOncoplotModel):
    __tablename__ = "nibmg_exome_germline_variant_oncoplot"


class NIBMGExomeGermlineGeneInteraction(BaseGeneInteractionModel):
    __tablename__ = "nibmg_exome_germline_gene_interaction"

    __table_args__ = (
        Index("index_nibmg_exome_germline_gene_interation", "gene1", "gene2"),
    )


class NIBMGExomeGermlineSampleTMB(BaseSampleTMBModel):
    __tablename__ = "nibmg_exome_germline_sample_tmb"


class NIBMGExomeGermlineSampleTiTv(BaseSampleTiTvModel):
    __tablename__ = "nibmg_exome_germline_sample_titv"


# Section for NIBMG Whole Genome Germline Tables
class NIBMGWgGermlineVariant(BaseVariantModel):
    __tablename__ = "nibmg_wg_germline_variants"

    remarks = Column(String(500))


class NIBMGWgGermlineVariantOncoplot(BaseOncoplotModel):
    __tablename__ = "nibmg_wg_germline_variant_oncoplot"


class NIBMGWgGermlineGeneInteraction(BaseGeneInteractionModel):
    __tablename__ = "nibmg_wg_germline_gene_interaction"

    __table_args__ = (
        Index("index_nibmg_wg_germline_gene_interation", "gene1", "gene2"),
    )


class NIBMGWgGermlineSampleTMB(BaseSampleTMBModel):
    __tablename__ = "nibmg_wg_germline_sample_tmb"


class NIBMGWgGermlineSampleTiTv(BaseSampleTiTvModel):
    __tablename__ = "nibmg_wg_germline_sample_titv"
