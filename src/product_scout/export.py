from __future__ import annotations

import csv
from pathlib import Path
from typing import TextIO

from .models import KeywordMetric, KeywordSeed, ProductCandidate, ScoreSnapshot, SupplierOffer
from .scoring import rank_opportunities


OPPORTUNITY_COLUMNS = [
    "rank",
    "product_id",
    "sku",
    "product_name",
    "prelaunch_score",
    "confidence",
    "status",
    "search_demand_score",
    "import_evidence_score",
    "unit_economics_score",
    "logistics_score",
    "supply_quality_score",
    "product_risk_fit_score",
    "rejection_reasons",
]

KEYWORD_METRIC_COLUMNS = [
    "product_id",
    "keyword",
    "keyword_cluster",
    "monthly_searches",
    "monthly_history",
    "competition_index",
    "bid_low",
    "bid_high",
]

PRODUCT_COLUMNS = [
    "id",
    "canonical_name",
    "sku",
    "category",
    "subcategory",
    "product_type",
    "weight_g",
    "length_mm",
    "width_mm",
    "height_mm",
    "thread_a",
    "thread_b",
    "material",
    "electrical",
    "battery",
    "laser",
    "solar_observation",
    "safety_risk",
    "hs_code",
    "trademe_category_id",
    "expected_sell_price_nzd",
]

SUPPLIER_OFFER_COLUMNS = [
    "source_url",
    "product_name",
    "sku",
    "unit_price_cny",
    "moq",
    "weight_g",
    "length_mm",
    "width_mm",
    "height_mm",
    "domestic_shipping_cny",
    "supplier",
    "monthly_sales_ref",
    "lead_time_days",
]

KEYWORD_SEED_COLUMNS = ["product_id", "keyword", "keyword_cluster"]


def export_opportunities_csv(
    snapshots: list[ScoreSnapshot], destination: str | Path | TextIO
) -> None:
    should_close = False
    if hasattr(destination, "write"):
        handle = destination
    else:
        handle = Path(destination).open("w", newline="", encoding="utf-8")
        should_close = True
    try:
        writer = csv.DictWriter(handle, fieldnames=OPPORTUNITY_COLUMNS)
        writer.writeheader()
        for rank, snapshot in enumerate(rank_opportunities(snapshots), start=1):
            writer.writerow(
                {
                    "rank": rank,
                    "product_id": snapshot.product_id,
                    "sku": snapshot.sku,
                    "product_name": snapshot.product_name,
                    "prelaunch_score": snapshot.prelaunch_score,
                    "confidence": snapshot.confidence,
                    "status": snapshot.status,
                    "search_demand_score": snapshot.search_demand_score,
                    "import_evidence_score": snapshot.import_evidence_score,
                    "unit_economics_score": snapshot.unit_economics_score,
                    "logistics_score": snapshot.logistics_score,
                    "supply_quality_score": snapshot.supply_quality_score,
                    "product_risk_fit_score": snapshot.product_risk_fit_score,
                    "rejection_reasons": "|".join(snapshot.rejection_reasons),
                }
            )
    finally:
        if should_close:
            handle.close()


def export_keyword_metrics_csv(
    metrics: list[KeywordMetric], destination: str | Path | TextIO
) -> None:
    should_close = False
    if hasattr(destination, "write"):
        handle = destination
    else:
        handle = Path(destination).open("w", newline="", encoding="utf-8")
        should_close = True
    try:
        writer = csv.DictWriter(handle, fieldnames=KEYWORD_METRIC_COLUMNS)
        writer.writeheader()
        for metric in sorted(metrics, key=lambda item: (item.product_id, item.keyword)):
            writer.writerow(
                {
                    "product_id": metric.product_id,
                    "keyword": metric.keyword,
                    "keyword_cluster": metric.keyword_cluster,
                    "monthly_searches": _blank_if_none(metric.monthly_searches),
                    "monthly_history": "|".join(str(value) for value in metric.monthly_history),
                    "competition_index": _blank_if_none(metric.competition_index),
                    "bid_low": _blank_if_none(metric.bid_low),
                    "bid_high": _blank_if_none(metric.bid_high),
                }
            )
    finally:
        if should_close:
            handle.close()


def _blank_if_none(value) -> str:
    return "" if value is None else str(value)


def export_products_csv(products: list[ProductCandidate], destination: str | Path | TextIO) -> None:
    handle, should_close = _open_destination(destination)
    try:
        writer = csv.DictWriter(handle, fieldnames=PRODUCT_COLUMNS)
        writer.writeheader()
        for product in products:
            writer.writerow(
                {
                    "id": product.id,
                    "canonical_name": product.canonical_name,
                    "sku": product.sku,
                    "category": product.category,
                    "subcategory": product.subcategory,
                    "product_type": product.product_type,
                    "weight_g": product.weight_g,
                    "length_mm": product.length_mm,
                    "width_mm": product.width_mm,
                    "height_mm": product.height_mm,
                    "thread_a": _blank_if_none(product.thread_a),
                    "thread_b": _blank_if_none(product.thread_b),
                    "material": _blank_if_none(product.material),
                    "electrical": product.electrical,
                    "battery": product.battery,
                    "laser": product.laser,
                    "solar_observation": product.solar_observation,
                    "safety_risk": _blank_if_none(product.safety_risk),
                    "hs_code": _blank_if_none(product.hs_code),
                    "trademe_category_id": _blank_if_none(product.trademe_category_id),
                    "expected_sell_price_nzd": product.expected_sell_price_nzd,
                }
            )
    finally:
        if should_close:
            handle.close()


def export_supplier_offers_csv(
    offers: list[SupplierOffer], destination: str | Path | TextIO
) -> None:
    handle, should_close = _open_destination(destination)
    try:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_OFFER_COLUMNS)
        writer.writeheader()
        for offer in offers:
            writer.writerow(
                {
                    "source_url": offer.source_url,
                    "product_name": offer.product_name,
                    "sku": offer.sku,
                    "unit_price_cny": offer.unit_price_cny,
                    "moq": offer.moq,
                    "weight_g": offer.weight_g,
                    "length_mm": offer.package_dimensions.length_mm,
                    "width_mm": offer.package_dimensions.width_mm,
                    "height_mm": offer.package_dimensions.height_mm,
                    "domestic_shipping_cny": offer.domestic_shipping_cny,
                    "supplier": offer.supplier,
                    "monthly_sales_ref": _blank_if_none(offer.monthly_sales_ref),
                    "lead_time_days": offer.lead_time_days,
                }
            )
    finally:
        if should_close:
            handle.close()


def export_keyword_seeds_csv(seeds: list[KeywordSeed], destination: str | Path | TextIO) -> None:
    handle, should_close = _open_destination(destination)
    try:
        writer = csv.DictWriter(handle, fieldnames=KEYWORD_SEED_COLUMNS)
        writer.writeheader()
        for seed in seeds:
            writer.writerow(
                {
                    "product_id": seed.product_id,
                    "keyword": seed.keyword,
                    "keyword_cluster": seed.keyword_cluster,
                }
            )
    finally:
        if should_close:
            handle.close()


def _open_destination(destination: str | Path | TextIO) -> tuple[TextIO, bool]:
    if hasattr(destination, "write"):
        return destination, False
    return Path(destination).open("w", newline="", encoding="utf-8"), True
