import traceback
from sqlalchemy import func
import fireducks.pandas as pandas
from fastapi import HTTPException
from app.core import row_to_dict, get_model_class
from app.schema import OncoplotRequest, OncoplotResponse


async def oncoplot_search(request: OncoplotRequest, table_name, db):
    """Search function that returns data in ECharts heatmap format"""
    try:
        model_class = get_model_class(table_name)
        genes = list(set(getattr(request, "genes", None)))

        if not genes:
            return OncoplotResponse(yAxis=[], xAxis=[], heatmap=[])

        query = db.query(model_class)
        query = query.filter(model_class.gene.in_(genes))
        results = query.all()

        gene_zero_counts = dict(
            db.query(model_class.gene, func.count(model_class.gene))
            .filter(model_class.gene.in_(genes), model_class.code == 0)
            .group_by(model_class.gene)
            .all()
        )

        sorted_genes = sorted(
            genes, key=lambda gene: gene_zero_counts.get(gene, 0), reverse=True
        )

        data_list = [row_to_dict(row) for row in results]
        df = pandas.DataFrame(data_list)
        df["value"] = (df["code"] != 0).astype(int)
        df["annotation"] = df["annotation"].replace("", "None")

        # Section for the number of sample data
        df_sample_bar_plot = df.pivot_table(
            fill_value=0,
            index="gene",
            aggfunc="sum",
            values="value",
            columns="annotation",
        )
        df_sample_bar_plot = df_sample_bar_plot.loc[sorted_genes]
        sample_bar_plot = [
            {
                "name": col,
                "type": "bar",
                "stack": "total_sample",
                "data": df_sample_bar_plot[col].tolist(),
            }
            for col in df_sample_bar_plot.columns
        ]

        # Section for the oncoplot data
        df_onco = df.pivot_table(
            fill_value=0,
            aggfunc="max",
            columns="gene",
            values="value",
            index="tumor_sample_barcode",
        )
        df_onco = df_onco.sort_values(by=sorted_genes[::-1], ascending=False)
        samples = df_onco.index.tolist()

        # Section for TMB data calculation
        df_tmb_plot = df.pivot_table(
            fill_value=0,
            aggfunc="sum",
            values="value",
            index="tumor_sample_barcode",
            columns="annotation",
        )

        # Reindex to match the sorted samples, fill missing with 0
        df_tmb_plot = df_tmb_plot.reindex(samples, fill_value=0)

        # Drop "None" column if it exists
        if "None" in df_tmb_plot.columns:
            df_tmb_plot = df_tmb_plot.drop(columns="None")

        tmb_bar_plot = [
            {
                "name": col,
                "type": "bar",
                "stack": "total_tmb",
                "data": df_tmb_plot[col].tolist(),
            }
            for col in df_tmb_plot.columns
        ]

        # Create mapping from sample/gene to index
        sample_to_idx = {sample: idx for idx, sample in enumerate(samples)}
        gene_to_idx = {gene: idx for idx, gene in enumerate(sorted_genes)}

        # Build heatmap data in [x, y, value] format
        heatmap_data = []
        for row in results:
            row_dict = row_to_dict(row)
            tumor_barcode = row_dict["tumor_sample_barcode"]

            # Skip if sample not in our sorted list
            if tumor_barcode not in sample_to_idx:
                continue

            sample_idx = sample_to_idx[tumor_barcode]
            gene_idx = gene_to_idx[row_dict["gene"]]
            evalue = row_dict["code"]

            heatmap_data.append([sample_idx, gene_idx, evalue])

        return OncoplotResponse(
            xAxis=samples,
            yAxis=sorted_genes,
            heatmap=heatmap_data,
            tmb_bar_plot=tmb_bar_plot,
            sample_bar_plot=sample_bar_plot,
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
