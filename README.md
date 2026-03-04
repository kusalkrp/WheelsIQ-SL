# Prime Wheels SL

> **Sri Lanka's most intelligent used vehicle market assistant** — powered by Corrective RAG, Google Gemini, and real-time riyasewana.com data.

Prime Wheels SL is a production-grade AI system that scrapes the entire Sri Lankan used vehicle marketplace, indexes every listing into a vector database, and answers natural-language queries with pinpoint accuracy — respecting price limits, districts, fuel types, makes, and more, without hallucination.

---

## Table of Contents

- [Purpose](#purpose)
- [Features](#features)
- [System Architecture](#system-architecture)
- [CRAG Pipeline — Detailed Flow](#crag-pipeline--detailed-flow)
- [CAG Cache Architecture](#cag-cache-architecture)
- [Constraint Extractor](#constraint-extractor)
- [Component Deep-Dive](#component-deep-dive)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [Deployment](#deployment)
- [Evaluation](#evaluation)
- [Cost](#cost)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)

---

## Purpose

Sri Lanka's used vehicle market is fragmented. riyasewana.com hosts tens of thousands of listings but offers only basic keyword search — no price-aware filtering, no natural-language queries, no market intelligence.

Prime Wheels SL solves this by:

- **Scraping** every listing (cars, SUVs, vans, motorcycles, lorries, pickups, three-wheelers, heavy-duties) weekly with Playwright
- **Indexing** every listing as a semantic vector in Qdrant with full payload metadata
- **Answering** natural language questions like *"Best hybrid under Rs. 5 million in Colombo?"* with verified, constraint-accurate responses
- **Never fabricating** — answers cite only real listings with prices, mileage, and listing URLs
- **Correcting itself** — Corrective RAG rewrites poorly-matched queries and re-retrieves automatically

---

## Features

| Feature | Detail |
|---|---|
| Natural language queries | Ask anything about the market in plain English |
| Constraint-aware retrieval | Price, district, fuel type, make, year, mileage — enforced at the Qdrant filter level before the LLM sees results |
| Ranking queries | "Highest mileage", "cheapest", "newest" — docs sorted by actual field value before synthesis |
| CRAG correction | Automatic query rewrite + re-retrieval when avg relevance < 0.4 |
| Dual-layer cache | Exact hash match (< 1ms, free) + semantic similarity match (fast, free), with smart bypass for numeric constraints |
| LLM-free constraint extraction | 100% regex — no API call needed to detect price / year / location / fuel / make / ranking intent |
| Structured search API | SQL-powered filtered search with pagination and multi-field sorting |
| Live market dashboard | Pricing trends, regional breakdowns, best-value rankings, and a full chat interface |
| Automated weekly scraping | Celery Beat schedule, random delays, user-agent rotation, resource blocking |
| Full query analytics | Every query logged: response time, relevance score, cache type, model used, CRAG rewrites |

---

## System Architecture

```
╔═════════════════════════════════════════════════════════════════════╗
║                          PRIME WHEELS SL                           ║
╠═════════════════════════════════════════════════════════════════════╣
║                                                                     ║
║   USER INTERFACES                                                   ║
║   ┌─────────────────────────┐    ┌────────────────────────────┐    ║
║   │  Streamlit Dashboard     │    │  FastAPI REST API           │    ║
║   │  :8501                   │    │  :8000                      │    ║
║   │                          │    │                             │    ║
║   │  Market Overview         │    │  POST /api/v1/query         │    ║
║   │  Pricing Charts          │    │  GET  /api/v1/search        │    ║
║   │  Regional Maps           │    │  GET  /api/v1/vehicles      │    ║
║   │  Best Value Ranker       │    │  POST /api/v1/scrape/trigger│    ║
║   │  Chat (RAG)              │    │  GET  /api/v1/health        │    ║
║   │  Market Trends           │    │  GET  /docs  (Swagger UI)   │    ║
║   └────────────┬────────────┘    └───────────────┬─────────────┘    ║
║                │                                 │                  ║
╠════════════════╪═════════════════════════════════╪══════════════════╣
║                │       CRAG PIPELINE             │                  ║
║                └──────────────┬──────────────────┘                  ║
║                               │                                     ║
║   ┌───────────────────────────▼───────────────────────────────┐    ║
║   │                                                            │    ║
║   │  Query ──► Constraint ──► CAG Cache  ──► Qdrant Search    │    ║
║   │            Extractor      (Redis)         (Dense + Filter) │    ║
║   │            (regex)                                         │    ║
║   │                                   ┌──────────────────────┐ │    ║
║   │                                   │  Document Grader      │ │    ║
║   │                                   │  (Gemini Flash)       │ │    ║
║   │                                   │  top 5 docs graded    │ │    ║
║   │                                   │  hard constraint rules│ │    ║
║   │                                   └──────────┬───────────┘ │    ║
║   │                                              │              │    ║
║   │                               avg_relevance < 0.4?         │    ║
║   │                               ┌──────────────┤              │    ║
║   │                              YES              NO             │    ║
║   │                               │               │              │    ║
║   │                    ┌──────────▼──────┐        │              │    ║
║   │                    │  Query Rewriter  │        │              │    ║
║   │                    │  (Gemini Flash)  │        │              │    ║
║   │                    │  re-embed, retry │        │              │    ║
║   │                    └──────────┬───────┘        │              │    ║
║   │                               └────────────────┘              │    ║
║   │                                              │                │    ║
║   │                               Ranking sort if needed          │    ║
║   │                               (highest/lowest/newest/cheapest)│    ║
║   │                                              │                │    ║
║   │                              ┌───────────────▼─────────────┐ │    ║
║   │                              │  Synthesizer (Gemini Flash)  │ │    ║
║   │                              │  constraint-aware prompt     │ │    ║
║   │                              │  table format for comparisons│ │    ║
║   │                              │  includes listing URLs       │ │    ║
║   │                              └───────────────┬─────────────┘ │    ║
║   │                                              │                │    ║
║   │                              Cache result + Log query (async) │    ║
║   └──────────────────────────────────────────────────────────────┘    ║
║                                                                     ║
╠═════════════════════════════════════════════════════════════════════╣
║                                                                     ║
║   DATA STORES                       SCRAPE & INGEST PIPELINE        ║
║   ┌─────────────────────┐           ┌──────────────────────────┐   ║
║   │  PostgreSQL 16       │           │  riyasewana.com          │   ║
║   │  vehicles            │           │  8 categories × 500 pages│   ║
║   │  scrape_jobs         │           │         │                │   ║
║   │  query_logs          │           │  Playwright Crawler      │   ║
║   │  location_mappings   │           │  (headless Chromium)     │   ║
║   └─────────────────────┘           │  stealth + rotating UA   │   ║
║                                     │  3–8s random delay       │   ║
║   ┌─────────────────────┐           │         │                │   ║
║   │  Qdrant 1.12         │           │  Parse + Validate + UPSERT│  ║
║   │  Collection: vehicles│           │  (PostgreSQL)            │   ║
║   │  3072-dim COSINE     │           │         │                │   ║
║   │  Payload indexes:    │           │  Document Builder        │   ║
║   │  make, yom, price,   │           │  (structured text)       │   ║
║   │  fuel, district, …   │           │         │                │   ║
║   └─────────────────────┘           │  Gemini Embedding        │   ║
║                                     │  (gemini-embedding-001)  │   ║
║   ┌─────────────────────┐           │  3072-dim vectors        │   ║
║   │  Redis 7             │           │         │                │   ║
║   │  exact cache (SHA256)│           │  Qdrant Upsert           │   ║
║   │  semantic cache      │           │  (batch 100 points)      │   ║
║   │  celery broker       │           │         │                │   ║
║   │  celery result backend│          │  Celery Beat Schedule    │   ║
║   └─────────────────────┘           │  Every Sunday @ 02:00    │   ║
║                                     │  Asia/Colombo UTC+5:30   │   ║
║                                     └──────────────────────────┘   ║
╚═════════════════════════════════════════════════════════════════════╝
```

---

## CRAG Pipeline — Detailed Flow

```
User Query: "Best hybrid under Rs. 5 million in Colombo"
      │
      ▼
 ┌──────────────────────────────────┐
 │  Step 1: Embed Query             │
 │  model: gemini-embedding-001     │
 │  output: 3072-dim float vector   │
 └──────────────┬───────────────────┘
                │
                ▼
 ┌──────────────────────────────────┐
 │  Step 2: Extract Constraints     │  ← zero LLM cost, pure regex
 │                                  │
 │  price_lkr:  { lte: 5,000,000 } │
 │  fuel_type:  "Hybrid"            │
 │  district:   "Colombo"           │
 │                                  │
 │  skip_semantic_cache = TRUE      │  ← any constraint present
 └──────────────┬───────────────────┘
                │
                ▼
 ┌──────────────────────────────────┐
 │  Step 3: CAG Cache Check         │
 │                                  │
 │  3a. Exact match                 │  ─── HIT → return in < 1ms
 │      key: SHA256(normalized q)   │
 │                                  │
 │  3b. Semantic match              │  ─── SKIPPED (has constraints)
 │      cosine > 0.92               │       prevents "5M" answer
 │      capped at 100 entries       │       for "10M" query
 │                                  │
 │  MISS → continue pipeline        │
 └──────────────┬───────────────────┘
                │
                ▼
 ┌──────────────────────────────────┐
 │  Step 4: Qdrant Dense Search     │
 │                                  │
 │  vector: pre-computed (Step 1)   │  ← no re-embedding
 │  payload filters:                │
 │    price_lkr  ≤ 5,000,000        │
 │    fuel_type  == "Hybrid"        │
 │    district   == "Colombo"       │
 │  top_k: 20                       │
 │                                  │
 │  Fallback if 0 results:          │
 │    1. Retry without district     │
 │    2. Retry without all filters  │
 └──────────────┬───────────────────┘
                │
                ▼
 ┌──────────────────────────────────┐
 │  Step 5: Grade Documents         │
 │  model: gemini-2.5-flash         │
 │  thinking_budget: 0 (disabled)   │
 │  max_output_tokens: 1024         │
 │                                  │
 │  Grades top 5 via LLM:           │
 │    Hard violations → 0.0:        │
 │      price > stated limit        │
 │      wrong fuel type             │
 │      wrong make/brand            │
 │      year outside stated range   │
 │    Location mismatch → -0.2/-0.3 │
 │                                  │
 │  Docs 6–20: fallback grade 0.5   │  ← rate limit prevention
 └──────────────┬───────────────────┘
                │
       avg_relevance < 0.4?
         ┌──────┴──────┐
        YES             NO
         │              │
         ▼              │
 ┌──────────────────┐   │
 │  Step 6: CRAG    │   │
 │  Correction      │   │
 │                  │   │
 │  Rewrite query   │   │
 │  (Gemini Flash)  │   │
 │  preserving all  │   │
 │  constraints     │   │
 │                  │   │
 │  Re-embed        │   │
 │  Re-retrieve     │   │
 │  Re-grade        │   │
 │  (max 1 rewrite) │   │
 └───────┬──────────┘   │
         └──────┬────────┘
                │
                ▼
 ┌──────────────────────────────────┐
 │  Step 7: Filter + Rank           │
 │                                  │
 │  Keep docs with relevance ≥ 0.3  │
 │  Fallback: top 5 if all < 0.3   │
 │                                  │
 │  Ranking sort if detected:       │
 │    "highest mileage" → DESC km   │
 │    "cheapest"        → ASC price │
 │    "newest"          → DESC yom  │
 │    "oldest/vintage"  → ASC yom   │
 └──────────────┬───────────────────┘
                │
                ▼
 ┌──────────────────────────────────┐
 │  Step 8: Synthesize Answer       │
 │  model: gemini-2.5-flash         │
 │  max_output_tokens: 8192         │
 │  thinking_budget: 0              │
 │                                  │
 │  Receives constraint block:      │
 │    Price: under Rs. 5,000,000    │
 │    Fuel type: Hybrid             │
 │    Location: Colombo district    │
 │                                  │
 │  Rules enforced:                 │
 │    Never change user's budget    │
 │    Always include listing URLs   │
 │    Table format for comparisons  │
 │    Label out-of-budget as such   │
 └──────────────┬───────────────────┘
                │
                ▼
 ┌──────────────────────────────────┐
 │  Step 9: Cache Result            │
 │  Exact cache: always stored      │
 │  Semantic:    SKIPPED            │  ← has constraints
 │  Both fire-and-forget (async)    │
 └──────────────┬───────────────────┘
                │
                ▼
 ┌──────────────────────────────────┐
 │  Step 10: Log Query (async)      │
 │  Table: query_logs               │
 │  Logs: response_time, relevance, │
 │  cache_type, crag_rewrite, cost  │
 └──────────────────────────────────┘
```

---

## CAG Cache Architecture

```
                    Query arrives
                         │
              ┌──────────▼──────────┐
              │  Extract Constraints │
              │  has any constraint? │
              │  → skip_semantic=T/F │
              └──────────┬───────────┘
                         │
 ┌───────────────────────▼──────────────────────────────┐
 │                  EXACT CACHE (Redis)                  │
 │                                                       │
 │  key:  cag:exact:{ SHA256(query.lower().strip()) }    │
 │  TTL:  24 hours                                       │
 │  cost: 0 API calls                                    │
 │  time: < 1ms                                          │
 │                                                       │
 │  Safe for ALL queries including constrained ones      │
 │  (full query text is hashed, so "5M" ≠ "10M")        │
 │                                                       │
 │  HIT  ──────────────────────────────► return          │
 │  MISS → continue                                      │
 └───────────────────────────────────────────────────────┘
                         │ MISS
                         ▼
 ┌───────────────────────────────────────────────────────┐
 │                SEMANTIC CACHE (Redis)                  │
 │                                                       │
 │  keys: cag:semantic:{md5}:embedding                   │
 │        cag:semantic:{md5}:response                    │
 │  similarity: cosine > 0.92                            │
 │  scan cap:   100 most recent entries (O(1) lookup)    │
 │  TTL:        24 hours                                 │
 │  cost:       0 API calls                              │
 │  time:       ~5ms                                     │
 │                                                       │
 │  BYPASSED when any constraint detected:               │
 │    price, year, mileage, fuel, make, location,        │
 │    ranking intent (highest/lowest/cheapest/newest)    │
 │                                                       │
 │  WHY: "hybrid under 5M" ≈ "hybrid under 10M"         │
 │       in embedding space (cosine ~0.97)               │
 │       → semantic cache would serve the wrong answer   │
 │                                                       │
 │  WHY: "lowest mileage" ≈ "highest mileage"            │
 │       in embedding space (cosine ~0.96)               │
 │       → semantic cache would serve wrong ranking      │
 │                                                       │
 │  HIT  ──────────────────────────────► return          │
 │  MISS → run full CRAG pipeline                        │
 └───────────────────────────────────────────────────────┘
```

---

## Constraint Extractor

Extracts structured Qdrant filters and ranking intent from natural language — **zero LLM calls, pure regex**.

```
Input: "Toyota hybrid SUV under 8 million, 2020 or newer, automatic, Kandy"
                              │
              ┌───────────────▼──────────────────┐
              │         extract_constraints()     │
              └───────────────┬──────────────────┘
                              │
              ┌───────────────▼──────────────────────────────┐
              │  Extracted Qdrant filters:                    │
              │                                               │
              │  price_lkr:    { lte: 8,000,000 }            │  "under 8 million"
              │  yom:          { gte: 2020 }                  │  "2020 or newer"
              │  fuel_type:    "Hybrid"                       │  "hybrid"
              │  make:         "Toyota"                       │  brand match
              │  category:     "suvs"                         │  "SUV"
              │  transmission: "Automatic"                    │  "automatic"
              │  district:     "Kandy"                        │  district match
              │                                               │
              │  Applied as Qdrant payload filter pre-search  │
              └───────────────────────────────────────────────┘

Ranking intent detection (special _ranking key, NOT a Qdrant filter):

  "cars with highest mileage"   → { field: "mileage_km", order: "desc" }
  "lowest mileage cars"         → { field: "mileage_km", order: "asc"  }
  "cheapest Toyota in Colombo"  → { field: "price_lkr",  order: "asc"  }
  "most expensive SUVs"         → { field: "price_lkr",  order: "desc" }
  "newest 2020+ Hondas"         → { field: "yom",        order: "desc" }
  "oldest/vintage cars"         → { field: "yom",        order: "asc"  }

  Effect: retrieved docs are sorted by the detected field before synthesis,
          so the LLM always sees the correct ordering regardless of which
          docs semantic search returned.

Supported constraint types:

  Price        "under 5M" · "5–10 million" · "above 3 lakh" · "max Rs. 8,500,000"
               "less than 2.5M" · "within 6 million" · "no more than 4M"

  Year         "2018 or newer" · "from 2020" · "since 2019" · "2015–2020"
               "before 2019" · "older than 2018"

  Mileage      "under 50,000 km" · "below 80k km" · "max 100,000 km"

  Districts    All 25 Sri Lankan districts:
               Colombo · Gampaha · Kalutara · Kandy · Matale · Nuwara Eliya
               Galle · Matara · Hambantota · Jaffna · Kilinochchi · Mannar
               Vavuniya · Mullaitivu · Batticaloa · Ampara · Trincomalee
               Kurunegala · Puttalam · Anuradhapura · Polonnaruwa · Badulla
               Monaragala · Ratnapura · Kegalle

  Fuel type    Hybrid (plug-in hybrid · PHEV · mild hybrid · full hybrid)
               Electric (EV · BEV · electric vehicle)
               Diesel · Petrol (Gasoline)

  Transmission Automatic · CVT · Tiptronic · Manual

  Category     Cars · SUV (4x4 · 4WD) · Van (minivan · minibus)
               Motorcycle (motorbike · bike) · Three-wheeler (trishaw · tuk-tuk)
               Pickup · Lorry · Heavy-duty

  Makes        25+ brands — Toyota · Suzuki · Honda · Nissan · Hyundai
               Mitsubishi · Mazda · Daihatsu · Subaru · Isuzu · Kia · Ford
               Mercedes-Benz · BMW · Audi · Lexus · Volkswagen · Peugeot
               Land Rover · Jeep · Tata · Bajaj · Yamaha · Hero · TVS · Micro
```

---

## Component Deep-Dive

### 1. Scraper

```
riyasewana.com
      │
      │  8 categories: cars · suvs · vans · motorcycles
      │                lorries · three-wheels · pickups · heavy-duties
      │
      ▼
 playwright_crawler.py         (search pages — 40 listings/page)
 ├── Headless Chromium
 ├── playwright-stealth (bot detection bypass)
 ├── 5 rotating desktop/mobile user agents
 ├── Resource blocking (images, ads, tracking)
 ├── Random delay: 3–8 seconds between pages
 ├── Locale: en-US · Timezone: Asia/Colombo
 └── Extracts: title, URL, price, location, thumbnail, is_premium
      │
      ▼
 detail_scraper.py             (individual listing pages)
 ├── Specs table (table.moret): make, model, yom, mileage, fuel,
 │   transmission, engine cc, colour, condition, options
 ├── Description (seller notes)
 ├── Images and thumbnail
 ├── Contact phone, seller name
 └── View count
      │
      ▼
 parsers.py + validators.py    (normalisation)
 ├── parse_price()      → (price_lkr: float, is_negotiable: bool)
 ├── normalize_fuel()   → Petrol | Diesel | Hybrid | Electric
 ├── normalize_trans()  → Automatic | Manual
 ├── validate_year()    → 1970–2026
 ├── map_location()     → (district, province) via 100+ city mappings
 └── extract_id()       → riyasewana_id from URL
      │
      ▼
 PostgreSQL UPSERT
 ON CONFLICT (riyasewana_id) DO UPDATE
 (price_lkr, mileage_km, view_count, last_seen_at, is_active, updated_at)
      │
 Celery Beat schedule:  every Sunday @ 02:00 Asia/Colombo
 Task soft limit:       6 hours · hard limit: 6.5 hours
```

### 2. Ingestion Pipeline

```
PostgreSQL vehicles table
      │
      ▼
 document_builder.py     ─── Structured text per listing:

   Toyota Corolla 2020 (Used)
   Price: Rs. 6,500,000 [Mid-Range] (Negotiable)
   Fuel: Hybrid
   Transmission: Automatic
   Year: 2020
   Specs: 1800cc | 45,000 km | Silver
   Location: Nugegoda, Colombo, Western Province
   Type: Sedan
   Listing URL: https://riyasewana.com/...
   ---
   Well maintained. Full service record. One owner.

   Price tiers: Budget (< 2M) · Mid-Range (2–6M) · Premium (6–15M) · Luxury (> 15M)

   Metadata payload (20+ fields for Qdrant filtering):
   make, model, yom, price_lkr, mileage_km, fuel_type, transmission,
   district, province, category, is_active, url, vehicle_id, …
      │
      ▼
 embedder.py             ─── Gemini embedding
   model:      gemini-embedding-001
   dimension:  3072
   batch_size: 32
   method:     aget_text_embedding_batch() (async)
      │
      ▼
 qdrant_indexer.py       ─── Vector + payload storage
   Collection:  vehicles
   Distance:    COSINE
   Batch size:  100 points
   Payload indexes:
     KEYWORD: category, make, model, fuel_type, transmission,
              district, province, is_active
     FLOAT:   price_lkr
     INTEGER: yom, mileage_km, engine_cc
```

### 3. FastAPI Backend

```
api/
├── main.py              App factory · CORS · lifespan · route registration
├── models.py            Pydantic schemas (QueryRequest, SearchRequest, …)
└── routes/
    ├── query.py         POST /api/v1/query   (CRAG pipeline, 55s timeout)
    ├── search.py        GET  /api/v1/search  (SQL + pagination + sorting)
    ├── vehicles.py      GET  /api/v1/vehicles/{id} and /stats
    ├── health.py        GET  /api/v1/health  (DB + Redis + Qdrant checks)
    └── admin.py         POST /scrape/trigger · GET /scrape/status · /cache/*

Workers: 4 Uvicorn workers
```

### 4. Streamlit Dashboard

```
dashboard/
├── app.py                    Home — 6 KPI cards + quick search form
└── pages/
    ├── 1_Market_Overview.py  Category breakdown · top makes · recent listings
    ├── 2_Pricing.py          Price histogram · by make · by mileage scatter
    ├── 3_Regional.py         District map · price by district · province split
    ├── 4_Best_Value.py       Price/mileage ratio scoring + ranking
    ├── 5_Chat.py             Full RAG chat interface + cache stats
    └── 6_Trends.py           Listings over time · make trends · fuel adoption

Charts: Plotly (interactive)
Data caching: @st.cache_data(ttl=300), @st.cache_resource
```

---

## Data Flow

### Write Path (Scrape → Index)

```
Celery Beat (Sunday @ 02:00)
    │
    ▼
scrape_all_categories()
    ├── scrape_category("cars")
    ├── scrape_category("suvs")
    ├── … (8 categories)
    │
    ▼  per category:
Playwright crawls search pages
(40 listings/page · up to 500 pages)
    │
    ▼
Detail page per listing URL
    │
    ▼
Parse + validate + normalise
    │
    ▼
PostgreSQL UPSERT (vehicles)
    │
    ▼
Document builder → Gemini embed → Qdrant upsert
    │
    ▼
mark_stale_listings() ─ is_active=FALSE for unseen > 14 days
```

### Read Path (Query → Answer)

```
Natural language query
    │
    ▼
FastAPI POST /api/v1/query
    │
    ▼
Embed query (3072-dim)
    │
    ▼
Extract constraints (regex, 0ms)
    │
    ▼
Check Redis cache
    ├── Exact hit → return instantly (< 1ms, $0)
    └── Semantic hit (if no constraints) → return fast (~5ms, $0)
         │ MISS
         ▼
Qdrant dense search with payload filters
    │
    ▼
Grade top 5 docs (Gemini, ~3–5s)
    │
    ├── avg_relevance < 0.4 → rewrite query → re-retrieve → re-grade (once)
    │
    ▼
Filter relevance ≥ 0.3 · ranking sort if needed
    │
    ▼
Synthesize answer (Gemini Flash, ~3–5s)
    │
    ▼
Cache result (async, fire-and-forget)
Log query to query_logs (async, fire-and-forget)
    │
    ▼
Return QueryResponse (~8–15s total for cache miss)
```

---

## Database Schema

### `vehicles`

```sql
CREATE TABLE vehicles (
    id                SERIAL PRIMARY KEY,
    riyasewana_id     BIGINT UNIQUE NOT NULL,
    url               TEXT UNIQUE NOT NULL,
    category          TEXT,                    -- cars · suvs · vans · motorcycles · …
    title             TEXT,
    make              TEXT,
    model             TEXT,
    year              INTEGER,
    body_type         TEXT,
    price_lkr         NUMERIC(14, 2),
    is_negotiable     BOOLEAN DEFAULT FALSE,
    yom               INTEGER,                 -- year of manufacture
    mileage_km        INTEGER,
    transmission      TEXT,                    -- Automatic | Manual
    fuel_type         TEXT,                    -- Petrol | Diesel | Hybrid | Electric
    engine_cc         INTEGER,
    color             TEXT,
    condition         TEXT,                    -- Used | Reconditioned | Brand New
    location_raw      TEXT,
    district          TEXT,
    province          TEXT,
    options           TEXT[],                  -- GIN indexed
    description       TEXT,
    features_extracted JSONB,                 -- GIN indexed
    contact_phone     TEXT,
    seller_name       TEXT,
    is_dealer         BOOLEAN DEFAULT FALSE,
    is_premium_ad     BOOLEAN DEFAULT FALSE,
    view_count        INTEGER DEFAULT 0,
    images            TEXT[],
    thumbnail_url     TEXT,
    posted_at         TIMESTAMPTZ,
    scraped_at        TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    is_active         BOOLEAN DEFAULT TRUE,
    raw_html          TEXT,
    raw_json          JSONB                    -- GIN indexed
);
```

**Indexes:** 12 single-field · 3 composite (make+yom+price, district+price, fuel+price) · 3 GIN (options, raw\_json, features\_extracted)

### `scrape_jobs`

```sql
CREATE TABLE scrape_jobs (
    job_id            UUID PRIMARY KEY,
    category          TEXT,
    status            TEXT,         -- pending · running · completed · failed
    pages_scraped     INTEGER DEFAULT 0,
    listings_found    INTEGER DEFAULT 0,
    listings_new      INTEGER DEFAULT 0,
    listings_updated  INTEGER DEFAULT 0,
    errors            JSONB,
    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
```

### `query_logs`

```sql
CREATE TABLE query_logs (
    id                   SERIAL PRIMARY KEY,
    query_text           TEXT,
    query_type           TEXT,     -- PRICE_CHECK · COMPARISON · RECOMMENDATION ·
                                   -- MARKET_TREND · SPECS_LOOKUP · AVAILABILITY · GENERAL
    cache_hit            BOOLEAN DEFAULT FALSE,
    cache_type           TEXT,     -- exact · semantic · miss
    response_time_ms     INTEGER,
    num_docs_retrieved   INTEGER,
    avg_relevance_score  FLOAT,
    crag_rewrite         BOOLEAN DEFAULT FALSE,
    model_used           TEXT,
    tokens_used          INTEGER,
    cost_usd             FLOAT,
    user_feedback        INTEGER,  -- future: 1 thumbs up · -1 thumbs down
    created_at           TIMESTAMPTZ DEFAULT NOW()
);
```

### `location_mappings`

```sql
CREATE TABLE location_mappings (
    id            SERIAL PRIMARY KEY,
    raw_location  TEXT UNIQUE,
    district      TEXT,
    province      TEXT
);
-- Seeded with 100+ city → district mappings for all 25 Sri Lankan districts
```

---

## API Reference

### `POST /api/v1/query` — Natural language query

**Request:**
```json
{
  "query": "Best hybrid cars under Rs. 5 million in Colombo",
  "filters": {},
  "top_k": 20,
  "skip_cache": false
}
```

**Response:**
```json
{
  "answer": "Here are the best hybrid cars under Rs. 5,000,000 in Colombo…",
  "vehicles_mentioned": [
    {
      "make": "Suzuki",
      "model": "Alto",
      "year": 2019,
      "price_lkr": 4200000,
      "url": "https://riyasewana.com/…"
    }
  ],
  "confidence": 0.87,
  "follow_up_suggestions": [
    "Would you like to compare with Kandy listings?",
    "Shall I show options above Rs. 5 million as well?"
  ],
  "query_type": "RECOMMENDATION",
  "avg_relevance": 0.82,
  "num_docs_retrieved": 20,
  "crag_rewrite": false,
  "cache_hit": false,
  "cache_type": "miss",
  "response_time_ms": 4821,
  "model_used": "gemini-2.5-flash"
}
```

---

### `GET /api/v1/search` — Structured search

| Parameter | Type | Example | Description |
|---|---|---|---|
| `make` | string | `Toyota` | Filter by make |
| `model` | string | `Corolla` | Filter by model |
| `year_min` | int | `2018` | Min year of manufacture |
| `year_max` | int | `2023` | Max year of manufacture |
| `price_min` | float | `2000000` | Min price (LKR) |
| `price_max` | float | `8000000` | Max price (LKR) |
| `fuel_type` | string | `Hybrid` | Petrol / Diesel / Hybrid / Electric |
| `transmission` | string | `Automatic` | Automatic / Manual |
| `district` | string | `Colombo` | Any of the 25 districts |
| `category` | string | `cars` | cars / suvs / vans / motorcycles / … |
| `sort_by` | string | `price_lkr` | Field to sort by |
| `sort_order` | string | `asc` | `asc` or `desc` |
| `page` | int | `1` | Page number (1-based) |
| `page_size` | int | `20` | Results per page (max 100) |

**Response:**
```json
{
  "vehicles": [ { "id": 1234, "make": "Toyota", "price_lkr": 6500000 } ],
  "total": 847,
  "page": 1,
  "page_size": 20,
  "pages": 43
}
```

---

### `GET /api/v1/vehicles/{vehicle_id}` — Vehicle detail

Returns full `VehicleDetail` with all 35+ fields.

### `GET /api/v1/vehicles/stats` — Market statistics

```json
{
  "total_listings": 12453,
  "avg_price": 6230000,
  "median_mileage": 87000,
  "pct_hybrid": 18.4,
  "pct_automatic": 62.1,
  "top_make": "Toyota",
  "categories": {
    "cars": 7800,
    "suvs": 2100,
    "motorcycles": 1400,
    "vans": 850
  }
}
```

### `GET /api/v1/health`

```json
{
  "status": "healthy",
  "database": true,
  "redis": true,
  "qdrant": true,
  "timestamp": "2025-10-12T08:00:00Z"
}
```

### `POST /api/v1/scrape/trigger`

```json
{ "category": "cars", "max_pages": 50 }
```

Response:
```json
{ "status": "dispatched", "task_id": "abc123", "category": "cars" }
```

### `GET /api/v1/scrape/status/{task_id}`

```json
{ "task_id": "abc123", "status": "SUCCESS", "result": { "listings_found": 847 } }
```

### `GET /api/v1/cache/stats`

```json
{
  "exact_entries": 342,
  "semantic_entries": 87,
  "memory_used_mb": 4.2,
  "ttl_seconds": 86400,
  "semantic_threshold": 0.92
}
```

### `POST /api/v1/cache/flush`

```json
{ "status": "flushed", "entries_deleted": 429 }
```

---

## Configuration

All settings live in `shared/config.py` and are loaded from the `.env` file via `pydantic-settings`.

| Variable | Default | Required | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | — | **Yes** | Google Gemini API key |
| `PG_PASSWORD` | `changeme` | Yes | PostgreSQL password |
| `APP_ENV` | `development` | No | `development` or `production` |
| `LOG_LEVEL` | `INFO` | No | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `DATABASE_URL` | `postgresql+asyncpg://pw_user:…@postgres:5432/primewheels` | No | Async DB URL (FastAPI) |
| `SYNC_DATABASE_URL` | `postgresql://pw_user:…@postgres:5432/primewheels` | No | Sync DB URL (Celery / Streamlit) |
| `REDIS_URL` | `redis://redis:6379/0` | No | Redis — cache + Celery broker + result backend |
| `QDRANT_URL` | `http://qdrant:6333` | No | Qdrant vector DB |
| `QDRANT_COLLECTION` | `vehicles` | No | Qdrant collection name |
| `GEMINI_FLASH_MODEL` | `gemini-2.5-flash` | No | LLM for grading + synthesis |
| `EMBEDDING_MODEL` | `gemini-embedding-001` | No | Embedding model |
| `EMBEDDING_DIMENSION` | `3072` | No | Vector dimension |
| `SCRAPE_DELAY_MIN` | `3.0` | No | Min seconds between pages (anti-rate-limit) |
| `SCRAPE_DELAY_MAX` | `8.0` | No | Max seconds between pages |
| `SCRAPE_MAX_PAGES` | `500` | No | Max pages per category per scrape run |
| `CACHE_TTL_SECONDS` | `86400` | No | Redis TTL (24 hours) |
| `SEMANTIC_CACHE_THRESHOLD` | `0.92` | No | Cosine similarity cutoff for semantic cache |
| `LANGFUSE_HOST` | — | No | LangFuse observability host |
| `LANGFUSE_PUBLIC_KEY` | — | No | LangFuse public key |
| `LANGFUSE_SECRET_KEY` | — | No | LangFuse secret key |

---

## Quick Start

### Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- Google Gemini API key — [get one free at aistudio.google.com](https://aistudio.google.com)

### 1. Clone and configure

```bash
git clone <repo-url>
cd prime-wheels-sl
cp .env.example .env
# Open .env and set GEMINI_API_KEY — that is the only required value
```

### 2. Start all services

```bash
docker compose up -d
```

Starts 7 containers: PostgreSQL 16 · Qdrant 1.12 · Redis 7 · FastAPI API (4 workers) · Celery Worker · Celery Beat · Streamlit Dashboard

### 3. Verify health

```bash
curl http://localhost:8000/api/v1/health
# {"status": "healthy", "database": true, "redis": true, "qdrant": true}
```

### 4. Trigger an initial scrape

```bash
# Scrape 5 pages of cars (~200 listings, ~2 minutes)
curl -X POST http://localhost:8000/api/v1/scrape/trigger \
  -H "Content-Type: application/json" \
  -d '{"category": "cars", "max_pages": 5}'

# Check status using the task_id returned above
curl http://localhost:8000/api/v1/scrape/status/<task_id>
```

### 5. Index listings into Qdrant

```bash
docker compose exec api python -m ingestion.pipeline
```

### 6. Ask a question

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Best Toyota under Rs. 6 million in Colombo"}'
```

### 7. Open the dashboard

```
http://localhost:8501
```

---

## Deployment

### Common commands

```bash
# Full rebuild
docker compose build

# Start / restart everything
docker compose up -d

# Restart API only (after code change)
docker compose build api && docker compose up -d api

# Always flush Redis after a redeploy to avoid stale cached answers
docker compose exec redis redis-cli FLUSHDB

# View live API logs
docker compose logs -f api

# View scraper logs
docker compose logs -f celery-worker

# Manual scrape of all categories
curl -X POST http://localhost:8000/api/v1/scrape/trigger \
  -d '{"category": "cars", "max_pages": 500}'
# Repeat for suvs, vans, motorcycles, lorries, three-wheels, pickups, heavy-duties
```

### Service URLs

| Service | URL |
|---|---|
| FastAPI API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Streamlit Dashboard | http://localhost:8501 |
| Qdrant Dashboard | http://localhost:6333/dashboard |

### Celery Beat — Automatic weekly scrape

```
Schedule: Every Sunday @ 02:00 AM (Asia/Colombo, UTC+5:30)
Task:     scraper.tasks.scrape_all_categories
          → dispatches one scrape_category task per category
          → 8 categories × up to 500 pages × 40 listings ≈ up to 160,000 listings
Limits:   soft 6 hours · hard 6.5 hours
```

---

## Evaluation

The `eval/` directory contains a 50-question test dataset and automated evaluation runner.

```bash
python -m eval.ragas_eval
# Output: eval/results.json
```

**Question types:**

| Type | Count | Example question |
|---|---|---|
| `PRICE_CHECK` | 8 | "What is the price of a 2018 Toyota Corolla?" |
| `COMPARISON` | 7 | "Compare hybrid SUVs under 10 million" |
| `RECOMMENDATION` | 10 | "Best budget car for a family of four?" |
| `MARKET_TREND` | 6 | "Are hybrid cars becoming more popular?" |
| `SPECS_LOOKUP` | 7 | "What fuel types are available for pickups?" |
| `AVAILABILITY` | 6 | "Are there electric vehicles in Colombo?" |
| `GENERAL` | 6 | "Tell me about the Sri Lankan used vehicle market" |

**Metrics collected per question:**

- `response_time_ms` — end-to-end latency
- `confidence` — synthesizer self-reported confidence (0–1)
- `avg_relevance_score` — grader average document relevance
- `cache_hit` — whether the response came from cache
- `crag_rewrite` — whether query correction was triggered

---

## Cost

| Component | Monthly | Notes |
|---|---|---|
| VPS (Hetzner CPX21) | ~$10 | 4 vCPU · 8 GB RAM · sufficient for all services |
| Gemini Embedding API | ~$2–3 | `gemini-embedding-001` @ $0.02 / 1M tokens |
| Gemini Flash API | ~$3–5 | `gemini-2.5-flash` @ $0.075 / 1M input tokens |
| **Total** | **~$15–18/month** | |

**Cost optimisations built in:**

- Only top 5 of 20 retrieved docs are graded by LLM
- `thinking_budget=0` disables Gemini 2.5 thinking tokens (saves ~21s and significant token cost per request)
- Exact cache hit: zero Gemini API calls, < 1ms
- Semantic cache hit: zero Gemini API calls, ~5ms
- Cache TTL: 24 hours — repeated queries are free

---

## Project Structure

```
prime-wheels-sl/
│
├── api/                          FastAPI backend
│   ├── main.py                   App factory · CORS · lifespan
│   ├── models.py                 Pydantic request/response schemas
│   └── routes/
│       ├── query.py              POST /api/v1/query
│       ├── search.py             GET  /api/v1/search
│       ├── vehicles.py           GET  /api/v1/vehicles/*
│       ├── health.py             GET  /api/v1/health
│       └── admin.py              Scrape triggers + cache management
│
├── rag/                          CRAG pipeline
│   ├── crag_workflow.py          Main async orchestrator (10-step pipeline)
│   ├── cag_cache.py              Redis dual-layer cache (exact + semantic)
│   ├── constraint_extractor.py   Regex constraint + ranking intent extraction
│   ├── grader.py                 Gemini document grader (constraint-aware)
│   ├── synthesizer.py            Gemini answer synthesizer (constraint-aware)
│   ├── query_classifier.py       Query classification + CRAG query rewriting
│   └── prompts.py                All prompt templates with {constraints_block}
│
├── ingestion/                    Data → vectors pipeline
│   ├── pipeline.py               Orchestrates load → embed → index
│   ├── document_builder.py       Vehicle row → structured LlamaIndex Document
│   ├── embedder.py               Gemini embedding (3072-dim, batched)
│   ├── qdrant_indexer.py         Qdrant upsert + dense search with filters
│   └── chunkers.py               5 chunking strategies (per_vehicle recommended)
│
├── scraper/                      Playwright web scraper
│   ├── config.py                 Categories · CSS selectors · user agents
│   ├── playwright_crawler.py     Search page scraper (stealth + anti-detection)
│   ├── detail_scraper.py         Individual listing detail scraper
│   ├── parsers.py                Data extraction and normalisation
│   ├── validators.py             Input validation (price, year, mileage, etc.)
│   ├── location_mapper.py        Raw location → (district, province)
│   └── tasks.py                  Celery tasks + Beat weekly schedule
│
├── shared/                       Shared infrastructure
│   ├── config.py                 Settings (pydantic-settings · @lru_cache)
│   ├── database.py               Async + sync SQLAlchemy engines + sessions
│   ├── models.py                 SQLAlchemy ORM (Vehicle · ScrapeJob · QueryLog)
│   └── logging.py                structlog — JSON in production · console in dev
│
├── dashboard/                    Streamlit analytics UI
│   ├── app.py                    Home — KPI row + quick search
│   └── pages/
│       ├── 1_Market_Overview.py  Category charts · top makes
│       ├── 2_Pricing.py          Price distributions and trends
│       ├── 3_Regional.py         District map and analysis
│       ├── 4_Best_Value.py       Price/mileage value scoring
│       ├── 5_Chat.py             Full RAG chat interface
│       └── 6_Trends.py           Time-series market trends
│
├── eval/                         Evaluation
│   ├── ragas_eval.py             Automated evaluation runner
│   └── questions.json            50-question test dataset (7 query types)
│
├── docker/                       Container definitions
│   ├── Dockerfile.api            FastAPI image (python:3.11-slim)
│   ├── Dockerfile.dashboard      Streamlit image
│   ├── Dockerfile.worker         Celery worker image
│   └── init.sql                  PostgreSQL schema + seed data
│
├── docker-compose.yml            Full stack orchestration (7 services)
├── requirements.txt              Python dependencies
├── pyproject.toml                Project metadata + Ruff linter config
└── .env.example                  Environment variable template
```

---

## Tech Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Language | Python | 3.11+ | Runtime |
| API | FastAPI + Uvicorn | latest | REST API (4 workers) |
| Dashboard | Streamlit + Plotly | latest | Analytics and chat UI |
| LLM | Google Gemini Flash | 2.5 | Document grading + answer synthesis |
| Embeddings | Google Gemini Embedding | gemini-embedding-001 | 3072-dim semantic vectors |
| Vector DB | Qdrant | 1.12.1 | Semantic search + payload filtering |
| Cache | Redis | 7 | Exact + semantic cache · Celery broker · result backend |
| Database | PostgreSQL | 16 | Primary data store + analytics queries |
| ORM | SQLAlchemy | 2.x | Async (FastAPI) + sync (Celery/Streamlit) engines |
| Task queue | Celery + Celery Beat | latest | Async scraping + weekly scheduling |
| Scraping | Playwright | latest | Headless Chromium + playwright-stealth |
| RAG framework | LlamaIndex | 0.12+ | Document indexing and chunking |
| Structured logging | structlog | latest | JSON logs in production · console in development |
| JSON resilience | dirtyjson | latest | Partial/truncated JSON parsing fallback |
| Containers | Docker Compose | v2 | Full stack orchestration |

---

*Built for the Sri Lankan vehicle market. Data source: [riyasewana.com](https://riyasewana.com) — Sri Lanka's largest used vehicle marketplace.*

**License: MIT**
