from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation

from .models import (
    Dimensions,
    HsMapping,
    ImportMetric,
    KeywordMetric,
    KeywordSeed,
    ProductCandidate,
    ShippingRate,
    SupplierOffer,
)


class CSVValidationError(ValueError):
    pass


SUPPLIER_COLUMNS = {
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
}

SHIPPING_COLUMNS = {
    "provider",
    "route",
    "min_weight_g",
    "max_weight_g",
    "volumetric_divisor",
    "base_fee_cny",
    "fee_per_kg_cny",
    "delivery_days",
}

HS_MAPPING_COLUMNS = {
    "product_id",
    "hs_code",
    "mapping_confidence",
    "analyst_notes",
}

STATS_NZ_COLUMNS = {
    "hs_code",
    "year",
    "month",
    "origin_country",
    "import_nzd",
    "quantity",
    "unit",
}

PRODUCT_COLUMNS = {
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
    "hs_code",
    "expected_sell_price_nzd",
}

KEYWORD_COLUMNS = {
    "product_id",
    "keyword",
    "keyword_cluster",
    "monthly_searches",
    "monthly_history",
    "competition_index",
    "bid_low",
    "bid_high",
}

KEYWORD_SEED_COLUMNS = {
    "product_id",
    "keyword",
    "keyword_cluster",
}


def import_supplier_offers_csv(csv_text: str) -> list[SupplierOffer]:
    rows = _read_rows(csv_text, SUPPLIER_COLUMNS)
    seen_skus: set[str] = set()
    offers: list[SupplierOffer] = []
    for row_number, row in enumerate(rows, start=2):
        sku = _required_text(row, "sku", row_number)
        if sku in seen_skus:
            raise CSVValidationError(f"Duplicate sku '{sku}' at row {row_number}")
        seen_skus.add(sku)
        try:
            offers.append(
                SupplierOffer(
                    id=f"supplier_offer_{sku}",
                    source_url=_required_text(row, "source_url", row_number),
                    product_name=_required_text(row, "product_name", row_number),
                    sku=sku,
                    unit_price_cny=_decimal(row, "unit_price_cny", row_number),
                    moq=_int(row, "moq", row_number),
                    weight_g=_int(row, "weight_g", row_number),
                    package_dimensions=Dimensions(
                        length_mm=_int(row, "length_mm", row_number),
                        width_mm=_int(row, "width_mm", row_number),
                        height_mm=_int(row, "height_mm", row_number),
                    ),
                    domestic_shipping_cny=_decimal(row, "domestic_shipping_cny", row_number),
                    supplier=_required_text(row, "supplier", row_number),
                    monthly_sales_ref=_optional_int(row, "monthly_sales_ref", row_number),
                    lead_time_days=_int(row, "lead_time_days", row_number),
                )
            )
        except ValueError as exc:
            raise CSVValidationError(f"Invalid supplier row {row_number}: {exc}") from exc
    return offers


def import_product_candidates_csv(csv_text: str) -> list[ProductCandidate]:
    rows = _read_rows(csv_text, PRODUCT_COLUMNS)
    seen_ids: set[str] = set()
    seen_skus: set[str] = set()
    products: list[ProductCandidate] = []
    for row_number, row in enumerate(rows, start=2):
        product_id = _required_text(row, "id", row_number)
        sku = _required_text(row, "sku", row_number)
        if product_id in seen_ids:
            raise CSVValidationError(f"Duplicate product id '{product_id}' at row {row_number}")
        if sku in seen_skus:
            raise CSVValidationError(f"Duplicate sku '{sku}' at row {row_number}")
        seen_ids.add(product_id)
        seen_skus.add(sku)
        products.append(
            ProductCandidate(
                id=product_id,
                canonical_name=_required_text(row, "canonical_name", row_number),
                sku=sku,
                category=_required_text(row, "category", row_number),
                subcategory=_required_text(row, "subcategory", row_number),
                product_type=_required_text(row, "product_type", row_number),
                weight_g=_int(row, "weight_g", row_number),
                length_mm=_int(row, "length_mm", row_number),
                width_mm=_int(row, "width_mm", row_number),
                height_mm=_int(row, "height_mm", row_number),
                thread_a=_optional_text(row, "thread_a"),
                thread_b=_optional_text(row, "thread_b"),
                material=_optional_text(row, "material"),
                electrical=_bool(row, "electrical"),
                battery=_bool(row, "battery"),
                laser=_bool(row, "laser"),
                solar_observation=_bool(row, "solar_observation"),
                safety_risk=_optional_text(row, "safety_risk"),
                hs_code=_optional_text(row, "hs_code"),
                trademe_category_id=_optional_text(row, "trademe_category_id"),
                expected_sell_price_nzd=_decimal(row, "expected_sell_price_nzd", row_number),
            )
        )
    return products


def import_shipping_rates_csv(csv_text: str) -> list[ShippingRate]:
    rows = _read_rows(csv_text, SHIPPING_COLUMNS)
    rates: list[ShippingRate] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            rates.append(
                ShippingRate(
                    provider=_required_text(row, "provider", row_number),
                    route=_required_text(row, "route", row_number),
                    min_weight_g=_non_negative_int(row, "min_weight_g", row_number),
                    max_weight_g=_int(row, "max_weight_g", row_number),
                    volumetric_divisor=_decimal(row, "volumetric_divisor", row_number),
                    base_fee_cny=_decimal(row, "base_fee_cny", row_number),
                    fee_per_kg_cny=_decimal(row, "fee_per_kg_cny", row_number),
                    delivery_days=_int(row, "delivery_days", row_number),
                )
            )
        except ValueError as exc:
            raise CSVValidationError(f"Invalid shipping row {row_number}: {exc}") from exc
    return rates


def import_hs_mapping_csv(csv_text: str) -> list[HsMapping]:
    rows = _read_rows(csv_text, HS_MAPPING_COLUMNS)
    mappings: list[HsMapping] = []
    for row_number, row in enumerate(rows, start=2):
        confidence = _int(row, "mapping_confidence", row_number)
        mappings.append(
            HsMapping(
                product_id=_required_text(row, "product_id", row_number),
                hs_code=_required_text(row, "hs_code", row_number),
                mapping_confidence=confidence,
                analyst_notes=(row.get("analyst_notes") or "").strip() or None,
                requires_manual_confirmation=confidence < 80,
            )
        )
    return mappings


def import_stats_nz_csv(csv_text: str) -> list[ImportMetric]:
    rows = _read_rows(csv_text, STATS_NZ_COLUMNS)
    metrics: list[ImportMetric] = []
    for row_number, row in enumerate(rows, start=2):
        metrics.append(
            ImportMetric(
                hs_code=_required_text(row, "hs_code", row_number),
                year=_int(row, "year", row_number),
                month=_month(row, row_number),
                origin_country=_required_text(row, "origin_country", row_number),
                import_nzd=_decimal(row, "import_nzd", row_number),
                quantity=_optional_decimal(row, "quantity", row_number),
                unit=(row.get("unit") or "").strip() or None,
            )
        )
    return metrics


def import_keyword_metrics_csv(csv_text: str) -> list[KeywordMetric]:
    rows = _read_rows(csv_text, KEYWORD_COLUMNS)
    metrics: list[KeywordMetric] = []
    for row_number, row in enumerate(rows, start=2):
        metrics.append(
            KeywordMetric(
                product_id=_required_text(row, "product_id", row_number),
                keyword=_required_text(row, "keyword", row_number),
                keyword_cluster=_required_text(row, "keyword_cluster", row_number),
                monthly_searches=_optional_non_negative_int(
                    row, "monthly_searches", row_number
                ),
                monthly_history=_monthly_history(row, row_number),
                competition_index=_optional_non_negative_int(
                    row, "competition_index", row_number
                ),
                bid_low=_optional_decimal(row, "bid_low", row_number),
                bid_high=_optional_decimal(row, "bid_high", row_number),
            )
        )
    return metrics


def import_keyword_seeds_csv(csv_text: str) -> list[KeywordSeed]:
    rows = _read_rows(csv_text, KEYWORD_SEED_COLUMNS)
    seeds: list[KeywordSeed] = []
    seen: set[tuple[str, str]] = set()
    for row_number, row in enumerate(rows, start=2):
        product_id = _required_text(row, "product_id", row_number)
        keyword = _required_text(row, "keyword", row_number)
        key = (product_id, " ".join(keyword.lower().split()))
        if key in seen:
            raise CSVValidationError(
                f"Duplicate keyword seed '{keyword}' for product '{product_id}' at row {row_number}"
            )
        seen.add(key)
        seeds.append(
            KeywordSeed(
                product_id=product_id,
                keyword=keyword,
                keyword_cluster=_required_text(row, "keyword_cluster", row_number),
            )
        )
    return seeds


def _read_rows(csv_text: str, required_columns: set[str]) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    columns = set(reader.fieldnames or [])
    missing = sorted(required_columns - columns)
    if missing:
        raise CSVValidationError(f"Missing required columns: {', '.join(missing)}")
    return list(reader)


def _required_text(row: dict[str, str], field: str, row_number: int) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise CSVValidationError(f"Missing {field} at row {row_number}")
    return value


def _optional_text(row: dict[str, str], field: str) -> str | None:
    value = (row.get(field) or "").strip()
    return value or None


def _decimal(row: dict[str, str], field: str, row_number: int) -> Decimal:
    text = _required_text(row, field, row_number)
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise CSVValidationError(f"Invalid {field} at row {row_number}") from exc
    if value < 0:
        raise CSVValidationError(f"Invalid {field} at row {row_number}: must be non-negative")
    return value


def _int(row: dict[str, str], field: str, row_number: int) -> int:
    text = _required_text(row, field, row_number)
    try:
        value = int(text)
    except ValueError as exc:
        raise CSVValidationError(f"Invalid {field} at row {row_number}") from exc
    if value <= 0:
        raise CSVValidationError(f"Invalid {field} at row {row_number}: must be positive")
    return value


def _optional_int(row: dict[str, str], field: str, row_number: int) -> int | None:
    text = (row.get(field) or "").strip()
    if not text:
        return None
    try:
        value = int(text)
    except ValueError as exc:
        raise CSVValidationError(f"Invalid {field} at row {row_number}") from exc
    if value < 0:
        raise CSVValidationError(f"Invalid {field} at row {row_number}: must be non-negative")
    return value


def _optional_non_negative_int(
    row: dict[str, str], field: str, row_number: int
) -> int | None:
    text = (row.get(field) or "").strip()
    if not text:
        return None
    try:
        value = int(text)
    except ValueError as exc:
        raise CSVValidationError(f"Invalid {field} at row {row_number}") from exc
    if value < 0:
        raise CSVValidationError(f"Invalid {field} at row {row_number}: must be non-negative")
    return value


def _optional_decimal(row: dict[str, str], field: str, row_number: int) -> Decimal | None:
    text = (row.get(field) or "").strip()
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise CSVValidationError(f"Invalid {field} at row {row_number}") from exc
    if value < 0:
        raise CSVValidationError(f"Invalid {field} at row {row_number}: must be non-negative")
    return value


def _non_negative_int(row: dict[str, str], field: str, row_number: int) -> int:
    text = _required_text(row, field, row_number)
    try:
        value = int(text)
    except ValueError as exc:
        raise CSVValidationError(f"Invalid {field} at row {row_number}") from exc
    if value < 0:
        raise CSVValidationError(f"Invalid {field} at row {row_number}: must be non-negative")
    return value


def _month(row: dict[str, str], row_number: int) -> int:
    value = _int(row, "month", row_number)
    if value < 1 or value > 12:
        raise CSVValidationError(f"Invalid month at row {row_number}: must be 1-12")
    return value


def _monthly_history(row: dict[str, str], row_number: int) -> list[int]:
    text = (row.get("monthly_history") or "").strip()
    if not text:
        return []
    values: list[int] = []
    for part in text.replace(",", "|").split("|"):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError as exc:
            raise CSVValidationError(f"Invalid monthly_history at row {row_number}") from exc
        if value < 0:
            raise CSVValidationError(
                f"Invalid monthly_history at row {row_number}: must be non-negative"
            )
        values.append(value)
    return values


def _bool(row: dict[str, str], field: str) -> bool:
    text = (row.get(field) or "").strip().lower()
    if not text:
        return False
    return text in {"1", "true", "yes", "y"}
