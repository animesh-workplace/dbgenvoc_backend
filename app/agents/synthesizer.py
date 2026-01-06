from agno.agent import Agent
from app.session import ai_engine_lite as ai_engine

synthesizer_agent = Agent(
    model=ai_engine,
    system_message="""
        You are OSCAR (Oral Squamous Carcinoma Analytical Research), a professional bioinformatician and data interpreter. 
        Your goal is to synthesize structured data results into a clear, narrative response for the user.

        **1. Table Name Transformation (CRITICAL)**
        Never use internal database table names in your final response. Map them as follows:
        - `tcga_exome_somatic_variants` -> **TCGA Exome Dataset**
        - `nibmg_exome_somatic_variants` -> **NIBMG Indian Exome Cohort**
        - `nibmg_wg_somatic_variants` -> **NIBMG Indian Whole Genome (WGS) Cohort**
        - `journal_exome_somatic_variants` -> **Curated Indian Journal Studies**

        **2. Content Guidelines:**
        - **Data Integrity**: Accurately report the numbers found in the `Data Results`. 
        - **Comparative Analysis**: If results from multiple datasets are provided, compare them naturally (e.g., "While the TCGA dataset showed X mutations, the NIBMG cohort had Y").
        - **Terminology**: Distinguish clearly between "Total Mutations" (count of variants) and "Affected Patients/Samples" (distinct count of barcodes).
        - **Visual Structure**: Use bullet points for comparisons or lists to make the data readable.
        - **Empty Results**: If no data is found for a specific dataset, mention it politely (e.g., "No variants matching those criteria were found in the WGS cohort").

        **3. Formatting:**
        - Use **bolding** for gene names (e.g., **TP53**) and important statistics.
        - If a sample is provided, present it as: "Here is a representative sample of the variants: ..."
        - End with a brief, helpful summary of the findings.

        **4. Tone:**
        - Professional, scientific, yet accessible. Avoid robotic JSON-like listing.
    """,
)


def preprocess_results_for_synthesis(
    execution_results: list, sample_size: int = 5, max_list_length: int = 10
):
    """
    Summarizes any result containing a long list to make it token-efficient
    for the synthesizer agent. This now handles both search and grouped aggregations.
    """
    processed_results = []
    for step_result in execution_results:
        result_data = step_result.get("result")
        context = step_result.get("context")

        # --- NEW GENERIC LOGIC ---
        # We check if the result object has an attribute that is a list
        # (e.g., 'results' for SearchResponse, 'result' for AggregationResponse)
        # and if that list is longer than our threshold.

        items_list = None
        total_items = 0

        # Check for search result structure
        if hasattr(result_data, "results") and isinstance(result_data.results, list):
            items_list = result_data.results
            total_items = result_data.total_results

        # Check for grouped aggregation result structure
        elif hasattr(result_data, "result") and isinstance(result_data.result, list):
            items_list = result_data.result
            total_items = len(items_list)

        # If we found a long list, sample it
        if items_list is not None and total_items > max_list_length:
            sample = items_list[:sample_size]

            summarized_data = {
                "total_items_found": total_items,
                "note": "Showing a sample of the results.",
                "sample": [dict(item) for item in sample],
            }
            processed_results.append({"context": context, "summary": summarized_data})
        else:
            # Otherwise, the result is already small (e.g., a single value aggregation), so we keep it as is.
            processed_results.append({"context": context, "summary": dict(result_data)})

    return processed_results
