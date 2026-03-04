"""
Prime Wheels SL — SQLAlchemy ORM models matching the PostgreSQL schema.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, Integer, Numeric,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    riyasewana_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="cars")

    # Identity
    title: Mapped[str] = mapped_column(Text, nullable=False)
    make: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(200))
    year: Mapped[Optional[int]] = mapped_column(Integer)
    body_type: Mapped[Optional[str]] = mapped_column(String(50))

    # Pricing
    price_lkr: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    price_currency: Mapped[str] = mapped_column(String(10), default="LKR")
    is_negotiable: Mapped[bool] = mapped_column(Boolean, default=False)

    # Core specs
    yom: Mapped[Optional[int]] = mapped_column(Integer)
    mileage_km: Mapped[Optional[int]] = mapped_column(Integer)
    transmission: Mapped[Optional[str]] = mapped_column(String(50))
    fuel_type: Mapped[Optional[str]] = mapped_column(String(50))
    engine_cc: Mapped[Optional[int]] = mapped_column(Integer)
    color: Mapped[Optional[str]] = mapped_column(String(50))
    condition: Mapped[Optional[str]] = mapped_column(String(50))

    # Location
    location_raw: Mapped[Optional[str]] = mapped_column(Text)
    district: Mapped[Optional[str]] = mapped_column(String(100))
    province: Mapped[Optional[str]] = mapped_column(String(100))

    # Rich text & features
    options: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    description: Mapped[Optional[str]] = mapped_column(Text)
    features_extracted: Mapped[Optional[dict]] = mapped_column(JSONB, default={})

    # Seller
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    seller_name: Mapped[Optional[str]] = mapped_column(String(200))
    is_dealer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium_ad: Mapped[bool] = mapped_column(Boolean, default=False)

    # Engagement
    view_count: Mapped[int] = mapped_column(Integer, default=0)

    # Media
    images: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Raw data
    raw_html: Mapped[Optional[str]] = mapped_column(Text)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, default={})

    def __repr__(self) -> str:
        return f"<Vehicle {self.riyasewana_id}: {self.make} {self.model} {self.yom}>"


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), unique=True, nullable=False, default=lambda: str(uuid4())
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    pages_scraped: Mapped[int] = mapped_column(Integer, default=0)
    listings_found: Mapped[int] = mapped_column(Integer, default=0)
    listings_new: Mapped[int] = mapped_column(Integer, default=0)
    listings_updated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[dict]] = mapped_column(JSONB, default=[])
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<ScrapeJob {self.job_id}: {self.category} [{self.status}]>"


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[Optional[str]] = mapped_column(String(20))
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_type: Mapped[Optional[str]] = mapped_column(String(20))
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    num_docs_retrieved: Mapped[Optional[int]] = mapped_column(Integer)
    avg_relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    crag_rewrite: Mapped[bool] = mapped_column(Boolean, default=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(50))
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float)
    user_feedback: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LocationMapping(Base):
    __tablename__ = "location_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_location: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    district: Mapped[str] = mapped_column(Text, nullable=False)
    province: Mapped[str] = mapped_column(Text, nullable=False)
