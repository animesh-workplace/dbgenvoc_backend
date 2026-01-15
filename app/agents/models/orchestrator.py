from typing import List
from pydantic import BaseModel


class SimplePlanStep(BaseModel):
    step_id: str
    tool_name: str
    query_context: str
    deps: List[str] = []


class SimplePlan(BaseModel):
    plan: List[SimplePlanStep]
