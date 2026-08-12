from decimal import Decimal

from product_scout.imports import calculate_import_evidence_score
from product_scout.models import ImportMetric, KeywordMetric, ProductCandidate
from product_scout.risk import evaluate_product_risk
from product_scout.scoring import (
    ConfidenceInputs,
    build_score_snapshot,
    rank_opportunities,
)
from product_scout.search import calculate_search_demand_scores


def _product(
    product_id: str,
    name: str,
    sku: str,
    product_type: str,
    price: str = "29.90",
    hs_code: str = "9002900000",
) -> ProductCandidate:
    return ProductCandidate(
        id=product_id,
        canonical_name=name,
        sku=sku,
        category="adapter",
        subcategory=product_type.replace("_", " "),
        product_type=product_type,
        weight_g=40,
        length_mm=50,
        width_mm=50,
        height_mm=15,
        hs_code=hs_code,
        expected_sell_price_nzd=Decimal(price),
    )


def test_risk_rules_block_high_risk_products_and_allow_passive_accessories():
    solar = _product("p1", "Solar Telescope Filter", "SOLAR-FILTER", "solar_filter")
    laser = _product("p2", "High Power Laser Collimator", "LASER-COLL", "laser_collimator")
    battery = _product("p3", "Powered Dew Heater Battery Pack", "DEW-BATT", "dew_heater")
    adapter = _product("p4", "M48 to T2 Adapter", "M48-T2", "thread_adapter")

    assert evaluate_product_risk(solar).status == "BLOCKED"
    assert evaluate_product_risk(laser).status == "BLOCKED"
    assert evaluate_product_risk(battery).status == "BLOCKED"
    assert evaluate_product_risk(adapter).status == "LOW"


def test_search_demand_clusters_synonyms_and_penalizes_missing_data_confidence():
    product_a = _product("p1", "M48 to T2 Adapter", "M48-T2", "thread_adapter")
    product_b = _product("p2", "Dust Cap", "DUST-CAP", "dust_cap")
    metrics = [
        KeywordMetric(product_id="p1", keyword="m48 t2 adapter", keyword_cluster="m48_t2_adapter", monthly_searches=210, monthly_history=[160, 170, 180, 190, 200, 210, 210, 220, 225, 230, 235, 240]),
        KeywordMetric(product_id="p1", keyword="telescope t adapter", keyword_cluster="m48_t2_adapter", monthly_searches=190, monthly_history=[150, 160, 170, 180, 185, 190, 195, 200, 200, 205, 210, 215]),
        KeywordMetric(product_id="p2", keyword="dust cap telescope", keyword_cluster="dust_cap", monthly_searches=20, monthly_history=[20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20]),
    ]

    scores = calculate_search_demand_scores([product_a, product_b], metrics)

    assert scores["p1"].cluster_monthly_searches == {"m48_t2_adapter": 210}
    assert scores["p1"].score > scores["p2"].score
    assert scores["p1"].confidence == 100
    assert calculate_search_demand_scores([product_a], [])["p1"].confidence == 0


def test_import_evidence_calculates_china_share_growth_and_caps_low_value_accessories():
    metrics = [
        ImportMetric(hs_code="9002900000", year=2023, month=1, origin_country="China", import_nzd=Decimal("10000"), quantity=100, unit="EA"),
        ImportMetric(hs_code="9002900000", year=2023, month=1, origin_country="World", import_nzd=Decimal("20000"), quantity=200, unit="EA"),
        ImportMetric(hs_code="9002900000", year=2024, month=1, origin_country="China", import_nzd=Decimal("15000"), quantity=140, unit="EA"),
        ImportMetric(hs_code="9002900000", year=2024, month=1, origin_country="World", import_nzd=Decimal("30000"), quantity=280, unit="EA"),
        ImportMetric(hs_code="9002900000", year=2025, month=1, origin_country="China", import_nzd=Decimal("22000"), quantity=190, unit="EA"),
        ImportMetric(hs_code="9002900000", year=2025, month=1, origin_country="World", import_nzd=Decimal("40000"), quantity=350, unit="EA"),
    ]

    score = calculate_import_evidence_score("9002900000", metrics, low_value_accessory=True)

    assert score.china_share == Decimal("0.5500")
    assert score.import_value_12m_nzd == Decimal("40000")
    assert score.cagr_3y > Decimal("0.40")
    assert score.score <= 70


def test_prelaunch_ranking_uses_evidence_chain_not_margin_alone():
    strong_demand = _product("p1", "M48 to T2 Adapter", "M48-T2", "thread_adapter")
    no_demand = _product("p2", "Obscure High Margin Bracket", "ODD-BRACKET", "bracket", price="79.90")

    snapshots = [
        build_score_snapshot(
            strong_demand,
            search_score=82,
            import_score=65,
            unit_economics_score=74,
            logistics_score=95,
            supply_quality_score=80,
            risk_fit_score=100,
            confidence_inputs=ConfidenceInputs(has_google_keyword_data=True, has_stats_nz_data=True, supplier_count=3, has_shipping_quote=True),
        ),
        build_score_snapshot(
            no_demand,
            search_score=0,
            import_score=65,
            unit_economics_score=100,
            logistics_score=95,
            supply_quality_score=80,
            risk_fit_score=100,
            confidence_inputs=ConfidenceInputs(has_google_keyword_data=False, has_stats_nz_data=True, supplier_count=3, has_shipping_quote=True),
        ),
    ]

    ranked = rank_opportunities(snapshots)

    assert ranked[0].product_id == "p1"
    assert ranked[0].prelaunch_score > ranked[1].prelaunch_score
    assert ranked[1].confidence < ranked[0].confidence

