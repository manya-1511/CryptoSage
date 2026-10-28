
"""
Database setup for CryptoSage.

Defines the SQLAlchemy engine, session factory, declarative base, and
FastAPI dependency for obtaining a database session per request.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings

settings = get_settings()

engine_options = {
    "pool_pre_ping": True,
}

# SQLite may use a different pool implementation, so apply the configurable
# connection-pool settings only to non-SQLite database URLs.
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_options.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT_SECONDS,
            "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
        }
    )

engine = create_engine(settings.DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Base class that all SQLAlchemy models inherit from."""

    pass


def get_db() -> Generator:
    """Provide a database session and always close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
