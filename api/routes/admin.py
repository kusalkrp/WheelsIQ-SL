"""
Prime Wheels SL — Admin endpoints (scrape trigger, cache management).
"""

import asyncio

from celery import Celery
from fastapi import APIRouter

from api.models import CacheStatsResponse, ScrapeRequest
from rag.cag_cache import flush_cache, get_cache_stats
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()

# Celery app reference (send tasks by name — no need to import scraper module)
_celery_app = Celery("prime_wheels", broker=settings.redis_url, backend=settings.redis_url)


@router.post("/scrape/trigger")
async def trigger_scrape(request: ScrapeRequest):
    """Manually trigger a scrape for a category."""
    logger.info("manual_scrape_triggered", category=request.category)
    result = _celery_app.send_task(
        "scraper.tasks.scrape_category",
        kwargs={
            "category": request.category,
            "max_pages": request.max_pages,
        },
    )
    return {
        "status": "dispatched",
        "task_id": result.id,
        "category": request.category,
    }


@router.get("/scrape/status/{task_id}")
async def scrape_status(task_id: str):
    """Check the status of a scrape task."""
    result = _celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def cache_stats():
    """Get CAG cache statistics."""
    stats = await asyncio.to_thread(get_cache_stats)
    return CacheStatsResponse(**stats)


@router.post("/cache/flush")
async def flush_cag_cache():
    """Flush all CAG cache entries."""
    deleted = await asyncio.to_thread(flush_cache)
    return {"status": "flushed", "entries_deleted": deleted}
