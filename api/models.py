"""
Prime Wheels SL — Pydantic request/response schemas for the API.
"""

from pydantic import BaseModel, Field


# ── Request Schemas ──
class QueryRequest(BaseModel):
    """RAG query request."""
    query: str = Field(..., min_length=3, max_length=500, description="Natural language query")
    filters: dict | None = Field(None, description="Optional Qdrant filters")
    top_k: int = Field(20, ge=1, le=100, description="Number of documents to retrieve")
    skip_cache: bool = Field(False, description="Bypass cache for fresh results")


class SearchRequest(BaseModel):
    """Structured vehicle search."""
    make: str | None = None
    model: str | None = None
    year_min: int | None = Field(None, ge=1970)
    year_max: int | None = Field(None, le=2030)
    price_min: float | None = Field(None, ge=0)
    price_max: float | None = None
    fuel_type: str | None = None
    transmission: str | None = None
    district: str | None = None
    category: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort_by: str = Field("posted_at", description="Sort field")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")


class ScrapeRequest(BaseModel):
    """Manual scrape trigger."""
    category: str = Field("cars", description="Vehicle category to scrape")
    max_pages: int | None = Field(None, ge=1, le=500)


# ── Response Schemas ──
class VehicleSummary(BaseModel):
    """Vehicle in response."""
    make: str | None = None
    model: str | None = None
    year: int | None = None
    price_lkr: float | None = None
    url: str | None = None


class QueryResponse(BaseModel):
    """RAG query response."""
    answer: str
    vehicles_mentioned: list[VehicleSummary] = []
    confidence: float = 0.0
    follow_up_suggestions: list[str] = []
    query_type: str | None = None
    avg_relevance: float | None = None
    num_docs_retrieved: int | None = None
    crag_rewrite: bool = False
    cache_hit: bool = False
    cache_type: str = "miss"
    response_time_ms: int = 0
    model_used: str | None = None


class VehicleDetail(BaseModel):
    """Full vehicle detail response."""
    id: int
    riyasewana_id: int
    url: str
    category: str
    title: str
    make: str | None = None
    model: str | None = None
    year: int | None = None
    price_lkr: float | None = None
    is_negotiable: bool = False
    yom: int | None = None
    mileage_km: int | None = None
    transmission: str | None = None
    fuel_type: str | None = None
    engine_cc: int | None = None
    color: str | None = None
    condition: str | None = None
    location_raw: str | None = None
    district: str | None = None
    province: str | None = None
    options: list[str] | None = None
    description: str | None = None
    contact_phone: str | None = None
    images: list[str] | None = None
    thumbnail_url: str | None = None
    posted_at: str | None = None
    view_count: int = 0

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Paginated search results."""
    vehicles: list[VehicleDetail]
    total: int
    page: int
    page_size: int
    pages: int


class CacheStatsResponse(BaseModel):
    """Cache statistics."""
    exact_entries: int
    semantic_entries: int
    memory_used_mb: float
    ttl_seconds: int
    semantic_threshold: float


class MarketStatsResponse(BaseModel):
    """Aggregated market stats for dashboard."""
    total_listings: int
    avg_price: float | None
    median_mileage: int | None
    pct_hybrid: float | None
    pct_automatic: float | None
    top_make: str | None
    top_make_pct: float | None
    categories: dict | None = None


class HealthResponse(BaseModel):
    """Service health check."""
    status: str
    database: str
    redis: str
    qdrant: str
    timestamp: str
