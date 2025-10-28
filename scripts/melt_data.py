import fireducks.pandas as pandas

df = pandas.read_csv("../database/wg_germline_oncoplot_matrix.tsv", sep="\t")
sample_ids = df.columns[1:].tolist()

melted_df = df.melt(
    id_vars=["Gene"], value_vars=sample_ids, var_name="sample_id", value_name="evalue"
)
variant_dict = {
    0: "",
    1: "Missense_Mutation",
    2: "Frame_Shift_Ins",
    3: "In_Frame_Del",
    4: "Frame_Shift_Del",
    5: "Nonsense_Mutation",
    6: "Splice_Site",
    7: "Nonstop_Mutation",
    8: "In_Frame_Ins",
    9: "Multi_Hit",
}
melted_df.sort_values(["Gene", "sample_id"], inplace=True)
melted_df.reset_index(inplace=True, drop=True)
melted_df["annotation"] = melted_df["evalue"].map(variant_dict)
melted_df.to_csv(
    "../database/wg_germline_melted.tsv", sep="\t", index=True, header=True
)
