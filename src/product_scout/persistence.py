from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, TypeVar

from .models import (
    EconomicsResult,
    ImportMetric,
    KeywordMetric,
    ProductCandidate,
    ScoreSnapshot,
    ShippingRate,
    SupplierOffer,
)
from .repository import InMemoryRepository

T = TypeVar("T")


class JsonRepositoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, repo: InMemoryRepository) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "products": [
                product.model_dump(mode="json") for product in repo.products.values()
            ],
            "supplier_offers": [
                offer.model_dump(mode="json") for offer in repo.offers_by_sku.values()
            ],
            "shipping_rates": [
                rate.model_dump(mode="json") for rate in repo.shipping_rates
            ],
            "economics": [
                result.model_dump(mode="json")
                for result in repo.economics_by_product.values()
            ],
            "keyword_metrics": [
                metric.model_dump(mode="json") for metric in repo.keyword_metrics
            ],
            "import_metrics": [
                metric.model_dump(mode="json") for metric in repo.import_metrics
            ],
            "score_snapshots": [
                snapshot.model_dump(mode="json")
                for snapshot in repo.score_snapshots.values()
            ],
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load(self) -> InMemoryRepository:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        repo = InMemoryRepository()
        repo.products = {
            product.id: product
            for product in (
                ProductCandidate(**item) for item in payload.get("products", [])
            )
        }
        repo.offers_by_sku = {
            offer.sku: offer
            for offer in (
                SupplierOffer(**item) for item in payload.get("supplier_offers", [])
            )
        }
        repo.shipping_rates = [
            ShippingRate(**item) for item in payload.get("shipping_rates", [])
        ]
        repo.economics_by_product = {
            result.product_id: result
            for result in (
                EconomicsResult(**item) for item in payload.get("economics", [])
            )
        }
        repo.keyword_metrics = [
            KeywordMetric(**item) for item in payload.get("keyword_metrics", [])
        ]
        repo.import_metrics = [
            ImportMetric(**item) for item in payload.get("import_metrics", [])
        ]
        repo.score_snapshots = {
            snapshot.product_id: snapshot
            for snapshot in (
                ScoreSnapshot(**item) for item in payload.get("score_snapshots", [])
            )
        }
        return repo


class SQLiteRepositoryStore:
    """Local durable store for the V1 repository without adding an ORM dependency."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, repo: InMemoryRepository) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            self._create_schema(connection)
            self._replace_rows(
                connection,
                "product_candidate",
                "id",
                ((product.id, product.model_dump(mode="json")) for product in repo.products.values()),
            )
            self._replace_rows(
                connection,
                "supplier_offer",
                "sku",
                ((offer.sku, offer.model_dump(mode="json")) for offer in repo.offers_by_sku.values()),
            )
            self._replace_rows(
                connection,
                "shipping_rate",
                "id",
                (
                    (f"{rate.provider}:{rate.route}:{rate.min_weight_g}:{rate.max_weight_g}", rate.model_dump(mode="json"))
                    for rate in repo.shipping_rates
                ),
            )
            self._replace_rows(
                connection,
                "economics_result",
                "product_id",
                (
                    (result.product_id, result.model_dump(mode="json"))
                    for result in repo.economics_by_product.values()
                ),
            )
            self._replace_rows(
                connection,
                "keyword_metric",
                "id",
                (
                    (f"{index}:{metric.product_id}:{metric.keyword}", metric.model_dump(mode="json"))
                    for index, metric in enumerate(repo.keyword_metrics)
                ),
            )
            self._replace_rows(
                connection,
                "import_metric",
                "id",
                (
                    (
                        f"{metric.hs_code}:{metric.year}:{metric.month}:{metric.origin_country}",
                        metric.model_dump(mode="json"),
                    )
                    for metric in repo.import_metrics
                ),
            )
            self._replace_rows(
                connection,
                "score_snapshot",
                "product_id",
                (
                    (snapshot.product_id, snapshot.model_dump(mode="json"))
                    for snapshot in repo.score_snapshots.values()
                ),
            )

    def load(self) -> InMemoryRepository:
        repo = InMemoryRepository()
        if not self.path.exists():
            return repo
        with sqlite3.connect(self.path) as connection:
            self._create_schema(connection)
            repo.products = {
                product.id: product
                for product in self._load_models(
                    connection, "product_candidate", ProductCandidate
                )
            }
            repo.offers_by_sku = {
                offer.sku: offer
                for offer in self._load_models(connection, "supplier_offer", SupplierOffer)
            }
            repo.shipping_rates = self._load_models(connection, "shipping_rate", ShippingRate)
            repo.economics_by_product = {
                result.product_id: result
                for result in self._load_models(
                    connection, "economics_result", EconomicsResult
                )
            }
            repo.keyword_metrics = self._load_models(
                connection, "keyword_metric", KeywordMetric
            )
            repo.import_metrics = self._load_models(
                connection, "import_metric", ImportMetric
            )
            repo.score_snapshots = {
                snapshot.product_id: snapshot
                for snapshot in self._load_models(
                    connection, "score_snapshot", ScoreSnapshot
                )
            }
        return repo

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        for table, key in [
            ("product_candidate", "id"),
            ("supplier_offer", "sku"),
            ("shipping_rate", "id"),
            ("economics_result", "product_id"),
            ("keyword_metric", "id"),
            ("import_metric", "id"),
            ("score_snapshot", "product_id"),
        ]:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    {key} TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _replace_rows(
        connection: sqlite3.Connection,
        table: str,
        key_column: str,
        rows: Iterable[tuple[str, dict]],
    ) -> None:
        connection.execute(f"DELETE FROM {table}")
        connection.executemany(
            f"INSERT INTO {table} ({key_column}, payload) VALUES (?, ?)",
            ((key, json.dumps(payload, ensure_ascii=False)) for key, payload in rows),
        )

    @staticmethod
    def _load_models(
        connection: sqlite3.Connection,
        table: str,
        model: type[T],
    ) -> list[T]:
        rows = connection.execute(f"SELECT payload FROM {table}").fetchall()
        return [model(**json.loads(row[0])) for row in rows]
