filter_examples = """
**Complex Filter Construction (CRITICAL)**
- **Structure**: ALL filters must be inside a `filters` object with `logic` (AND/OR) and `conditions` list
- **Single Condition**: Even one condition requires the full structure:
```json
    "filters": {
    "logic": "AND",
    "conditions": [
        {"column": "gene", "operator": "eq", "value": "TP53"}
    ]
    }
```
- **Multiple Values for Same Column**: Use `"in"` operator with a list:
```json
    {"column": "gene", "operator": "in", "value": ["BRCA1", "BRCA2", "TP53"]}
```
- **Multiple Columns**: Use multiple conditions with appropriate logic:
```json
    "filters": {
    "logic": "AND",
    "conditions": [
        {"column": "gene", "operator": "eq", "value": "TP53"},
        {"column": "variant_type", "operator": "eq", "value": "SNP"}
    ]
    }
```
- **Nested Logic:**
```json
    "filters": {
        "logic": "AND",
        "conditions": [
        {"column": "variant_type", "operator": "eq", "value": "SNP"},
        {
            "logic": "OR",
            "conditions": [
            {"column": "gene", "operator": "eq", "value": "TP53"},
            {"column": "gene", "operator": "eq", "value": "BRCA1"}
            ]
        }
        ]
    }
```

**Operator Selection Guidelines**
- **"eq"**: Single exact match (gene = "TP53")
- **"in"**: Multiple possible values (gene in ["TP53", "BRCA1"])
- **"ne"**: Not equal (rarely used, explicit exclusions)
- **"gt", "gte", "lt", "lte"**: Numeric comparisons (rarely used in genomics context)
"""
