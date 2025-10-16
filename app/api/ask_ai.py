import json
from pydantic import ValidationError
from fastapi import HTTPException, status
from app.api.search import generic_search
from app.api.aggregate import generic_aggregate
from app.agents.search import search_agent, SearchModel
from app.agents.orchestrator import orchestrator_agent
from app.agents.aggregate import aggregate_agent, AggregationModel
from app.api.concate_aggregate import generic_concatenated_aggregate
from app.agents.concate_aggregate import (
    concate_aggregate_agent,
    ConcatenatedAggregationModel,
)


async def execute_api_call(
    tool_name: str,
    params: SearchModel | AggregationModel | ConcatenatedAggregationModel,
    db,
) -> dict:
    # Note: The type hint for params is now a generic BaseModel
    try:
        if tool_name == "generic_search":
            return await generic_search(params.table_name, params.request_body, db)
        elif tool_name == "generic_aggregate":
            return await generic_aggregate(
                table_name=params.table_name, request=params.request_body, db=db
            )
        elif tool_name == "generic_concatenated_aggregate":
            return await generic_concatenated_aggregate(
                table_name=params.table_name, request=params.request_body, db=db
            )
        else:
            # This handles the case where the orchestrator hallucinates a tool
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Orchestrator planned an unknown tool: {tool_name}",
            )
    except HTTPException as e:
        # Re-raise HTTPException from the API functions to be caught by the main handler
        raise e
    except Exception as e:
        # Catch any other unexpected database or code errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during the database call for tool '{tool_name}': {str(e)}",
        )


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

    try:
        plan_response = orchestrator_agent.run(query)
        # The .content attribute from agno should already be a validated Pydantic model
        plan = plan_response.content
    except (ValidationError, json.JSONDecodeError) as e:
        # Catches cases where the orchestrator fails to produce a valid plan
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"The orchestrator agent failed to generate a valid plan. Error: {str(e)}",
        )

    execution_results = []
    for step in plan.plan:
        tool_name = step.tool_name
        query_context = step.query_context

        if tool_name not in specialists:
            # Handle cases where the orchestrator hallucinates a tool name
            # We can choose to log this and skip, or raise an error. Raising is safer.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Orchestrator planned an unknown tool: '{tool_name}'",
            )

        try:
            specialist_agent = specialists[tool_name]
            params_response = specialist_agent.run(query_context)
            params = (
                params_response.content
            )  # .content already gives the Pydantic model

            # This is the most critical call. It runs the database function
            # which might raise an HTTPException for a bad column name.
            result = await execute_api_call(tool_name, params, db)

            execution_results.append({"context": query_context, "result": result})

        except ValidationError as e:
            # This catches errors if the specialist agent produces malformed JSON
            # that doesn't match its Pydantic output_schema.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Specialist agent '{tool_name}' produced invalid parameters for context '{query_context}'. Error: {str(e)}",
            )
        except HTTPException as e:
            # This catches validation errors FROM your database functions.
            # This is where the "column does not exist" error will be caught!
            # We add context to the original error message.
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Error in step '{query_context}': {e.detail}",
            )

    return execution_results
