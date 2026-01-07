examples = """
**Example Responses:**

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
    "group_by": ["variant_class"],
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
            {"column": "variant_class", "operator": "eq", "value": "Silent"}
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

**Example 7: HAVING - Patients with mutations in BOTH genes**
Query: "Table: tcga_exome_somatic_variants | Request: Find patients with mutations in both TP53 and PIK3CA"
```json
{
    "table_name": "tcga_exome_somatic_variants",
    "request_body": {
        "column": "gene",
        "aggregation_type": "distinct_count",
        "group_by": ["tumor_sample_barcode"],
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "gene", "operator": "in", "value": ["TP53", "PIK3CA"]}
            ]
        },
        "having": {
            "logic": "AND",
            "conditions": [
                {"operator": "eq", "value": 2}
            ]
        }
    }
}
```

**Example 8: HAVING - Patients with more than X mutations in specific gene**
Query: "Table: tcga_exome_somatic_variants | Request: Find patients with more than 5 TP53 mutations (use HAVING: count > 5)"
```json
{
    "table_name": "tcga_exome_somatic_variants",
    "request_body": {
        "column": "variant_id",
        "aggregation_type": "count",
        "group_by": ["tumor_sample_barcode"],
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "gene", "operator": "eq", "value": "TP53"}
            ]
        },
        "having": {
            "logic": "AND",
            "conditions": [
                {"operator": "gt", "value": 5}
            ]
        }
    }
}
```

**Example 9: HAVING - Range filtering**
Query: "Table: journal_exome_somatic_variants | Request: Show genes with mutation counts between 10 and 100 (use HAVING: count >= 10 AND count <= 100)"
```json
{
    "table_name": "journal_exome_somatic_variants",
    "request_body": {
        "column": "variant_id",
        "aggregation_type": "count",
        "group_by": ["gene"],
        "having": {
            "logic": "AND",
            "conditions": [
                {"operator": "gte", "value": 10},
                {"operator": "lte", "value": 100}
            ]
        }
    }
}
```

**Example 10: HAVING - Multiple genes co-occurrence**
Query: "Table: nibmg_wg_somatic_variants | Request: Find patients with mutations in at least 3 of: TP53, PIK3CA, NOTCH1, BRCA1 (use HAVING to filter for atleast 3 distinct genes)"
```json
{
    "table_name": "nibmg_wg_somatic_variants",
    "request_body": {
        "column": "gene",
        "aggregation_type": "distinct_count",
        "group_by": ["tumor_sample_barcode"],
        "filters": {
            "logic": "AND",
            "conditions": [
                {"column": "gene", "operator": "in", "value": ["TP53", "PIK3CA", "NOTCH1", "BRCA1"]}
            ]
        },
        "having": {
            "logic": "AND",
            "conditions": [
                {"operator": "gte", "value": 3}
            ]
        }
    }
}
```
"""
