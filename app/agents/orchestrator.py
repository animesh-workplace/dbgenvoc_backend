from typing import List
from pathlib import Path
from agno.agent import Agent
from pydantic import BaseModel, Field
from app.session import ai_engine_pro as ai_engine

BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT = (BASE_DIR / "prompts" / "orchestrator_v1.md").read_text(
    encoding="utf-8"
)


class SimplePlanStep(BaseModel):
    step_id: str = Field(
        ...,
        description=(
            "Unique identifier for this execution step within the plan. "
            "This ID is used to reference the step in dependency lists (deps)."
        ),
    )

    tool_name: str = Field(
        ...,
        description=(
            "Name of the tool or executor to be used for this step "
            "(e.g., 'generic_search', 'generic_aggregate', 'llm_reasoning')."
        ),
    )

    query_context: str = Field(
        ...,
        description=(
            "Self-contained instruction or query describing what this step should execute. "
            "Must include all required parameters, filters, and constraints needed by the tool."
        ),
    )

    deps: List[str] = Field(
        default_factory=list,
        description=(
            "List of step_id values that must complete before this step can execute. "
            "An empty list indicates the step can run independently."
        ),
    )


class SimplePlan(BaseModel):
    plan: List[SimplePlanStep] = Field(
        ...,
        description=(
            "Ordered list of execution steps that together form a complete execution plan. "
            "Actual execution order is determined by step dependencies (deps), not list position. "
            "The plan must form a directed acyclic graph (DAG)."
        ),
    )


orchestrator_agent = Agent(
    retries=4,
    model=ai_engine,
    use_json_mode=True,
    output_schema=SimplePlan,
    system_message=SYSTEM_PROMPT,
)
