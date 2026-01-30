import json
import os
from datetime import datetime
from typing import List, Dict, Any

# Test configuration
BASE_URL = "http://10.10.6.80/dbgenvoc/api/v2"
TABLE_NAME = "nibmg_exome_somatic_variants"  # Change to your table

# Common columns for testing (adjust based on your schema)
COLUMN_NAMES = {
    "numeric": ["tumor_depth", "tumor_vaf", "normal_depth", "cancer_cell_fraction"],
    "categorical": ["gene", "variant_class", "consequence", "chromosome"],
    "id_columns": ["variant_id", "sample_id", "patient_id"],
    "text": ["hgvsp_short", "hgvsc", "reference_allele", "alternate_allele"],
}


def create_test_request(
    name: str, request_body: Dict[str, Any], expected_checks: List[str]
) -> Dict[str, Any]:
    """Create a test case for manual execution."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"aggregate_test_{name}_{timestamp}.json"

    test_case = {
        "name": name,
        "timestamp": timestamp,
        "endpoint": f"/api/aggregate/{TABLE_NAME}",
        "request": request_body,
        "expected_checks": expected_checks,
        "actual_response": None,
        "pass": None,
        "notes": "",
        "test_category": None,  # Will be set later
    }

    # Save to file
    os.makedirs("aggregate", exist_ok=True)
    with open(f"aggregate/{filename}", "w") as f:
        json.dump(test_case, f, indent=2)

    return test_case


# --------------------------------------------------
# TEST SUITE GENERATION
# --------------------------------------------------


def generate_test_suite() -> List[Dict[str, Any]]:
    """Generate 50 test cases for Aggregate API."""
    tests = []

    # --------------------------------------------------
    # CATEGORY 1: BASIC SCALAR AGGREGATIONS (no group_by)
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 1: BASIC SCALAR AGGREGATIONS")
    print("=" * 60)

    # Test 1: Simple count
    tests.append(
        create_test_request(
            name="scalar_count_all",
            request_body={"column": "variant_id", "aggregation_type": "count"},
            expected_checks=[
                "Status code: 200",
                "result should be object with 'value' field",
                "value should be total count of variant_id (non-null)",
                "total_records should match value",
                "group_by should be null",
                "groups_after_having and groups_before_having should be null",
            ],
        )
    )
    tests[-1]["test_category"] = "Scalar Aggregations"

    # Test 2: Sum of numeric column
    tests.append(
        create_test_request(
            name="scalar_sum_numeric",
            request_body={"column": "tumor_depth", "aggregation_type": "sum"},
            expected_checks=[
                "Status code: 200",
                "result.value should be sum of tumor_depth (if numeric column exists)",
                "aggregation_type should be 'sum'",
                "Should handle null values correctly",
            ],
        )
    )
    tests[-1]["test_category"] = "Scalar Aggregations"

    # Test 3: Average of numeric column
    tests.append(
        create_test_request(
            name="scalar_average_numeric",
            request_body={"column": "tumor_vaf", "aggregation_type": "avg"},
            expected_checks=[
                "Status code: 200",
                "result.value should be average of tumor_vaf",
                "Should be decimal value (not integer)",
                "Should handle division by zero gracefully",
            ],
        )
    )
    tests[-1]["test_category"] = "Scalar Aggregations"

    # Test 4: Minimum value
    tests.append(
        create_test_request(
            name="scalar_min_value",
            request_body={"column": "tumor_depth", "aggregation_type": "min"},
            expected_checks=[
                "Status code: 200",
                "result.value should be minimum tumor_depth",
                "Should handle empty results (null handling)",
            ],
        )
    )
    tests[-1]["test_category"] = "Scalar Aggregations"

    # Test 5: Maximum value
    tests.append(
        create_test_request(
            name="scalar_max_value",
            request_body={"column": "tumor_depth", "aggregation_type": "max"},
            expected_checks=[
                "Status code: 200",
                "result.value should be maximum tumor_depth",
                "Should return null if no data",
            ],
        )
    )
    tests[-1]["test_category"] = "Scalar Aggregations"

    # Test 6: Distinct count
    tests.append(
        create_test_request(
            name="scalar_distinct_count",
            request_body={"column": "gene", "aggregation_type": "distinct_count"},
            expected_checks=[
                "Status code: 200",
                "result.value should be count of distinct genes",
                "Should be integer",
                "Should be <= total_records",
            ],
        )
    )
    tests[-1]["test_category"] = "Scalar Aggregations"

    # Test 7: Global percentage (scalar)
    tests.append(
        create_test_request(
            name="scalar_global_percentage",
            request_body={"column": "variant_id", "aggregation_type": "percentage"},
            expected_checks=[
                "Status code: 200",
                "result.value should be 100.0 (percentage of all records)",
                "Should be decimal between 0 and 100",
                "group_totals should have 'global' key with total_records",
            ],
        )
    )
    tests[-1]["test_category"] = "Scalar Aggregations"

    # --------------------------------------------------
    # CATEGORY 2: BASIC GROUPED AGGREGATIONS
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 2: BASIC GROUPED AGGREGATIONS")
    print("=" * 60)

    # Test 8: Group by single column with count
    tests.append(
        create_test_request(
            name="group_by_gene_count",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
            },
            expected_checks=[
                "Status code: 200",
                "result should be array of objects",
                "Each object should have 'gene' and 'aggregated_value'",
                "aggregated_value should be count per gene",
                "groups_before_having should equal groups_after_having (no having clause)",
                "total_results should match number of unique genes",
            ],
        )
    )
    tests[-1]["test_category"] = "Grouped Aggregations"

    # Test 9: Group by multiple columns
    tests.append(
        create_test_request(
            name="group_by_multiple_columns",
            request_body={
                "column": "variant_id",
                "group_by": ["gene", "variant_class"],
                "aggregation_type": "count",
            },
            expected_checks=[
                "Status code: 200",
                "Each result should have gene, variant_class, aggregated_value",
                "Should show count for each gene-variant_class combination",
                "Number of groups should be unique combinations",
            ],
        )
    )
    tests[-1]["test_category"] = "Grouped Aggregations"

    # Test 10: Group by with sum
    tests.append(
        create_test_request(
            name="group_by_sum",
            request_body={
                "column": "tumor_depth",
                "group_by": ["gene"],
                "aggregation_type": "sum",
            },
            expected_checks=[
                "Status code: 200",
                "aggregated_value should be sum of tumor_depth per gene",
                "Should be numeric (could be decimal)",
                "Genes with null tumor_depth should have sum of 0 or null",
            ],
        )
    )
    tests[-1]["test_category"] = "Grouped Aggregations"

    # Test 11: Group by with average
    tests.append(
        create_test_request(
            name="group_by_average",
            request_body={
                "column": "tumor_vaf",
                "group_by": ["gene"],
                "aggregation_type": "avg",
            },
            expected_checks=[
                "Status code: 200",
                "aggregated_value should be average tumor_vaf per gene",
                "Should handle null values (exclude from average)",
                "Genes with no tumor_vaf should have null average",
            ],
        )
    )
    tests[-1]["test_category"] = "Grouped Aggregations"

    # Test 12: Group by with distinct count
    tests.append(
        create_test_request(
            name="group_by_distinct_count",
            request_body={
                "column": "sample_id",
                "group_by": ["gene"],
                "aggregation_type": "distinct_count",
            },
            expected_checks=[
                "Status code: 200",
                "aggregated_value should be distinct sample count per gene",
                "Should be integer",
                "Should show how many samples have each gene mutated",
            ],
        )
    )
    tests[-1]["test_category"] = "Grouped Aggregations"

    # --------------------------------------------------
    # CATEGORY 3: PERCENTAGE CALCULATIONS
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 3: PERCENTAGE CALCULATIONS")
    print("=" * 60)

    # Test 13: Global percentage with group_by
    tests.append(
        create_test_request(
            name="grouped_global_percentage",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "percentage",
            },
            expected_checks=[
                "Status code: 200",
                "aggregated_value should be percentage of total mutations per gene",
                "Sum of all percentages should be approximately 100 (within rounding)",
                "group_totals should have 'global' key with total_records",
                "percentages should be rounded to 2 decimal places",
            ],
        )
    )
    tests[-1]["test_category"] = "Percentage Calculations"

    # Test 14: Partitioned percentage (percentage_by subset of group_by)
    tests.append(
        create_test_request(
            name="partitioned_percentage",
            request_body={
                "column": "variant_id",
                "group_by": ["gene", "variant_class"],
                "percentage_by": ["gene"],
                "aggregation_type": "percentage",
            },
            expected_checks=[
                "Status code: 200",
                "percentage_by columns must be in group_by (gene)",
                "For each gene, sum of percentages across variant_classs should be ~100",
                "group_totals should have entries for each gene",
                "Should show percentage within each gene group",
            ],
        )
    )
    tests[-1]["test_category"] = "Percentage Calculations"

    # Test 15: Multiple columns for percentage_by
    tests.append(
        create_test_request(
            name="multi_column_percentage_by",
            request_body={
                "column": "variant_id",
                "group_by": ["chromosome", "gene", "variant_class"],
                "percentage_by": ["chromosome", "gene"],
                "aggregation_type": "percentage",
            },
            expected_checks=[
                "Status code: 200",
                "percentage_by includes chromosome and gene (both in group_by)",
                "Percentages should sum to ~100 for each chromosome+gene combination",
                "group_totals should have compound keys (e.g., '17|TP53')",
            ],
        )
    )
    tests[-1]["test_category"] = "Percentage Calculations"

    # --------------------------------------------------
    # CATEGORY 4: FILTERS
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 4: FILTERS")
    print("=" * 60)

    # Test 16: Simple filter on group_by column
    tests.append(
        create_test_request(
            name="filter_on_group_column",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "filters": {
                    "logic": "AND",
                    "conditions": [
                        {"column": "gene", "operator": "eq", "value": "TP53"}
                    ],
                },
            },
            expected_checks=[
                "Status code: 200",
                "Should return only TP53 in results",
                "Number of groups should be 1",
                "total_records should be count of TP53 mutations",
            ],
        )
    )
    tests[-1]["test_category"] = "Filters"

    # Test 17: Filter on non-group column
    tests.append(
        create_test_request(
            name="filter_on_non_group_column",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "filters": {
                    "logic": "AND",
                    "conditions": [
                        {
                            "column": "variant_class",
                            "operator": "eq",
                            "value": "Missense_Mutation",
                        }
                    ],
                },
            },
            expected_checks=[
                "Status code: 200",
                "Should only count missense mutations",
                "Each gene count should be <= total missense mutations for that gene",
                "Filters should be applied before grouping",
            ],
        )
    )
    tests[-1]["test_category"] = "Filters"

    # Test 18: Complex filter with OR logic
    tests.append(
        create_test_request(
            name="complex_or_filter",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "filters": {
                    "logic": "OR",
                    "conditions": [
                        {"column": "gene", "operator": "eq", "value": "TP53"},
                        {"column": "gene", "operator": "eq", "value": "KRAS"},
                    ],
                },
            },
            expected_checks=[
                "Status code: 200",
                "Should return only TP53 and KRAS",
                "Number of groups should be 2",
                "Should handle OR logic correctly",
            ],
        )
    )
    tests[-1]["test_category"] = "Filters"

    # Test 19: Multiple condition filter
    tests.append(
        create_test_request(
            name="multi_condition_filter",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "filters": {
                    "logic": "AND",
                    "conditions": [
                        {"column": "gene", "operator": "eq", "value": "TP53"},
                        {
                            "column": "variant_class",
                            "operator": "eq",
                            "value": "Missense_Mutation",
                        },
                        {"column": "tumor_vaf", "operator": "gt", "value": "0.1"},
                    ],
                },
            },
            expected_checks=[
                "Status code: 200",
                "Should count TP53 missense mutations with tumor_vaf > 0.1",
                "All conditions must be satisfied",
                "Should handle numeric comparison correctly",
            ],
        )
    )
    tests[-1]["test_category"] = "Filters"

    # Test 20: Genomic position filter
    tests.append(
        create_test_request(
            name="genomic_filter_single_position",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "genomic_filter": {"positions": ["chr17:7578407"]},
            },
            expected_checks=[
                "Status code: 200",
                "Should only count variants at chr17:7578407",
                "TP53 should be in results (if position is TP53)",
                "genomic_filter should work with group_by",
            ],
        )
    )
    tests[-1]["test_category"] = "Filters"

    # Test 21: Genomic range filter
    tests.append(
        create_test_request(
            name="genomic_filter_range",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "genomic_filter": {"ranges": ["chr17:7570000-7580000"]},
            },
            expected_checks=[
                "Status code: 200",
                "Should count variants in chr17:7570000-7580000 range",
                "Should include multiple genes in that region",
                "Range filter should be inclusive",
            ],
        )
    )
    tests[-1]["test_category"] = "Filters"

    # Test 22: Combined filters and genomic filter
    tests.append(
        create_test_request(
            name="combined_filters_genomic",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "filters": {
                    "logic": "AND",
                    "conditions": [
                        {
                            "column": "variant_class",
                            "operator": "eq",
                            "value": "Missense_Mutation",
                        }
                    ],
                },
                "genomic_filter": {"ranges": ["chr17:7570000-7580000"]},
            },
            expected_checks=[
                "Status code: 200",
                "Should count missense mutations in chr17:7570000-7580000",
                "Both filters should be applied (AND between them)",
                "Should be subset of each individual filter result",
            ],
        )
    )
    tests[-1]["test_category"] = "Filters"

    # --------------------------------------------------
    # CATEGORY 5: HAVING CLAUSE
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 5: HAVING CLAUSE")
    print("=" * 60)

    # Test 23: Simple having clause (greater than)
    tests.append(
        create_test_request(
            name="having_greater_than",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "having": {"column": "aggregated_value", "operator": "gt", "value": 10},
            },
            expected_checks=[
                "Status code: 200",
                "Should only include genes with count > 10",
                "groups_after_having should be <= groups_before_having",
                "All aggregated_values should be > 10",
                "having is applied after grouping",
            ],
        )
    )
    tests[-1]["test_category"] = "Having Clause"

    # Test 24: Having clause with equals
    tests.append(
        create_test_request(
            name="having_equals",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "having": {"column": "aggregated_value", "operator": "eq", "value": 1},
            },
            expected_checks=[
                "Status code: 200",
                "Should include genes with exactly 1 mutation",
                "All counts should equal 1",
                "Should filter out genes with 0 or >1 mutations",
            ],
        )
    )
    tests[-1]["test_category"] = "Having Clause"

    # Test 25: Having clause on percentage
    tests.append(
        create_test_request(
            name="having_on_percentage",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "percentage",
                "having": {
                    "column": "aggregated_value",
                    "operator": "gt",
                    "value": 1.0,
                },
            },
            expected_checks=[
                "Status code: 200",
                "Should include genes with >1% of total mutations",
                "aggregated_value should be percentages > 1.0",
                "Should filter based on aggregated (percentage) value",
            ],
        )
    )
    tests[-1]["test_category"] = "Having Clause"

    # Test 26: Complex having clause with AND
    tests.append(
        create_test_request(
            name="having_complex_and",
            request_body={
                "column": "variant_id",
                "group_by": ["gene", "variant_class"],
                "aggregation_type": "count",
                "having": {
                    "logic": "AND",
                    "conditions": [
                        {"column": "aggregated_value", "operator": "gt", "value": 5},
                        {"column": "aggregated_value", "operator": "lt", "value": 100},
                    ],
                },
            },
            expected_checks=[
                "Status code: 200",
                "Should include groups with count between 5 and 100",
                "All counts should be >5 AND <100",
                "Should handle multiple having conditions",
            ],
        )
    )
    tests[-1]["test_category"] = "Having Clause"

    # --------------------------------------------------
    # CATEGORY 6: ORDERING
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 6: ORDERING")
    print("=" * 60)

    # Test 27: Order by aggregated_value ascending
    tests.append(
        create_test_request(
            name="order_by_aggregated_value_asc",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "order_by": "aggregated_value",
                "order_direction": "asc",
            },
            expected_checks=[
                "Status code: 200",
                "Results should be sorted by count ascending",
                "First result should have smallest count",
                "Last result should have largest count",
                "order_direction should be 'asc' in response",
            ],
        )
    )
    tests[-1]["test_category"] = "Ordering"

    # Test 28: Order by aggregated_value descending
    tests.append(
        create_test_request(
            name="order_by_aggregated_value_desc",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "order_by": "aggregated_value",
                "order_direction": "desc",
            },
            expected_checks=[
                "Status code: 200",
                "Results should be sorted by count descending",
                "First result should have largest count",
                "Last result should have smallest count",
            ],
        )
    )
    tests[-1]["test_category"] = "Ordering"

    # Test 29: Order by group column
    tests.append(
        create_test_request(
            name="order_by_group_column",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "order_by": "gene",
                "order_direction": "asc",
            },
            expected_checks=[
                "Status code: 200",
                "Results should be sorted alphabetically by gene",
                "Gene names should be in A-Z order",
                "Counts will not be in order",
            ],
        )
    )
    tests[-1]["test_category"] = "Ordering"

    # Test 30: Order by multiple columns
    tests.append(
        create_test_request(
            name="order_by_multiple_columns",
            request_body={
                "column": "variant_id",
                "group_by": ["gene", "variant_class"],
                "aggregation_type": "count",
                "order_by": ["gene", "aggregated_value"],
                "order_direction": "asc",
            },
            expected_checks=[
                "Status code: 200",
                "Results should be sorted by gene (primary), then count (secondary)",
                "Within each gene, counts should be ascending",
                "Should handle array order_by parameter",
            ],
        )
    )
    tests[-1]["test_category"] = "Ordering"

    # --------------------------------------------------
    # CATEGORY 7: LIMIT
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 7: LIMIT")
    print("=" * 60)

    # Test 31: Limit results
    tests.append(
        create_test_request(
            name="limit_results",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "order_by": "aggregated_value",
                "order_direction": "desc",
                "limit": 5,
            },
            expected_checks=[
                "Status code: 200",
                "Should return exactly 5 results (or fewer if less data)",
                "Results should be top 5 genes by mutation count",
                "limit should be 5 in response",
                "Should still calculate groups_before_having correctly",
            ],
        )
    )
    tests[-1]["test_category"] = "Limit"

    # Test 32: Limit with having clause
    tests.append(
        create_test_request(
            name="limit_with_having",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "having": {"column": "aggregated_value", "operator": "gt", "value": 5},
                "order_by": "aggregated_value",
                "order_direction": "desc",
                "limit": 3,
            },
            expected_checks=[
                "Status code: 200",
                "Should return at most 3 results",
                "All results should have count > 5",
                "Limit should be applied after having clause",
            ],
        )
    )
    tests[-1]["test_category"] = "Limit"

    # Test 33: Small limit (1)
    tests.append(
        create_test_request(
            name="limit_one",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "order_by": "aggregated_value",
                "order_direction": "desc",
                "limit": 1,
            },
            expected_checks=[
                "Status code: 200",
                "Should return exactly 1 result",
                "Should be the gene with highest mutation count",
                "limit should be 1 in response",
            ],
        )
    )
    tests[-1]["test_category"] = "Limit"

    # --------------------------------------------------
    # CATEGORY 8: COMPLEX COMBINATIONS
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 8: COMPLEX COMBINATIONS")
    print("=" * 60)

    # Test 34: All parameters combined
    tests.append(
        create_test_request(
            name="all_parameters_combined",
            request_body={
                "column": "variant_id",
                "group_by": ["gene", "variant_class"],
                "percentage_by": ["gene"],
                "aggregation_type": "percentage",
                "filters": {
                    "logic": "AND",
                    "conditions": [
                        {"column": "tumor_vaf", "operator": "gt", "value": "0.05"}
                    ],
                },
                "genomic_filter": {"ranges": ["chr17:7570000-7580000"]},
                "having": {
                    "column": "aggregated_value",
                    "operator": "gt",
                    "value": 10.0,
                },
                "order_by": ["gene", "aggregated_value"],
                "order_direction": "desc",
                "limit": 10,
            },
            expected_checks=[
                "Status code: 200",
                "Should apply all filters (tumor_vaf > 0.05 AND genomic range)",
                "Should calculate percentages within each gene",
                "Should filter percentages > 10%",
                "Should sort by gene then percentage descending",
                "Should limit to 10 results",
                "All parameters should work together correctly",
            ],
        )
    )
    tests[-1]["test_category"] = "Complex Combinations"

    # Test 35: Complex aggregation with sum and filters
    tests.append(
        create_test_request(
            name="complex_sum_aggregation",
            request_body={
                "column": "tumor_depth",
                "group_by": ["gene", "sample_id"],
                "aggregation_type": "sum",
                "filters": {
                    "logic": "OR",
                    "conditions": [
                        {"column": "gene", "operator": "eq", "value": "TP53"},
                        {"column": "gene", "operator": "eq", "value": "KRAS"},
                    ],
                },
                "having": {
                    "column": "aggregated_value",
                    "operator": "gt",
                    "value": 100,
                },
                "order_by": "aggregated_value",
                "order_direction": "desc",
            },
            expected_checks=[
                "Status code: 200",
                "Should sum tumor_depth per gene per sample",
                "Should only include TP53 or KRAS",
                "Should filter sums > 100",
                "Should sort by sum descending",
                "Should handle numeric aggregation with grouping",
            ],
        )
    )
    tests[-1]["test_category"] = "Complex Combinations"

    # --------------------------------------------------
    # CATEGORY 9: EDGE CASES AND ERROR CONDITIONS
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 9: EDGE CASES AND ERROR CONDITIONS")
    print("=" * 60)

    # Test 36: Invalid column name
    tests.append(
        create_test_request(
            name="error_invalid_column",
            request_body={"column": "nonexistent_column", "aggregation_type": "count"},
            expected_checks=[
                "Status code: 400 or 500",
                "Should return error about invalid column",
                "Should not crash server",
            ],
        )
    )
    tests[-1]["test_category"] = "Error Conditions"

    # Test 37: Invalid aggregation type
    tests.append(
        create_test_request(
            name="error_invalid_aggregation_type",
            request_body={"column": "variant_id", "aggregation_type": "invalid_type"},
            expected_checks=[
                "Status code: 422 (validation error)",
                "Should reject invalid aggregation_type",
                "Should provide meaningful error message",
            ],
        )
    )
    tests[-1]["test_category"] = "Error Conditions"

    # Test 38: Having without group_by (should fail)
    tests.append(
        create_test_request(
            name="error_having_without_group",
            request_body={
                "column": "variant_id",
                "aggregation_type": "count",
                "having": {"column": "aggregated_value", "operator": "gt", "value": 10},
            },
            expected_checks=[
                "Status code: 400 or 422",
                "Should reject having clause without group_by",
                "Should explain that having requires group_by",
            ],
        )
    )
    tests[-1]["test_category"] = "Error Conditions"

    # Test 39: percentage_by not subset of group_by
    tests.append(
        create_test_request(
            name="error_percentage_by_not_subset",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "percentage_by": ["variant_class"],
                "aggregation_type": "percentage",
            },
            expected_checks=[
                "Status code: 400 or 422",
                "Should reject because variant_class not in group_by",
                "Should explain percentage_by must be subset of group_by",
            ],
        )
    )
    tests[-1]["test_category"] = "Error Conditions"

    # Test 40: Invalid filter column
    tests.append(
        create_test_request(
            name="error_invalid_filter_column",
            request_body={
                "column": "variant_id",
                "aggregation_type": "count",
                "filters": {
                    "logic": "AND",
                    "conditions": [
                        {
                            "column": "nonexistent_column",
                            "operator": "eq",
                            "value": "test",
                        }
                    ],
                },
            },
            expected_checks=[
                "Status code: 400 or 500",
                "Should handle invalid filter column gracefully",
                "Should return appropriate error",
            ],
        )
    )
    tests[-1]["test_category"] = "Error Conditions"

    # Test 41: Zero limit (invalid)
    tests.append(
        create_test_request(
            name="error_zero_limit",
            request_body={
                "column": "variant_id",
                "aggregation_type": "count",
                "limit": 0,
            },
            expected_checks=[
                "Status code: 422",
                "Should reject limit <= 0",
                "Should require limit >= 1",
            ],
        )
    )
    tests[-1]["test_category"] = "Error Conditions"

    # Test 42: Negative page size (if pagination exists)
    tests.append(
        create_test_request(
            name="error_negative_page_size",
            request_body={
                "column": "variant_id",
                "aggregation_type": "count",
                "page": 1,
                "page_size": -1,
            },
            expected_checks=[
                "Status code: 422",
                "Should reject negative page_size",
                "Should validate numeric constraints",
            ],
        )
    )
    tests[-1]["test_category"] = "Error Conditions"

    # Test 43: Empty group_by array
    tests.append(
        create_test_request(
            name="empty_group_by_array",
            request_body={
                "column": "variant_id",
                "group_by": [],
                "aggregation_type": "count",
            },
            expected_checks=[
                "Status code: 200 or 422",
                "Either should treat as scalar aggregation or reject empty array",
                "Behavior should be consistent",
            ],
        )
    )
    tests[-1]["test_category"] = "Error Conditions"

    # Test 44: Null values in aggregation column
    tests.append(
        create_test_request(
            name="null_values_in_column",
            request_body={
                "column": "tumor_vaf",  # May have nulls
                "group_by": ["gene"],
                "aggregation_type": "avg",
            },
            expected_checks=[
                "Status code: 200",
                "Should handle null values gracefully",
                "Should exclude nulls from average calculation",
                "Genes with all null tumor_vaf should have null average",
            ],
        )
    )
    tests[-1]["test_category"] = "Edge Cases"

    # Test 45: Empty result set from filters
    tests.append(
        create_test_request(
            name="empty_result_from_filter",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "filters": {
                    "logic": "AND",
                    "conditions": [
                        {"column": "gene", "operator": "eq", "value": "NONEXISTENTGENE"}
                    ],
                },
            },
            expected_checks=[
                "Status code: 200",
                "Should return empty result array",
                "total_records should be 0",
                "groups_before_having and groups_after_having should be 0",
                "Should not error on empty result",
            ],
        )
    )
    tests[-1]["test_category"] = "Edge Cases"

    # --------------------------------------------------
    # CATEGORY 10: PERFORMANCE AND SCALABILITY
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 10: PERFORMANCE AND SCALABILITY")
    print("=" * 60)

    # Test 46: Large group_by (many groups)
    tests.append(
        create_test_request(
            name="performance_many_groups",
            request_body={
                "column": "variant_id",
                "group_by": ["gene", "sample_id"],
                "aggregation_type": "count",
            },
            expected_checks=[
                "Status code: 200",
                "Response time should be reasonable (< 5 seconds)",
                "Should handle potentially thousands of groups",
                "groups_before_having should be large number",
                "Should not timeout or crash",
            ],
        )
    )
    tests[-1]["test_category"] = "Performance"

    # Test 47: Complex aggregation on large dataset
    tests.append(
        create_test_request(
            name="performance_complex_aggregation",
            request_body={
                "column": "tumor_depth",
                "group_by": ["gene"],
                "aggregation_type": "avg",
                "filters": {
                    "logic": "OR",
                    "conditions": [
                        {
                            "column": "gene",
                            "operator": "in",
                            "value": ["TP53", "KRAS", "EGFR", "PIK3CA", "BRAF"],
                        }
                    ],
                },
                "having": {"column": "aggregated_value", "operator": "gt", "value": 50},
                "order_by": "aggregated_value",
                "order_direction": "desc",
            },
            expected_checks=[
                "Status code: 200",
                "Should complete within reasonable time",
                "Should handle IN operator efficiently",
                "Should apply having clause correctly",
                "Should return sorted results",
            ],
        )
    )
    tests[-1]["test_category"] = "Performance"

    # Test 48: Window function performance (percentage with partition)
    tests.append(
        create_test_request(
            name="performance_window_function",
            request_body={
                "column": "variant_id",
                "group_by": ["gene", "variant_class"],
                "percentage_by": ["gene"],
                "aggregation_type": "percentage",
                "limit": 100,
            },
            expected_checks=[
                "Status code: 200",
                "Window function (OVER partition) should perform well",
                "Should calculate percentages correctly",
                "Should respect limit",
                "Response time should be acceptable",
            ],
        )
    )
    tests[-1]["test_category"] = "Performance"

    # --------------------------------------------------
    # CATEGORY 11: DATA INTEGRITY AND CONSISTENCY
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("CATEGORY 11: DATA INTEGRITY AND CONSISTENCY")
    print("=" * 60)

    # Test 49: Verify groups_before_having vs groups_after_having
    tests.append(
        create_test_request(
            name="consistency_groups_counts",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "having": {"column": "aggregated_value", "operator": "gt", "value": 5},
            },
            expected_checks=[
                "Status code: 200",
                "groups_after_having should be <= groups_before_having",
                "Difference should equal number of groups filtered by having",
                "Both counts should be consistent with actual groups",
            ],
        )
    )
    tests[-1]["test_category"] = "Data Integrity"

    # Test 50: Cross-verify with simple SQL query
    tests.append(
        create_test_request(
            name="cross_verification_simple",
            request_body={
                "column": "variant_id",
                "group_by": ["gene"],
                "aggregation_type": "count",
                "filters": {
                    "logic": "AND",
                    "conditions": [
                        {"column": "gene", "operator": "eq", "value": "TP53"}
                    ],
                },
            },
            expected_checks=[
                "Status code: 200",
                "Result should match: SELECT gene, COUNT(*) FROM table WHERE gene='TP53' GROUP BY gene",
                "total_records should match count of TP53 variants",
                "Should be verifiable with direct database query",
            ],
        )
    )
    tests[-1]["test_category"] = "Data Integrity"

    return tests


def main():
    """Generate and display the test suite."""
    print("=" * 80)
    print("AGGREGATE API MANUAL TEST SUITE (50 TESTS)")
    print("=" * 80)
    print(f"Table: {TABLE_NAME}")
    print(f"Base URL: {BASE_URL}")
    print("=" * 80)

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
    print("-" * 40)
    for category, cat_tests in categories.items():
        print(f"{category}: {len(cat_tests)} tests")

    print(f"\nTotal tests generated: {len(tests)}")

    # Ask user which tests to display
    print("\n" + "=" * 80)
    print("OPTIONS:")
    print("1. Display all tests (verbose)")
    print("2. Display tests by category")
    print("3. Display specific test")
    print("4. Generate test execution script")
    print("5. Exit")

    choice = input("\nEnter choice (1-5): ").strip()

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

    print(f"\n{'=' * 80}")
    print("TEST FILES SAVED IN: test_results/aggregate/")
    print("=" * 80)
    print("\nNEXT STEPS:")
    print("1. Start your FastAPI server")
    print("2. Run curl commands from test files")
    print("3. Save responses in the test files")
    print("4. Verify each expected check")
    print("5. Mark test as pass/fail")
    print("=" * 80)


def generate_execution_script(tests):
    """Generate a bash script to execute all tests."""
    script_content = """#!/bin/bash
# Aggregate API Test Execution Script
# Generated: {timestamp}
# Total tests: {total_tests}

echo "Starting Aggregate API Test Suite"
echo "================================="
echo ""

BASE_URL="{base_url}"
TABLE_NAME="{table_name}"

""".format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_tests=len(tests),
        base_url=BASE_URL,
        table_name=TABLE_NAME,
    )

    # Add test execution for each test
    for i, test in enumerate(tests, 1):
        script_content += f"""
echo "Test {i}: {test["name"]}"
echo "Category: {test.get("test_category", "General")}"
echo "---"

# Create request file
cat > /tmp/aggregate_request_{i}.json << 'EOF'
{json.dumps(test["request"], indent=2)}
EOF

# Execute request
curl -X POST "$BASE_URL/api/aggregate/$TABLE_NAME" \\
  -H 'Content-Type: application/json' \\
  -d @/tmp/aggregate_request_{i}.json \\
  -w "\\nStatus: %{http_code}\\nTime: %{time_total}s\\n" \\
  -o /tmp/aggregate_response_{i}.json

echo "Response saved to: /tmp/aggregate_response_{i}.json"
echo ""

# Sleep to avoid overwhelming the server
sleep 0.5

"""

    script_content += """
echo "Test suite completed!"
echo "====================="
"""

    script_path = "test_results/aggregate/run_all_tests.sh"
    with open(script_path, "w") as f:
        f.write(script_content)

    os.chmod(script_path, 0o755)
    print(f"Execution script generated: {script_path}")
    print("To run all tests: ./test_results/aggregate/run_all_tests.sh")


if __name__ == "__main__":
    main()
