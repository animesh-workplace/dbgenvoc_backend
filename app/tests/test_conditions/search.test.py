import os
import json
import requests
from datetime import datetime

# Test configuration
BASE_URL = "http://10.10.6.80/dbgenvoc/api/v2"
TABLE_NAME = "nibmg_exome_somatic_variants"  # Change to your table


def create_test_request(
    name, request_body, expected_checks, actual_response=None, test_pass=True
):
    """Create a test case for manual execution."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_{name}_{timestamp}.json"

    test_case = {
        "url": f"{BASE_URL}/nibmg_exome_somatic_variants/search",
        "name": name,
        "timestamp": timestamp,
        "request": request_body,
        "expected_checks": expected_checks,
        "actual_response": actual_response,
        "pass": test_pass,
        "notes": "",
    }

    try:
        response = requests.post(
            f"{BASE_URL}/{TABLE_NAME}/search",
            json=request_body,
            headers={"Content-Type": "application/json"},
        )

        actual_response = {
            "status_code": response.status_code,
            "response_body": response.json()
            if response.status_code == 200
            else {"error": response.text},
            "headers": dict(response.headers),
            "elapsed_ms": response.elapsed.total_seconds() * 1000,
        }

    except Exception as e:
        actual_response = {"error": str(e), "status_code": None}

    test_case["actual_response"] = actual_response

    # Save to file
    with open(f"search/{filename}", "w") as f:
        json.dump(test_case, f, indent=2)

    return test_case


# --------------------------------------------------
# TEST SUITE
# --------------------------------------------------

os.makedirs("search", exist_ok=True)

print("=" * 60)
print("SEARCH API MANUAL TEST SUITE")
print("=" * 60)
print(f"Table: {TABLE_NAME}")
print(f"Base URL: {BASE_URL}")
print("=" * 60)

# --------------------------------------------------
# 1. BASIC FUNCTIONALITY TESTS
# --------------------------------------------------
tests = []

# Test 1: Basic search (no filters)
tests.append(
    create_test_request(
        name="basic_search",
        request_body={"page": 1, "page_size": 5},
        expected_checks=[
            "Status code should be 200",
            "Should have 'results' array",
            "Results length should be <= 5",
            "Should have 'total_results' field",
            "Should have 'table_name' field",
            "Page should be 1",
            "Page_size should be 5",
        ],
    )
)

# Test 2: With pagination
tests.append(
    create_test_request(
        name="pagination_test",
        request_body={"page": 2, "page_size": 3},
        expected_checks=[
            "Status code should be 200",
            "Results length should be <= 3",
            "Page should be 2",
            "Page_size should be 3",
        ],
    )
)

# --------------------------------------------------
# 2. TEXT SEARCH TESTS
# --------------------------------------------------

# Test 3: Basic text search
tests.append(
    create_test_request(
        name="text_search_basic",
        request_body={"term": "TP53", "page": 1, "page_size": 10},
        expected_checks=[
            "Status code should be 200",
            "Search results should contain 'TP53' in some columns",
            "Total_results should be > 0 (if TP53 exists)",
            "search_term in response should be 'TP53'",
        ],
    )
)

# Test 4: Text search with specific columns
tests.append(
    create_test_request(
        name="text_search_specific_columns",
        request_body={
            "term": "missense",
            "search_columns": ["variant_class"],
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "All results should have 'missense' in variant_class column",
            "search_term should be 'missense'",
            "search_columns should be applied correctly",
        ],
    )
)

# Test 5: Text search with multiple columns
tests.append(
    create_test_request(
        name="text_search_multiple_columns",
        request_body={
            "term": "17",
            "search_columns": ["chrom", "start"],
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "Results should contain '17' in chromosome or start_position",
            "total_results should be > 0 (if chromosome 17 exists)",
        ],
    )
)

# Test 6: Empty term (should return all results)
tests.append(
    create_test_request(
        name="empty_term",
        request_body={"term": "", "page": 1, "page_size": 5},
        expected_checks=[
            "Status code should be 200",
            "search_term should be null (not empty string)",
            "Should return results (same as no term)",
        ],
    )
)

# Test 7: Whitespace term
tests.append(
    create_test_request(
        name="whitespace_term",
        request_body={"term": "   ", "page": 1, "page_size": 5},
        expected_checks=[
            "Status code should be 200",
            "search_term should be null",
            "Should return all results",
        ],
    )
)

# --------------------------------------------------
# 3. FILTER TESTS
# --------------------------------------------------

# Test 8: With simple filter
tests.append(
    create_test_request(
        name="simple_filter",
        request_body={
            "filters": {
                "logic": "AND",
                "conditions": [{"column": "gene", "operator": "eq", "value": "TP53"}],
            },
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "All results should have gene = 'TP53'",
            "Should return fewer results than unfiltered search",
        ],
    )
)

# Test 9: Complex filter (AND/OR)
tests.append(
    create_test_request(
        name="complex_filter",
        request_body={
            "filters": {
                "logic": "OR",
                "conditions": [
                    {"column": "gene", "operator": "eq", "value": "TP53"},
                    {"column": "gene", "operator": "eq", "value": "KRAS"},
                ],
            },
            "page": 1,
            "page_size": 10,
        },
        expected_checks=[
            "Status code should be 200",
            "All results should have gene = 'TP53' OR gene = 'KRAS'",
            "Results count should be sum of TP53 and KRAS mutations",
        ],
    )
)

# Test 10: Multiple condition filter
tests.append(
    create_test_request(
        name="multi_condition_filter",
        request_body={
            "filters": {
                "logic": "AND",
                "conditions": [
                    {"column": "gene", "operator": "eq", "value": "TP53"},
                    {
                        "column": "variant_class",
                        "operator": "eq",
                        "value": "Missense_Mutation",
                    },
                ],
            },
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "All results should have gene = 'TP53'",
            "All results should have variant_classification = 'Missense_Mutation'",
        ],
    )
)

# --------------------------------------------------
# 4. GENOMIC FILTER TESTS
# --------------------------------------------------

# Test 11: Genomic position filter (single position)
tests.append(
    create_test_request(
        name="genomic_single_position",
        request_body={
            "genomic_filter": {
                "positions": [{"chromosome": "chr17", "start": 7577058}]
            },
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "Results should be from chromosome 17, position 7577058",
            "TP53 gene should be in results (if position is TP53)",
        ],
    )
)

# Test 12: Genomic range filter
tests.append(
    create_test_request(
        name="genomic_range",
        request_body={
            "genomic_filter": {
                "positions": [{"chromosome": "chr17", "start": 7570000, "end": 7580000}]
            },
            "page": 1,
            "page_size": 10,
        },
        expected_checks=[
            "Status code should be 200",
            "All results should be within chr17:7570000-7580000",
            "Should include multiple variants in TP53 region",
        ],
    )
)

# Test 13: Multiple genomic positions
tests.append(
    create_test_request(
        name="genomic_multiple_positions",
        request_body={
            "genomic_filter": {
                "positions": [
                    {"chromosome": "chr17", "start": 7577058},
                    {"chromosome": "chr12", "start": 53292675},
                ]
            },
            "page": 1,
            "page_size": 10,
        },
        expected_checks=[
            "Status code should be 200",
            "Results should be from either position",
            "Should include TP53 and KRT8 variants",
        ],
    )
)

# --------------------------------------------------
# 5. SORTING TESTS
# --------------------------------------------------

# Test 14: Sort ascending
tests.append(
    create_test_request(
        name="sort_ascending",
        request_body={
            "sort_by": "start",
            "sort_order": "asc",
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "Results should be sorted by start_position ascending",
            "First result should have smallest start_position",
        ],
    )
)

# Test 15: Sort descending
tests.append(
    create_test_request(
        name="sort_descending",
        request_body={
            "sort_by": "start",
            "sort_order": "desc",
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "Results should be sorted by start_position descending",
            "First result should have largest start_position",
        ],
    )
)

# Test 16: Sort by gene
tests.append(
    create_test_request(
        name="sort_by_gene",
        request_body={
            "sort_by": "gene",
            "sort_order": "asc",
            "page": 1,
            "page_size": 10,
        },
        expected_checks=[
            "Status code should be 200",
            "Results should be sorted alphabetically by gene",
            "Genes should be in alphabetical order (A-Z)",
        ],
    )
)

# --------------------------------------------------
# 6. COMBINATION TESTS
# --------------------------------------------------

# Test 17: Text search + filter
tests.append(
    create_test_request(
        name="text_and_filter",
        request_body={
            "term": "missense",
            "filters": {
                "logic": "AND",
                "conditions": [{"column": "gene", "operator": "eq", "value": "TP53"}],
            },
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "All results should have gene = 'TP53'",
            "All results should contain 'missense' in searchable columns",
        ],
    )
)

# Test 18: Filter + genomic filter
tests.append(
    create_test_request(
        name="filter_and_genomic",
        request_body={
            "filters": {
                "logic": "AND",
                "conditions": [{"column": "gene", "operator": "eq", "value": "TP53"}],
            },
            "genomic_filter": {
                "position": [{"chromosome": "chr17", "start": 7570000, "end": 7580000}]
            },
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "All results should have gene = 'TP53'",
            "All results should be within chr17:7570000-7580000",
            "Should be TP53 variants in TP53 genomic region",
        ],
    )
)

# Test 19: Text search + genomic filter + sorting
tests.append(
    create_test_request(
        name="all_combined",
        request_body={
            "term": "mut",
            "genomic_filter": {
                "position": [{"chromosome": "chr17", "start": 7570000, "end": 7580000}]
            },
            "sort_by": "start",
            "sort_order": "asc",
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 200",
            "Results should contain 'mut' in searchable columns",
            "Results should be within chr17:7570000-7580000",
            "Results should be sorted by start_position ascending",
        ],
    )
)

# --------------------------------------------------
# 7. EDGE CASES AND ERROR CONDITIONS
# --------------------------------------------------

# Test 20: Large page size (max allowed)
tests.append(
    create_test_request(
        name="max_page_size",
        request_body={"page": 1, "page_size": 1000},
        expected_checks=[
            "Status code should be 200",
            "Should return up to 1000 results",
            "page_size should be 1000",
        ],
    )
)

# Test 21: Very specific search (likely no results)
tests.append(
    create_test_request(
        name="no_results_expected",
        request_body={"term": "XYZ123nonexistent", "page": 1, "page_size": 5},
        expected_checks=[
            "Status code should be 200",
            "total_results should be 0",
            "results array should be empty",
        ],
    )
)

# Test 22: Search with invalid column (should error)
tests.append(
    create_test_request(
        name="invalid_search_column",
        request_body={
            "term": "test",
            "search_columns": ["nonexistent_column"],
            "page": 1,
            "page_size": 5,
        },
        expected_checks=[
            "Status code should be 400 or 500",
            "Should return error message about invalid column",
        ],
        test_pass=False,
    )
)

# Test 23: Invalid sort column (should error)
tests.append(
    create_test_request(
        name="invalid_sort_column",
        request_body={"sort_by": "nonexistent_column", "page": 1, "page_size": 5},
        expected_checks=[
            "Status code should be 400 or 500",
            "Should return error message about invalid sort column",
        ],
        test_pass=False,
    )
)

# --------------------------------------------------
# 8. PERFORMANCE TESTS
# --------------------------------------------------

# Test 24: Empty search (baseline performance)
tests.append(
    create_test_request(
        name="performance_baseline",
        request_body={"page": 1, "page_size": 10},
        expected_checks=[
            "Status code should be 200",
            "Response time should be reasonable (< 1 second)",
            "Should return results",
        ],
    )
)

# Test 25: Complex query performance
tests.append(
    create_test_request(
        name="performance_complex",
        request_body={
            "term": "mut",
            "filters": {
                "logic": "OR",
                "conditions": [
                    {"column": "gene", "operator": "eq", "value": "TP53"},
                    {"column": "gene", "operator": "eq", "value": "KRAS"},
                    {"column": "gene", "operator": "eq", "value": "EGFR"},
                ],
            },
            "page": 1,
            "page_size": 20,
        },
        expected_checks=[
            "Status code should be 200",
            "Response time should be reasonable (< 2 seconds)",
            "Should return TP53, KRAS, or EGFR mutations",
        ],
    )
)

# --------------------------------------------------
# 9. PAGINATION VALIDATION TESTS
# --------------------------------------------------

# Test 26: Page beyond results
tests.append(
    create_test_request(
        name="page_beyond_results",
        request_body={"page": 1000, "page_size": 60},
        expected_checks=[
            "Status code should be 200",
            "results array should be empty (or have few results)",
            "total_results should be less than page * page_size",
        ],
    )
)

# Test 27: Page size of 1
tests.append(
    create_test_request(
        name="single_result_page",
        request_body={"page": 1, "page_size": 1},
        expected_checks=[
            "Status code should be 200",
            "results array should have exactly 1 item",
            "page_size should be 1",
        ],
    )
)

# --------------------------------------------------
# 10. COMPLEX FILTERING TESTS
# --------------------------------------------------

# Test 28: Complex AND filter with multiple conditions
tests.append(
    create_test_request(
        name="complex_and_filter_multiple_conditions",
        request_body={
            "page": 1,
            "page_size": 10,
            "filters": {
                "logic": "AND",
                "conditions": [
                    {
                        "logic": "OR",
                        "conditions": [
                            {
                                "column": "variant_class",
                                "operator": "eq",
                                "value": "Missense_Mutation",
                            },
                            {
                                "column": "variant_class",
                                "operator": "eq",
                                "value": "Nonsense_Mutation",
                            },
                            {
                                "column": "variant_class",
                                "operator": "eq",
                                "value": "Frame_Shift_Ins",
                            },
                        ],
                    },
                    {
                        "logic": "AND",
                        "conditions": [
                            {
                                "column": "gene",
                                "operator": "in",
                                "value": ["TP53", "KRAS", "BRAF", "EGFR"],
                            },
                            {
                                "column": "tumor_sample_barcode",
                                "operator": "like",
                                "value": "TCGA",
                            },
                        ],
                    },
                    {
                        "logic": "AND",
                        "conditions": [
                            {"column": "ncbi_build", "operator": "eq", "value": "37"}
                        ],
                    },
                ],
            },
        },
        expected_checks=[
            "Status code should be 200",
            "All results should have variant_class in ['Missense_Mutation', 'Nonsense_Mutation', 'Frame_Shift_Ins']",
            "All results should have gene in ['TP53', 'KRAS', 'BRAF', 'EGFR']",
            "All results should have tumor_sample_barcode containing 'TCGA'",
            "All results should have ncbi_build = '37'",
            "Results should be limited to 10 items",
        ],
    )
)

# Test 29: Nested OR with AND inside
tests.append(
    create_test_request(
        name="nested_or_with_internal_and",
        request_body={
            "page": 1,
            "page_size": 8,
            "filters": {
                "logic": "OR",
                "conditions": [
                    {
                        "logic": "AND",
                        "conditions": [
                            {"column": "gene", "operator": "eq", "value": "TP53"},
                            {"column": "chrom", "operator": "eq", "value": "chr17"},
                            {"column": "start", "operator": "gte", "value": "7570000"},
                            {"column": "start", "operator": "lte", "value": "7590000"},
                        ],
                    },
                    {
                        "logic": "AND",
                        "conditions": [
                            {"column": "gene", "operator": "eq", "value": "EGFR"},
                            {"column": "chrom", "operator": "eq", "value": "chr7"},
                            {
                                "column": "variant_class",
                                "operator": "in",
                                "value": ["Missense_Mutation", "In_Frame_Del"],
                            },
                        ],
                    },
                    {
                        "logic": "AND",
                        "conditions": [
                            {"column": "gene", "operator": "eq", "value": "HRAS"},
                            {"column": "chrom", "operator": "eq", "value": "chr11"},
                            {
                                "column": "cDNA_change",
                                "operator": "like",
                                "value": "c.35",
                            },
                        ],
                    },
                ],
            },
            "sort_by": "gene",
            "sort_order": "asc",
        },
        expected_checks=[
            "Status code should be 200",
            "Results should contain only TP53, EGFR, or HRAS mutations",
            "TP53 results should be on chr17 between positions 7,570,000-7,590,000",
            "EGFR results should be on chr7 and be Missense or Inframe deletions",
            "HRAS results should be on chr11 with cDNA_change containing 'c.35'",
            "Results should be sorted alphabetically by gene",
            "Results count should be <= 8",
        ],
    )
)


print(f"\n{'=' * 60}")
print(f"TEST SUITE GENERATED: {len(tests)} tests")
print("Test files saved in: search")
print(f"{'=' * 60}")
