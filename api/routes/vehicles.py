"""
Prime Wheels SL — Vehicle detail and stats endpoints.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from api.models import MarketStatsResponse, VehicleDetail
from shared.database import SyncSessionLocal
from shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/vehicles/{vehicle_id}", response_model=VehicleDetail)
async def get_vehicle(vehicle_id: int):
    """Get a single vehicle by database ID."""
    session = SyncSessionLocal()
    try:
        result = session.execute(
            text("SELECT * FROM vehicles WHERE id = :id"),
            {"id": vehicle_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        r = dict(row._mapping)
        return VehicleDetail(
            id=r["id"],
            riyasewana_id=r["riyasewana_id"],
            url=r["url"],
            category=r["category"],
            title=r["title"],
            make=r.get("make"),
            model=r.get("model"),
            year=r.get("year"),
            price_lkr=float(r["price_lkr"]) if r.get("price_lkr") else None,
            is_negotiable=r.get("is_negotiable", False),
            yom=r.get("yom"),
            mileage_km=r.get("mileage_km"),
            transmission=r.get("transmission"),
            fuel_type=r.get("fuel_type"),
            engine_cc=r.get("engine_cc"),
            color=r.get("color"),
            condition=r.get("condition"),
            location_raw=r.get("location_raw"),
            district=r.get("district"),
            province=r.get("province"),
            options=r.get("options"),
            description=r.get("description"),
            contact_phone=r.get("contact_phone"),
            images=r.get("images"),
            thumbnail_url=r.get("thumbnail_url"),
            posted_at=str(r["posted_at"]) if r.get("posted_at") else None,
            view_count=r.get("view_count", 0),
        )
    finally:
        session.close()


@router.get("/vehicles/stats", response_model=MarketStatsResponse)
async def get_market_stats():
    """Get aggregated market statistics."""
    session = SyncSessionLocal()
    try:
        stats = session.execute(text("""
            SELECT
                COUNT(*) as total,
                AVG(price_lkr) as avg_price,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mileage_km) as median_mileage,
                COUNT(*) FILTER (WHERE LOWER(fuel_type) LIKE '%hybrid%') * 100.0 / NULLIF(COUNT(*), 0) as pct_hybrid,
                COUNT(*) FILTER (WHERE LOWER(transmission) = 'automatic') * 100.0 / NULLIF(COUNT(*), 0) as pct_auto,
                MODE() WITHIN GROUP (ORDER BY make) as top_make
            FROM vehicles
            WHERE is_active = TRUE AND price_lkr IS NOT NULL
        """)).fetchone()

        r = dict(stats._mapping)

        # Get top make percentage
        top_make_pct = None
        if r.get("top_make"):
            top_pct = session.execute(
                text("""
                    SELECT COUNT(*) * 100.0 / (SELECT COUNT(*) FROM vehicles WHERE is_active = TRUE)
                    FROM vehicles WHERE is_active = TRUE AND make = :make
                """),
                {"make": r["top_make"]},
            ).scalar()
            top_make_pct = round(float(top_pct), 1) if top_pct else None

        # Get category breakdown
        cats = session.execute(text("""
            SELECT category, COUNT(*) as count
            FROM vehicles WHERE is_active = TRUE
            GROUP BY category ORDER BY count DESC
        """))
        categories = {row.category: row.count for row in cats}

        return MarketStatsResponse(
            total_listings=r["total"] or 0,
            avg_price=round(float(r["avg_price"]), 2) if r.get("avg_price") else None,
            median_mileage=int(r["median_mileage"]) if r.get("median_mileage") else None,
            pct_hybrid=round(float(r["pct_hybrid"]), 1) if r.get("pct_hybrid") else None,
            pct_automatic=round(float(r["pct_auto"]), 1) if r.get("pct_auto") else None,
            top_make=r.get("top_make"),
            top_make_pct=top_make_pct,
            categories=categories,
        )
    finally:
        session.close()
