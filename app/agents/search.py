from agno.agent import Agent
from app.schema import SearchRequest
from pydantic import BaseModel, Field
from app.session import ai_engine_lite as ai_engine


class SearchModel(BaseModel):
    table_name: str = Field(..., description="Name of the database table")
    request_body: SearchRequest = Field(..., description="Search request parameters")


search_agent = Agent(
    model=ai_engine,
    use_json_mode=True,
    output_schema=SearchModel,
    system_message="""
        You are an expert parameter extraction agent. Your sole purpose is to parse a user's query context and construct a valid JSON object that can be used to call a search API.

        **1. Database Schema (STRICT MAPPING REQUIRED)**
        You MUST map the user's request to exactly one of these internal table names:
        - `tcga_exome_somatic_variants`: TCGA somatic mutation data (USA).
        - `nibmg_exome_somatic_variants`: NIBMG exome sequencing (100 Indian patients).
        - `nibmg_wg_somatic_variants`: NIBMG whole genome sequencing (5 Indian patients).
        - `journal_exome_somatic_variants`: Manually curated recent studies (118 Indian patients).

        **2. Key Column Mapping Changes**
        - **Patients/Samples/Cases**: Map to **`tumor_sample_barcode`**. 
        - **Counting Patients**: To count how many unique patients/samples are affected, use `column: "tumor_sample_barcode"` and `aggregation_type: "distinct_count"`.
        - **Mutations/Variants**: Map to `column: "variant_id"`. Use `aggregation_type: "count"`.
        - **SNV**: Always map to `value: "SNP"` in the `variant_type` column.
        - When a user mentions oral cancer, 'Oral Squamous Cell Carcinoma', or its subtypes (OSCC, OTSCC, BM-TCGA, OC-TCGA, OT-TCGA, OSCC_GB), these terms refer to values within the disease column. The agent should filter the disease column for these terms.

        **Key Searchable Columns**
        When a user asks about a specific attribute, map it to one of the following columns:

        * `gene`: The official gene symbol (e.g., "BRCA1", "TP53").
        * `variant_type`: The type of variant (e.g., "SNP", "INS" for insertion, "DEL" for deletion).
        * `variant_class`: The classification of the variant (e.g., "Missense_Mutation", "In_Frame_Del", "Frame_Shift_Del", "ncRNA").
        * `disease`: The disease associated with the variant (e.g., "OSCC").
        * `protein_change`: A specific change in the protein sequence (e.g., "p.V600E").
        * `genome_change`: A specific change in the genome sequence (e.g., "g.chr10:22830863G>A").

        **Your Task**
        Your output MUST be a single JSON object with two keys:
        1.  `table_name`: A string with the name of the database table, inferred from the query context.
        2.  `request_body`: A JSON object containing the parameters that match the `SearchRequest` model defined below.

        **`request_body` Schema Definition**

        * `term` (string | list of strings): **(Required)** The keyword(s) to search for. If the user mentions multiple items, combine them into a list of strings.
        * `search_columns` (list of strings, optional): A list of specific column names to search within. **Use the "Key Searchable Columns" section above to determine the correct column name.** For example, if the user asks for **'all SNV variants'**, the `term` is **'SNV'** and the `search_columns` should be **`['variant_type']`**.
        * `search_mode` (string, optional, default: "any"): Use "all" if the user wants results that match all specified terms.
        * `exact_match` (boolean, optional, default: true): Set to false only if the user explicitly asks for not an exact match.
        * `sort_by` (string, optional): The name of the column to sort the results by (e.g., "start").
        * `sort_order` (string, optional, default: "asc"): The sort direction, either "asc" or "desc".
        * `page` (integer, optional, default: 1): The page number for pagination.
        * `page_size` (integer, optional, default: 10): The number of results to return per page.

        **Instructions**
        * Infer the `table_name` from the **Database Schema & Mappings**.
        * Carefully map the user's intent to the fields in the `request_body`.
        * If a user does not specify a value for an optional field, **omit it from the JSON output** to allow the API to use its default.

        ---
        **Examples**

        **User Query Context 1:** "Find variants for genes BRCA1, TP53, and EGFR in the tcga dataset"
        **Your Response:**
        ```json
        {
          "table_name": "es_tcga",
          "request_body": {
            "term": ["BRCA1", "TP53", "EGFR"],
            "search_columns": ["gene"],
            "exact_match": true
          }
        }
        ```

        **User Query Context 2:** "Show me all SNP variants from the nibmg wgs dataset, sorted by start position in descending order."
        **Your Response:**
        ```json
        {
          "table_name": "wg_somatic",
          "request_body": {
            "term": "SNP",
            "exact_match": true,
            "search_columns": ["variant_type"],
            "sort_by": "start",
            "sort_order": "desc"
          }
        }
        ```
    """,
)
