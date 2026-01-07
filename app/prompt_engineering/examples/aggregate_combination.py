examples = """
**Example Responses:**

**Example 1: CRITICAL ERROR TO AVOID:**
WRONG (missing ref_allele):
{
    "logic": "OR",
    "conditions": [
        {"column": "tumor_seq_allele2", "operator": "in", "value": ["C", "T"]}
    ]
}

CORRECT (both alleles specified):
{
    "logic": "OR",
    "conditions": [
    {
        "logic": "AND",
        "conditions": [
            {"column": "ref_allele", "operator": "eq", "value": "A"},           // ✓ Must have ref
            {"column": "tumor_seq_allele2", "operator": "in", "value": ["C", "T"]} // ✓ And tumor
        ]
    }
    ]
}        

**Example 2: All transitions for TP53 (A↔G, C↔T)**
Query: Table: nibmg_wg_somatic_variants | Request: Count all SNV class transitions (ref_allele to tumor_seq_allele2) for TP53 gene
```json
{
  "table_name": "nibmg_wg_somatic_variants",
  "request_body": {
    "columns": ["ref_allele", "tumor_seq_allele2"],
    "separator": ">",
    "aggregation_type": "count",
    "group_by": null,
    "percentage_by": null,
    "filters": {
      "logic": "AND",
      "conditions": [
        { "column": "gene", "operator": "eq", "value": "TP53" },
        { "column": "variant_type", "operator": "eq", "value": "SNP" },
        {
          "logic": "OR",
          "conditions": [
            {
              "logic": "AND",
              "conditions": [
                { "column": "ref_allele", "operator": "eq", "value": "A" },
                { "column": "tumor_seq_allele2", "operator": "eq", "value": "G" }
              ]
            },
            {
              "logic": "AND",
              "conditions": [
                { "column": "ref_allele", "operator": "eq", "value": "G" },
                { "column": "tumor_seq_allele2", "operator": "eq", "value": "A" }
              ]
            },
            {
              "logic": "AND",
              "conditions": [
                { "column": "ref_allele", "operator": "eq", "value": "C" },
                { "column": "tumor_seq_allele2", "operator": "eq", "value": "T" }
              ]
            },
            {
              "logic": "AND",
              "conditions": [
                { "column": "ref_allele", "operator": "eq", "value": "T" },
                { "column": "tumor_seq_allele2", "operator": "eq", "value": "C" }
              ]
            }
          ]
        }
      ]
    }
  }
}

```

**Example 3: Multiple specific substitutions (e.g., A>C and A>T)**
Query: "Table: tcga_exome_somatic_variants | Request: Count A>C and A>T substitutions in TP53"
```json
{
    "table_name": "tcga_exome_somatic_variants",
    "request_body": {
        "columns": ["ref_allele", "tumor_seq_allele2"],
        "separator": ">",
        "aggregation_type": "count",
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "gene", "operator": "eq", "value": "TP53"},
                {"column": "ref_allele", "operator": "eq", "value": "A"},
            {
                "logic": "OR",
                "conditions": [
                    {"column": "tumor_seq_allele2", "operator": "eq", "value": "C"},
                    {"column": "tumor_seq_allele2", "operator": "eq", "value": "T"}
                ]
            }
            ]
        }
    }
}
```

**Example 4: All transitions (C>T or T>C)**
Query: "Table: journal_exome_somatic_variants | Request: Count C>T and T>C transitions in TP53"
```json
{
    "table_name": "journal_exome_somatic_variants",
    "request_body": {
        "columns": ["ref_allele", "tumor_seq_allele2"],
        "separator": ">",
        "aggregation_type": "count",
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "gene", "operator": "eq", "value": "TP53"},
                {"column": "variant_type", "operator": "eq", "value": "SNP"},
            {
                "logic": "OR",
                "conditions": [
                {
                    "logic": "AND",
                    "conditions": [
                        {"column": "ref_allele", "operator": "eq", "value": "C"},
                        {"column": "tumor_seq_allele2", "operator": "eq", "value": "T"}
                    ]
                },
                {
                    "logic": "AND",
                    "conditions": [
                        {"column": "ref_allele", "operator": "eq", "value": "T"},
                        {"column": "tumor_seq_allele2", "operator": "eq", "value": "C"}
                    ]
                }
                ]
            }
            ]
        }
    }
}
```

**Example 5: Multiple genes using "in" operator**
Query: "Table: nibmg_exome_somatic_variants | Request: Count substitutions in TP53, BRCA1, and EGFR"
```json
{
    "table_name": "nibmg_exome_somatic_variants",
    "request_body": {
        "columns": ["ref_allele", "tumor_seq_allele2"],
        "separator": ">",
        "aggregation_type": "count",
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "gene", "operator": "in", "value": ["TP53", "BRCA1", "EGFR"]},
                {"column": "variant_type", "operator": "eq", "value": "SNP"}
            ]
        }
    }
}
```

**Example 6: Substitutions in specific disease**
Query: "Table: tcga_exome_somatic_variants | Request: Count substitutions in TP53 for OSCC patients"
```json
{
    "table_name": "tcga_exome_somatic_variants",
    "request_body": {
        "columns": ["ref_allele", "tumor_seq_allele2"],
        "separator": ">",
        "aggregation_type": "count",
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "gene", "operator": "eq", "value": "TP53"},
                {"column": "variant_type", "operator": "eq", "value": "SNP"},
                {"column": "disease", "operator": "eq", "value": "OSCC"}
            ]
        }
    }
}
```

**Example 7: Grouped by gene with percentages**
Query: "Table: nibmg_wg_somatic_variants | Request: Show substitution percentages for each gene"
```json
{
    "table_name": "nibmg_wg_somatic_variants",
    "request_body": {
        "columns": ["ref_allele", "tumor_seq_allele2"],
        "separator": ">",
        "aggregation_type": "percentage",
        "group_by": ["gene"],
        "percentage_by": ["gene"],
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "variant_type", "operator": "eq", "value": "SNP"}
            ]
        }
    }
}
```

Example 8: HAVING : keep only frequent substitutions per gene
Query: "Table: nibmg_wg_somatic_variants | Request: For each gene, keep only substitution patterns with count ≥ 10"

```json
{
    "table_name": "nibmg_wg_somatic_variants",
    "request_body": {
        "columns": ["ref_allele", "tumor_seq_allele2"],
        "separator": ">",
        "aggregation_type": "count",
        "group_by": ["gene"],
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "variant_type", "operator": "eq", "value": "SNP"}
            ]
        },
        "having": {
            "logic": "AND",
            "conditions": [
                {
                    "operator": "gte",
                    "value": 10
                }
            ]
        }
    }
}
```

Example 9: HAVING : percentage threshold within disease
Query: "Table: tcga_exome_somatic_variants | Request: For each disease, show only substitutions contributing ≥ 5% of that disease's substitutions"

```json
{
    "table_name": "tcga_exome_somatic_variants",
    "request_body": {
        "columns": ["ref_allele", "tumor_seq_allele2"],
        "separator": ">",
        "aggregation_type": "percentage",
        "group_by": ["disease"],
        "percentage_by": ["disease"],
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "variant_type", "operator": "eq", "value": "SNP"}
            ]
        },
        "having": {
            "logic": "AND",
            "conditions": [
                {
                    "operator": "gte",
                    "value": 5      // keep only substitutions with percentage >= 5
                }
            ]
        }
    }
}
```

Example 10: HAVING : nested OR/AND on aggregated value
Query: "Table: nibmg_exome_somatic_variants | Request: Keep substitutions with count < 5 or between 20 and 50"

```json
{
    "table_name": "nibmg_exome_somatic_variants",
    "request_body": {
        "columns": ["ref_allele", "tumor_seq_allele2"],
        "separator": ">",
        "aggregation_type": "count",
        "group_by": ["gene"],
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "variant_type", "operator": "eq", "value": "SNP"}
            ]
        },
        "having": {
            "logic": "OR",
            "conditions": [
                {
                    "operator": "lt",
                    "value": 5
                },
                {
                    "logic": "AND",
                    "conditions": [
                        {"operator": "gte", "value": 20},
                        {"operator": "lte", "value": 50}
                    ]
                }
            ]
        }
    }
}
```
"""
