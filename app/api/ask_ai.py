from fastapi import HTTPException
from pydantic import BaseModel, Field
from app.agents.search import search_agent
from app.api.aggregate import generic_aggregate
from app.agents.aggregate import aggregate_agent
from app.agents.orchestrator import orchestrator_agent
from app.api.search import generic_search, SearchRequest
from app.agents.concate_aggregate import concate_aggregate_agent
from app.api.concate_aggregate import generic_concatenated_aggregate


class SearchModel(BaseModel):
    table_name: str = Field(..., description="Name of the database table")
    request_body: SearchRequest = Field(..., description="Search request parameters")


async def execute_api_call(tool_name: str, params: SearchModel, db) -> dict:
    if tool_name == "generic_search":
        output = await generic_search(params.table_name, params.request_body, db)
        print("Output from search Call", output)
        return output
    elif tool_name == "generic_aggregate":
        output = await generic_aggregate(
            table_name=params.table_name, request=params.request_body, db=db
        )
        print("Output from aggregate Call", output)
        return output
    elif tool_name == "generic_concatenated_aggregate":
        output = await generic_concatenated_aggregate(
            table_name=params.table_name, request=params.request_body, db=db
        )
        print("Output from concatenated aggregate Call", output)
        return output


async def ask_database(query: str, db):
    """
    Query SQLite database using natural language via Bedrock.
    Includes table context for better results.
    """
    specialists = {
        "generic_search": search_agent,
        "generic_aggregate": aggregate_agent,
        "generic_concatenated_aggregate": concate_aggregate_agent,
    }
    plan_response = orchestrator_agent.run(query)
    print("orchestrator_agent: ", plan_response.content)

    for step in plan_response.content.plan:
        tool_name = step.tool_name
        query_context = step.query_context

        if tool_name in specialists:
            specialist_agent = specialists[tool_name]
            params_response = specialist_agent.run(query_context)
            params = params_response.content
            print("\n\n", tool_name, params)
            await execute_api_call(tool_name, params, db)
            # result = execute_api_call(tool_name, params)
            # execution_results.append({"context": query_context, "result": result})

    return "Query processed successfully"
