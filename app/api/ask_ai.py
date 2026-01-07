import json
from pydantic import ValidationError
from fastapi import HTTPException, status
from app.api.search import generic_search
from app.api.aggregate import generic_aggregate
from app.agents.orchestrator import orchestrator_agent
from app.agents.search import search_agent, SearchModel
from app.agents.aggregate import aggregate_agent, AggregationModel
from app.api.aggregate_combination import generic_concatenated_aggregate
from langtrace_python_sdk.utils.with_root_span import with_langtrace_root_span
from app.agents.synthesizer import preprocess_results_for_synthesis, synthesizer_agent
from app.agents.aggregate_combination import (
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


@with_langtrace_root_span()
async def ask_database(query: str, db):
    specialists = {
        "generic_search": search_agent,
        "generic_aggregate": aggregate_agent,
        "generic_concatenated_aggregate": concate_aggregate_agent,
    }

    # --- 1. PLAN ---
    try:
        plan_response = orchestrator_agent.run(query)
        plan = plan_response.content
        print(plan)
        print("--------")
    except (ValidationError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Plan failed: {str(e)}")

    # --- 2. EXECUTE ---
    execution_results = []
    conversational_notes = []  # Store agent insights here

    for step in plan.plan:
        tool_name = step.tool_name
        query_context = step.query_context

        # HANDLE CONVERSATIONAL QUERIES WITHOUT EXITING
        if tool_name == "answer_conversational":
            conversational_notes.append(query_context)
            continue  # Move to the next step in the plan

        if tool_name not in specialists:
            # Optional: Log warning instead of hard fail if other tools exist
            continue

        try:
            specialist_agent = specialists[tool_name]
            params_response = specialist_agent.run(query_context)
            params = params_response.content
            print(params)
            print("--------")

            result = await execute_api_call(tool_name, params, db)

            execution_results.append(
                {
                    "result": result,
                    "params": params,
                    "tool_name": tool_name,
                    "context": query_context,
                }
            )
        except Exception as e:
            # Log error but consider if you want to continue with other steps
            print(f"Error executing {tool_name}: {e}")

    # --- 3. SYNTHESIZE ---

    # If no data and no notes, then we have nothing
    if not execution_results and not conversational_notes:
        return {"answer": "I couldn't find any information regarding your request."}

    summarized_data = preprocess_results_for_synthesis(execution_results)

    # Inject BOTH data and conversational context into the prompt
    synthesis_prompt = f"""
        Original User Query: "{query}"

        Context/Insights from Specialist:
        {" ".join(conversational_notes)}

        Database Results:
        {json.dumps(summarized_data)}

        Please provide a final response that incorporates the data results and
        addresses any limitations mentioned in the insights.
    """
    print(synthesis_prompt)
    print("--------")

    try:
        synthesis_response = synthesizer_agent.run(synthesis_prompt)
        final_answer = synthesis_response.content
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Synthesis failed.")

    return {
        "plan": plan,
        "answer": final_answer,
        "data": summarized_data,
        "notes": conversational_notes,  # Helpful for frontend debugging
        "results": execution_results,
    }
