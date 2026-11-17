import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

db_url = settings.effective_database_url

# Configure engine arguments depending on DB dialect
engine_kwargs = {
    "echo": settings.DEBUG,
}

if db_url.startswith("sqlite"):
    # SQLite requires check_same_thread=False for FastAPI multithreaded requests
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / Aurora connection pooling options
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(db_url, **engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy database models."""
    pass


def get_db():
    """
    FastAPI dependency that yields an isolated database session per request.
    Ensures safe session lifecycle and closes session upon completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
