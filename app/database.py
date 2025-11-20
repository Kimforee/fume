from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from contextlib import asynccontextmanager
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from dotenv import load_dotenv

load_dotenv()

def clean_asyncpg_url(url: str) -> tuple[str, dict]:
    """
    Clean database URL for asyncpg compatibility.
    Removes ALL query params (asyncpg doesn't support most psycopg2-style params)
    and converts sslmode to connect_args format.
    Returns (cleaned_url, connect_args_dict)
    """
    if not url.startswith("postgresql+asyncpg://"):
        return url, {}
    
    # Parse the URL
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    # Extract sslmode if present and convert to connect_args
    # asyncpg doesn't support query parameters, so we remove them all
    connect_args = {}
    if 'sslmode' in query_params:
        sslmode = query_params.pop('sslmode')[0]
        # Convert sslmode to asyncpg's SSL format
        # asyncpg uses ssl=True for SSL connections, ssl=False to disable
        if sslmode == 'disable':
            connect_args['ssl'] = False
        else:
            # For require, prefer, allow, or any other mode, enable SSL
            connect_args['ssl'] = True
    
    # Remove ALL query parameters - asyncpg doesn't support them in the URL
    # Rebuild URL without any query params
    new_parsed = parsed._replace(query='')
    cleaned_url = urlunparse(new_parsed)
    
    return cleaned_url, connect_args

# Async database URL for FastAPI
raw_database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/product_importer")
DATABASE_URL, asyncpg_connect_args = clean_asyncpg_url(raw_database_url)

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
    connect_args=asyncpg_connect_args if asyncpg_connect_args else {},
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

