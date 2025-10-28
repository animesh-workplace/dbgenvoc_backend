from tqdm import tqdm
import fireducks.pandas as pd
from sqlalchemy import create_engine

SQLALCHEMY_DATABASE_URL = "sqlite:///../database/database.sqlite3"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
    if "sqlite" in SQLALCHEMY_DATABASE_URL
    else {},
)


def upload_data():
    # 1. Upload Foundation Tables
    print("Uploading foundation data...")

    # Genelist
    genes_df = pd.read_csv(
        "database/final_db_tables/essential/essential_gene_list.tsv", sep="\t"
    )
    genes_df.to_sql("genelist", engine, if_exists="append", index=False)
    print(f"✓ Uploaded {len(genes_df)} genes")

    # Patient Barcodes
    barcodes_df = pd.read_csv(
        "database/final_db_tables/essential/essential_patient_barcode.tsv", sep="\t"
    )
    barcodes_df.to_sql("patient_barcode", engine, if_exists="append", index=False)
    print(f"✓ Uploaded {len(barcodes_df)} patient barcodes")

    # Pathways
    pathways_df = pd.read_csv(
        "database/final_db_tables/essential/essential_pathway.tsv", sep="\t"
    )
    pathways_df.to_sql("pathway", engine, if_exists="append", index=False)
    print(f"✓ Uploaded {len(pathways_df)} pathways")

    # Pathway association
    pathways_association_df = pd.read_csv(
        "database/final_db_tables/essential/essential_pathway_associations.tsv",
        sep="\t",
    )
    pathways_association_df.to_sql(
        "pathway_gene_association", engine, if_exists="append", index=False
    )
    print(f"✓ Uploaded {len(pathways_association_df)} pathway association")

    # Uniprot
    uniprot_df = pd.read_csv(
        "database/final_db_tables/essential/essential_uniprot.tsv", sep="\t"
    )
    uniprot_df.to_sql("uniprot_structure", engine, if_exists="append", index=False)
    print(f"✓ Uploaded {len(uniprot_df)} structure uniprot")

    # 2. Upload Variant Tables
    print("Uploading variant data...")

    # # Dictionary with table names as keys and file names as values
    variant_files = {
        "journal_exome_somatic_variants": "database/final_db_tables/main/journal_exome_somatic.tsv",
        "tcga_exome_somatic_variants": "database/final_db_tables/main/tcga_exome_somatic.tsv",
        "nibmg_exome_somatic_variants": "database/final_db_tables/main/nibmg_exome_somatic.tsv",
        "nibmg_wg_somatic_variants": "database/final_db_tables/main/nibmg_wg_somatic.tsv",
        "nibmg_exome_germline_variants": "database/final_db_tables/main/nibmg_exome_germline.tsv",
        "nibmg_wg_germline_variants": "database/final_db_tables/main/nibmg_wg_germline.tsv",
        #     Oncoplot tables
        "journal_exome_somatic_variant_oncoplot": "database/final_db_tables/oncoplot/journal_exome_somatic_oncoplot.tsv",
        "tcga_exome_somatic_variant_oncoplot": "database/final_db_tables/oncoplot/tcga_exome_somatic_oncoplot.tsv",
        "nibmg_exome_somatic_variant_oncoplot": "database/final_db_tables/oncoplot/nibmg_exome_somatic_oncoplot.tsv",
        "nibmg_wg_somatic_variant_oncoplot": "database/final_db_tables/oncoplot/nibmg_wg_somatic_oncoplot.tsv",
        "nibmg_exome_germline_variant_oncoplot": "database/final_db_tables/oncoplot/nibmg_exome_germline_oncoplot.tsv",
        "nibmg_wg_germline_variant_oncoplot": "database/final_db_tables/oncoplot/nibmg_wg_germline_oncoplot.tsv",
        #     Gene interaction tables
        "journal_exome_somatic_gene_interaction": "database/final_db_tables/interaction/journal_exome_somatic_interaction.tsv",
        "tcga_exome_somatic_gene_interaction": "database/final_db_tables/interaction/tcga_exome_somatic_interaction.tsv",
        "nibmg_exome_somatic_gene_interaction": "database/final_db_tables/interaction/nibmg_exome_somatic_interaction.tsv",
        "nibmg_wg_somatic_gene_interaction": "database/final_db_tables/interaction/nibmg_wg_somatic_interaction.tsv",
        "nibmg_exome_germline_gene_interaction": "database/final_db_tables/interaction/nibmg_exome_germline_interaction.tsv",
        "nibmg_wg_germline_gene_interaction": "database/final_db_tables/interaction/nibmg_wg_germline_interaction.tsv",
        #     TMB tables
        "journal_exome_somatic_sample_tmb": "database/final_db_tables/tmb/journal_exome_somatic_tmb.tsv",
        "tcga_exome_somatic_sample_tmb": "database/final_db_tables/tmb/tcga_exome_somatic_tmb.tsv",
        "nibmg_exome_somatic_sample_tmb": "database/final_db_tables/tmb/nibmg_exome_somatic_tmb.tsv",
        "nibmg_wg_somatic_sample_tmb": "database/final_db_tables/tmb/nibmg_wg_somatic_tmb.tsv",
        "nibmg_exome_germline_sample_tmb": "database/final_db_tables/tmb/nibmg_exome_germline_tmb.tsv",
        "nibmg_wg_germline_sample_tmb": "database/final_db_tables/tmb/nibmg_wg_germline_tmb.tsv",
        #     TiTv tables
        "journal_exome_somatic_sample_titv": "database/final_db_tables/titv/journal_exome_somatic_titv.tsv",
        "tcga_exome_somatic_sample_titv": "database/final_db_tables/titv/tcga_exome_somatic_titv.tsv",
        "nibmg_exome_somatic_sample_titv": "database/final_db_tables/titv/nibmg_exome_somatic_titv.tsv",
        "nibmg_wg_somatic_sample_titv": "database/final_db_tables/titv/nibmg_wg_somatic_titv.tsv",
        "nibmg_exome_germline_sample_titv": "database/final_db_tables/titv/nibmg_exome_germline_titv.tsv",
        "nibmg_wg_germline_sample_titv": "database/final_db_tables/titv/nibmg_wg_germline_titv.tsv",
    }

    # Define your batch size
    BATCH_SIZE = 80000

    for table_name, csv_file in variant_files.items():
        total_rows = 0
        try:
            print(f"Processing {csv_file} for {table_name}...")

            # Create an iterator that reads the file in chunks of BATCH_SIZE
            df_iterator = pd.read_csv(csv_file, sep="\t", chunksize=BATCH_SIZE)

            # Loop through each chunk and append it to the SQL table
            for df_chunk in tqdm(df_iterator):
                df_chunk.to_sql(table_name, engine, if_exists="append", index=False)
                total_rows += len(df_chunk)

            print(
                f"✓ Successfully uploaded {total_rows} total rows to {table_name} from {csv_file}"
            )

        except FileNotFoundError:
            print(f"⚠ File not found: {csv_file}, skipping {table_name}")
        except Exception as e:
            # This error is more informative if it fails part-way through
            print(
                f"✗ Failed to upload {table_name} from {csv_file} (failed after {total_rows} rows): {e}"
            )

    print("✅ Data upload complete!")


if __name__ == "__main__":
    upload_data()
