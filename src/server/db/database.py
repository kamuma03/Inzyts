"""
Database Configuration Module.

This module initializes the SQLAlchemy engines and session factories for
PostgreSQL interaction. It supports:
1. Async Engine (for FastAPI routes) using asyncpg.
2. Sync Engine (for Celery tasks) using psycopg2 (implicit).

Attributes:
    engine: Async engine instance.
    async_session_maker: Factory for creating AsyncSession instances.
    sync_engine: Sync engine instance.
    SessionLocal: Factory for creating sync Session instances.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import DeclarativeBase
from src.config import settings

# Async Engine
engine = create_async_engine(
    settings.db.url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
)

# Async Session Factory
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

# Sync Engine (for Celery)
sync_engine = create_engine(
    settings.db.sync_url,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


# Base Model
class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_maker() as session:
        yield session
