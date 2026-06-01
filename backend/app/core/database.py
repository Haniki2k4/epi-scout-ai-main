import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[3]

# Load the repository-level .env regardless of the current working directory.
load_dotenv(ROOT_DIR / ".env")

# Prefer a full DATABASE_URL when provided. Otherwise build a local MySQL URL.
SERVER_NAME = os.getenv("DB_SERVER", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DATABASE_NAME = os.getenv("DB_NAME", "EpiScoutDB")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = os.getenv("DATABASE_URL")
DB_SSL = os.getenv("DB_SSL", "false").lower() == "true"

if DATABASE_URL:
    # Ensure it uses pymysql driver if only mysql:// is provided
    if DATABASE_URL.startswith("mysql://"):
        DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)
        
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    connect_args = {}
    if "tidb" in DATABASE_URL or "ssl" in DATABASE_URL or DB_SSL:
        connect_args = {"ssl": {}}
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
        pool_recycle=300,
        connect_args=connect_args,
    )
else:
    SQLALCHEMY_DATABASE_URL = str(
        URL.create(
            drivername="mysql+pymysql",
            username=DB_USER,
            password=DB_PASSWORD,
            host=SERVER_NAME,
            port=int(DB_PORT),
            database=DATABASE_NAME,
        )
    )
    # Use a direct PyMySQL creator for local env-driven config.
    # This avoids SQLAlchemy DSN parsing/auth edge cases while keeping the
    # connection settings in one place.
    connect_kwargs = {
        "host": SERVER_NAME,
        "port": int(DB_PORT),
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": DATABASE_NAME,
    }
    if DB_SSL or "tidb" in SERVER_NAME:
        connect_kwargs["ssl"] = {}

    engine = create_engine(
        "mysql+pymysql://",
        creator=lambda: pymysql.connect(**connect_kwargs),
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
        pool_recycle=300,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
