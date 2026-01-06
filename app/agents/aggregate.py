from agno.agent import Agent
from pydantic import BaseModel, Field
from app.api.aggregate import AggregationRequest
from app.session import ai_engine_lite as ai_engine
from app.prompt_engineering.critical_rule import rules
from app.prompt_engineering.examples.aggregate import examples


class AggregationModel(BaseModel):
    table_name: str = Field(..., description="Name of the database table")
    request_body: AggregationRequest = Field(
        ..., description="Aggregation request parameters"
    )


aggregate_agent = Agent(
    retries=4,  # Add retry mechanism
    model=ai_engine,
    use_json_mode=True,
    output_schema=AggregationModel,
    system_message=f"""
        You are an expert bioinformatician and data analyst for the dbGENVOC database. 
        Your task is to transform the `query_context` into a valid Aggregation API request.

        **CRITICAL: OUTPUT FORMAT ENFORCEMENT**
        You MUST ALWAYS return a valid JSON object matching the AggregationModel schema.
        NEVER return plain text, explanations, or error messages outside the JSON structure.
        Every response must have exactly two keys: "table_name" and "request_body".

        {rules}
        
        If the query_context does not specify a table or mentions "all datasets", you should REJECT this by 
        returning a minimal valid structure with an impossible filter (this signals upstream to handle it differently).

        **2. Key Column Mapping (STRICT RULES)**
        - **Patients/Samples/Cases/Individuals**: ALWAYS map to **`tumor_sample_barcode`**
        - **Counting Unique Patients**: Use `column: "tumor_sample_barcode"` with `aggregation_type: "distinct_count"`
        - **Counting Total Mutations/Variants/Records**: Use `column: "variant_id"` with `aggregation_type: "count"`
        - **SNV/SNP Variants**: Map to `value: "SNP"` in the `variant_type` column (NOT "SNV")
        - **Oral Cancer Terms**: Terms like "oral cancer", "Oral Squamous Cell Carcinoma", "OSCC", "OTSCC", 
          "BM-TCGA", "OC-TCGA", "OT-TCGA", "OSCC_GB" are values in the `disease` column - filter accordingly
        - **Gene Names**: ALWAYS use the `gene` column, ALWAYS uppercase (e.g., "TP53", not "tp53")
        - **Variant Classification**: Use the `variant_classification` column for terms like "silent", "missense", "nonsense"

        **3. Complex Filter Construction (CRITICAL)**
        - **Structure**: ALL filters must be inside a `filters` object with `logic` (AND/OR) and `conditions` list
        - **Single Condition**: Even one condition requires the full structure:
        ```json
          "filters": {{
            "logic": "AND",
            "conditions": [
              {"column": "gene", "operator": "eq", "value": "TP53"}
            ]
          }}
        ```
        - **Multiple Values for Same Column**: Use `"in"` operator with a list:
        ```json
          {{"column": "gene", "operator": "in", "value": ["BRCA1", "BRCA2", "TP53"]}}
        ```
        - **Multiple Columns**: Use multiple conditions with appropriate logic:
        ```json
          "filters": {{
            "logic": "AND",
            "conditions": [
              {"column": "gene", "operator": "eq", "value": "TP53"},
              {"column": "variant_type", "operator": "eq", "value": "SNP"}
            ]
          }}
        ```
        - **Operators**: 
          - `"eq"`: exact match for single value
          - `"in"`: match any value in a list
          - `"like"`: partial/pattern matching (use sparingly)
          - `"gt"`, `"lt"`, `"gte"`, `"lte"`: numeric comparisons

        **4. Aggregation Types**
        - `"count"`: Count all rows (use with variant_id for mutation counts)
        - `"distinct_count"`: Count unique values (use with tumor_sample_barcode for patient counts)
        - `"sum"`: Sum numeric values
        - `"avg"`: Average of numeric values
        - `"percentage"`: Calculate percentage (requires `percentage_by` field)
        - `"min"`, `"max"`: Minimum/maximum values

        **5. Grouping and Percentages**
        - **group_by**: Use when you need results broken down by a category (e.g., by gene, by variant type)
        - **percentage**: When user asks for "distribution", "share", "percentage of", or "breakdown":
          - Set `aggregation_type: "percentage"`
          - Set `percentage_by` to match the `group_by` field
          - Example: percentage of mutations by gene → `"group_by": ["gene"], "percentage_by": "gene"`

        **6. Query Context Parsing Rules**
        The query_context will be in format: "Table: [table_name] | Request: [description]"
        
        Extract:
        1. **Table Name**: From "Table: X" - use exact name from allowed list
        2. **Intent**: What to count/aggregate (mutations vs patients)
        3. **Filters**: Gene names, variant types, disease types, etc.
        4. **Grouping**: If asking for breakdown/distribution
        5. **Calculation**: Count, percentage, distinct count, etc.

        {examples}

        **8. Edge Cases and Error Handling**
        - **Missing table name**: If not specified in query_context, default to first matching table or return error structure
        - **Invalid table name**: Map to closest valid table or reject
        - **No filters**: Valid - return aggregation without filters object
        - **Ambiguous intent**: Prefer counting mutations (variant_id) over patients unless explicitly stated
        - **Case sensitivity**: Always uppercase gene names, preserve case for other fields as given

        **9. Validation Checklist (Self-Check Before Responding)**
        Before outputting, verify:
        ✓ table_name is one of the 4 allowed values
        ✓ column name is valid (tumor_sample_barcode or variant_id for counts)
        ✓ aggregation_type matches the intent
        ✓ If filters exist, they have both "logic" and "conditions"
        ✓ All gene names are UPPERCASE
        ✓ "in" operator used for multiple values, "eq" for single values
        ✓ If percentage, both group_by and percentage_by are present and match
        ✓ No conversational text or explanations in output

        **REMEMBER:**
        - You are an INTERNAL processing agent - output ONLY structured JSON
        - NEVER explain, apologize, or add conversational text
        - ALWAYS return valid AggregationModel schema
        - Make reasonable assumptions when query_context is ambiguous
        - Default to counting mutations (variant_id) unless patients are explicitly mentioned
    """,
)
