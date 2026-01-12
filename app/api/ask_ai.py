import json
import asyncio
from typing import Dict, Any
from agno.utils.log import logger
from agno.workflow import Workflow
from pydantic import ValidationError
from app.api.search import generic_search
from app.agents.search import search_agent
from app.api.aggregate import generic_aggregate
from app.agents.aggregate import aggregate_agent
from app.agents.orchestrator import orchestrator_agent
from app.agents.aggregate_combination import concate_aggregate_agent
from app.api.aggregate_combination import generic_concatenated_aggregate
from app.agents.synthesizer import synthesizer_agent, preprocess_results_for_synthesis
from app.agents.equalizer import equalizer_agent


# Wrapper to ensure we catch DB execution errors per task
async def execute_api_call(tool_name: str, params: Any, db) -> Any:
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
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        return {"error": f"API Call Failed: {str(e)}"}


class VocalResearchWorkflow(Workflow):
    """
    VOCAL Research Pipeline:
    1. Orchestrator (Planning)
    2. Parallel Specialists (Parameter Generation + DB Execution)
    3. Synthesizer (Reporting)
    """

    # Define agents map for easy routing
    specialists: Dict[str, Any] = {
        "generic_search": search_agent,
        "generic_aggregate": aggregate_agent,
        "generic_concatenated_aggregate": concate_aggregate_agent,
    }

    def run(self, query: str, db: Any) -> Dict[str, Any]:
        """
        Entry point for the workflow.
        Note: We use asyncio.run() internally if called synchronously,
        or await the internal logic if called from an async endpoint.
        """
        # Since FastAPI is async, we call the async method directly
        # If this method itself is not async, we bridge it.
        # Ideally, make this method `async def run` if your library supports it.
        # Below is the logic assuming we are inside an async context.
        return asyncio.run(self.run_async(query, db))

    async def run_async(self, query: str, db: Any) -> Dict[str, Any]:
        logger.info(f"Starting Workflow for: {query}")

        equalizer_response = await asyncio.to_thread(
            equalizer_agent.run, f"QUERY: {query}\nOUTPUT:"
        )
        logger.info(f"Equalizer response {equalizer_response.content}")
        return {"content": equalizer_response.content}

        # # --- STEP 1: PLAN (Orchestrator) ---
        # try:
        #     # Run Orchestrator to get the JSON plan
        #     # We use a thread executor to keep the main loop non-blocking
        #     plan_response = await asyncio.to_thread(orchestrator_agent.run, query)
        #     plan = plan_response.content
        #     logger.info(f"Plan for the workflow: {plan}")
        # except (ValidationError, json.JSONDecodeError) as e:
        #     logger.error(f"Planning failed: {e}")
        #     return {"answer": "I had trouble planning this analysis. Please try again."}

        # # --- STEP 2: PARALLEL EXECUTION ---
        # # We build a list of async tasks for every step in the plan
        # tasks = []
        # conversational_notes = []

        # for step in plan.plan:
        #     # Handle conversational/static steps immediately
        #     if step.tool_name == "answer_conversational":
        #         conversational_notes.append(step.query_context)
        #         continue

        #     # Queue up data steps
        #     if step.tool_name in self.specialists:
        #         tasks.append(
        #             self.process_step(
        #                 tool_name=step.tool_name, context=step.query_context, db=db
        #             )
        #         )

        # # Execute all gathered tasks in parallel
        # # return_exceptions=True ensures one failure doesn't crash the whole batch
        # results = []
        # if tasks:
        #     results = await asyncio.gather(*tasks, return_exceptions=True)

        # # Filter out any messy exceptions from the list
        # valid_results = [r for r in results if not isinstance(r, Exception)]

        # # --- STEP 3: SYNTHESIS ---
        # if not valid_results and not conversational_notes:
        #     return {"answer": "I couldn't find any relevant data for your request."}

        # # Prepare context for the synthesizer
        # summarized_data = preprocess_results_for_synthesis(valid_results)

        # synthesis_prompt = f"""
        # Original User Query: "{query}"

        # Context/Insights from Specialist:
        # **Biological Knowledge**
        # When told to calculate the ratio of transition transversion use this grouping
        # - Transitions: A>G, G>A, C>T, T>C
        # - Transversions: A>C, C>A, A>T, T>A, G>C, C>G, G>T, T>G
        # {" ".join(conversational_notes)}

        # Database Results:
        # {json.dumps(summarized_data)}

        # Please provide a final response that incorporates the data results and
        # addresses any limitations mentioned in the insights.
        # """

        # try:
        #     # Run Synthesis
        #     synthesis_response = await asyncio.to_thread(
        #         synthesizer_agent.run, synthesis_prompt
        #     )
        #     final_answer = synthesis_response.content
        #     logger.info(f"Finally the answer: {final_answer}")
        #     logger.info(f"Complete Output {synthesis_response}")
        # except Exception as e:
        #     logger.error(f"Synthesis failed: {e}")
        #     final_answer = "I found the data but encountered an error summarizing it."
        # return {
        #     "plan": plan,
        #     "answer": final_answer,
        #     "data": summarized_data,
        #     "results": valid_results,
        # }

    async def process_step(
        self, tool_name: str, context: str, db: Any
    ) -> Dict[str, Any]:
        """
        A single unit of work:
        1. Agent converts Context string -> Pydantic Params
        2. Execute DB API with Params
        """
        agent = self.specialists[tool_name]

        # 1. Generate Parameters (Agent Call)
        # Offload CPU-bound Pydantic parsing/LLM call to thread
        params_response = await asyncio.to_thread(agent.run, context)
        params = params_response.content
        logger.info(f"Tool execution: {tool_name} with params {params}")

        # 2. Execute DB Query (IO Bound)
        # This remains awaited directly as it uses async DB drivers
        db_result = await execute_api_call(tool_name, params, db)

        return {
            "tool_name": tool_name,
            "params": params,
            "result": db_result,
            "context": context,
        }
