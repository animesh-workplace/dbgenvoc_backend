having_examples = """
**HAVING Structure:**
```json
"having": {
    "logic": "AND",  // or "OR"
    "conditions": [
        {
            "operator": "eq",    // eq, neq, gt, gte, lt, lte
            "value": 2           // numeric value (int or float)
        }
    ]
}
```

**HAVING supports nested AND/OR logic just like filters:**
```json
"having": {
    "logic": "AND",
    "conditions": [
        {"operator": "gte", "value": 2},
        {
            "logic": "OR",
            "conditions": [
                {"operator": "lt", "value": 10},
                {"operator": "gt", "value": 50}
            ]
        }
    ]
}
```

**Critical HAVING Use Cases:**

**1. Patients with mutations in BOTH gene X and gene Y:**
- Query intent: "Find patients with mutations in both TP53 and PIK3CA"
- Strategy:
    * Use `column: "gene"`, `aggregation_type: "distinct_count"`
    * `group_by: ["tumor_sample_barcode"]` (group by patient)
    * Filter genes using `filters` with `"operator": "in", "value": ["TP53", "PIK3CA"]`
    * Apply `having: {"logic": "AND", "conditions": [{"operator": "eq", "value": 2}]}`
- This returns only patients where distinct_count(gene) = 2

**2. Genes with at least N mutations:**
- Query intent: "Show genes with at least 50 mutations"
- Strategy:
    * Use `column: "variant_id"`, `aggregation_type: "count"`
    * `group_by: ["gene"]`
    * Apply `having: {"logic": "AND", "conditions": [{"operator": "gte", "value": 50}]}`

**3. Patients with more than X mutations in specific gene(s):**
- Query intent: "Find patients with more than 5 TP53 mutations"
- Strategy:
    * Use `column: "variant_id"`, `aggregation_type: "count"`
    * `group_by: ["tumor_sample_barcode"]`
    * Filter for gene: `filters` with `"column": "gene", "operator": "eq", "value": "TP53"`
    * Apply `having: {"logic": "AND", "conditions": [{"operator": "gt", "value": 5}]}`

**4. Range filtering on aggregates:**
- Query intent: "Show genes with mutation counts between 10 and 100"
- Strategy:
    * Use `column: "variant_id"`, `aggregation_type: "count"`
    * `group_by: ["gene"]`
    * Apply `having: {"logic": "AND", "conditions": [{"operator": "gte", "value": 10}, {"operator": "lte", "value": 100}]}`

**5. Multiple genes co-occurrence (3 or more genes):**
- Query intent: "Find patients with mutations in at least 3 of these genes: TP53, PIK3CA, NOTCH1, BRCA1"
- Strategy:
    * Use `column: "gene"`, `aggregation_type: "distinct_count"`
    * `group_by: ["tumor_sample_barcode"]`
    * Filter genes: `"operator": "in", "value": ["TP53", "PIK3CA", "NOTCH1", "BRCA1"]`
    * Apply `having: {"logic": "AND", "conditions": [{"operator": "gte", "value": 3}]}`

**HAVING vs FILTERS - Key Difference:**
- **FILTERS**: Applied BEFORE grouping (filters raw rows)
    * Example: `"filters": {"column": "gene", "operator": "in", "value": ["TP53", "PIK3CA"]}`
    * This keeps only rows where gene is TP53 or PIK3CA

- **HAVING**: Applied AFTER grouping (filters aggregated results)
    * Example: `"having": {"operator": "eq", "value": 2}`
    * This keeps only groups where the aggregate value equals 2
"""
