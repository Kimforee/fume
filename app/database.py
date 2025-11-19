from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

# Async database URL for FastAPI
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/product_importer")

# Sync database URL for Alembic migrations
DATABASE_URL_SYNC = os.getenv("DATABASE_URL_SYNC", "postgresql://user:password@localhost:5432/product_importer")

# Async engine for FastAPI
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Sync engine for Alembic
sync_engine = create_engine(
    DATABASE_URL_SYNC,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factories
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)

# Base class for models
Base = declarative_base()


# Dependency for FastAPI to get async database session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Dependency for sync operations (like Alembic migrations)
def get_sync_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

