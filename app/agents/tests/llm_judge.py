import json
from pathlib import Path
from agno.agent import Agent
from app.session import ai_engine_pro as ai_judge
from typing import Dict, Any, List
from pydantic import BaseModel, Field, ValidationError

# Import the search agent
from app.agents.search import search_agent


# ==========================================
# JUDGE CONFIGURATION
# ==========================================


class JudgmentResult(BaseModel):
    """Structure for judge's evaluation result"""

    is_correct: bool = Field(..., description="Whether the output is correct")
    score: float = Field(..., ge=0.0, le=1.0, description="Score from 0 to 1")
    reasoning: str = Field(..., description="Detailed reasoning for the judgment")
    issues: List[str] = Field(default_factory=list, description="List of issues found")
    suggestions: List[str] = Field(
        default_factory=list, description="Suggestions for improvement"
    )


# Judge system prompt with explicit JSON structure requirements
JUDGE_SYSTEM_PROMPT = """You are an expert judge evaluating search agent outputs for genomic variant search APIs.

Your task is to compare the agent's output against the expected output and determine if they are semantically equivalent and structurally correct.

## Evaluation Criteria

### 1. Structural Correctness (40%)
- All filters MUST have `logic` and `conditions` keys wrapped correctly
- Logic values must be uppercase ("AND" or "OR")
- Proper nesting for complex logic
- Correct JSON structure

### 2. Semantic Equivalence (40%)
- Same table_name
- Equivalent filter conditions (order doesn't matter)
- Same operators used correctly
- Array values can be in different order but must contain same elements
- Term/search parameters match when specified
- Sort/pagination parameters match when specified

### 3. Operator Selection (20%)
- Single values use "eq" operator
- Multiple values use "in" operator (not multiple "eq")
- Nested OR logic properly structured
- No redundant conditions

## Optional Parameters Handling

These parameters are **OPTIONAL** and their presence in actual output when not in expected output is **ACCEPTABLE**:
- `page` (default: 1)
- `page_size` (default: 10)
- `sort_by` (default: null/omitted)
- `sort_order` (default: "asc")

**Do NOT penalize** if actual output includes these with default values when expected output omits them.

## Parameters That Must Match

These parameters MUST be present in actual output if they exist in expected output:
- `filters` - Must match if specified in expected
- `genomic_filter` - Must match if specified in expected
- `term` - Must match if specified in expected
- `search_columns` - Must match if specified in expected

## Scoring Guide

- **1.0**: Perfect match, semantically equivalent (extra defaults OK)
- **0.95-0.99**: Extra optional parameters with non-default but reasonable values
- **0.9-0.94**: Minor formatting difference (e.g., array order)
- **0.7-0.8**: Small structural issue but intent is correct
- **0.5-0.6**: Missing required parameters or wrong operators
- **0.3-0.4**: Major structural problems
- **0.0-0.2**: Completely wrong or invalid JSON

## Output Format

You MUST output ONLY valid JSON matching this EXACT structure:

```json
{
    "is_correct": true,
    "score": 1.0,
    "reasoning": "Detailed explanation here",
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"]
}
```

**CRITICAL REQUIREMENTS:**
- `is_correct`: boolean (true/false)
- `score`: number between 0.0 and 1.0
- `reasoning`: string (detailed explanation)
- `issues`: array of strings (use [] if no issues)
- `suggestions`: array of strings (use [] if no suggestions)

**DO NOT:**
- Return suggestions as a single string
- Return issues as a single string
- Return any text outside the JSON object
- Use null for issues or suggestions (use [] instead)

Be strict about structure but flexible about optional defaults. Focus on real errors, not acceptable variations.
"""

judge_agent = Agent(
    retries=2,
    model=ai_judge,
    use_json_mode=True,
    output_schema=JudgmentResult,
    system_message=JUDGE_SYSTEM_PROMPT,
)


# ==========================================
# TEST EXECUTION
# ==========================================


def load_test_cases(
    test_file: str = "search_agent_test_cases.json",
) -> List[Dict[str, Any]]:
    """Load test cases from JSON file"""
    script_dir = Path(__file__).resolve().parent
    test_file_path = script_dir / test_file

    with open(test_file_path, "r") as f:
        return json.load(f)


def run_search_agent(orchestrator_query: str) -> Dict[str, Any]:
    """
    Execute search agent with orchestrator query
    Returns the parsed output
    """
    try:
        response = search_agent.run(orchestrator_query)

        # Extract the output
        if hasattr(response, "content"):
            output = response.content
        else:
            output = response

        # Convert to dict if needed
        if hasattr(output, "model_dump"):
            output = output.model_dump()
        elif hasattr(output, "dict"):
            output = output.dict()

        return output
    except Exception as e:
        return {"error": f"Search agent failed: {str(e)}"}


def parse_judgment_response(response: Any) -> JudgmentResult:
    """
    Safely parse judgment response with multiple fallback strategies
    """
    # Strategy 1: Try direct conversion if it's already JudgmentResult
    if isinstance(response, JudgmentResult):
        return response

    # Strategy 2: Extract content if available
    if hasattr(response, "content"):
        content = response.content
    else:
        content = response

    # Strategy 3: If content is dict, try to create JudgmentResult
    if isinstance(content, dict):
        try:
            # Ensure lists for issues and suggestions
            if "issues" in content and isinstance(content["issues"], str):
                content["issues"] = [content["issues"]] if content["issues"] else []
            if "suggestions" in content and isinstance(content["suggestions"], str):
                content["suggestions"] = (
                    [content["suggestions"]] if content["suggestions"] else []
                )

            # Ensure defaults
            content.setdefault("issues", [])
            content.setdefault("suggestions", [])

            return JudgmentResult(**content)
        except ValidationError as e:
            print(f"WARNING: Validation error in dict response: {e}")
            # Return default failure judgment
            return JudgmentResult(
                is_correct=False,
                score=0.0,
                reasoning=f"Failed to parse judgment response: {str(e)}",
                issues=["Response parsing failed"],
                suggestions=["Check judge agent output format"],
            )

    # Strategy 4: If content is string, try to parse as JSON
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            # Ensure lists
            if "issues" in parsed and isinstance(parsed["issues"], str):
                parsed["issues"] = [parsed["issues"]] if parsed["issues"] else []
            if "suggestions" in parsed and isinstance(parsed["suggestions"], str):
                parsed["suggestions"] = (
                    [parsed["suggestions"]] if parsed["suggestions"] else []
                )

            parsed.setdefault("issues", [])
            parsed.setdefault("suggestions", [])

            return JudgmentResult(**parsed)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"WARNING: Failed to parse string response: {e}")
            return JudgmentResult(
                is_correct=False,
                score=0.0,
                reasoning=f"Failed to parse string response: {str(e)}",
                issues=["Response parsing failed"],
                suggestions=["Check judge agent JSON output"],
            )

    # Strategy 5: Complete fallback
    print(f"WARNING: Unexpected response type: {type(response)}")
    return JudgmentResult(
        is_correct=False,
        score=0.0,
        reasoning=f"Unexpected response type: {type(response)}",
        issues=["Unknown response format"],
        suggestions=["Review judge agent configuration"],
    )


def judge_output(
    test_case_id: int,
    orchestrator_query: str,
    actual_output: Dict[str, Any],
    expected_output: Dict[str, Any],
) -> JudgmentResult:
    """
    Use LLM judge to evaluate if actual output matches expected output
    WITH ROBUST ERROR HANDLING
    """

    judge_prompt = f"""## Test Case {test_case_id}

**Orchestrator Query:**
{orchestrator_query}

**Expected Output:**
```json
{json.dumps(expected_output, indent=2)}
```

**Actual Output:**
```json
{json.dumps(actual_output, indent=2)}
```

Evaluate if the actual output is correct. Remember that page, page_size, sort_by, and sort_order are optional and should not be penalized if they appear in actual output with default values when not in expected output.

Output ONLY valid JSON with this structure:
{{
    "is_correct": boolean,
    "score": number,
    "reasoning": "string",
    "issues": ["array", "of", "strings"],
    "suggestions": ["array", "of", "strings"]
}}
"""

    try:
        # Run judge with error handling
        response = judge_agent.run(judge_prompt)

        # Parse with fallback strategies
        judgment = parse_judgment_response(response)

        return judgment

    except Exception as e:
        # Ultimate fallback for any exception
        print(f"ERROR: Judge execution failed for test {test_case_id}: {str(e)}")
        return JudgmentResult(
            is_correct=False,
            score=0.0,
            reasoning=f"Judge execution failed: {str(e)}",
            issues=[f"Exception: {str(e)}"],
            suggestions=["Check judge agent configuration and model availability"],
        )


def run_test_suite(
    test_cases_file: str = "search_agent_test_cases.json",
    output_file: str = "test_results.json",
    verbose: bool = True,
    continue_on_error: bool = True,
) -> Dict[str, Any]:
    """
    Run complete test suite with LLM-as-judge
    NOW WITH ROBUST ERROR HANDLING AND CONTINUE ON ERROR
    """

    # Get script directory for file paths
    script_dir = Path(__file__).resolve().parent
    output_file_path = script_dir / output_file

    # Load test cases
    test_cases = load_test_cases(test_cases_file)

    results = {
        "total_tests": len(test_cases),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "average_score": 0.0,
        "test_results": [],
    }

    total_score = 0.0

    print(f"\n{'=' * 80}")
    print(f"Running Search Agent Test Suite: {len(test_cases)} test cases")
    print(f"Continue on error: {continue_on_error}")
    print(f"{'=' * 80}\n")

    for i, test_case in enumerate(test_cases, 1):
        test_id = test_case["id"]
        category = test_case["category"]
        orchestrator_query = test_case["orchestrator_query"]
        expected_output = test_case["expected_output"]

        if verbose:
            print(f"\n[{i}/{len(test_cases)}] Test Case {test_id}: {category}")
            print(f"Query: {orchestrator_query[:80]}...")

        try:
            # Run search agent
            actual_output = run_search_agent(orchestrator_query)

            # Judge the output
            judgment = judge_output(
                test_id, orchestrator_query, actual_output, expected_output
            )

            # Ensure judgment is valid
            if not isinstance(judgment, JudgmentResult):
                print(f"ERROR: Invalid judgment type: {type(judgment)}")
                judgment = JudgmentResult(
                    is_correct=False,
                    score=0.0,
                    reasoning="Invalid judgment format",
                    issues=["Judgment parsing failed"],
                    suggestions=[],
                )

            # Update statistics
            total_score += judgment.score
            if judgment.is_correct:
                results["passed"] += 1
                status = "✓ PASSED"
            else:
                results["failed"] += 1
                status = "✗ FAILED"

            # Store result
            test_result = {
                "id": test_id,
                "category": category,
                "query": orchestrator_query,
                "status": status,
                "score": judgment.score,
                "is_correct": judgment.is_correct,
                "reasoning": judgment.reasoning,
                "issues": judgment.issues
                if isinstance(judgment.issues, list)
                else [str(judgment.issues)],
                "suggestions": judgment.suggestions
                if isinstance(judgment.suggestions, list)
                else [str(judgment.suggestions)],
                "expected": expected_output,
                "actual": actual_output,
            }
            results["test_results"].append(test_result)

            # Print result
            if verbose:
                print(f"Status: {status} (Score: {judgment.score:.2f})")
                if not judgment.is_correct:
                    print(f"Reasoning: {judgment.reasoning[:200]}...")
                    if judgment.issues:
                        print(f"Issues: {', '.join(judgment.issues[:3])}...")

        except Exception as e:
            # Handle any exception during test execution
            results["errors"] += 1
            error_msg = f"Test execution error: {str(e)}"
            print(f"ERROR: {error_msg}")

            if continue_on_error:
                # Log error and continue
                test_result = {
                    "id": test_id,
                    "category": category,
                    "query": orchestrator_query,
                    "status": "✗ ERROR",
                    "score": 0.0,
                    "is_correct": False,
                    "reasoning": error_msg,
                    "issues": [str(e)],
                    "suggestions": ["Check test case and agent configuration"],
                    "expected": expected_output,
                    "actual": {"error": str(e)},
                }
                results["test_results"].append(test_result)
            else:
                # Stop execution
                print(f"\nStopping test suite due to error.")
                break

    # Calculate average score
    completed_tests = results["passed"] + results["failed"]
    results["average_score"] = (
        total_score / completed_tests if completed_tests > 0 else 0.0
    )

    # Save results
    try:
        with open(output_file_path, "w") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        print(f"WARNING: Failed to save results: {e}")

    # Print summary
    print(f"\n{'=' * 80}")
    print(f"Test Suite Summary")
    print(f"{'=' * 80}")
    print(f"Total Tests: {results['total_tests']}")
    print(
        f"Passed: {results['passed']} ({results['passed'] / results['total_tests'] * 100:.1f}%)"
    )
    print(
        f"Failed: {results['failed']} ({results['failed'] / results['total_tests'] * 100:.1f}%)"
    )
    if results["errors"] > 0:
        print(
            f"Errors: {results['errors']} ({results['errors'] / results['total_tests'] * 100:.1f}%)"
        )
    print(f"Average Score: {results['average_score']:.3f}")
    print(f"\nDetailed results saved to: {output_file_path}")
    print(f"{'=' * 80}\n")

    return results


def run_single_test(
    test_id: int, test_cases_file: str = "search_agent_test_cases.json"
):
    """
    Run a single test case for debugging
    """
    test_cases = load_test_cases(test_cases_file)
    test_case = next((tc for tc in test_cases if tc["id"] == test_id), None)

    if not test_case:
        print(f"Test case {test_id} not found")
        return

    print(f"\n{'=' * 80}")
    print(f"Test Case {test_id}: {test_case['category']}")
    print(f"{'=' * 80}")
    print(f"\nOrchestrator Query:\n{test_case['orchestrator_query']}")
    print(f"\nExpected Output:")
    print(json.dumps(test_case["expected_output"], indent=2))

    # Run agent
    print(f"\nRunning search agent...")
    try:
        actual_output = run_search_agent(test_case["orchestrator_query"])
        print(f"\nActual Output:")
        print(json.dumps(actual_output, indent=2))
    except Exception as e:
        print(f"ERROR: Search agent failed: {e}")
        actual_output = {"error": str(e)}

    # Judge
    print(f"\nJudging output...")
    try:
        judgment = judge_output(
            test_id,
            test_case["orchestrator_query"],
            actual_output,
            test_case["expected_output"],
        )

        print(f"\n{'=' * 80}")
        print(f"Judgment Result")
        print(f"{'=' * 80}")
        print(f"Correct: {judgment.is_correct}")
        print(f"Score: {judgment.score:.2f}")
        print(f"\nReasoning:\n{judgment.reasoning}")

        if judgment.issues:
            print(f"\nIssues:")
            for issue in judgment.issues:
                print(f"  - {issue}")

        if judgment.suggestions:
            print(f"\nSuggestions:")
            for suggestion in judgment.suggestions:
                print(f"  - {suggestion}")

        print(f"\n{'=' * 80}\n")

        return judgment
    except Exception as e:
        print(f"ERROR: Judgment failed: {e}")
        return None


def analyze_failures(results_file: str = "test_results.json"):
    """
    Analyze failed test cases to identify patterns
    """
    script_dir = Path(__file__).resolve().parent
    results_file_path = script_dir / results_file

    try:
        with open(results_file_path, "r") as f:
            results = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load results: {e}")
        return

    failed_tests = [t for t in results["test_results"] if not t["is_correct"]]

    if not failed_tests:
        print("✓ All tests passed! No failures to analyze.")
        return

    print(f"\n{'=' * 80}")
    print(f"Failure Analysis: {len(failed_tests)} failed tests")
    print(f"{'=' * 80}\n")

    # Group by category
    from collections import defaultdict

    failures_by_category = defaultdict(list)

    for test in failed_tests:
        failures_by_category[test["category"]].append(test)

    print("Failures by Category:")
    for category, tests in sorted(failures_by_category.items()):
        print(f"\n  {category}: {len(tests)} failure(s)")
        for test in tests:
            print(f"    - Test {test['id']}: Score {test['score']:.2f}")
            if test.get("issues"):
                issues = (
                    test["issues"]
                    if isinstance(test["issues"], list)
                    else [test["issues"]]
                )
                print(f"      Issues: {issues[0] if issues else 'None'}")

    # Common issues
    all_issues = []
    for test in failed_tests:
        issues = test.get("issues", [])
        if isinstance(issues, list):
            all_issues.extend(issues)
        else:
            all_issues.append(str(issues))

    from collections import Counter

    issue_counts = Counter(all_issues)

    print(f"\nMost Common Issues:")
    for issue, count in issue_counts.most_common(5):
        print(f"  {count}x: {issue}")

    print(f"\n{'=' * 80}\n")


# ==========================================
# CLI INTERFACE
# ==========================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "single" and len(sys.argv) > 2:
            # Run single test
            test_id = int(sys.argv[2])
            run_single_test(test_id)

        elif command == "analyze":
            # Analyze failures
            analyze_failures()

        else:
            print("Usage:")
            print(
                "  python -m app.agents.tests.llm_judge              - Run full test suite"
            )
            print(
                "  python -m app.agents.tests.llm_judge single <id>  - Run single test"
            )
            print(
                "  python -m app.agents.tests.llm_judge analyze      - Analyze failures"
            )
    else:
        # Run full test suite with continue on error
        run_test_suite(verbose=True, continue_on_error=True)
