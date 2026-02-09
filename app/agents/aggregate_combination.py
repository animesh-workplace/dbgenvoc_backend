from pathlib import Path
from agno.agent import Agent
from pydantic import BaseModel, Field
from app.session import ai_shakti_lite_engine as ai_engine
from app.api.aggregate_combination import ConcatenatedAggregationRequest

BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT = (BASE_DIR / "prompts" / "aggregate_combination.md").read_text(
    encoding="utf-8"
)


class ConcatenatedAggregationModel(BaseModel):
    table_name: str = Field(..., description="Name of the database table")
    request_body: ConcatenatedAggregationRequest = Field(
        ..., description="Aggregation request parameters"
    )


concate_aggregate_agent = Agent(
    retries=4,
    model=ai_engine,
    use_json_mode=True,
    system_message=SYSTEM_PROMPT,
    output_schema=ConcatenatedAggregationModel,
)
