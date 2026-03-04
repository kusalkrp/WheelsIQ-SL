"""
Prime Wheels SL — Structured search endpoint.
Filter vehicles from PostgreSQL with pagination and sorting.
"""

import math

from fastapi import APIRouter
from sqlalchemy import text

from api.models import SearchRequest, SearchResponse, VehicleDetail
from shared.database import SyncSessionLocal
from shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/search", response_model=SearchResponse)
async def search_vehicles(
    make: str | None = None,
    model: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    fuel_type: str | None = None,
    transmission: str | None = None,
    district: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "posted_at",
    sort_order: str = "desc",
):
    """Search vehicles with structured filters."""
    session = SyncSessionLocal()
    try:
        # Build WHERE clauses
        conditions = ["is_active = TRUE"]
        params = {}

        if make:
            conditions.append("LOWER(make) = LOWER(:make)")
            params["make"] = make
        if model:
            conditions.append("LOWER(model) LIKE LOWER(:model)")
            params["model"] = f"%{model}%"
        if year_min:
            conditions.append("yom >= :year_min")
            params["year_min"] = year_min
        if year_max:
            conditions.append("yom <= :year_max")
            params["year_max"] = year_max
        if price_min:
            conditions.append("price_lkr >= :price_min")
            params["price_min"] = price_min
        if price_max:
            conditions.append("price_lkr <= :price_max")
            params["price_max"] = price_max
        if fuel_type:
            conditions.append("LOWER(fuel_type) = LOWER(:fuel_type)")
            params["fuel_type"] = fuel_type
        if transmission:
            conditions.append("LOWER(transmission) = LOWER(:transmission)")
            params["transmission"] = transmission
        if district:
            conditions.append("LOWER(district) = LOWER(:district)")
            params["district"] = district
        if category:
            conditions.append("category = :category")
            params["category"] = category

        where_clause = " AND ".join(conditions)

        # Validate sort field
        valid_sorts = {"posted_at", "price_lkr", "yom", "mileage_km", "created_at"}
        if sort_by not in valid_sorts:
            sort_by = "posted_at"
        sort_dir = "DESC" if sort_order == "desc" else "ASC"

        # Count total
        count_query = f"SELECT COUNT(*) FROM vehicles WHERE {where_clause}"
        total = session.execute(text(count_query), params).scalar()

        # Fetch page
        offset = (page - 1) * page_size
        data_query = f"""
            SELECT * FROM vehicles
            WHERE {where_clause}
            ORDER BY {sort_by} {sort_dir} NULLS LAST
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = offset

        rows = session.execute(text(data_query), params)
        vehicles = []
        for row in rows:
            r = dict(row._mapping)
            vehicles.append(VehicleDetail(
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
            ))

        return SearchResponse(
            vehicles=vehicles,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    finally:
        session.close()
