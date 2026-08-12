from __future__ import annotations

from collections import defaultdict

from .models import (
    EconomicsResult,
    ImportMetric,
    KeywordMetric,
    ProductCandidate,
    ScoreSnapshot,
    ShippingRate,
    SupplierOffer,
)


class InMemoryRepository:
    def __init__(self) -> None:
        self.products: dict[str, ProductCandidate] = {}
        self.offers_by_sku: dict[str, SupplierOffer] = {}
        self.shipping_rates: list[ShippingRate] = []
        self.economics_by_product: dict[str, EconomicsResult] = {}
        self.keyword_metrics: list[KeywordMetric] = []
        self.import_metrics: list[ImportMetric] = []
        self.score_snapshots: dict[str, ScoreSnapshot] = {}

    def import_products(
        self,
        products: list[ProductCandidate],
        offers: list[SupplierOffer],
        shipping_rates: list[ShippingRate],
    ) -> None:
        for product in products:
            self.products[product.id] = product
        for offer in offers:
            matching = next((product for product in products if product.sku == offer.sku), None)
            if matching:
                offer.product_id = matching.id
            self.offers_by_sku[offer.sku] = offer
        self.shipping_rates = shipping_rates

    def offers_by_product_id(self) -> dict[str, list[SupplierOffer]]:
        grouped: dict[str, list[SupplierOffer]] = defaultdict(list)
        for offer in self.offers_by_sku.values():
            if offer.product_id:
                grouped[offer.product_id].append(offer)
        return dict(grouped)

