"""
Database setup for CryptoSage.

Defines the SQLAlchemy engine, session factory, and declarative base used
throughout the application, along with a FastAPI dependency for obtaining
a database session per request.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings

settings = get_settings()

# The engine manages the connection pool to the PostgreSQL database.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# SessionLocal is a factory for creating new database sessions.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class that all SQLAlchemy models inherit from."""
    pass


def get_db() -> Generator:
    """FastAPI dependency that provides a database session.

    Yields a session for use within a request and guarantees it is closed
    afterwards, even if an error occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
