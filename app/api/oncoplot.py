from sqlalchemy import func, case
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
            .filter(model_class.gene.in_(genes), model_class.evalue == 0)
            .group_by(model_class.gene)
            .all()
        )

        sorted_genes = sorted(
            genes, key=lambda gene: gene_zero_counts[gene], reverse=True
        )
        data_list = [row_to_dict(row) for row in results]
        df = pandas.DataFrame(data_list)
        df["value"] = (df["evalue"] != 0).astype(int)
        df["annotation"] = df["annotation"].replace("", "None")

        # Section for the number of sample data
        df_sample_bar_plot = df.pivot_table(
            fill_value=0,
            index="gene",
            aggfunc="sum",
            values="value",
            columns="annotation",
        )
        df_sample_bar_plot = df_sample_bar_plot.loc[sorted_genes].drop(columns="None")
        sample_bar_plot = [
            {
                "name": col,
                "type": "bar",
                "stack": "total_sample",
                "data": df_sample_bar_plot[col].tolist(),
            }
            for col in df_sample_bar_plot.columns
        ]

        # Section for TMB data calculation
        df_tmb_plot = df.pivot_table(
            fill_value=0,
            aggfunc="sum",
            values="value",
            index="sample_id",
            columns="annotation",
        )

        # Section for the oncoplot data
        df = df.pivot_table(
            fill_value=0,
            aggfunc="max",
            columns="gene",
            values="value",
            index="sample_id",
        )
        df = df.sort_values(by=sorted_genes[::-1], ascending=False)
        samples = df.index.tolist()

        df_tmb_plot = df_tmb_plot.loc[samples].drop(columns="None")
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
            sample_idx = sample_to_idx[row_dict["sample_id"]]
            gene_idx = gene_to_idx[row_dict["gene"]]
            evalue = row_dict["evalue"]

            heatmap_data.append([sample_idx, gene_idx, evalue])

        return OncoplotResponse(
            xAxis=samples,
            yAxis=sorted_genes,
            heatmap=heatmap_data,
            tmb_bar_plot=tmb_bar_plot,
            sample_bar_plot=sample_bar_plot,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
