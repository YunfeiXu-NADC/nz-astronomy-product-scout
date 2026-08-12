from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Dimensions(BaseModel):
    length_mm: int
    width_mm: int
    height_mm: int

    @field_validator("length_mm", "width_mm", "height_mm")
    @classmethod
    def dimensions_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("dimension must be positive")
        return value


class ProductCandidate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    canonical_name: str
    sku: str
    category: str
    subcategory: str
    product_type: str
    weight_g: int
    length_mm: int
    width_mm: int
    height_mm: int
    thread_a: str | None = None
    thread_b: str | None = None
    optical_length_mm: Decimal | None = None
    material: str | None = None
    electrical: bool = False
    battery: bool = False
    laser: bool = False
    solar_observation: bool = False
    safety_risk: str | None = None
    hs_code: str | None = None
    trademe_category_id: str | None = None
    status: str = "CANDIDATE"
    expected_sell_price_nzd: Decimal

    @field_validator("weight_g", "length_mm", "width_mm", "height_mm")
    @classmethod
    def physical_values_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("physical values must be positive")
        return value


class SupplierOffer(BaseModel):
    id: str
    product_id: str | None = None
    source_url: str
    product_name: str
    sku: str
    unit_price_cny: Decimal
    moq: int
    domestic_shipping_cny: Decimal
    supplier: str
    monthly_sales_ref: int | None = None
    lead_time_days: int
    weight_g: int
    package_dimensions: Dimensions
    supplier_score: Decimal | None = None
    sample_cost: Decimal | None = None

    @field_validator("unit_price_cny", "domestic_shipping_cny")
    @classmethod
    def money_must_not_be_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("money values must not be negative")
        return value

    @field_validator("moq", "lead_time_days", "weight_g")
    @classmethod
    def integer_values_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("integer values must be positive")
        return value


class ShippingRate(BaseModel):
    provider: str
    route: str
    min_weight_g: int
    max_weight_g: int
    volumetric_divisor: Decimal
    base_fee_cny: Decimal
    fee_per_kg_cny: Decimal
    delivery_days: int

    def supports(self, route: str, chargeable_weight_g: int) -> bool:
        return (
            self.route == route
            and self.min_weight_g <= chargeable_weight_g <= self.max_weight_g
        )


class ShippingQuote(BaseModel):
    product_id: str
    route: str
    provider: str
    actual_weight_g: int
    volumetric_weight_g: int
    chargeable_weight_g: int
    shipping_cny: Decimal
    delivery_days: int


class EconomicsResult(BaseModel):
    product_id: str
    sku: str
    revenue_nzd: Decimal
    purchase_cost_nzd: Decimal
    china_domestic_shipping_nzd: Decimal
    international_shipping_nzd: Decimal
    packaging_nzd: Decimal
    trade_me_fee_nzd: Decimal
    payment_fee_nzd: Decimal
    refund_reserve_nzd: Decimal
    landed_cost_nzd: Decimal
    contribution_profit_nzd: Decimal
    contribution_margin: Decimal
    shipping_ratio: Decimal
    break_even_price_nzd: Decimal
    chargeable_weight_g: int
    status: Literal["QUALIFIED", "REJECT", "BLOCKED"]
    rejection_reasons: list[str] = Field(default_factory=list)


class KeywordMetric(BaseModel):
    product_id: str
    keyword: str
    keyword_cluster: str
    monthly_searches: int | None = None
    monthly_history: list[int] = Field(default_factory=list)
    competition_index: int | None = None
    bid_low: Decimal | None = None
    bid_high: Decimal | None = None


class KeywordSearchScore(BaseModel):
    product_id: str
    cluster_monthly_searches: dict[str, int]
    total_cluster_searches: int
    yoy_growth_score: Decimal
    stability_score: Decimal
    search_volume_percentile: Decimal
    score: Decimal
    confidence: int


class ImportMetric(BaseModel):
    hs_code: str
    year: int
    month: int
    origin_country: str
    import_nzd: Decimal
    quantity: Decimal | None = None
    unit: str | None = None


class ImportEvidenceScore(BaseModel):
    hs_code: str
    import_value_12m_nzd: Decimal
    import_quantity_12m: Decimal | None
    china_share: Decimal
    cagr_3y: Decimal
    score: Decimal
    confidence: int


class RiskAssessment(BaseModel):
    status: Literal["LOW", "MEDIUM", "HIGH", "BLOCKED"]
    reasons: list[str]
    score: int


class ConfidenceInputs(BaseModel):
    has_google_keyword_data: bool = False
    has_stats_nz_data: bool = False
    supplier_count: int = 0
    has_shipping_quote: bool = False
    has_trade_me_own_sales: bool = False
    has_30_day_experiment: bool = False


class ScoreSnapshot(BaseModel):
    product_id: str
    sku: str
    product_name: str
    search_demand_score: Decimal
    import_evidence_score: Decimal
    unit_economics_score: Decimal
    logistics_score: Decimal
    supply_quality_score: Decimal
    product_risk_fit_score: Decimal
    prelaunch_score: Decimal
    confidence: int
    status: Literal["QUALIFIED", "REJECT", "BLOCKED", "CANDIDATE"]
    rejection_reasons: list[str] = Field(default_factory=list)


class HsMapping(BaseModel):
    product_id: str
    hs_code: str
    mapping_confidence: int
    analyst_notes: str | None = None
    requires_manual_confirmation: bool

