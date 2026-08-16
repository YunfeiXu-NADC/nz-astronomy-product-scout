from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .batch import RankBatchPaths, run_rank_batch
from .csv_import import (
    CSVValidationError,
    import_shipping_rates_csv,
    import_stats_nz_csv,
    import_supplier_offers_csv,
)
from .discovery import build_discovery_result, parse_1688_html, parse_1688_json_payload
from .models import ImportMetric, KeywordMetric, ProductCandidate
from .pipeline import recalculate_repository
from .repository import InMemoryRepository
from .scoring import rank_opportunities
from .targets import (
    DEFAULT_BUSINESS_TARGETS,
    InventoryCommitment,
    assess_initial_inventory_risk,
)


class ProductImportRequest(BaseModel):
    supplier_offers_csv: str
    shipping_rates_csv: str
    products: list[ProductCandidate]


class KeywordRefreshRequest(BaseModel):
    metrics: list[KeywordMetric]


class ImportRefreshRequest(BaseModel):
    metrics: list[ImportMetric] = []
    stats_nz_csv: str | None = None


class BatchRankRequest(BaseModel):
    products_csv_path: str
    supplier_offers_csv_path: str
    shipping_rates_csv_path: str
    stats_nz_csv_path: str | None = None
    keyword_metrics_csv_path: str | None = None
    output_csv_path: str | None = None
    json_store_path: str | None = None
    sqlite_store_path: str | None = None


class Discover1688Request(BaseModel):
    source_html: str | None = None
    source_json: Any | None = None
    source_url: str = "uploaded_1688_source"
    limit: int = 100


class InventoryRiskRequest(BaseModel):
    commitments: list[InventoryCommitment]


def create_app(repository: InMemoryRepository | None = None) -> FastAPI:
    repo = repository or InMemoryRepository()
    app = FastAPI(title="NZ Astronomy Product Scout V1")

    @app.get("/business/targets")
    def business_targets() -> dict[str, Any]:
        return DEFAULT_BUSINESS_TARGETS.summary()

    @app.post("/business/inventory-risk")
    def inventory_risk(payload: InventoryRiskRequest) -> dict[str, Any]:
        return assess_initial_inventory_risk(payload.commitments)

    @app.post("/products/import")
    def import_products(payload: ProductImportRequest) -> dict[str, int]:
        try:
            offers = import_supplier_offers_csv(payload.supplier_offers_csv)
            shipping_rates = import_shipping_rates_csv(payload.shipping_rates_csv)
        except CSVValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repo.import_products(payload.products, offers, shipping_rates)
        recalculate_repository(repo)
        return {
            "imported_products": len(payload.products),
            "imported_supplier_offers": len(offers),
            "imported_shipping_rates": len(shipping_rates),
        }

    @app.post("/products")
    def create_product(product: ProductCandidate) -> dict[str, Any]:
        if product.id in repo.products:
            raise HTTPException(status_code=409, detail="product id already exists")
        if any(existing.sku == product.sku for existing in repo.products.values()):
            raise HTTPException(status_code=409, detail="sku already exists")
        repo.products[product.id] = product
        recalculate_repository(repo)
        return product.model_dump(mode="json")

    @app.get("/products")
    def list_products() -> list[dict[str, Any]]:
        return [
            product.model_dump(mode="json")
            for product in sorted(repo.products.values(), key=lambda item: item.sku)
        ]

    @app.get("/products/{product_id}")
    def get_product(product_id: str) -> dict[str, Any]:
        product = repo.products.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="product not found")
        return product.model_dump(mode="json")

    @app.patch("/products/{product_id}")
    def update_product(product_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        product = repo.products.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="product not found")
        updated = product.model_copy(update=patch)
        repo.products[product_id] = updated
        recalculate_repository(repo)
        return updated.model_dump(mode="json")

    @app.get("/products/{product_id}/economics")
    def get_economics(product_id: str) -> dict[str, Any]:
        if product_id not in repo.economics_by_product:
            raise HTTPException(status_code=404, detail="economics not found")
        return repo.economics_by_product[product_id].model_dump(mode="json")

    @app.post("/keywords/refresh")
    def refresh_keywords(payload: KeywordRefreshRequest) -> dict[str, int]:
        repo.keyword_metrics = payload.metrics
        recalculate_repository(repo)
        return {"updated_products": len({metric.product_id for metric in payload.metrics})}

    @app.post("/imports/refresh")
    def refresh_imports(payload: ImportRefreshRequest) -> dict[str, int]:
        try:
            csv_metrics = import_stats_nz_csv(payload.stats_nz_csv) if payload.stats_nz_csv else []
        except CSVValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repo.import_metrics = payload.metrics + csv_metrics
        recalculate_repository(repo)
        return {"imported_metrics": len(repo.import_metrics)}

    @app.post("/sources/1688/discover")
    def discover_1688_source(payload: Discover1688Request) -> dict[str, Any]:
        source_count = sum(bool(value) for value in [payload.source_html, payload.source_json])
        if source_count != 1:
            raise HTTPException(
                status_code=422,
                detail="Provide exactly one source_html or source_json payload",
            )
        listings = (
            parse_1688_html(
                payload.source_html or "",
                source_url=payload.source_url,
                limit=payload.limit,
            )
            if payload.source_html
            else parse_1688_json_payload(
                payload.source_json,
                source_url=payload.source_url,
                limit=payload.limit,
            )
        )
        if not listings:
            raise HTTPException(status_code=422, detail="No parseable 1688 listings found")
        result = build_discovery_result(listings)
        return {
            "discovered_listings": len(result.listings),
            "products": [product.model_dump(mode="json") for product in result.products],
            "supplier_offers": [
                offer.model_dump(mode="json") for offer in result.supplier_offers
            ],
            "keyword_seeds": [seed.model_dump(mode="json") for seed in result.keyword_seeds],
        }

    @app.get("/opportunities")
    def opportunities(
        status: str | None = None,
        min_score: float | None = None,
        min_confidence: int | None = None,
    ) -> list[dict[str, Any]]:
        snapshots = list(repo.score_snapshots.values())
        if status:
            snapshots = [snapshot for snapshot in snapshots if snapshot.status == status]
        if min_score is not None:
            snapshots = [snapshot for snapshot in snapshots if snapshot.prelaunch_score >= min_score]
        if min_confidence is not None:
            snapshots = [snapshot for snapshot in snapshots if snapshot.confidence >= min_confidence]
        return [snapshot.model_dump(mode="json") for snapshot in rank_opportunities(snapshots)]

    @app.get("/opportunities/{product_id}")
    def opportunity_detail(product_id: str) -> dict[str, Any]:
        product = repo.products.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="product not found")
        snapshot = repo.score_snapshots.get(product_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="opportunity not found")
        return {
            "product": product.model_dump(mode="json"),
            "economics": repo.economics_by_product.get(product_id).model_dump(mode="json")
            if product_id in repo.economics_by_product
            else None,
            "score": snapshot.model_dump(mode="json"),
        }

    @app.post("/batches/rank")
    def rank_batch(payload: BatchRankRequest) -> dict[str, Any]:
        try:
            result = run_rank_batch(
                RankBatchPaths(
                    products_csv_path=payload.products_csv_path,
                    supplier_offers_csv_path=payload.supplier_offers_csv_path,
                    shipping_rates_csv_path=payload.shipping_rates_csv_path,
                    stats_nz_csv_path=payload.stats_nz_csv_path,
                    keyword_metrics_csv_path=payload.keyword_metrics_csv_path,
                    output_csv_path=payload.output_csv_path,
                    json_store_path=payload.json_store_path,
                    sqlite_store_path=payload.sqlite_store_path,
                )
            )
        except (CSVValidationError, OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        repo.products = result.repo.products
        repo.offers_by_sku = result.repo.offers_by_sku
        repo.shipping_rates = result.repo.shipping_rates
        repo.economics_by_product = result.repo.economics_by_product
        repo.keyword_metrics = result.repo.keyword_metrics
        repo.import_metrics = result.repo.import_metrics
        repo.score_snapshots = result.repo.score_snapshots

        return {
            "ranked_products": len(result.ranked_product_ids),
            "top_sku": result.top_sku,
            "output_csv_path": payload.output_csv_path,
            "json_store_path": payload.json_store_path,
            "sqlite_store_path": payload.sqlite_store_path,
        }
    return app
