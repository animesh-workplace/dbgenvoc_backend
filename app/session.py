import os
from dotenv import load_dotenv
from agno.models.groq import Groq
from sqlalchemy import create_engine
from agno.models.nvidia import Nvidia
from agno.models.google import Gemini
from agno.models.aws import AwsBedrock
from agno.models.openai import OpenAILike
from langtrace_python_sdk import langtrace
from sqlalchemy.orm import registry, sessionmaker

load_dotenv()
SQLALCHEMY_DATABASE_URL = "sqlite:///database/database.sqlite3"

# langtrace.init(
#     api_key="e46c7e7a3da2478c4864f3c46beab8a00416a4fbfcfd175390e159e731b97a91"
# )

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
    if "sqlite" in SQLALCHEMY_DATABASE_URL
    else {},
)

# ai_engine_open = Nvidia(
#     id="moonshotai/kimi-k2-instruct", api_key=os.getenv("NVIDIA_KEY")
# )
# ai_engine_open = Gemini(id="gemini-3-flash", api_key=os.getenv("GOOGLE_KEY"))
# ai_engine_open = OpenAILike(
#     id="google/gemma-3-27b-instruct/bf-16",
#     api_key=os.getenv("INFERENCE_KEY"),
#     base_url="https://api.inference.net/v1",
# )
# ai_engine_open = Groq(id="groq/compound", api_key=os.getenv("GROQ_KEY"))

ai_engine_pro = AwsBedrock(
    top_p=1.0,
    temperature=0.1,
    aws_region=os.getenv("AWS_REGION"),
    id=os.getenv("AMAZON_MODEL_ID_PRO"),
    aws_access_key_id=os.getenv("AMAZON_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AMAZON_SECRET_ACCESS_KEY"),
)

ai_engine_lite = AwsBedrock(
    top_p=1.0,
    temperature=0.1,
    aws_region=os.getenv("AWS_REGION"),
    id=os.getenv("AMAZON_MODEL_ID_LITE"),
    aws_access_key_id=os.getenv("AMAZON_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AMAZON_SECRET_ACCESS_KEY"),
)

ai_engine_reason = AwsBedrock(
    id="google.gemma-3-27b-it",
    aws_region=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AMAZON_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AMAZON_SECRET_ACCESS_KEY"),
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
mapper_registry = registry()
Base = mapper_registry.generate_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
