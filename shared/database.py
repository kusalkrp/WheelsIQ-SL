"""
Prime Wheels SL — Database engine & session factories.
Provides both async (for API/scraper) and sync (for dashboard/Celery) sessions.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.config import get_settings

settings = get_settings()

# ── Async engine (FastAPI, async scraper) ──
async_engine = create_async_engine(
    settings.database_url,
    echo=(settings.app_env == "development"),
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Sync engine (Streamlit dashboard, Celery workers) ──
sync_engine = create_engine(
    settings.sync_database_url,
    echo=False,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncSession:
    """Dependency for FastAPI endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_session() -> Session:
    """For Streamlit and Celery workers."""
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()
