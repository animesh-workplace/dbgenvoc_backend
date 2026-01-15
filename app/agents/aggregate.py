from pathlib import Path
from agno.agent import Agent
from pydantic import BaseModel, Field
from app.api.aggregate import AggregationRequest
from app.session import ai_engine_lite as ai_engine

BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT = (BASE_DIR / "prompts" / "aggregate.md").read_text(encoding="utf-8")


class AggregationModel(BaseModel):
    table_name: str = Field(..., description="Name of the database table")
    request_body: AggregationRequest = Field(
        ..., description="Aggregation request parameters"
    )


aggregate_agent = Agent(
    retries=4,
    model=ai_engine,
    use_json_mode=True,
    system_message=SYSTEM_PROMPT,
    output_schema=AggregationModel,
)
