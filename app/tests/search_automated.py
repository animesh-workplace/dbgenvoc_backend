import os
import json
import glob
import pytest
import requests
from datetime import datetime


# Pytest test functions
def pytest_generate_tests(metafunc):
    """Generate test cases for pytest dynamically from JSON files."""
    if "test_case" in metafunc.fixturenames:
        # Load test cases from the test_results_dir
        test_results_dir = "test_conditions/search"
        test_files = glob.glob(f"{test_results_dir}/test_*.json")
        test_cases = []

        for file_path in test_files:
            with open(file_path, "r") as f:
                test_case = json.load(f)
                test_cases.append(test_case)

        # Parametrize the test function with all test cases
        metafunc.parametrize(
            "test_case", test_cases, ids=lambda tc: tc.get("name", "unnamed_test")
        )


def test_api_search(test_case):
    """Test individual API search case."""
    # Make the API request
    response = requests.post(
        test_case["url"], json=test_case.get("request", {}), timeout=30
    )

    # Check status code
    if test_case["pass"]:
        assert response.status_code == 200, (
            f"Expected status 200, got {response.status_code}"
        )
    else:
        assert response.status_code == 400

    # Parse response
    response_json = response.json()

    # Validate expected checks
    if "expected_checks" in test_case:
        for check in test_case["expected_checks"]:
            if "Status code should be 200" in check:
                continue  # Already checked
            elif "Should have 'results' array" in check:
                assert "results" in response_json, "Missing 'results' array"
                assert isinstance(response_json["results"], list), (
                    "'results' should be an array"
                )
            elif "Results length should be <=" in check:
                import re

                match = re.search(r"<= (\d+)", check)
                if match:
                    max_length = int(match.group(1))
                    assert len(response_json.get("results", [])) <= max_length, (
                        f"Results length {len(response_json.get('results', []))} > {max_length}"
                    )
            elif "Should have 'total_results' field" in check:
                assert "total_results" in response_json, "Missing 'total_results' field"
            elif "Should have 'table_name' field" in check:
                assert "table_name" in response_json, "Missing 'table_name' field"
            elif "Page should be" in check:
                import re

                match = re.search(r"Page should be (\d+)", check)
                if match:
                    expected_page = int(match.group(1))
                    assert response_json.get("page") == expected_page, (
                        f"Expected page {expected_page}, got {response_json.get('page')}"
                    )
            elif "Page_size should be" in check:
                import re

                match = re.search(r"Page_size should be (\d+)", check)
                if match:
                    expected_page_size = int(match.group(1))
                    assert response_json.get("page_size") == expected_page_size, (
                        f"Expected page_size {expected_page_size}, got {response_json.get('page_size')}"
                    )

    # Compare with saved response if available
    if (
        "actual_response" in test_case
        and "response_body" in test_case["actual_response"]
    ):
        saved_response = test_case["actual_response"]["response_body"]

        # Compare key metadata fields
        key_fields = ["page", "page_size", "table_name", "total_results"]
        for field in key_fields:
            if field in saved_response and field in response_json:
                assert response_json[field] == saved_response[field], (
                    f"{field} mismatch: {response_json[field]} != {saved_response[field]}"
                )

        # Verify results structure
        if "results" in saved_response and "results" in response_json:
            assert len(response_json["results"]) == len(saved_response["results"]), (
                f"Results count mismatch: {len(response_json['results'])} != {len(saved_response['results'])}"
            )

            # Check that results have the same structure
            if len(response_json["results"]) > 0 and len(saved_response["results"]) > 0:
                expected_keys = set(saved_response["results"][0].keys())
                actual_keys = set(response_json["results"][0].keys())
                assert expected_keys == actual_keys, (
                    f"Result structure mismatch. Expected keys: {expected_keys}, Actual keys: {actual_keys}"
                )


# Additional comprehensive tests
def test_api_response_time(test_case):
    """Test that API response time is reasonable."""
    if "actual_response" in test_case and "elapsed_ms" in test_case["actual_response"]:
        max_response_time = 5000  # 5 seconds maximum
        response = requests.post(
            test_case["url"], json=test_case.get("request", {}), timeout=30
        )
        assert response.elapsed.total_seconds() * 1000 < max_response_time, (
            f"Response time {response.elapsed.total_seconds() * 1000:.2f}ms exceeds {max_response_time}ms limit"
        )


def test_api_response_headers(test_case):
    """Test that API returns appropriate headers."""
    response = requests.post(
        test_case["url"], json=test_case.get("request", {}), timeout=30
    )

    # Check for required headers
    assert "Content-Type" in response.headers, "Missing Content-Type header"
    assert "application/json" in response.headers["Content-Type"], (
        f"Content-Type should be application/json, got {response.headers['Content-Type']}"
    )


# Run the test suite
if __name__ == "__main__":
    print("\n\nRunning pytest tests...")
    pytest_args = [__file__, "-v", "--tb=short"]
    pytest.main(pytest_args)
