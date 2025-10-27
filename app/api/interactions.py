import traceback
import fireducks.pandas as pandas
from fastapi import HTTPException
from app.core import row_to_dict, get_model_class
from app.schema import OncoplotRequest, InteractionResponse


async def interaction_search(request: OncoplotRequest, table_name, db):
    """Search function that returns data in ECharts heatmap format for gene-gene interactions"""
    try:
        model_class = get_model_class(table_name)
        genes = getattr(request, "genes", None)

        if not genes:
            return InteractionResponse(yAxis=[], xAxis=[], heatmap=[])

        # Get all unique combinations of the input genes
        query = db.query(model_class)
        query = query.filter(
            (model_class.gene1.in_(genes)) & (model_class.gene2.in_(genes))
        )
        results = query.all()
        sorted_genes = sorted(genes)
        # Convert to DataFrame for easier manipulation
        data_list = [row_to_dict(row) for row in results]
        df = pandas.DataFrame(data_list)

        df_symmetric = df[["gene1", "gene2", "neg_log10_pval"]].copy()
        df_reverse = df[["gene2", "gene1", "neg_log10_pval"]].copy()
        df_reverse.columns = ["gene1", "gene2", "neg_log10_pval"]
        df_combined = pandas.concat([df_symmetric, df_reverse], ignore_index=True)
        print(df_combined)

        # Create pivot table
        df_pivot = df_combined.pivot_table(
            fill_value=0,
            aggfunc="max",
            index="gene1",
            columns="gene2",
            values="neg_log10_pval",
        )
        print(df_pivot)
        # Build heatmap data for upper triangle only
        heatmap_data = []
        for i, gene_y in enumerate(sorted_genes):  # y-axis (rows)
            for j, gene_x in enumerate(sorted_genes):  # x-axis (columns)
                if i < j:  # Upper triangle including diagonal
                    value = df_pivot.loc[gene_y, gene_x]
                    original_row = df[(df["gene1"] == gene_y) & (df["gene2"] == gene_x)]
                    if (
                        not original_row.empty
                        and original_row["odds_ratio"].iloc[0] < 1
                    ):
                        value = -value
                    heatmap_data.append([gene_y, gene_x, value])

        return InteractionResponse(
            yAxis=sorted_genes, xAxis=sorted_genes, heatmap=heatmap_data
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
