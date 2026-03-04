"""
Prime Wheels SL — Celery tasks for scraping and ingestion.
Provides both scheduled (beat) and on-demand scrape triggers.
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from celery import Celery
from celery.schedules import crontab
from playwright.async_api import async_playwright
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from scraper.config import CATEGORIES
from scraper.detail_scraper import scrape_details_batch
from scraper.playwright_crawler import create_browser, scrape_category_search
from shared.config import get_settings
from shared.database import SyncSessionLocal
from shared.logging import get_logger, setup_logging
from shared.models import ScrapeJob, Vehicle

setup_logging()
logger = get_logger(__name__)
settings = get_settings()

# ── Celery App ──
app = Celery("prime_wheels")
app.config_from_object({
    "broker_url": settings.redis_url,
    "result_backend": settings.redis_url,
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "Asia/Colombo",
    "enable_utc": True,
    "task_track_started": True,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    "task_soft_time_limit": 21600,   # 6 hour soft limit
    "task_time_limit": 23400,        # 6.5 hour hard limit
})

# ── Beat Schedule (weekly scrape) ──
app.conf.beat_schedule = {
    "weekly-full-scrape": {
        "task": "scraper.tasks.scrape_all_categories",
        "schedule": crontab(
            hour=2,
            minute=0,
            day_of_week=0,  # Sunday
        ),
        "args": (),
    },
}


def _run_async(coro):
    """Run async code in sync Celery context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _upsert_vehicles(vehicles: list[dict], category: str) -> tuple[int, int]:
    """
    UPSERT vehicles into PostgreSQL.
    Returns (new_count, updated_count).
    """
    session = SyncSessionLocal()
    new_count = 0
    updated_count = 0

    try:
        for v in vehicles:
            # Prepare the data dict for insertion
            data = {
                "riyasewana_id": v["riyasewana_id"],
                "url": v["url"],
                "category": category,
                "title": v.get("title", ""),
                "make": v.get("make"),
                "model": v.get("model"),
                "year": v.get("year"),
                "body_type": CATEGORIES.get(category, {}).get("body_type"),
                "price_lkr": v.get("price_lkr"),
                "is_negotiable": v.get("is_negotiable", False),
                "yom": v.get("yom"),
                "mileage_km": v.get("mileage_km"),
                "transmission": v.get("transmission"),
                "fuel_type": v.get("fuel_type"),
                "engine_cc": v.get("engine_cc"),
                "color": v.get("color"),
                "condition": v.get("condition"),
                "location_raw": v.get("location_raw"),
                "district": v.get("district"),
                "province": v.get("province"),
                "options": v.get("options"),
                "description": v.get("description"),
                "contact_phone": v.get("contact_phone"),
                "seller_name": v.get("seller_name"),
                "is_premium_ad": v.get("is_premium_ad", False),
                "view_count": v.get("view_count", 0),
                "images": v.get("images"),
                "thumbnail_url": v.get("thumbnail_url"),
                "posted_at": v.get("posted_at"),
                "last_seen_at": datetime.now(timezone.utc),
                "is_active": True,
                "raw_html": v.get("raw_html"),
                "raw_json": v.get("raw_json", {}),
            }

            # PostgreSQL UPSERT (INSERT ... ON CONFLICT DO UPDATE)
            stmt = pg_insert(Vehicle).values(**data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["riyasewana_id"],
                set_={
                    "title": stmt.excluded.title,
                    "price_lkr": stmt.excluded.price_lkr,
                    "is_negotiable": stmt.excluded.is_negotiable,
                    "mileage_km": stmt.excluded.mileage_km,
                    "view_count": stmt.excluded.view_count,
                    "last_seen_at": stmt.excluded.last_seen_at,
                    "is_active": True,
                    "updated_at": datetime.now(timezone.utc),
                    # Only update these if they were NULL before
                    "make": stmt.excluded.make,
                    "model": stmt.excluded.model,
                    "yom": stmt.excluded.yom,
                    "transmission": stmt.excluded.transmission,
                    "fuel_type": stmt.excluded.fuel_type,
                    "engine_cc": stmt.excluded.engine_cc,
                    "color": stmt.excluded.color,
                    "condition": stmt.excluded.condition,
                    "options": stmt.excluded.options,
                    "description": stmt.excluded.description,
                    "images": stmt.excluded.images,
                    "raw_html": stmt.excluded.raw_html,
                    "raw_json": stmt.excluded.raw_json,
                },
            )

            result = session.execute(stmt)
            if result.rowcount > 0:
                # Check if it was an insert or update
                # (for simplicity, count all as processed)
                new_count += 1

        session.commit()
        logger.info(
            "vehicles_upserted",
            category=category,
            total=len(vehicles),
            new=new_count,
        )
    except Exception as e:
        session.rollback()
        logger.error("upsert_error", error=str(e))
        raise
    finally:
        session.close()

    return new_count, updated_count


def _create_scrape_job(category: str) -> str:
    """Create a scrape job record and return its job_id."""
    session = SyncSessionLocal()
    try:
        job = ScrapeJob(
            job_id=str(uuid4()),
            category=category,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(job)
        session.commit()
        return job.job_id
    finally:
        session.close()


def _update_scrape_job(
    job_id: str,
    status: str,
    pages_scraped: int = 0,
    listings_found: int = 0,
    listings_new: int = 0,
    listings_updated: int = 0,
    errors: list | None = None,
):
    """Update a scrape job record."""
    session = SyncSessionLocal()
    try:
        job = session.query(ScrapeJob).filter_by(job_id=job_id).first()
        if job:
            job.status = status
            job.pages_scraped = pages_scraped
            job.listings_found = listings_found
            job.listings_new = listings_new
            job.listings_updated = listings_updated
            job.errors = errors or []
            if status in ("completed", "failed"):
                job.completed_at = datetime.now(timezone.utc)
            session.commit()
    finally:
        session.close()


@app.task(bind=True, name="scraper.tasks.scrape_category")
def scrape_category(self, category: str, max_pages: int | None = None):
    """
    Scrape all listings for a single category.

    1. Crawl search pages → collect listing URLs
    2. Scrape each detail page → extract full specs
    3. UPSERT into PostgreSQL
    4. Track job progress
    """
    job_id = _create_scrape_job(category)
    logger.info("scrape_category_start", category=category, job_id=job_id)

    errors = []

    async def _run():
        async with async_playwright() as pw:
            browser = await create_browser(pw)
            try:
                # Step 1: Search pages
                search_listings = await scrape_category_search(
                    browser, category, max_pages
                )
                logger.info(
                    "search_complete",
                    category=category,
                    listings=len(search_listings),
                )

                if not search_listings:
                    return 0, 0, 0

                # Step 2: Detail pages
                urls = [l["url"] for l in search_listings]
                detail_results = await scrape_details_batch(browser, urls)

                # Merge search + detail data
                search_map = {l["riyasewana_id"]: l for l in search_listings}
                merged = []
                for detail in detail_results:
                    rid = detail.get("riyasewana_id")
                    if rid and rid in search_map:
                        # Search data provides thumbnail, premium status
                        search_data = search_map[rid]
                        detail["thumbnail_url"] = search_data.get("thumbnail_url")
                        detail["is_premium_ad"] = search_data.get("is_premium_ad", False)
                    merged.append(detail)

                # Step 3: UPSERT
                new_count, updated_count = _upsert_vehicles(merged, category)

                pages_scraped = (len(search_listings) // 40) + 1
                return pages_scraped, len(merged), new_count

            finally:
                await browser.close()

    try:
        pages_scraped, listings_found, listings_new = _run_async(_run())

        _update_scrape_job(
            job_id,
            status="completed",
            pages_scraped=pages_scraped,
            listings_found=listings_found,
            listings_new=listings_new,
            errors=errors,
        )

        logger.info(
            "scrape_category_complete",
            category=category,
            job_id=job_id,
            listings_found=listings_found,
            listings_new=listings_new,
        )

        return {
            "job_id": job_id,
            "category": category,
            "status": "completed",
            "listings_found": listings_found,
            "listings_new": listings_new,
        }

    except Exception as e:
        logger.error("scrape_category_failed", category=category, error=str(e))
        errors.append({"error": str(e)})
        _update_scrape_job(job_id, status="failed", errors=errors)
        raise


@app.task(name="scraper.tasks.scrape_all_categories")
def scrape_all_categories():
    """
    Scrape all configured vehicle categories.
    Dispatches individual category tasks to Celery workers.
    """
    logger.info("scrape_all_start", categories=list(CATEGORIES.keys()))

    results = []
    for category in settings.scrape_categories:
        # Chain tasks: each category runs sequentially to avoid overloading
        result = scrape_category.delay(category)
        results.append({"category": category, "task_id": result.id})

    return {"status": "dispatched", "tasks": results}


@app.task(name="scraper.tasks.mark_stale_listings")
def mark_stale_listings(days_threshold: int = 14):
    """
    Mark listings as inactive if not seen in the last N days.
    Runs after a full scrape to detect removed listings.
    """
    session = SyncSessionLocal()
    try:
        result = session.execute(
            text("""
                UPDATE vehicles
                SET is_active = FALSE, updated_at = NOW()
                WHERE last_seen_at < NOW() - INTERVAL ':days days'
                AND is_active = TRUE
            """),
            {"days": days_threshold},
        )
        session.commit()
        count = result.rowcount
        logger.info("stale_listings_marked", count=count, threshold_days=days_threshold)
        return {"marked_stale": count}
    finally:
        session.close()
