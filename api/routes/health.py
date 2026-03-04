"""
Prime Wheels SL — Health check endpoint.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from api.models import HealthResponse
from shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check health of all services."""
    db_status = "unknown"
    redis_status = "unknown"
    qdrant_status = "unknown"

    # Check PostgreSQL
    try:
        from shared.database import async_engine
        from sqlalchemy import text
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    # Check Redis
    try:
        from rag.cag_cache import get_redis_client
        client = get_redis_client()
        client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {e}"

    # Check Qdrant
    try:
        from ingestion.qdrant_indexer import get_qdrant_client
        client = get_qdrant_client()
        client.get_collections()
        qdrant_status = "healthy"
    except Exception as e:
        qdrant_status = f"unhealthy: {e}"

    overall = "healthy" if all(
        s == "healthy" for s in [db_status, redis_status, qdrant_status]
    ) else "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        qdrant=qdrant_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
