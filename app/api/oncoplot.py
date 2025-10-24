from sqlalchemy import func
import fireducks.pandas as pandas
from fastapi import HTTPException
from app.core import row_to_dict, get_model_class
from app.schema import OncoplotRequest, OncoplotResponse


async def oncoplot_search(request: OncoplotRequest, table_name, db):
    """Search function that returns data in ECharts heatmap format"""
    try:
        model_class = get_model_class(table_name)
        genes = getattr(request, "genes", None)

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
        df = df.pivot_table(
            fill_value=0,
            aggfunc="max",
            columns="gene",
            values="value",
            index="sample_id",
        )
        df = df.sort_values(by=sorted_genes[::-1], ascending=False)
        samples = df.index.tolist()

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

        return OncoplotResponse(yAxis=sorted_genes, xAxis=samples, heatmap=heatmap_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
