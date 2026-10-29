import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables from .env file (looks in current working directory and backend directory)
load_dotenv()

# Read individual database connection parameters from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "medishop")

# Build the MySQL connection URL safely (escapes special characters in the password)
# Format: mysql+pymysql://<user>:<password>@<host>:<port>/<dbname>
encoded_password = quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Create the SQLAlchemy engine
# pool_pre_ping=True checks the health of existing pool connections before using them
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# SessionLocal class will be used in future steps to create database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for future SQLAlchemy declarative models
Base = declarative_base()


def get_db():
    """FastAPI dependency to yield a database session per request and close it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection():
    """
    Tests the connection to MySQL by executing a lightweight query ('SELECT 1').
    Returns a tuple: (is_connected: bool, error_message: str | None)
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)

