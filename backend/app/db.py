from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import time

DB_USER = os.getenv("POSTGRES_USER", "helpdesk")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "helpdesk")
DB_HOST = os.getenv("POSTGRES_HOST", "db")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "helpdesk")

SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine with connection pool settings for resilience
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,  # Check connection before using
    pool_recycle=300,    # Recycle connections every 5 minutes
    pool_size=5,
    max_overflow=10,
    connect_args={"connect_timeout": 10}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def wait_for_db(max_retries=30, delay=2):
    """Wait for database to be available"""
    import psycopg2
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASS,
                dbname=DB_NAME,
                connect_timeout=5
            )
            conn.close()
            print(f"[DB] Connected to database successfully")
            return True
        except Exception as e:
            print(
                f"[DB] Waiting for database (attempt {attempt + 1}/{max_retries}): {e}")
            time.sleep(delay)
    raise Exception("Could not connect to database after maximum retries")
