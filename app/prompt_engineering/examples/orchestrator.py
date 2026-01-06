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

**Example 2 (Conversational - Identity in Third Person):**
User: "What can you do, write it in third person"
Response:
{
    "plan": [
    {
        "tool_name": "answer_conversational",
        "query_context": "OSCAR is an AI assistant specialized in analyzing oral squamous carcinoma genomic data from the dbGENVOC database. It can search for specific mutations across multiple genes, calculate statistical summaries like mutation counts and percentages, identify variant patterns and transitions, filter results by various criteria, and compare genomic findings between different patient populations. OSCAR provides access to data from TCGA, NIBMG sequencing studies, and curated published research on Indian patients."
    }
    ]
}

**Example 3 (Conversational - How OSCAR Works - WRONG):**
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

**Example 4 (Data Query - Multiple Genes):**
User: "give me the count of mutations of mapk1 and brca2"
Response:
{
    "plan": [
    {
        "tool_name": "generic_aggregate",
        "query_context": "Table: tcga_exome_somatic_variants | Request: Count mutations for MAPK1 and BRCA2"
    },
    {
        "tool_name": "generic_aggregate",
        "query_context": "Table: nibmg_exome_somatic_variants | Request: Count mutations for MAPK1 and BRCA2"
    },
    {
        "tool_name": "generic_aggregate",
        "query_context": "Table: nibmg_wg_somatic_variants | Request: Count mutations for MAPK1 and BRCA2"
    },
    {
        "tool_name": "generic_aggregate",
        "query_context": "Table: journal_exome_somatic_variants | Request: Count mutations for MAPK1 and BRCA2"
    }
    ]
}

**Example 5 (Data Query - Comparison):**
User: "Compare silent mutations in BRCA1 between TCGA and NIBMG Exome"
Response:
{
    "plan": [
    {
        "tool_name": "generic_aggregate",
        "query_context": "Table: tcga_exome_somatic_variants | Request: Count silent mutations in BRCA1"
    },
    {
        "tool_name": "generic_aggregate",
        "query_context": "Table: nibmg_exome_somatic_variants | Request: Count silent mutations in BRCA1"
    }
    ]
}
"""
