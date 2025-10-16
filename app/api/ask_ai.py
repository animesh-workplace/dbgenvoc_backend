import json
from pydantic import ValidationError
from fastapi import HTTPException, status
from app.api.search import generic_search
from app.api.aggregate import generic_aggregate
from app.agents.orchestrator import orchestrator_agent
from app.agents.search import search_agent, SearchModel
from app.agents.aggregate import aggregate_agent, AggregationModel
from app.api.concate_aggregate import generic_concatenated_aggregate
from app.agents.synthesizer import preprocess_results_for_synthesis, synthesizer_agent
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
    Query database using the full Plan -> Execute -> Synthesize workflow.
    """
    specialists = {
        "generic_search": search_agent,
        "generic_aggregate": aggregate_agent,
        "generic_concatenated_aggregate": concate_aggregate_agent,
    }

    # --- 1. PLAN ---
    try:
        plan_response = orchestrator_agent.run(query)
        plan = plan_response.content
    except (ValidationError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"The orchestrator agent failed to generate a valid plan. Error: {str(e)}",
        )

    # --- 2. EXECUTE ---
    execution_results = []
    for step in plan.plan:
        tool_name = step.tool_name
        query_context = step.query_context

        if tool_name not in specialists:
            raise HTTPException(
                status_code=500,
                detail=f"Orchestrator planned an unknown tool: '{tool_name}'",
            )

        try:
            specialist_agent = specialists[tool_name]
            params_response = specialist_agent.run(query_context)
            params = params_response.content

            result = await execute_api_call(tool_name, params, db)

            # Important: Add tool_name to results for the pre-processor
            execution_results.append(
                {
                    "result": result,
                    "params": params,
                    "tool_name": tool_name,
                    "context": query_context,
                }
            )
        except HTTPException as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Error in step '{query_context}': {e.detail}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred during execution: {str(e)}",
            )

    # --- 3. SYNTHESIZE ---
    if not execution_results:
        return (
            "I was able to create a plan, but no data was returned from the database."
        )

    # Pre-process the results to make them concise
    summarized_data = preprocess_results_for_synthesis(execution_results)
    print(f"Summarized Data for Synthesis:\n{json.dumps(summarized_data, indent=2)}\n")

    synthesis_prompt = f"""
        Original User Query: "{query}"

        Data Results:
        {json.dumps(summarized_data)}
    """

    try:
        synthesis_response = synthesizer_agent.run(synthesis_prompt)
        final_answer = synthesis_response.content
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"The synthesizer agent failed to generate a final answer. Error: {str(e)}",
        )

    return {
        "plan": plan,
        "answer": final_answer,
        "data": summarized_data,
        "results": execution_results,
        "synthesis_prompt": synthesis_prompt,
    }
