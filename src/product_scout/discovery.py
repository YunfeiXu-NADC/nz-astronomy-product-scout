from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_UP
import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin

from .models import (
    Dimensions,
    KeywordSeed,
    ProductCandidate,
    SourceListing,
    SupplierOffer,
)


class DiscoverySourceError(ValueError):
    pass


@dataclass(frozen=True)
class DiscoveryResult:
    listings: list[SourceListing]
    products: list[ProductCandidate]
    supplier_offers: list[SupplierOffer]
    keyword_seeds: list[KeywordSeed]


def fetch_1688_html(source_url: str, *, timeout_seconds: int = 30) -> str:
    """Fetch a 1688 page without login bypass or anti-bot circumvention."""

    try:
        import requests
    except ImportError as exc:  # pragma: no cover - dependency is installed in normal envs
        raise DiscoverySourceError("requests is required for direct URL discovery") from exc

    response = requests.get(
        source_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        timeout=timeout_seconds,
    )
    if response.status_code >= 400:
        raise DiscoverySourceError(
            f"1688 source request failed with HTTP {response.status_code}"
        )
    return response.text


def parse_1688_html(html: str, *, source_url: str, limit: int = 100) -> list[SourceListing]:
    listings: list[SourceListing] = []
    seen: set[tuple[str, str]] = set()
    for payload in _extract_json_values(html):
        for listing in _source_listings_from_json(payload, source_url=source_url):
            key = (listing.title.lower(), listing.source_url)
            if key in seen:
                continue
            seen.add(key)
            listings.append(listing)
            if len(listings) >= limit:
                return listings
    return listings


def parse_1688_json_payload(
    payload: Any, *, source_url: str, limit: int = 100
) -> list[SourceListing]:
    listings: list[SourceListing] = []
    seen: set[tuple[str, str]] = set()
    for listing in _source_listings_from_json(payload, source_url=source_url):
        key = (listing.title.lower(), listing.source_url)
        if key in seen:
            continue
        seen.add(key)
        listings.append(listing)
        if len(listings) >= limit:
            break
    return listings


def build_discovery_result(listings: list[SourceListing]) -> DiscoveryResult:
    products: list[ProductCandidate] = []
    offers: list[SupplierOffer] = []
    keyword_seeds: list[KeywordSeed] = []
    used_skus: set[str] = set()

    for listing in listings:
        metadata = infer_product_metadata(listing.title)
        base_sku = _sku_from_title(listing.title, metadata["product_type"])
        sku = _dedupe_sku(base_sku, used_skus)
        used_skus.add(sku)
        product_id = _product_id(listing.source_url, sku)
        canonical_name = _canonical_name(listing.title)
        expected_sell_price = estimate_sell_price_nzd(
            listing.unit_price_cny,
            product_type=metadata["product_type"],
        )

        products.append(
            ProductCandidate(
                id=product_id,
                canonical_name=canonical_name,
                sku=sku,
                category=metadata["category"],
                subcategory=metadata["subcategory"],
                product_type=metadata["product_type"],
                weight_g=listing.weight_g,
                length_mm=listing.length_mm,
                width_mm=listing.width_mm,
                height_mm=listing.height_mm,
                hs_code=metadata["hs_code"],
                electrical=metadata["electrical"],
                battery=metadata["battery"],
                laser=metadata["laser"],
                solar_observation=metadata["solar_observation"],
                safety_risk=metadata["safety_risk"],
                expected_sell_price_nzd=expected_sell_price,
            )
        )
        offers.append(
            SupplierOffer(
                id=f"supplier_offer_{sku}",
                product_id=product_id,
                source_url=listing.source_url,
                product_name=canonical_name,
                sku=sku,
                unit_price_cny=listing.unit_price_cny,
                moq=listing.moq,
                domestic_shipping_cny=listing.domestic_shipping_cny,
                supplier=listing.supplier,
                monthly_sales_ref=listing.monthly_sales_ref,
                lead_time_days=listing.lead_time_days,
                weight_g=listing.weight_g,
                package_dimensions=Dimensions(
                    length_mm=listing.length_mm,
                    width_mm=listing.width_mm,
                    height_mm=listing.height_mm,
                ),
            )
        )
        keyword_seeds.extend(_keyword_seeds(product_id, canonical_name, metadata["product_type"]))

    return DiscoveryResult(
        listings=listings,
        products=products,
        supplier_offers=offers,
        keyword_seeds=_dedupe_keyword_seeds(keyword_seeds),
    )


def infer_product_metadata(title: str) -> dict[str, Any]:
    text = title.lower()
    solar = _contains_any(text, ["solar", "sun observation", "sun filter", "太阳"])
    laser = _contains_any(text, ["laser", "激光"])
    battery = _contains_any(text, ["battery", "lithium", "18650", "锂电", "电池"])
    electrical = battery or _contains_any(
        text, ["powered", "usb", "electronic", "dew heater", "电动", "加热"]
    )

    if _contains_any(text, ["bahtinov", "focus mask", "巴赫金诺夫"]):
        product_type = "bahtinov_mask"
        category = "passive"
        subcategory = "focus mask"
        hs_code = "9002900000"
    elif _contains_any(text, ["dust cap", "dust cover", "防尘盖"]):
        product_type = "dust_cap"
        category = "passive"
        subcategory = "dust cap"
        hs_code = "9005900000"
    elif _contains_any(text, ["filter case", "filter box", "滤镜盒"]):
        product_type = "filter_case"
        category = "passive"
        subcategory = "filter case"
        hs_code = "9005900000"
    elif _contains_any(text, ["spacer", "extension ring", "延长环"]):
        product_type = "spacer"
        category = "adapter"
        subcategory = "spacer"
        hs_code = "9002900000"
    elif _contains_any(text, ["nosepiece", "eyepiece adapter", "目镜接口"]):
        product_type = "nosepiece_adapter"
        category = "adapter"
        subcategory = "nosepiece adapter"
        hs_code = "9002900000"
    elif _contains_any(text, ["camera adapter", "camera mount", "相机转接"]):
        product_type = "camera_adapter"
        category = "adapter"
        subcategory = "camera adapter"
        hs_code = "9002900000"
    elif _contains_any(text, ["bracket", "holder", "支架"]):
        product_type = "bracket"
        category = "mounting"
        subcategory = "bracket"
        hs_code = "9005900000"
    elif _contains_any(text, ["adapter", "adaptor", "t2", "m48", "m42", "转接"]):
        product_type = "thread_adapter"
        category = "adapter"
        subcategory = "thread adapter"
        hs_code = "9002900000"
    else:
        product_type = "astronomy_accessory"
        category = "passive"
        subcategory = "accessory"
        hs_code = "9005900000"

    risk_reasons = []
    if solar:
        risk_reasons.append("solar_observation")
    if laser:
        risk_reasons.append("laser")
    if battery:
        risk_reasons.append("battery")
    if electrical:
        risk_reasons.append("powered_electronics")

    return {
        "category": category,
        "subcategory": subcategory,
        "product_type": product_type,
        "hs_code": hs_code,
        "electrical": electrical,
        "battery": battery,
        "laser": laser,
        "solar_observation": solar,
        "safety_risk": ",".join(risk_reasons) or None,
    }


def estimate_sell_price_nzd(unit_price_cny: Decimal, *, product_type: str | None = None) -> Decimal:
    price_floor = {
        "thread_adapter": Decimal("39.90"),
        "camera_adapter": Decimal("39.90"),
        "nosepiece_adapter": Decimal("29.90"),
        "spacer": Decimal("24.90"),
        "bahtinov_mask": Decimal("24.90"),
        "bracket": Decimal("29.90"),
        "dust_cap": Decimal("14.90"),
        "filter_case": Decimal("14.90"),
    }.get(product_type or "", Decimal("19.90"))
    rough_nzd_cost = unit_price_cny * Decimal("0.23")
    estimated = max(price_floor, rough_nzd_cost * Decimal("4.0") + Decimal("12.00"))
    return _psychological_price(estimated)


def _source_listings_from_json(payload: Any, *, source_url: str) -> list[SourceListing]:
    listings: list[SourceListing] = []
    for item in _iter_dicts(payload):
        listing = _listing_from_mapping(item, source_url=source_url)
        if listing:
            listings.append(listing)
    return listings


def _listing_from_mapping(data: dict[str, Any], *, source_url: str) -> SourceListing | None:
    title = _pick_text(data, ["title", "subject", "name", "offerTitle", "productName"])
    price = _pick_decimal(
        data,
        ["unit_price_cny", "unitPriceCny", "price", "priceCny", "salePrice", "discountPrice"],
    )
    if not title or price is None:
        return None

    item_url = _normalize_url(
        _pick_text(data, ["source_url", "detailUrl", "detail_url", "url", "offerUrl", "productUrl"]),
        source_url,
    )
    return SourceListing(
        source="1688",
        source_url=item_url or source_url,
        title=title,
        unit_price_cny=price,
        moq=_pick_int(data, ["moq", "beginAmount", "minOrderQuantity", "minimumOrderQuantity"])
        or 1,
        weight_g=_pick_int(data, ["weight_g", "weightG", "grossWeightG", "weight"]) or 50,
        length_mm=_pick_int(data, ["length_mm", "lengthMm", "packageLengthMm"]) or 80,
        width_mm=_pick_int(data, ["width_mm", "widthMm", "packageWidthMm"]) or 80,
        height_mm=_pick_int(data, ["height_mm", "heightMm", "packageHeightMm"]) or 20,
        domestic_shipping_cny=_pick_decimal(
            data, ["domestic_shipping_cny", "domesticShippingCny", "postFee", "shippingFee"]
        )
        or Decimal("0"),
        supplier=_pick_text(data, ["supplier", "companyName", "sellerName", "shopName"])
        or "Unknown supplier",
        monthly_sales_ref=_pick_int(
            data, ["monthly_sales_ref", "monthlySalesRef", "saleQuantity", "soldCount"]
        ),
        lead_time_days=_pick_int(data, ["lead_time_days", "leadTimeDays", "deliveryDays"])
        or 7,
        image_url=_normalize_url(_pick_text(data, ["imageUrl", "image_url", "picUrl"]), source_url),
    )


def _extract_json_values(html: str) -> list[Any]:
    values: list[Any] = []
    decoder = json.JSONDecoder()
    for script in re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.IGNORECASE | re.DOTALL):
        for index, character in enumerate(script):
            if character not in "[{":
                continue
            try:
                value, _ = decoder.raw_decode(script[index:])
            except json.JSONDecodeError:
                continue
            values.append(value)
    if not values:
        for index, character in enumerate(html):
            if character not in "[{":
                continue
            try:
                value, _ = decoder.raw_decode(html[index:])
            except json.JSONDecodeError:
                continue
            values.append(value)
    return values


def _iter_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    queue = [value]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            found.append(current)
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    return found


def _pick_text(data: dict[str, Any], keys: list[str]) -> str | None:
    value = _pick_value(data, keys)
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _pick_decimal(data: dict[str, Any], keys: list[str]) -> Decimal | None:
    value = _pick_value(data, keys)
    if value is None:
        return None
    if isinstance(value, dict):
        value = _pick_value(value, ["value", "amount", "price"])
    text = str(value)
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        decimal = Decimal(match.group(0))
    except InvalidOperation:
        return None
    return decimal if decimal >= 0 else None


def _pick_int(data: dict[str, Any], keys: list[str]) -> int | None:
    value = _pick_value(data, keys)
    if value is None:
        return None
    text = str(value)
    match = re.search(r"\d+", text.replace(",", ""))
    if not match:
        return None
    integer = int(match.group(0))
    return integer if integer > 0 else None


def _pick_value(data: dict[str, Any], keys: list[str], *, max_depth: int = 2) -> Any:
    wanted = {key.lower() for key in keys}
    queue: list[tuple[dict[str, Any], int]] = [(data, 0)]
    while queue:
        current, depth = queue.pop(0)
        for key, value in current.items():
            if key.lower() in wanted:
                return value
        if depth >= max_depth:
            continue
        for value in current.values():
            if isinstance(value, dict):
                queue.append((value, depth + 1))
    return None


def _normalize_url(url: str | None, base_url: str) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    return urljoin(base_url, url)


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _canonical_name(title: str) -> str:
    cleaned = re.sub(r"[\u4e00-\u9fff]+", " ", title)
    cleaned = re.sub(r"[^\w\s.+/-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_/")
    return cleaned[:120] or title[:120]


def _sku_from_title(title: str, product_type: str) -> str:
    ascii_title = _canonical_name(title).upper()
    tokens = re.findall(r"[A-Z]*\d+[A-Z]*|[A-Z]+", ascii_title)
    skipped = {"FOR", "AND", "THE", "TO", "NEW"}
    tokens = [token for token in tokens if token not in skipped][:5]
    if not tokens:
        tokens = product_type.upper().split("_")
    sku = "-".join(tokens)
    return sku[:32].strip("-") or "DISCOVERY-SKU"


def _dedupe_sku(base_sku: str, used_skus: set[str]) -> str:
    if base_sku not in used_skus:
        return base_sku
    counter = 2
    while True:
        suffix = f"-{counter}"
        candidate = f"{base_sku[: 32 - len(suffix)]}{suffix}"
        if candidate not in used_skus:
            return candidate
        counter += 1


def _product_id(source_url: str, sku: str) -> str:
    digest = hashlib.sha1(f"{source_url}|{sku}".encode("utf-8")).hexdigest()[:10]
    return f"disc_{digest}"


def _keyword_seeds(product_id: str, canonical_name: str, product_type: str) -> list[KeywordSeed]:
    cluster = product_type
    seed_terms = [
        canonical_name.lower(),
        product_type.replace("_", " "),
    ]
    if "adapter" in product_type:
        seed_terms.append("telescope adapter")
    if product_type == "bahtinov_mask":
        seed_terms.append("bahtinov mask")
    if product_type == "dust_cap":
        seed_terms.append("telescope dust cap")
    return [
        KeywordSeed(
            product_id=product_id,
            keyword=re.sub(r"\s+", " ", term).strip(),
            keyword_cluster=cluster,
        )
        for term in seed_terms
        if term.strip()
    ]


def _dedupe_keyword_seeds(seeds: list[KeywordSeed]) -> list[KeywordSeed]:
    seen: set[tuple[str, str]] = set()
    deduped: list[KeywordSeed] = []
    for seed in seeds:
        key = (seed.product_id, seed.keyword.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(seed)
    return deduped


def _psychological_price(value: Decimal) -> Decimal:
    rounded_up = value.quantize(Decimal("1"), rounding=ROUND_UP)
    return max(Decimal("0.90"), rounded_up - Decimal("0.10"))
