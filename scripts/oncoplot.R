library(RSQLite)
library(maftools)
library(data.table)

# Function to parse command line arguments
parse_arguments <- function() {
  args <- commandArgs(trailingOnly = TRUE)

  if (length(args) < 1) {
    stop("Usage: Rscript generate_oncoplot_matrix.R <database_table>
		 \nExample: Rscript generate_oncoplot_matrix.R es_tcga")
  }

  list(table_name = args[1])
}

# Function to read and prepare MAF data from SQLite
prepare_maf_data <- function(
  table_name,
  database_path = "../database/database.sqlite3"
) {
  # Connect to database
  con <- RSQLite::dbConnect(RSQLite::SQLite(), database_path)
  on.exit(RSQLite::dbDisconnect(con))

  # Read table
  maf_df <- RSQLite::dbReadTable(con, table_name)

  # Rename columns for maftools
  setnames(maf_df,
    old = c(
      "gene",
      "chrom",
      "end",
      "start",
      "ncbi_build",
      "variant_type",
      "protein_change",
      "ref_allele",
      "entrez_gene_id",
      "tumor_seq_allele2",
      "variant_class",
      "tumor_sample_barcode"
    ),
    new = c(
      "Hugo_Symbol",
      "Chromosome",
      "End_Position",
      "Start_Position",
      "NCBI_Build",
      "Variant_Type",
      "HGVSp_Short",
      "Reference_Allele",
      "Entrez_Gene_Id",
      "Tumor_Seq_Allele2",
      "Variant_Classification",
      "Tumor_Sample_Barcode"
    )
  )

  return(maf_df)
}

# Function to create MAF object and generate oncoplot matrix
generate_oncoplot_matrix <- function(table_name, maf_df) {
  # Create MAF object
  maf_obj <- maftools::read.maf(maf = maf_df)

  # Check if specified genes are in the MAF
  available_genes <- unique(maf_obj@gene.summary$Hugo_Symbol)
  titv_data = titv(maf=maf_obj)
  write.table(titv_data$fraction.contribution, paste0(table_name, '_fraction_contribution.tsv'),    
    sep = "\t",
    quote = FALSE,
    col.names = TRUE
  )
  write.table(titv_data$raw.counts, paste0(table_name, '_raw_counts.tsv'),    
    sep = "\t",
    quote = FALSE,
    col.names = TRUE
  ) 
  write.table(titv_data$TiTv.fractions, paste0(table_name, '_titv_fractions.tsv'),    
    sep = "\t",
    quote = FALSE,
    col.names = TRUE
  ) 
  # write.table(maf_obj@variant.classification.summary, paste0(table_name, '_tmb.tsv'),    
  #   sep = "\t",
  #   quote = FALSE,
  #   col.names = TRUE
  # )
  # write.table(available_genes, paste0(table_name, "_available_genes.tsv"),
  #   sep = "\t",
  #   quote = FALSE,
  #   col.names = FALSE
  # )
  if (length(available_genes) == 0) {
    stop("None of the specified genes found in the MAF data")
  }

  # # Generate oncoplot and capture the matrix
  # oncoplot_matrix <- maftools::oncoplot(maf = maf_obj, top = 20)
  # somatic_interaction <- maftools::somaticInteractions(maf = maf_obj, top = 5)

  # output_file <- paste0(table_name, "_oncoplot_matrix.tsv")
  # write.table(oncoplot_matrix$oncomatrix, output_file,
  #   sep = "\t",
  #   quote = FALSE
  # )
}

# Main function
main <- function() {
  # Parse command line arguments
  args <- parse_arguments()

  # Prepare MAF data
  maf_data <- prepare_maf_data(args$table_name)

  # Generate oncoplot matrix
  generate_oncoplot_matrix(args$table_name, maf_data)
}

# Run the script if executed directly
if (!interactive()) {
  result <- main()
}
