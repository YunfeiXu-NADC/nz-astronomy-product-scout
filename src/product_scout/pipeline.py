from __future__ import annotations

from decimal import Decimal

from .economics import ChinaDirectCostEngine, logistics_score, unit_economics_score
from .imports import calculate_import_evidence_score
from .models import ConfidenceInputs
from .repository import InMemoryRepository
from .risk import evaluate_product_risk
from .scoring import build_score_snapshot, supply_quality_score
from .search import calculate_search_demand_scores


LOW_VALUE_ACCESSORY_TYPES = {
    "thread_adapter",
    "spacer",
    "nosepiece_adapter",
    "dust_cap",
    "filter_case",
}


def recalculate_repository(repo: InMemoryRepository) -> None:
    if not repo.products:
        return

    products = list(repo.products.values())
    offers_by_product = repo.offers_by_product_id()
    search_scores = calculate_search_demand_scores(products, repo.keyword_metrics)
    engine = ChinaDirectCostEngine(repo.shipping_rates) if repo.shipping_rates else None
    snapshots = {}

    for product in products:
        offer = offers_by_product.get(product.id, [None])[0]
        economics = None
        risk = evaluate_product_risk(product)
        rejection_reasons: list[str] = []

        if engine and offer:
            economics = engine.calculate(product, offer)
            repo.economics_by_product[product.id] = economics
            rejection_reasons.extend(economics.rejection_reasons)

        import_score = (
            calculate_import_evidence_score(
                product.hs_code,
                repo.import_metrics,
                low_value_accessory=product.product_type in LOW_VALUE_ACCESSORY_TYPES,
            )
            if product.hs_code
            else None
        )
        search = search_scores[product.id]
        supplier_count = len(offers_by_product.get(product.id, []))
        status = "BLOCKED" if risk.status == "BLOCKED" else None
        if economics and economics.status == "REJECT":
            status = "REJECT"

        snapshots[product.id] = build_score_snapshot(
            product,
            search_score=search.score,
            import_score=import_score.score if import_score else Decimal("0"),
            unit_economics_score=unit_economics_score(economics)
            if economics
            else Decimal("0"),
            logistics_score=logistics_score(economics.chargeable_weight_g, product)
            if economics
            else Decimal("0"),
            supply_quality_score=supply_quality_score(supplier_count),
            risk_fit_score=risk.score,
            confidence_inputs=ConfidenceInputs(
                has_google_keyword_data=search.confidence > 0,
                has_stats_nz_data=bool(import_score and import_score.confidence > 0),
                supplier_count=supplier_count,
                has_shipping_quote=economics is not None,
            ),
            status=status,
            rejection_reasons=rejection_reasons + risk.reasons,
        )

    repo.score_snapshots = snapshots

