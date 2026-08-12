CREATE TABLE product_candidate (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    sku TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    product_type TEXT NOT NULL,
    weight_g INTEGER NOT NULL CHECK (weight_g > 0),
    length_mm INTEGER NOT NULL CHECK (length_mm > 0),
    width_mm INTEGER NOT NULL CHECK (width_mm > 0),
    height_mm INTEGER NOT NULL CHECK (height_mm > 0),
    thread_a TEXT,
    thread_b TEXT,
    optical_length_mm NUMERIC(10, 2),
    material TEXT,
    electrical BOOLEAN NOT NULL DEFAULT FALSE,
    battery BOOLEAN NOT NULL DEFAULT FALSE,
    laser BOOLEAN NOT NULL DEFAULT FALSE,
    solar_observation BOOLEAN NOT NULL DEFAULT FALSE,
    safety_risk TEXT,
    hs_code TEXT,
    trademe_category_id TEXT,
    status TEXT NOT NULL DEFAULT 'CANDIDATE',
    expected_sell_price_nzd NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE supplier_offer (
    id TEXT PRIMARY KEY,
    product_id TEXT REFERENCES product_candidate(id),
    supplier TEXT NOT NULL,
    source_url TEXT NOT NULL,
    product_name TEXT NOT NULL,
    sku TEXT NOT NULL,
    unit_price_cny NUMERIC(12, 2) NOT NULL CHECK (unit_price_cny >= 0),
    moq INTEGER NOT NULL CHECK (moq > 0),
    domestic_shipping_cny NUMERIC(12, 2) NOT NULL CHECK (domestic_shipping_cny >= 0),
    weight_g INTEGER NOT NULL CHECK (weight_g > 0),
    length_mm INTEGER NOT NULL CHECK (length_mm > 0),
    width_mm INTEGER NOT NULL CHECK (width_mm > 0),
    height_mm INTEGER NOT NULL CHECK (height_mm > 0),
    lead_time_days INTEGER NOT NULL CHECK (lead_time_days > 0),
    supplier_score NUMERIC(5, 2),
    sample_cost NUMERIC(12, 2),
    monthly_sales_ref INTEGER,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shipping_rate (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    route TEXT NOT NULL,
    min_weight_g INTEGER NOT NULL,
    max_weight_g INTEGER NOT NULL,
    volumetric_divisor NUMERIC(12, 2) NOT NULL,
    base_fee_cny NUMERIC(12, 2) NOT NULL,
    fee_per_kg_cny NUMERIC(12, 2) NOT NULL,
    delivery_days INTEGER NOT NULL
);

CREATE TABLE keyword (
    id BIGSERIAL PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES product_candidate(id),
    keyword TEXT NOT NULL,
    keyword_cluster TEXT NOT NULL,
    locale TEXT NOT NULL DEFAULT 'en-NZ'
);

CREATE TABLE keyword_metric_monthly (
    keyword_id BIGINT NOT NULL REFERENCES keyword(id),
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    nz_search_volume INTEGER,
    competition_index INTEGER,
    bid_low NUMERIC(12, 2),
    bid_high NUMERIC(12, 2),
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (keyword_id, year, month)
);

CREATE TABLE import_metric (
    hs_code TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    origin_country TEXT NOT NULL,
    import_nzd NUMERIC(14, 2) NOT NULL,
    quantity NUMERIC(14, 2),
    unit TEXT,
    PRIMARY KEY (hs_code, year, month, origin_country)
);

CREATE TABLE hs_mapping (
    product_id TEXT PRIMARY KEY REFERENCES product_candidate(id),
    hs_code TEXT NOT NULL,
    mapping_confidence INTEGER NOT NULL CHECK (mapping_confidence BETWEEN 0 AND 100),
    analyst_notes TEXT,
    requires_manual_confirmation BOOLEAN NOT NULL
);

CREATE TABLE market_snapshot (
    id BIGSERIAL PRIMARY KEY,
    keyword TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    trademe_result_count INTEGER,
    price_p25 NUMERIC(12, 2),
    price_median NUMERIC(12, 2),
    price_p75 NUMERIC(12, 2),
    local_listing_estimate INTEGER,
    international_listing_estimate INTEGER,
    analyst_notes TEXT
);

CREATE TABLE economics_result (
    product_id TEXT PRIMARY KEY REFERENCES product_candidate(id),
    revenue_nzd NUMERIC(12, 2) NOT NULL,
    landed_cost_nzd NUMERIC(12, 2) NOT NULL,
    contribution_profit_nzd NUMERIC(12, 2) NOT NULL,
    contribution_margin NUMERIC(8, 4) NOT NULL,
    shipping_ratio NUMERIC(8, 4) NOT NULL,
    break_even_price_nzd NUMERIC(12, 2) NOT NULL,
    status TEXT NOT NULL,
    rejection_reasons TEXT[] NOT NULL DEFAULT '{}',
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE score_snapshot (
    product_id TEXT PRIMARY KEY REFERENCES product_candidate(id),
    search_demand_score NUMERIC(5, 2) NOT NULL,
    import_evidence_score NUMERIC(5, 2) NOT NULL,
    unit_economics_score NUMERIC(5, 2) NOT NULL,
    logistics_score NUMERIC(5, 2) NOT NULL,
    supply_quality_score NUMERIC(5, 2) NOT NULL,
    product_risk_fit_score NUMERIC(5, 2) NOT NULL,
    prelaunch_score NUMERIC(5, 2) NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    status TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

