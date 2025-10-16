from fastapi import HTTPException
from llama_index.core import SQLDatabase
from llama_index.llms.ollama import Ollama
from app.session import SQLALCHEMY_DATABASE_URL
from llama_index.core.indices.struct_store import NLSQLTableQueryEngine
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from sqlalchemy import create_engine, inspect
import logging

logger = logging.getLogger(__name__)


async def ask_ollama_sql(query: str):
    """
    Query SQLite database using natural language via Ollama + LlamaIndex.
    Includes table context for better results.
    """

    try:
        if not query or len(query.strip()) < 5:
            raise HTTPException(
                status_code=400, detail="Query must be at least 5 characters long"
            )

        query = query.strip()
        logger.info(f"Processing SQL query: {query}")

        # ✅ Verify tables exist and get column information
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        inspector = inspect(engine)
        available_tables = inspector.get_table_names()

        # Check if our target tables exist
        target_tables = ["wg_somatic", "es_tcga"]
        existing_tables = [
            table for table in target_tables if table in available_tables
        ]

        if not existing_tables:
            raise HTTPException(
                status_code=404,
                detail=f"Target tables {target_tables} not found. Available tables: {available_tables}",
            )

        # ✅ Create detailed custom_table_info for each table
        custom_table_info = {}
        for table in existing_tables:
            if table == "wg_somatic":
                custom_table_info[table] = (
                    "Oral cancer somatic mutations from Indian patients. "
                    "disease column ONLY contains: OSCC (Oral Squamous Cell Carcinoma), OTSCC (Oral Tongue SCC). "
                    "gene: mutated genes, mutation_type: variant classification, "
                    "patient_id: Indian patient identifiers, frequency: mutation frequency."
                )
            elif table == "es_tcga":
                custom_table_info[table] = (
                    "TCGA oral cancer mutation data. "
                    "disease column ONLY contains: OSCC_GB (Oral SCC), OT-TCGA (Oral Tongue), "
                    "BM-TCGA (Buccal Mucosa), OC-TCGA (Oral Cavity). "
                    "sample_id: TCGA sample IDs, project: TCGA project codes, "
                    "gene: cancer genes, frequency: variant allele frequency."
                )

        # ✅ Create SQLDatabase with custom_table_info
        sql_database = SQLDatabase.from_uri(
            SQLALCHEMY_DATABASE_URL.split("?")[0],  # Remove query params
            include_tables=existing_tables,
            custom_table_info=custom_table_info,  # Use custom_table_info instead of context_dict
        )

        # ✅ Use Ollama as the LLM
        llm = Ollama(model="gemma3:4b", request_timeout=300.0)

        # ✅ Use HuggingFace embedding model
        embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        # ✅ Create query engine with context
        query_engine = NLSQLTableQueryEngine(
            sql_database=sql_database,
            llm=llm,
            embed_model=embed_model,
        )

        # ✅ Run query
        response = query_engine.query(query)

        return {
            "query": query,
            "sql": response.metadata.get("sql_query", ""),
            "answer": str(response),
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process query: {str(e)}"
        )
