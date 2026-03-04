-- ============================================================
-- Prime Wheels SL — PostgreSQL Init Script
-- Runs automatically on first docker-compose up
-- ============================================================

-- Core vehicles table
CREATE TABLE IF NOT EXISTS vehicles (
    id                  SERIAL PRIMARY KEY,
    riyasewana_id       BIGINT UNIQUE NOT NULL,
    url                 TEXT UNIQUE NOT NULL,
    category            TEXT NOT NULL DEFAULT 'cars',

    -- Parsed identity
    title               TEXT NOT NULL,
    make                TEXT,
    model               TEXT,
    year                INTEGER,
    body_type           TEXT,

    -- Pricing
    price_lkr           NUMERIC(14,2),
    price_currency      TEXT DEFAULT 'LKR',
    is_negotiable       BOOLEAN DEFAULT FALSE,

    -- Core specs (from table.moret)
    yom                 INTEGER,
    mileage_km          INTEGER,
    transmission        TEXT,
    fuel_type           TEXT,
    engine_cc           INTEGER,
    color               TEXT,
    condition           TEXT,

    -- Location
    location_raw        TEXT,
    district            TEXT,
    province            TEXT,

    -- Rich text & features
    options             TEXT[],
    description         TEXT,
    features_extracted  JSONB DEFAULT '{}',

    -- Seller
    contact_phone       TEXT,
    seller_name         TEXT,
    is_dealer           BOOLEAN DEFAULT FALSE,
    is_premium_ad       BOOLEAN DEFAULT FALSE,

    -- Engagement
    view_count          INTEGER DEFAULT 0,

    -- Media
    images              TEXT[],
    thumbnail_url       TEXT,

    -- Timestamps
    posted_at           TIMESTAMPTZ,
    scraped_at          TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    is_active           BOOLEAN DEFAULT TRUE,

    -- Raw data backup
    raw_html            TEXT,
    raw_json            JSONB DEFAULT '{}'
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_vehicles_category ON vehicles(category);
CREATE INDEX IF NOT EXISTS idx_vehicles_make ON vehicles(make);
CREATE INDEX IF NOT EXISTS idx_vehicles_make_model ON vehicles(make, model);
CREATE INDEX IF NOT EXISTS idx_vehicles_year ON vehicles(year);
CREATE INDEX IF NOT EXISTS idx_vehicles_yom ON vehicles(yom);
CREATE INDEX IF NOT EXISTS idx_vehicles_price ON vehicles(price_lkr);
CREATE INDEX IF NOT EXISTS idx_vehicles_mileage ON vehicles(mileage_km);
CREATE INDEX IF NOT EXISTS idx_vehicles_fuel ON vehicles(fuel_type);
CREATE INDEX IF NOT EXISTS idx_vehicles_transmission ON vehicles(transmission);
CREATE INDEX IF NOT EXISTS idx_vehicles_district ON vehicles(district);
CREATE INDEX IF NOT EXISTS idx_vehicles_province ON vehicles(province);
CREATE INDEX IF NOT EXISTS idx_vehicles_posted ON vehicles(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_vehicles_active ON vehicles(is_active);
CREATE INDEX IF NOT EXISTS idx_vehicles_riyasewana_id ON vehicles(riyasewana_id);
CREATE INDEX IF NOT EXISTS idx_options_gin ON vehicles USING GIN(options);
CREATE INDEX IF NOT EXISTS idx_raw_json_gin ON vehicles USING GIN(raw_json);
CREATE INDEX IF NOT EXISTS idx_features_gin ON vehicles USING GIN(features_extracted);

-- Composite indexes for common dashboard queries
CREATE INDEX IF NOT EXISTS idx_vehicles_make_year_price ON vehicles(make, yom, price_lkr);
CREATE INDEX IF NOT EXISTS idx_vehicles_district_price ON vehicles(district, price_lkr);
CREATE INDEX IF NOT EXISTS idx_vehicles_fuel_price ON vehicles(fuel_type, price_lkr);

-- Scrape job tracking
CREATE TABLE IF NOT EXISTS scrape_jobs (
    id              SERIAL PRIMARY KEY,
    job_id          UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    category        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    pages_scraped   INTEGER DEFAULT 0,
    listings_found  INTEGER DEFAULT 0,
    listings_new    INTEGER DEFAULT 0,
    listings_updated INTEGER DEFAULT 0,
    errors          JSONB DEFAULT '[]',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Query analytics
CREATE TABLE IF NOT EXISTS query_logs (
    id              SERIAL PRIMARY KEY,
    query_text      TEXT NOT NULL,
    query_type      TEXT,
    cache_hit       BOOLEAN DEFAULT FALSE,
    cache_type      TEXT,
    response_time_ms INTEGER,
    num_docs_retrieved INTEGER,
    avg_relevance_score FLOAT,
    crag_rewrite    BOOLEAN DEFAULT FALSE,
    model_used      TEXT,
    tokens_used     INTEGER,
    cost_usd        FLOAT,
    user_feedback   INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Location mapping
CREATE TABLE IF NOT EXISTS location_mappings (
    id              SERIAL PRIMARY KEY,
    raw_location    TEXT UNIQUE NOT NULL,
    district        TEXT NOT NULL,
    province        TEXT NOT NULL
);

-- Seed common Sri Lankan location mappings
INSERT INTO location_mappings (raw_location, district, province) VALUES
    -- Western Province - Colombo
    ('Colombo', 'Colombo', 'Western'),
    ('Colombo 1', 'Colombo', 'Western'),
    ('Colombo 2', 'Colombo', 'Western'),
    ('Colombo 3', 'Colombo', 'Western'),
    ('Colombo 4', 'Colombo', 'Western'),
    ('Colombo 5', 'Colombo', 'Western'),
    ('Colombo 6', 'Colombo', 'Western'),
    ('Colombo 7', 'Colombo', 'Western'),
    ('Colombo 8', 'Colombo', 'Western'),
    ('Colombo 9', 'Colombo', 'Western'),
    ('Colombo 10', 'Colombo', 'Western'),
    ('Colombo 11', 'Colombo', 'Western'),
    ('Colombo 12', 'Colombo', 'Western'),
    ('Colombo 13', 'Colombo', 'Western'),
    ('Colombo 14', 'Colombo', 'Western'),
    ('Colombo 15', 'Colombo', 'Western'),
    ('Battaramulla', 'Colombo', 'Western'),
    ('Nugegoda', 'Colombo', 'Western'),
    ('Dehiwala', 'Colombo', 'Western'),
    ('Maharagama', 'Colombo', 'Western'),
    ('Piliyandala', 'Colombo', 'Western'),
    ('Moratuwa', 'Colombo', 'Western'),
    ('Kottawa', 'Colombo', 'Western'),
    ('Kaduwela', 'Colombo', 'Western'),
    ('Rajagiriya', 'Colombo', 'Western'),
    ('Boralesgamuwa', 'Colombo', 'Western'),
    ('Malabe', 'Colombo', 'Western'),
    ('Athurugiriya', 'Colombo', 'Western'),
    ('Homagama', 'Colombo', 'Western'),
    ('Nawala', 'Colombo', 'Western'),
    ('Wellampitiya', 'Colombo', 'Western'),
    ('Kotikawatta', 'Colombo', 'Western'),
    ('Mulleriyawa', 'Colombo', 'Western'),
    -- Western Province - Gampaha
    ('Gampaha', 'Gampaha', 'Western'),
    ('Kadawatha', 'Gampaha', 'Western'),
    ('Wattala', 'Gampaha', 'Western'),
    ('Negombo', 'Gampaha', 'Western'),
    ('Ja-Ela', 'Gampaha', 'Western'),
    ('Kiribathgoda', 'Gampaha', 'Western'),
    ('Kelaniya', 'Gampaha', 'Western'),
    ('Minuwangoda', 'Gampaha', 'Western'),
    ('Nittambuwa', 'Gampaha', 'Western'),
    ('Delgoda', 'Gampaha', 'Western'),
    ('Ragama', 'Gampaha', 'Western'),
    ('Kandana', 'Gampaha', 'Western'),
    ('Ganemulla', 'Gampaha', 'Western'),
    -- Western Province - Kalutara
    ('Kalutara', 'Kalutara', 'Western'),
    ('Panadura', 'Kalutara', 'Western'),
    ('Horana', 'Kalutara', 'Western'),
    ('Bandaragama', 'Kalutara', 'Western'),
    ('Beruwala', 'Kalutara', 'Western'),
    ('Aluthgama', 'Kalutara', 'Western'),
    -- Central Province
    ('Kandy', 'Kandy', 'Central'),
    ('Peradeniya', 'Kandy', 'Central'),
    ('Katugastota', 'Kandy', 'Central'),
    ('Matale', 'Matale', 'Central'),
    ('Nuwara Eliya', 'Nuwara Eliya', 'Central'),
    -- Southern Province
    ('Galle', 'Galle', 'Southern'),
    ('Matara', 'Matara', 'Southern'),
    ('Hambantota', 'Hambantota', 'Southern'),
    ('Weligama', 'Matara', 'Southern'),
    ('Ambalangoda', 'Galle', 'Southern'),
    -- Northern Province
    ('Jaffna', 'Jaffna', 'Northern'),
    ('Kilinochchi', 'Kilinochchi', 'Northern'),
    ('Vavuniya', 'Vavuniya', 'Northern'),
    -- Eastern Province
    ('Batticaloa', 'Batticaloa', 'Eastern'),
    ('Trincomalee', 'Trincomalee', 'Eastern'),
    ('Ampara', 'Ampara', 'Eastern'),
    -- North Western Province
    ('Kurunegala', 'Kurunegala', 'North Western'),
    ('Puttalam', 'Puttalam', 'North Western'),
    ('Chilaw', 'Puttalam', 'North Western'),
    -- North Central Province
    ('Anuradhapura', 'Anuradhapura', 'North Central'),
    ('Polonnaruwa', 'Polonnaruwa', 'North Central'),
    -- Uva Province
    ('Badulla', 'Badulla', 'Uva'),
    ('Monaragala', 'Monaragala', 'Uva'),
    -- Sabaragamuwa Province
    ('Ratnapura', 'Ratnapura', 'Sabaragamuwa'),
    ('Kegalle', 'Kegalle', 'Sabaragamuwa')
ON CONFLICT (raw_location) DO NOTHING;
