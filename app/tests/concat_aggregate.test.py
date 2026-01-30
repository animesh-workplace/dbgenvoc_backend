# tests/test_concat_aggregate_manual.py
"""
MANUAL TEST SUITE FOR CONCATENATED AGGREGATE API (50 TESTS)

This test suite covers:
- Basic concatenated aggregations
- Combination columns functionality
- All aggregation types with combination columns
- Percentage calculations with combination columns
- Computed fields (concatenation)
- Filters with combination queries
- Having clauses on concatenated aggregations
- Ordering (by aggregated_value and combination columns)
- Limit functionality
- Edge cases and error conditions
- Performance with multiple combination columns
- Data integrity and consistency

Run these tests manually by:
1. Starting your FastAPI server
2. Running each curl command
3. Verifying the output matches expectations
4. Saving responses for validation
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any

# Test configuration
BASE_URL = "http://localhost:8000"
TABLE_NAME = "nibmg_exome_somatic_variants"  # Change to your table

# Common columns for testing (adjust based on your schema)
COLUMN_NAMES = {
    "categorical": ["gene", "variant_classification", "consequence", "chromosome", "sample_id"],
    "numeric": ["tumor_depth", "tumor_vaf", "normal_depth"],
    "id_columns": ["variant_id", "patient_id"],
    "positional": ["start_position", "end_position"]
}

def create_test_request(name: str, request_body: Dict[str, Any], expected_checks: List[str]) -> Dict[str, Any]:
    """Create a test case for manual execution."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"concat_aggregate_test_{name}_{timestamp}.json"
    
    # Create curl command
    curl_command = f"""curl -X POST {BASE_URL}/api/concatenated_aggregate/{TABLE_NAME} \\
  -H 'Content-Type: application/json' \\
  -d '{json.dumps(request_body, indent=2)}'"""
    
    test_case = {
        "name": name,
        "timestamp": timestamp,
        "curl_command": curl_command,
        "endpoint": f"/api/concatenated_aggregate/{TABLE_NAME}",
        "request": request_body,
        "expected_checks": expected_checks,
        "actual_response": None,
        "pass": None,
        "notes": "",
        "test_category": None  # Will be set later
    }
    
    # Save to file
    os.makedirs("test_results/concat_aggregate", exist_ok=True)
    with open(f"test_results/concat_aggregate/{filename}", "w") as f:
        json.dump(test_case, f, indent=2)
    
    return test_case

def print_test_case(test_case: Dict[str, Any]):
    """Print test case details."""
    print(f"\n{'='*60}")
    print(f"TEST: {test_case['name']}")
    print(f"Category: {test_case.get('test_category', 'General')}")
    print(f"{'='*60}")
    print(f"Command:")
    print(test_case['curl_command'])
    print(f"\nExpected checks:")
    for i, check in enumerate(test_case['expected_checks'], 1):
        print(f"  {i:2d}. {check}")
    print(f"Saved to: test_results/concat_aggregate/{test_case['name']}_{test_case['timestamp']}.json")
    print()

# --------------------------------------------------
# TEST SUITE GENERATION
# --------------------------------------------------

def generate_test_suite() -> List[Dict[str, Any]]:
    """Generate 50 test cases for Concatenated Aggregate API."""
    tests = []
    
    # --------------------------------------------------
    # CATEGORY 1: BASIC CONCATENATED AGGREGATIONS
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 1: BASIC CONCATENATED AGGREGATIONS")
    print("="*60)
    
    # Test 1: Basic concatenated count
    tests.append(create_test_request(
        name="basic_concat_count",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 200",
            "result should be array of objects",
            "Each object should have gene, variant_classification, aggregated_value",
            "aggregated_value should be count per combination",
            "Should show count for each gene-variant_classification combination",
            "total_combinations should equal number of unique combinations"
        ]
    ))
    tests[-1]["test_category"] = "Basic Concatenated Aggregations"
    
    # Test 2: Single combination column
    tests.append(create_test_request(
        name="single_combination_column",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene"],
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 200",
            "Should behave like regular group_by with single column",
            "Each result should have gene and aggregated_value",
            "Should match regular aggregate with group_by=['gene']"
        ]
    ))
    tests[-1]["test_category"] = "Basic Concatenated Aggregations"
    
    # Test 3: Three combination columns
    tests.append(create_test_request(
        name="three_combination_columns",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "chromosome", "variant_classification"],
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 200",
            "Each result should have gene, chromosome, variant_classification, aggregated_value",
            "Should show count for each unique triple combination",
            "Number of combinations may be large"
        ]
    ))
    tests[-1]["test_category"] = "Basic Concatenated Aggregations"
    
    # Test 4: Concatenated sum
    tests.append(create_test_request(
        name="concat_sum",
        request_body={
            "aggregate_column": "tumor_depth",
            "combination_columns": ["gene", "sample_id"],
            "aggregation_type": "sum"
        },
        expected_checks=[
            "Status code: 200",
            "Should sum tumor_depth for each gene-sample combination",
            "aggregated_value should be numeric (could be decimal)",
            "Null tumor_depth values should be handled appropriately"
        ]
    ))
    tests[-1]["test_category"] = "Basic Concatenated Aggregations"
    
    # Test 5: Concatenated average
    tests.append(create_test_request(
        name="concat_average",
        request_body={
            "aggregate_column": "tumor_vaf",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "avg"
        },
        expected_checks=[
            "Status code: 200",
            "Should average tumor_vaf for each gene-variant_classification combination",
            "Should handle null values (exclude from average)",
            "aggregated_value should be decimal"
        ]
    ))
    tests[-1]["test_category"] = "Basic Concatenated Aggregations"
    
    # Test 6: Concatenated distinct count
    tests.append(create_test_request(
        name="concat_distinct_count",
        request_body={
            "aggregate_column": "sample_id",
            "combination_columns": ["gene", "chromosome"],
            "aggregation_type": "distinct_count"
        },
        expected_checks=[
            "Status code: 200",
            "Should count distinct samples for each gene-chromosome combination",
            "Should be integer values",
            "Shows how many samples have mutations in each gene on each chromosome"
        ]
    ))
    tests[-1]["test_category"] = "Basic Concatenated Aggregations"
    
    # --------------------------------------------------
    # CATEGORY 2: PERCENTAGE CALCULATIONS WITH COMBINATIONS
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 2: PERCENTAGE CALCULATIONS WITH COMBINATIONS")
    print("="*60)
    
    # Test 7: Global percentage with combinations
    tests.append(create_test_request(
        name="concat_global_percentage",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "percentage"
        },
        expected_checks=[
            "Status code: 200",
            "aggregated_value should be percentage of total mutations per combination",
            "Sum of all percentages should be approximately 100 (within rounding)",
            "group_totals should have 'global' key with total_records",
            "percentages should be rounded to 2 decimal places"
        ]
    ))
    tests[-1]["test_category"] = "Percentage Calculations"
    
    # Test 8: Partitioned percentage with subset of combination columns
    tests.append(create_test_request(
        name="concat_partitioned_percentage",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification", "chromosome"],
            "percentage_by": ["gene", "chromosome"],
            "aggregation_type": "percentage"
        },
        expected_checks=[
            "Status code: 200",
            "percentage_by columns must be subset of combination_columns",
            "For each gene+chromosome, sum of percentages across variant_classifications should be ~100",
            "group_totals should have entries for each gene+chromosome combination",
            "Should show percentage within each gene-chromosome group"
        ]
    ))
    tests[-1]["test_category"] = "Percentage Calculations"
    
    # Test 9: Single column percentage_by
    tests.append(create_test_request(
        name="concat_single_percentage_by",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "sample_id", "variant_classification"],
            "percentage_by": ["gene"],
            "aggregation_type": "percentage"
        },
        expected_checks=[
            "Status code: 200",
            "For each gene, sum of percentages across sample_id+variant_classification should be ~100",
            "Shows percentage breakdown within each gene",
            "Useful for seeing distribution of mutations within genes"
        ]
    ))
    tests[-1]["test_category"] = "Percentage Calculations"
    
    # Test 10: Complex percentage calculation
    tests.append(create_test_request(
        name="concat_complex_percentage",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["chromosome", "gene", "consequence", "sample_id"],
            "percentage_by": ["chromosome", "gene"],
            "aggregation_type": "percentage"
        },
        expected_checks=[
            "Status code: 200",
            "Should calculate percentages within each chromosome+gene combination",
            "group_totals should have compound keys (e.g., '17|TP53')",
            "Shows detailed breakdown of mutations by sample and consequence within gene-chromosome"
        ]
    ))
    tests[-1]["test_category"] = "Percentage Calculations"
    
    # --------------------------------------------------
    # CATEGORY 3: COMPUTED FIELDS
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 3: COMPUTED FIELDS")
    print("="*60)
    
    # Test 11: Basic computed field (concatenation)
    tests.append(create_test_request(
        name="computed_field_basic",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "computed_fields": [
                {
                    "name": "gene_variant",
                    "type": "concat",
                    "columns": ["gene", "variant_classification"],
                    "separator": "_"
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "Each result should have 'gene_variant' computed field",
            "gene_variant should be gene + '_' + variant_classification",
            "Computed field should be in addition to original columns",
            "Separator '_' should be used"
        ]
    ))
    tests[-1]["test_category"] = "Computed Fields"
    
    # Test 12: Multiple computed fields
    tests.append(create_test_request(
        name="multiple_computed_fields",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["chromosome", "start_position", "gene"],
            "aggregation_type": "count",
            "computed_fields": [
                {
                    "name": "chrom_pos",
                    "type": "concat",
                    "columns": ["chromosome", "start_position"],
                    "separator": ":"
                },
                {
                    "name": "location_gene",
                    "type": "concat",
                    "columns": ["chromosome", "gene"],
                    "separator": "|"
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "Should have both 'chrom_pos' and 'location_gene' fields",
            "chrom_pos should be 'chromosome:start_position'",
            "location_gene should be 'chromosome|gene'",
            "Both computed fields should be present in each result"
        ]
    ))
    tests[-1]["test_category"] = "Computed Fields"
    
    # Test 13: Computed field with custom separator
    tests.append(create_test_request(
        name="computed_field_custom_separator",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "consequence", "sample_id"],
            "aggregation_type": "count",
            "computed_fields": [
                {
                    "name": "full_id",
                    "type": "concat",
                    "columns": ["gene", "consequence", "sample_id"],
                    "separator": "||"
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "full_id should use '||' as separator",
            "Format should be 'gene||consequence||sample_id'",
            "Custom separator should be respected"
        ]
    ))
    tests[-1]["test_category"] = "Computed Fields"
    
    # Test 14: Computed field with empty separator
    tests.append(create_test_request(
        name="computed_field_empty_separator",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["chromosome", "start_position"],
            "aggregation_type": "count",
            "computed_fields": [
                {
                    "name": "genomic_coordinate",
                    "type": "concat",
                    "columns": ["chromosome", "start_position"],
                    "separator": ""
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "genomic_coordinate should concatenate without separator",
            "Should be 'chromosomestart_position' (no separator)",
            "Empty string separator should work"
        ]
    ))
    tests[-1]["test_category"] = "Computed Fields"
    
    # --------------------------------------------------
    # CATEGORY 4: FILTERS WITH CONCATENATED AGGREGATIONS
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 4: FILTERS WITH CONCATENATED AGGREGATIONS")
    print("="*60)
    
    # Test 15: Filter on combination column
    tests.append(create_test_request(
        name="filter_on_combination_column",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "filters": {
                "logic": "AND",
                "conditions": [
                    {"column": "gene", "operator": "eq", "value": "TP53"}
                ]
            }
        },
        expected_checks=[
            "Status code: 200",
            "Should only include TP53 in results",
            "Should show all variant_classifications for TP53",
            "Filters should be applied before grouping"
        ]
    ))
    tests[-1]["test_category"] = "Filters"
    
    # Test 16: Filter on non-combination column
    tests.append(create_test_request(
        name="filter_on_non_combination_column",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "sample_id"],
            "aggregation_type": "count",
            "filters": {
                "logic": "AND",
                "conditions": [
                    {"column": "tumor_vaf", "operator": "gt", "value": "0.1"}
                ]
            }
        },
        expected_checks=[
            "Status code: 200",
            "Should only count variants with tumor_vaf > 0.1",
            "Filters on non-combination columns should work",
            "Should reduce total counts appropriately"
        ]
    ))
    tests[-1]["test_category"] = "Filters"
    
    # Test 17: Complex filter affecting combinations
    tests.append(create_test_request(
        name="complex_filter_affecting_combinations",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification", "sample_id"],
            "aggregation_type": "count",
            "filters": {
                "logic": "OR",
                "conditions": [
                    {"column": "gene", "operator": "eq", "value": "TP53"},
                    {"column": "gene", "operator": "eq", "value": "KRAS"},
                    {"column": "variant_classification", "operator": "eq", "value": "Missense_Mutation"}
                ]
            }
        },
        expected_checks=[
            "Status code: 200",
            "Should include TP53, KRAS, OR missense mutations",
            "Complex OR logic should work with combination columns",
            "Should show appropriate combinations"
        ]
    ))
    tests[-1]["test_category"] = "Filters"
    
    # Test 18: Genomic filter with combinations
    tests.append(create_test_request(
        name="genomic_filter_with_combinations",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "chromosome", "start_position"],
            "aggregation_type": "count",
            "genomic_filter": {
                "ranges": ["chr17:7570000-7580000"]
            }
        },
        expected_checks=[
            "Status code: 200",
            "Should only count variants in chr17:7570000-7580000 range",
            "Should include TP53 (if in that region)",
            "Combination of gene, chromosome, position should be meaningful"
        ]
    ))
    tests[-1]["test_category"] = "Filters"
    
    # --------------------------------------------------
    # CATEGORY 5: HAVING CLAUSE WITH CONCATENATED AGGREGATIONS
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 5: HAVING CLAUSE WITH CONCATENATED AGGREGATIONS")
    print("="*60)
    
    # Test 19: Simple having clause on aggregated value
    tests.append(create_test_request(
        name="concat_having_greater_than",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "having": {
                "column": "aggregated_value",
                "operator": "gt",
                "value": 5
            }
        },
        expected_checks=[
            "Status code: 200",
            "Should only include combinations with count > 5",
            "groups_after_having should be <= groups_before_having",
            "All aggregated_values should be > 5"
        ]
    ))
    tests[-1]["test_category"] = "Having Clause"
    
    # Test 20: Having clause on percentage
    tests.append(create_test_request(
        name="concat_having_on_percentage",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "sample_id"],
            "aggregation_type": "percentage",
            "having": {
                "column": "aggregated_value",
                "operator": "gt",
                "value": 50.0
            }
        },
        expected_checks=[
            "Status code: 200",
            "Should include combinations where percentage > 50%",
            "All percentages should be > 50.0",
            "Useful for finding dominant mutation patterns"
        ]
    ))
    tests[-1]["test_category"] = "Having Clause"
    
    # Test 21: Complex having with AND logic
    tests.append(create_test_request(
        name="concat_complex_having_and",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "chromosome", "variant_classification"],
            "aggregation_type": "count",
            "having": {
                "logic": "AND",
                "conditions": [
                    {"column": "aggregated_value", "operator": "gt", "value": 2},
                    {"column": "aggregated_value", "operator": "lt", "value": 20}
                ]
            }
        },
        expected_checks=[
            "Status code: 200",
            "Should include combinations with count between 2 and 20",
            "All counts should be >2 AND <20",
            "Complex having logic should work"
        ]
    ))
    tests[-1]["test_category"] = "Having Clause"
    
    # --------------------------------------------------
    # CATEGORY 6: ORDERING WITH COMBINATION COLUMNS
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 6: ORDERING WITH COMBINATION COLUMNS")
    print("="*60)
    
    # Test 22: Order by aggregated_value
    tests.append(create_test_request(
        name="concat_order_by_aggregated_value",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "order_by": "aggregated_value",
            "order_direction": "desc"
        },
        expected_checks=[
            "Status code: 200",
            "Results should be sorted by count descending",
            "First result should have highest count",
            "order_direction should be 'desc' in response"
        ]
    ))
    tests[-1]["test_category"] = "Ordering"
    
    # Test 23: Order by combination column
    tests.append(create_test_request(
        name="concat_order_by_combination_column",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "order_by": "gene",
            "order_direction": "asc"
        },
        expected_checks=[
            "Status code: 200",
            "Results should be sorted alphabetically by gene",
            "Within same gene, order may not be defined",
            "Should sort by combination column correctly"
        ]
    ))
    tests[-1]["test_category"] = "Ordering"
    
    # Test 24: Order by multiple columns
    tests.append(create_test_request(
        name="concat_order_by_multiple_columns",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification", "chromosome"],
            "aggregation_type": "count",
            "order_by": ["gene", "aggregated_value"],
            "order_direction": "asc"
        },
        expected_checks=[
            "Status code: 200",
            "Primary sort by gene (A-Z), secondary sort by count (ascending)",
            "Within each gene, counts should be ascending",
            "Multiple column ordering should work"
        ]
    ))
    tests[-1]["test_category"] = "Ordering"
    
    # Test 25: Order by multiple combination columns
    tests.append(create_test_request(
        name="concat_order_by_multiple_combination_columns",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["chromosome", "gene", "variant_classification"],
            "aggregation_type": "count",
            "order_by": ["chromosome", "gene"],
            "order_direction": "asc"
        },
        expected_checks=[
            "Status code: 200",
            "Sort by chromosome, then gene",
            "Should group results by chromosome first",
            "Within each chromosome, sort by gene"
        ]
    ))
    tests[-1]["test_category"] = "Ordering"
    
    # --------------------------------------------------
    # CATEGORY 7: LIMIT WITH CONCATENATED AGGREGATIONS
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 7: LIMIT WITH CONCATENATED AGGREGATIONS")
    print("="*60)
    
    # Test 26: Limit results
    tests.append(create_test_request(
        name="concat_limit_results",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "order_by": "aggregated_value",
            "order_direction": "desc",
            "limit": 10
        },
        expected_checks=[
            "Status code: 200",
            "Should return at most 10 results",
            "Should be top 10 combinations by count",
            "limit should be 10 in response"
        ]
    ))
    tests[-1]["test_category"] = "Limit"
    
    # Test 27: Limit with having clause
    tests.append(create_test_request(
        name="concat_limit_with_having",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "sample_id"],
            "aggregation_type": "count",
            "having": {
                "column": "aggregated_value",
                "operator": "gt",
                "value": 1
            },
            "order_by": "aggregated_value",
            "order_direction": "desc",
            "limit": 5
        },
        expected_checks=[
            "Status code: 200",
            "Should return at most 5 results",
            "All results should have count > 1",
            "Limit applied after having clause"
        ]
    ))
    tests[-1]["test_category"] = "Limit"
    
    # --------------------------------------------------
    # CATEGORY 8: COMPLEX COMBINATIONS
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 8: COMPLEX COMBINATIONS")
    print("="*60)
    
    # Test 28: All parameters combined
    tests.append(create_test_request(
        name="concat_all_parameters_combined",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification", "sample_id"],
            "percentage_by": ["gene"],
            "aggregation_type": "percentage",
            "filters": {
                "logic": "AND",
                "conditions": [
                    {"column": "tumor_vaf", "operator": "gt", "value": "0.05"}
                ]
            },
            "genomic_filter": {
                "ranges": ["chr17:7570000-7580000"]
            },
            "having": {
                "column": "aggregated_value",
                "operator": "gt",
                "value": 10.0
            },
            "order_by": ["gene", "aggregated_value"],
            "order_direction": "desc",
            "limit": 20,
            "computed_fields": [
                {
                    "name": "gene_sample",
                    "type": "concat",
                    "columns": ["gene", "sample_id"],
                    "separator": "-"
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "Should apply all filters (tumor_vaf > 0.05 AND genomic range)",
            "Should calculate percentages within each gene",
            "Should filter percentages > 10%",
            "Should sort by gene then percentage descending",
            "Should limit to 20 results",
            "Should include computed field 'gene_sample'",
            "All parameters should work together correctly"
        ]
    ))
    tests[-1]["test_category"] = "Complex Combinations"
    
    # Test 29: Complex concatenated aggregation with sum
    tests.append(create_test_request(
        name="concat_complex_sum_aggregation",
        request_body={
            "aggregate_column": "tumor_depth",
            "combination_columns": ["gene", "chromosome", "variant_classification"],
            "aggregation_type": "sum",
            "filters": {
                "logic": "OR",
                "conditions": [
                    {"column": "gene", "operator": "eq", "value": "TP53"},
                    {"column": "gene", "operator": "eq", "value": "KRAS"}
                ]
            },
            "having": {
                "column": "aggregated_value",
                "operator": "gt",
                "value": 1000
            },
            "order_by": "aggregated_value",
            "order_direction": "desc",
            "computed_fields": [
                {
                    "name": "gene_location",
                    "type": "concat",
                    "columns": ["gene", "chromosome"],
                    "separator": "@"
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "Should sum tumor_depth per gene-chromosome-variant_classification",
            "Should only include TP53 or KRAS",
            "Should filter sums > 1000",
            "Should sort by sum descending",
            "Should include computed field 'gene_location'"
        ]
    ))
    tests[-1]["test_category"] = "Complex Combinations"
    
    # --------------------------------------------------
    # CATEGORY 9: EDGE CASES AND ERROR CONDITIONS
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 9: EDGE CASES AND ERROR CONDITIONS")
    print("="*60)
    
    # Test 30: Invalid combination column
    tests.append(create_test_request(
        name="error_invalid_combination_column",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["nonexistent_column", "gene"],
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 400 or 500",
            "Should return error about invalid column",
            "Should validate all combination columns exist"
        ]
    ))
    tests[-1]["test_category"] = "Error Conditions"
    
    # Test 31: Invalid aggregate column
    tests.append(create_test_request(
        name="error_invalid_aggregate_column",
        request_body={
            "aggregate_column": "nonexistent_column",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 400 or 500",
            "Should return error about invalid aggregate column",
            "Should validate aggregate column exists"
        ]
    ))
    tests[-1]["test_category"] = "Error Conditions"
    
    # Test 32: percentage_by not subset of combination_columns
    tests.append(create_test_request(
        name="error_percentage_by_not_subset",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "percentage_by": ["sample_id"],
            "aggregation_type": "percentage"
        },
        expected_checks=[
            "Status code: 400 or 422",
            "Should reject because sample_id not in combination_columns",
            "Should explain percentage_by must be subset of combination_columns"
        ]
    ))
    tests[-1]["test_category"] = "Error Conditions"
    
    # Test 33: Empty combination_columns array
    tests.append(create_test_request(
        name="error_empty_combination_columns",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": [],
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 422",
            "Should reject empty combination_columns",
            "combination_columns must have at least 1 column"
        ]
    ))
    tests[-1]["test_category"] = "Error Conditions"
    
    # Test 34: Invalid computed field column
    tests.append(create_test_request(
        name="error_invalid_computed_field_column",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "computed_fields": [
                {
                    "name": "invalid_field",
                    "type": "concat",
                    "columns": ["nonexistent_column", "gene"],
                    "separator": "_"
                }
            ]
        },
        expected_checks=[
            "Status code: 400 or 500",
            "Should handle invalid column in computed field",
            "Should either skip or error on invalid computed field columns"
        ]
    ))
    tests[-1]["test_category"] = "Error Conditions"
    
    # Test 35: Invalid computed field name
    tests.append(create_test_request(
        name="error_invalid_computed_field_name",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "computed_fields": [
                {
                    "name": "123invalid",  # Not a valid identifier
                    "type": "concat",
                    "columns": ["gene", "variant_classification"],
                    "separator": "_"
                }
            ]
        },
        expected_checks=[
            "Status code: 422",
            "Should reject invalid computed field name",
            "Computed field name must be valid identifier"
        ]
    ))
    tests[-1]["test_category"] = "Error Conditions"
    
    # Test 36: Duplicate computed field name
    tests.append(create_test_request(
        name="error_duplicate_computed_field_name",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "computed_fields": [
                {
                    "name": "gene_variant",
                    "type": "concat",
                    "columns": ["gene", "variant_classification"],
                    "separator": "_"
                },
                {
                    "name": "gene_variant",  # Duplicate name
                    "type": "concat",
                    "columns": ["gene", "variant_classification"],
                    "separator": "-"
                }
            ]
        },
        expected_checks=[
            "Status code: 422 or 400",
            "Should reject duplicate computed field names",
            "Computed field names must be unique"
        ]
    ))
    tests[-1]["test_category"] = "Error Conditions"
    
    # Test 37: Invalid order_by column (not in combination_columns)
    tests.append(create_test_request(
        name="error_invalid_order_by_column",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "order_by": "sample_id",
            "order_direction": "asc"
        },
        expected_checks=[
            "Status code: 400 or 422",
            "Should reject order_by column not in combination_columns",
            "order_by must be 'aggregated_value' or in combination_columns"
        ]
    ))
    tests[-1]["test_category"] = "Error Conditions"
    
    # Test 38: Null handling in combination columns
    tests.append(create_test_request(
        name="null_values_in_combination_columns",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "consequence"],  # consequence might have nulls
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 200",
            "Should handle null values in combination columns",
            "Nulls should be treated as a distinct group",
            "Should show count for 'null' consequence values"
        ]
    ))
    tests[-1]["test_category"] = "Edge Cases"
    
    # Test 39: Many combination columns (performance)
    tests.append(create_test_request(
        name="many_combination_columns",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["chromosome", "start_position", "gene", "variant_classification", "consequence"],
            "aggregation_type": "count",
            "limit": 50
        },
        expected_checks=[
            "Status code: 200",
            "Should handle 5 combination columns",
            "Each result should have all 5 combination columns",
            "Number of unique combinations may be very large",
            "Should respect limit of 50"
        ]
    ))
    tests[-1]["test_category"] = "Edge Cases"
    
    # --------------------------------------------------
    # CATEGORY 10: PERFORMANCE AND SCALABILITY
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 10: PERFORMANCE AND SCALABILITY")
    print("="*60)
    
    # Test 40: Large number of combinations
    tests.append(create_test_request(
        name="performance_large_combinations",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "sample_id"],
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 200",
            "Should handle potentially thousands of gene-sample combinations",
            "Response time should be reasonable (< 5 seconds)",
            "Should not timeout or crash",
            "groups_before_having should be large number"
        ]
    ))
    tests[-1]["test_category"] = "Performance"
    
    # Test 41: Complex concatenated aggregation with filters
    tests.append(create_test_request(
        name="performance_complex_concat_aggregation",
        request_body={
            "aggregate_column": "tumor_depth",
            "combination_columns": ["gene", "variant_classification", "sample_id"],
            "aggregation_type": "sum",
            "filters": {
                "logic": "OR",
                "conditions": [
                    {"column": "gene", "operator": "in", "value": ["TP53", "KRAS", "EGFR", "PIK3CA", "BRAF"]}
                ]
            },
            "having": {
                "column": "aggregated_value",
                "operator": "gt",
                "value": 100
            },
            "order_by": "aggregated_value",
            "order_direction": "desc",
            "limit": 100
        },
        expected_checks=[
            "Status code: 200",
            "Should complete within reasonable time",
            "Should handle IN operator with multiple genes",
            "Should apply having clause correctly",
            "Should return sorted and limited results"
        ]
    ))
    tests[-1]["test_category"] = "Performance"
    
    # Test 42: Window function performance with combinations
    tests.append(create_test_request(
        name="performance_window_function_with_combinations",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "chromosome", "variant_classification"],
            "percentage_by": ["gene", "chromosome"],
            "aggregation_type": "percentage",
            "limit": 50
        },
        expected_checks=[
            "Status code: 200",
            "Window function with multiple partition columns should perform well",
            "Should calculate percentages correctly",
            "Should respect limit",
            "Response time should be acceptable"
        ]
    ))
    tests[-1]["test_category"] = "Performance"
    
    # --------------------------------------------------
    # CATEGORY 11: DATA INTEGRITY AND CONSISTENCY
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 11: DATA INTEGRITY AND CONSISTENCY")
    print("="*60)
    
    # Test 43: Verify groups_before_having vs groups_after_having
    tests.append(create_test_request(
        name="concat_consistency_groups_counts",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "having": {
                "column": "aggregated_value",
                "operator": "gt",
                "value": 3
            }
        },
        expected_checks=[
            "Status code: 200",
            "groups_after_having should be <= groups_before_having",
            "Difference should equal number of combinations filtered by having",
            "Both counts should be consistent with actual combinations"
        ]
    ))
    tests[-1]["test_category"] = "Data Integrity"
    
    # Test 44: Cross-verify with simple SQL query
    tests.append(create_test_request(
        name="concat_cross_verification_simple",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "variant_classification"],
            "aggregation_type": "count",
            "filters": {
                "logic": "AND",
                "conditions": [
                    {"column": "gene", "operator": "eq", "value": "TP53"},
                    {"column": "variant_classification", "operator": "eq", "value": "Missense_Mutation"}
                ]
            }
        },
        expected_checks=[
            "Status code: 200",
            "Result should match: SELECT gene, variant_classification, COUNT(*) FROM table WHERE gene='TP53' AND variant_classification='Missense_Mutation' GROUP BY gene, variant_classification",
            "Should have exactly 1 result (if data exists)",
            "Should be verifiable with direct database query"
        ]
    ))
    tests[-1]["test_category"] = "Data Integrity"
    
    # Test 45: Verify total_combinations calculation
    tests.append(create_test_request(
        name="verify_total_combinations",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene"],
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 200",
            "total_combinations should equal number of distinct genes",
            "Should match groups_before_having",
            "Should be consistent with result array length"
        ]
    ))
    tests[-1]["test_category"] = "Data Integrity"
    
    # Test 46: Consistency with regular aggregate API
    tests.append(create_test_request(
        name="consistency_with_regular_aggregate",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene"],
            "aggregation_type": "count"
        },
        expected_checks=[
            "Status code: 200",
            "Should produce same results as regular aggregate with group_by=['gene']",
            "Result format may differ but counts should match",
            "Concatenated aggregate with single column should match regular aggregate"
        ]
    ))
    tests[-1]["test_category"] = "Data Integrity"
    
    # --------------------------------------------------
    # CATEGORY 12: SPECIFIC USE CASES
    # --------------------------------------------------
    print("\n" + "="*60)
    print("CATEGORY 12: SPECIFIC USE CASES")
    print("="*60)
    
    # Test 47: Mutation spectrum by gene and consequence
    tests.append(create_test_request(
        name="use_case_mutation_spectrum",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["gene", "consequence"],
            "aggregation_type": "count",
            "order_by": "aggregated_value",
            "order_direction": "desc",
            "limit": 20,
            "computed_fields": [
                {
                    "name": "gene_consequence",
                    "type": "concat",
                    "columns": ["gene", "consequence"],
                    "separator": " -> "
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "Shows mutation spectrum (gene + consequence)",
            "Top 20 most frequent gene-consequence combinations",
            "Includes computed field for display purposes"
        ]
    ))
    tests[-1]["test_category"] = "Use Cases"
    
    # Test 48: Sample-level mutation burden by gene
    tests.append(create_test_request(
        name="use_case_sample_mutation_burden",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["sample_id", "gene"],
            "aggregation_type": "count",
            "order_by": ["sample_id", "aggregated_value"],
            "order_direction": "desc",
            "limit": 50,
            "computed_fields": [
                {
                    "name": "sample_gene",
                    "type": "concat",
                    "columns": ["sample_id", "gene"],
                    "separator": ": "
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "Shows mutation count per sample per gene",
            "Sorted by sample then count descending",
            "Useful for identifying which genes are mutated in each sample"
        ]
    ))
    tests[-1]["test_category"] = "Use Cases"
    
    # Test 49: Chromosomal distribution of mutations
    tests.append(create_test_request(
        name="use_case_chromosomal_distribution",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["chromosome", "gene"],
            "aggregation_type": "count",
            "order_by": ["chromosome", "aggregated_value"],
            "order_direction": "desc",
            "computed_fields": [
                {
                    "name": "chr_gene",
                    "type": "concat",
                    "columns": ["chromosome", "gene"],
                    "separator": " "
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "Shows mutation distribution across chromosomes and genes",
            "Sorted by chromosome then gene count",
            "Shows which genes are most mutated on each chromosome"
        ]
    ))
    tests[-1]["test_category"] = "Use Cases"
    
    # Test 50: Comprehensive analysis with all features
    tests.append(create_test_request(
        name="comprehensive_analysis",
        request_body={
            "aggregate_column": "variant_id",
            "combination_columns": ["chromosome", "gene", "variant_classification", "sample_id"],
            "percentage_by": ["chromosome", "gene"],
            "aggregation_type": "percentage",
            "filters": {
                "logic": "AND",
                "conditions": [
                    {"column": "tumor_vaf", "operator": "gt", "value": "0.1"},
                    {"column": "variant_classification", "operator": "neq", "value": "Silent"}
                ]
            },
            "having": {
                "logic": "AND",
                "conditions": [
                    {"column": "aggregated_value", "operator": "gt", "value": 1.0},
                    {"column": "aggregated_value", "operator": "lt", "value": 50.0}
                ]
            },
            "order_by": ["chromosome", "gene", "aggregated_value"],
            "order_direction": "desc",
            "limit": 100,
            "computed_fields": [
                {
                    "name": "chr_gene_var",
                    "type": "concat",
                    "columns": ["chromosome", "gene", "variant_classification"],
                    "separator": "|"
                },
                {
                    "name": "gene_sample",
                    "type": "concat",
                    "columns": ["gene", "sample_id"],
                    "separator": "@"
                }
            ]
        },
        expected_checks=[
            "Status code: 200",
            "Comprehensive analysis of non-silent mutations with VAF > 10%",
            "Shows percentage within each chromosome-gene combination",
            "Filters out percentages <1% and >50%",
            "Sorted by chromosome, gene, then percentage",
            "Limited to 100 results",
            "Includes two computed fields for different views",
            "Tests all major features together"
        ]
    ))
    tests[-1]["test_category"] = "Use Cases"
    
    return tests

def main():
    """Generate and display the test suite."""
    print("="*80)
    print("CONCATENATED AGGREGATE API MANUAL TEST SUITE (50 TESTS)")
    print("="*80)
    print(f"Table: {TABLE_NAME}")
    print(f"Base URL: {BASE_URL}")
    print("="*80)
    
    # Generate test suite
    tests = generate_test_suite()
    
    # Display all tests by category
    categories = {}
    for test in tests:
        category = test.get("test_category", "Uncategorized")
        if category not in categories:
            categories[category] = []
        categories[category].append(test)
    
    # Print summary by category
    print("\nTEST SUITE SUMMARY BY CATEGORY:")
    print("-"*40)
    for category, cat_tests in sorted(categories.items()):
        print(f"{category}: {len(cat_tests)} tests")
    
    print(f"\nTotal tests generated: {len(tests)}")
    
    # Ask user which tests to display
    print("\n" + "="*80)
    print("OPTIONS:")
    print("1. Display all tests (verbose)")
    print("2. Display tests by category")
    print("3. Display specific test")
    print("4. Generate test execution script")
    print("5. Save test suite summary")
    print("6. Exit")
    
    choice = input("\nEnter choice (1-6): ").strip()
    
    if choice == "1":
        for test in tests:
            print_test_case(test)
    elif choice == "2":
        print("\nAvailable categories:")
        for i, category in enumerate(sorted(categories.keys()), 1):
            print(f"{i}. {category} ({len(categories[category])} tests)")
        
        cat_choice = input("\nEnter category number or name: ").strip()
        
        try:
            # Try as number
            cat_idx = int(cat_choice) - 1
            category = list(sorted(categories.keys()))[cat_idx]
        except (ValueError, IndexError):
            # Try as name
            category = cat_choice
        
        if category in categories:
            print(f"\nDisplaying tests for category: {category}")
            for test in categories[category]:
                print_test_case(test)
        else:
            print(f"Category '{category}' not found.")
    
    elif choice == "3":
        test_name = input("Enter test name (or number 1-50): ").strip()
        try:
            # Try as number
            test_idx = int(test_name) - 1
            if 0 <= test_idx < len(tests):
                print_test_case(tests[test_idx])
            else:
                print(f"Test number {test_name} out of range.")
        except ValueError:
            # Try as name
            found = [t for t in tests if t["name"] == test_name]
            if found:
                print_test_case(found[0])
            else:
                print(f"Test '{test_name}' not found.")
    
    elif choice == "4":
        generate_execution_script(tests)
    
    elif choice == "5":
        save_test_suite_summary(tests, categories)
    
    print(f"\n{'='*80}")
    print("TEST FILES SAVED IN: test_results/concat_aggregate/")
    print("="*80)
    print("\nNEXT STEPS:")
    print("1. Start your FastAPI server")
    print("2. Run curl commands from test files")
    print("3. Save responses in the test files")
    print("4. Verify each expected check")
    print("5. Mark test as pass/fail")
    print("="*80)

def generate_execution_script(tests):
    """Generate a bash script to execute all tests."""
    script_content = """#!/bin/bash
# Concatenated Aggregate API Test Execution Script
# Generated: {timestamp}
# Total tests: {total_tests}

echo "Starting Concatenated Aggregate API Test Suite"
echo "=============================================="
echo ""

BASE_URL="{base_url}"
TABLE_NAME="{table_name}"

""".format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_tests=len(tests),
        base_url=BASE_URL,
        table_name=TABLE_NAME
    )
    
    # Add test execution for each test
    for i, test in enumerate(tests, 1):
        script_content += f"""
echo "Test {i}: {test['name']}"
echo "Category: {test.get('test_category', 'General')}"
echo "---"

# Create request file
cat > /tmp/concat_aggregate_request_{i}.json << 'EOF'
{json.dumps(test['request'], indent=2)}
EOF

# Execute request
curl -X POST "$BASE_URL/api/concatenated_aggregate/$TABLE_NAME" \\
  -H 'Content-Type: application/json' \\
  -d @/tmp/concat_aggregate_request_{i}.json \\
  -w "\\nStatus: %{http_code}\\nTime: %{time_total}s\\n" \\
  -o /tmp/concat_aggregate_response_{i}.json

echo "Response saved to: /tmp/concat_aggregate_response_{i}.json"
echo ""

# Sleep to avoid overwhelming the server
sleep 0.5

"""
    
    script_content += """
echo "Test suite completed!"
echo "====================="
"""
    
    script_path = "test_results/concat_aggregate/run_all_tests.sh"
    with open(script_path, "w") as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    print(f"Execution script generated: {script_path}")
    print("To run all tests: ./test_results/concat_aggregate/run_all_tests.sh")

def save_test_suite_summary(tests, categories):
    """Save a summary of the test suite."""
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(tests),
        "table_name": TABLE_NAME,
        "base_url": BASE_URL,
        "categories": {},
        "test_list": []
    }
    
    for category, cat_tests in categories.items():
        summary["categories"][category] = len(cat_tests)
    
    for test in tests:
        summary["test_list"].append({
            "name": test["name"],
            "category": test.get("test_category"),
            "file": f"concat_aggregate_test_{test['name']}_{test['timestamp']}.json"
        })
    
    summary_path = "test_results/concat_aggregate/test_suite_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"Test suite summary saved: {summary_path}")
    
    # Also create a Markdown summary
    md_content = f"""# Concatenated Aggregate API Test Suite Summary

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Tests:** {len(tests)}
**Table:** {TABLE_NAME}
**Base URL:** {BASE_URL}

## Test Categories

"""
    
    for category, count in sorted(summary["categories"].items()):
        md_content += f"- **{category}**: {count} tests\n"
    
    md_content += "\n## Test List\n\n"
    md_content += "| # | Test Name | Category | File |\n"
    md_content += "|---|-----------|----------|------|\n"
    
    for i, test in enumerate(summary["test_list"], 1):
        md_content += f"| {i} | {test['name']} | {test['category']} | {test['file']} |\n"
    
    md_path = "test_results/concat_aggregate/test_suite_summary.md"
    with open(md_path, "w") as f:
        f.write(md_content)
    
    print(f"Markdown summary saved: {md_path}")

if __name__ == "__main__":
    main()