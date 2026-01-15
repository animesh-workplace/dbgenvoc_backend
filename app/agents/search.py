from pathlib import Path
from agno.agent import Agent
from pydantic import BaseModel, Field
from app.api.search import SearchRequest
from app.session import ai_engine_lite as ai_engine


BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT = (BASE_DIR / "prompts" / "orchestrator.md").read_text(encoding="utf-8")


class SearchModel(BaseModel):
    table_name: str = Field(..., description="Name of the database table")
    request_body: SearchRequest = Field(..., description="Search request parameters")


search_agent = Agent(
    retries=4,
    model=ai_engine,
    use_json_mode=True,
    output_schema=SearchModel,
    system_message=SYSTEM_PROMPT,
)
