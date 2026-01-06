examples = """
**7. Example Responses:**

**Example 1: Count mutations in specific genes**
Query: "Table: tcga_exome_somatic_variants | Request: Count mutations in TP53 and BRCA1"
```json
{
    "table_name": "tcga_exome_somatic_variants",
    "request_body": {
    "column": "variant_id",
    "aggregation_type": "count",
    "filters": {
        "logic": "AND",
        "conditions": [
            {"column": "gene", "operator": "in", "value": ["TP53", "BRCA1"]}
        ]
    }
    }
}
```

**Example 2: Count unique patients with mutations**
Query: "Table: nibmg_exome_somatic_variants | Request: How many patients have TP53 mutations?"
```json
{
    "table_name": "nibmg_exome_somatic_variants",
    "request_body": {
    "column": "tumor_sample_barcode",
    "aggregation_type": "distinct_count",
    "filters": {
        "logic": "AND",
        "conditions": [
            {"column": "gene", "operator": "eq", "value": "TP53"}
        ]
    }
    }
}
```

**Example 3: Distribution/percentage breakdown**
Query: "Table: tcga_exome_somatic_variants | Request: Distribution of mutation types in TP53"
```json
{
    "table_name": "tcga_exome_somatic_variants",
    "request_body": {
    "column": "variant_id",
    "aggregation_type": "percentage",
    "group_by": ["variant_classification"],
    "percentage_by": "variant_classification",
    "filters": {
        "logic": "AND",
        "conditions": [
            {"column": "gene", "operator": "eq", "value": "TP53"}
        ]
    }
    }
}
```

**Example 4: Silent/specific variant types**
Query: "Table: journal_exome_somatic_variants | Request: Count silent mutations in BRCA1"
```json
{
    "table_name": "journal_exome_somatic_variants",
    "request_body": {
    "column": "variant_id",
    "aggregation_type": "count",
    "filters": {
        "logic": "AND",
        "conditions": [
            {"column": "gene", "operator": "eq", "value": "BRCA1"},
            {"column": "variant_classification", "operator": "eq", "value": "Silent"}
        ]
    }
    }
}
```

**Example 5: SNV/SNP filtering**
Query: "Table: nibmg_wg_somatic_variants | Request: Count SNVs in TP53"
```json
{
    "table_name": "nibmg_wg_somatic_variants",
    "request_body": {
    "column": "variant_id",
    "aggregation_type": "count",
    "filters": {
        "logic": "AND",
        "conditions": [
            {"column": "gene", "operator": "eq", "value": "TP53"},
            {"column": "variant_type", "operator": "eq", "value": "SNP"}
        ]
    }
    }
}
```

**Example 6: Disease filtering**
Query: "Table: tcga_exome_somatic_variants | Request: Count TP53 mutations in OSCC patients"
```json
{
    "table_name": "tcga_exome_somatic_variants",
    "request_body": {
    "column": "variant_id",
    "aggregation_type": "count",
    "filters": {
        "logic": "AND",
        "conditions": [
            {"column": "gene", "operator": "eq", "value": "TP53"},
            {"column": "disease", "operator": "eq", "value": "OSCC"}
        ]
    }
    }
}
```
"""
