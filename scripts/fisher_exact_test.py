import sqlite3
import itertools
import numpy as np
from tqdm import tqdm
from mpire import WorkerPool
import fireducks.pandas as pd
from scipy.stats import fisher_exact


def split_chunks(lst, chunk_size=1_000_000):
    arr = np.asarray(lst)
    n = len(arr)
    for start in range(0, n, chunk_size):
        yield arr[start : start + chunk_size]


def fisher_test_with_logp(arr1, arr2, gene1, gene2):
    """
    Perform Fisher's Exact Test between two binary arrays.

    Parameters:
        arr1, arr2: array-like (same length)
            Binary arrays where 1 = mutated, 0 = not mutated.

    Returns:
        dict with keys:
            - 'odds_ratio'
            - 'p_value'
            - 'neg_log10_pval'
    """
    arr1 = np.asarray(arr1).astype(int)
    arr2 = np.asarray(arr2).astype(int)
    assert len(arr1) == len(arr2), "Arrays must be the same length"

    # Construct 2x2 contingency table
    a = np.sum((arr1 == 1) & (arr2 == 1))  # both mutated
    b = np.sum((arr1 == 1) & (arr2 == 0))  # gene1 mutated only
    c = np.sum((arr1 == 0) & (arr2 == 1))  # gene2 mutated only
    d = np.sum((arr1 == 0) & (arr2 == 0))  # neither mutated
    table = np.array([[a, b], [c, d]])

    # Fisher's Exact Test
    odds_ratio, p_value = fisher_exact(table, alternative="two-sided")

    # Avoid log10(0)
    neg_log10_pval = -np.log10(p_value) if p_value > 0 else np.inf

    return {
        "gene1": gene1,
        "gene2": gene2,
        "p_value": p_value,
        "odds_ratio": odds_ratio,
        "neg_log10_pval": neg_log10_pval,
    }


conn = sqlite3.connect("database.sqlite3")
df = pd.read_sql_query("SELECT * FROM es_journal;", conn)
conn.close()
genes_of_interest = pd.unique(df["gene"])
combinations = list(itertools.combinations(genes_of_interest, 2))
sub_df = df.loc[df["gene"].isin(genes_of_interest), ["gene", "tumor_sample_barcode"]]
binary_matrix = (
    sub_df.assign(mutated=1)
    .pivot_table(
        index="tumor_sample_barcode",
        columns="gene",
        values="mutated",
        fill_value=0,
        aggfunc="max",
    )
    .astype("int8")  # compact, fast type
)
input_gene_array = {
    gene: binary_matrix.get(gene, pd.Series(0, index=binary_matrix.index)).to_numpy()
    for gene in tqdm(genes_of_interest)
}

chunk_generator = split_chunks(combinations, 1_000_000)

for idx, block in enumerate(chunk_generator):
    print(f"Block {idx}: {len(block)} pairs")
    worker_args = [
        (input_gene_array[gene1], input_gene_array[gene2], gene1, gene2)
        for gene1, gene2 in tqdm(block)
    ]

    with WorkerPool(n_jobs=100) as pool:
        results = pool.map(fisher_test_with_logp, worker_args, progress_bar=True)

    result_df = pd.DataFrame(results)
    output_file = f"fisher_exact_results_block_{idx}.tsv"
    result_df.to_csv(output_file, sep="\t", index=False)
    print(f"Results written to {output_file}")
