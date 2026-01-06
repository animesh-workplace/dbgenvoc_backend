import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from agno.models.aws import AwsBedrock
from langtrace_python_sdk import langtrace
from sqlalchemy.orm import registry, sessionmaker
# from sqlalchemy.ext.declarative import declarative_base

load_dotenv()
SQLALCHEMY_DATABASE_URL = "sqlite:///database/database.sqlite3"

langtrace.init(
    api_key="e46c7e7a3da2478c4864f3c46beab8a00416a4fbfcfd175390e159e731b97a91"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
    if "sqlite" in SQLALCHEMY_DATABASE_URL
    else {},
)

ai_engine_pro = AwsBedrock(
    id=os.getenv("AMAZON_MODEL_ID_PRO"),
    aws_region=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AMAZON_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AMAZON_SECRET_ACCESS_KEY"),
)

ai_engine_lite = AwsBedrock(
    id=os.getenv("AMAZON_MODEL_ID_LITE"),
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
