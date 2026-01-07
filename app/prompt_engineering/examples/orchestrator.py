having_examples = """
**HAVING Clause Guidance (CRITICAL FOR AGGREGATE TOOL):**
When formulating the `query_context` for `generic_aggregate`, you MUST explicitly indicate whether HAVING should be used:

**Use HAVING when:**
- Query asks for entities with mutations in "BOTH" or "ALL" of multiple genes
    * Example: "patients with mutations in both TP53 and PIK3CA"
    * query_context: "Table: X | Request: Find patients with mutations in BOTH TP53 and PIK3CA (use HAVING to filter for exactly 2 distinct genes)"

- Query asks for groups meeting threshold criteria
    * Example: "genes with at least 50 mutations"
    * query_context: "Table: X | Request: Show genes with at least 50 mutations (use HAVING to filter count >= 50)"

- Query asks for entities with "at least N" or "more than N" occurrences
    * Example: "patients with more than 5 TP53 mutations"
    * query_context: "Table: X | Request: Find patients with more than 5 TP53 mutations (use HAVING to filter count > 5)"

- Query asks for co-occurrence patterns
    * Example: "patients with mutations in at least 3 of these genes"
    * query_context: "Table: X | Request: Find patients with mutations in at least 3 of: TP53, PIK3CA, NOTCH1, BRCA1 (use HAVING to filter for distinct_count >= 3)"

**DO NOT use HAVING when:**
- Query asks for mutations "in TP53 OR PIK3CA" (this is a filter, not aggregate threshold)
    * query_context: "Table: X | Request: Count mutations in TP53 or PIK3CA (no HAVING needed)"

- Query asks for simple counts without co-occurrence
    * Example: "count mutations in TP53 and BRCA1"
    * query_context: "Table: X | Request: Count mutations where gene is TP53 or BRCA1 (no HAVING needed)"

- Query asks for distribution/breakdown without threshold
    * Example: "show mutation distribution by gene"
    * query_context: "Table: X | Request: Calculate percentage distribution grouped by gene (no HAVING needed)"

**HAVING Syntax in query_context:**
When HAVING is needed, explicitly mention it in parentheses at the end of the Request portion:
- Format: "Table: [name] | Request: [description] (use HAVING: [condition])"
- Examples:
    * "(use HAVING to filter for exactly 2 distinct genes)"
    * "(use HAVING to filter count >= 50)"
    * "(use HAVING: distinct_count >= 3)"
    * "(use HAVING: count > 5 AND count < 100)"
"""

examples = """
**Example Responses:**

**Example 1 (Conversational - Capabilities):**
User: "What can you do?"
Response:
{
    "plan": [
        {
            "tool_name": "answer_conversational",
            "query_context": "OSCAR can help you explore genomic data related to oral squamous carcinoma. You can search for mutations in specific genes, calculate mutation frequencies, identify variant patterns, filter by patient characteristics, and compare findings across different datasets including TCGA and Indian patient populations from NIBMG studies and published research."
        }
    ]
}

**Example 2 (Conversational - How OSCAR Works - WRONG):**
User: "How do you work?"
WRONG Response:
{
    "plan": [
        {
            "tool_name": "answer_conversational",
            "query_context": "OSCAR uses generic_search and generic_aggregate tools to query tables like tcga_exome_somatic_variants..."
        }
    ]
}
CORRECT Response:
{
    "plan": [
        {
            "tool_name": "answer_conversational",
            "query_context": "OSCAR processes your questions about oral cancer genomics and retrieves relevant information from the dbGENVOC database. You can ask about specific genes, mutation types, patient cohorts, or request statistical analyses. OSCAR handles complex queries and presents results in an easy-to-understand format."
        }
    ]
}

**Example 4: HAVING - Multiple datasets with co-occurrence**
User Query: "Show me patients with mutations in both TP53 and PIK3CA across all datasets, and show me the distribution of mutation types for TP53 in TCGA data"
Orchestrator Output:
{
    "plan": [
        {
            "tool_name": "generic_aggregate",
            "query_context": "Table: tcga_exome_somatic_variants | Request: Find patients with mutations in BOTH TP53 and PIK3CA (use HAVING to filter for exactly 2 distinct genes)"
        },
        {
            "tool_name": "generic_aggregate",
            "query_context": "Table: nibmg_exome_somatic_variants | Request: Find patients with mutations in BOTH TP53 and PIK3CA (use HAVING to filter for exactly 2 distinct genes)"
        },
        {
            "tool_name": "generic_aggregate",
            "query_context": "Table: nibmg_wg_somatic_variants | Request: Find patients with mutations in BOTH TP53 and PIK3CA (use HAVING to filter for exactly 2 distinct genes)"
        },
        {
            "tool_name": "generic_aggregate",
            "query_context": "Table: journal_exome_somatic_variants | Request: Find patients with mutations in BOTH TP53 and PIK3CA (use HAVING to filter for exactly 2 distinct genes)"
        },
        {
            "tool_name": "generic_aggregate",
            "query_context": "Table: tcga_exome_somatic_variants | Request: Calculate percentage distribution of mutations in TP53 grouped by variant_class (no HAVING needed)"
        }
    ]
}

**Example 5: HAVING with range**
User Query: "Show me genes with mutation counts between 20 and 100 in journal data"
Orchestrator Output:
{
    "plan": [
        {
            "tool_name": "generic_aggregate",
            "query_context": "Table: journal_exome_somatic_variants | Request: Show genes with mutation counts between 20 and 100 (use HAVING: count >= 20 AND count <= 100)"
        }
    ]
}

**Example 6: NO HAVING - Simple OR logic (IMPORTANT)**
User Query: "Count mutations in TP53 or PIK3CA in TCGA"
Orchestrator Output:
{
    "plan": [
        {
            "tool_name": "generic_aggregate",
            "query_context": "Table: tcga_exome_somatic_variants | Request: Count mutations where gene is TP53 or PIK3CA (no HAVING needed)"
        }
    ]
}

**Example 7: SNV Class Transitions**
User Query: "Show me the distribution of SNV transition types in TP53 from TCGA data"
Response:
{
    "plan": [
        {
            "tool_name": "generic_concatenated_aggregate",
            "query_context": "Table: tcga_exome_somatic_variants | Request: Count all SNV class transitions (reference_allele to tumor_seq_allele1) for TP53 gene"
        }
    ]
}

**Example 8: Invalid/Overly Broad Request**
User Query: "Show me all the data"
Response:
{
    "plan": [
        {
            "tool_name": "answer_conversational",
            "query_context": "I can help you explore the mutation data, but I need more specific criteria to provide useful results. Please specify what you'd like to see, such as: specific genes (e.g., TP53, BRCA1), mutation types (e.g., missense, frameshift), data sources (TCGA or Indian cohorts), or patient characteristics. For example, you could ask 'Show mutations in TP53 from TCGA data' or 'Count missense mutations in BRCA1 from NIBMG studies.'"
        }
    ]
}

**Example 9: Hybrid Query (Data + Explanation)**
User Query: "How many SNP variants are in the TCGA dataset? and what therapeutic targets can be used"
Orchestrator Output:
{
    "plan": [
        {
            "tool_name": "generic_aggregate",
            "query_context": "Table: tcga_exome_somatic_variants | Request: Count SNP variants (no HAVING needed)"
        },
        {
            "tool_name": "answer_conversational",
            "query_context": "At present, we do not have access to a database that provides information on potential therapeutic targets. As a result, we are unable to answer this question at this time."
        }
    ]
}

**Example 10: Multi-Gene with Grouping (NO HAVING)**
User Query: "Show me mutation counts for TP53, PIK3CA, and NOTCH1 grouped by variant type in NIBMG exome"
Orchestrator Output:
{
    "plan": [
        {
            "tool_name": "generic_aggregate",
            "query_context": "Table: nibmg_exome_somatic_variants | Request: Count mutations where gene is TP53, PIK3CA, or NOTCH1, grouped by gene and variant_class, with percentage breakdown (no HAVING needed)"
        }
    ]
}
"""
