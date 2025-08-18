import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base

# For MySQL (original)
# SQLALCHEMY_DATABASE_URL = "mysql://user:password@localhost/oralcancerdb"

# For SQLite (converted)
SQLALCHEMY_DATABASE_URL = "sqlite:///database/database.sqlite3"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
    if "sqlite" in SQLALCHEMY_DATABASE_URL
    else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
