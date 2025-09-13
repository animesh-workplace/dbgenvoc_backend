from fastapi import HTTPException
from sqlalchemy import create_engine
from llama_index.core import SQLDatabase
from llama_index.llms.ollama import Ollama
from app.session import SQLALCHEMY_DATABASE_URL
from llama_index.core.indices.struct_store import NLSQLTableQueryEngine


async def ask_ollama_sql(db_path: str, query: str, model: str = "llama3.2"):
    """
    Query SQLite database using natural language via Ollama + LlamaIndex.

    Args:
        db_path (str): Path to SQLite database
        query (str): Natural language query
        model (str): Ollama model (default: llama3.2)
    """

    try:
        if not query or len(query.strip()) < 5:
            raise HTTPException(
                status_code=400, detail="Query must be at least 5 characters long"
            )

        # ✅ Connect to SQLite (restrict only to es_somatic + ej_tcga)
        engine = create_engine(f"{SQLALCHEMY_DATABASE_URL}?mode=ro&uri=true")
        sql_database = SQLDatabase(
            engine,
            include_tables=["wg_somatic", "es_tcga"],
            table_descriptions={
                "wg_somatic": "Somatic mutation data from Indian oral cancer patients",
                "es_tcga": "Somatic mutation data from TCGA oral cancer subset",
            },
        )

        # ✅ Use Ollama as the LLM
        llm = Ollama(model=model, request_timeout=120.0)

        # ✅ Create NL→SQL engine
        query_engine = NLSQLTableQueryEngine(sql_database=sql_database, llm=llm)

        # ✅ Run query
        response = query_engine.query(query)

        return {
            "query": query,
            "answer": str(response),  # LlamaIndex response object → string
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama SQL API failed: {str(e)}")
