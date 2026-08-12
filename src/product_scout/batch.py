from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .csv_import import (
    import_keyword_metrics_csv,
    import_product_candidates_csv,
    import_shipping_rates_csv,
    import_stats_nz_csv,
    import_supplier_offers_csv,
)
from .export import export_opportunities_csv
from .persistence import JsonRepositoryStore, SQLiteRepositoryStore
from .pipeline import recalculate_repository
from .repository import InMemoryRepository
from .scoring import rank_opportunities


@dataclass(frozen=True)
class RankBatchPaths:
    products_csv_path: str | Path
    supplier_offers_csv_path: str | Path
    shipping_rates_csv_path: str | Path
    stats_nz_csv_path: str | Path | None = None
    keyword_metrics_csv_path: str | Path | None = None
    output_csv_path: str | Path | None = None
    json_store_path: str | Path | None = None
    sqlite_store_path: str | Path | None = None


@dataclass(frozen=True)
class RankBatchResult:
    repo: InMemoryRepository
    ranked_product_ids: list[str]

    @property
    def top_sku(self) -> str | None:
        if not self.ranked_product_ids:
            return None
        return self.repo.score_snapshots[self.ranked_product_ids[0]].sku


def run_rank_batch(paths: RankBatchPaths) -> RankBatchResult:
    repo = InMemoryRepository()
    products = import_product_candidates_csv(_read_text(paths.products_csv_path))
    offers = import_supplier_offers_csv(_read_text(paths.supplier_offers_csv_path))
    shipping_rates = import_shipping_rates_csv(_read_text(paths.shipping_rates_csv_path))
    repo.import_products(products, offers, shipping_rates)

    if paths.stats_nz_csv_path:
        repo.import_metrics = import_stats_nz_csv(_read_text(paths.stats_nz_csv_path))
    if paths.keyword_metrics_csv_path:
        repo.keyword_metrics = import_keyword_metrics_csv(
            _read_text(paths.keyword_metrics_csv_path)
        )

    recalculate_repository(repo)
    ranked = rank_opportunities(list(repo.score_snapshots.values()))

    if paths.output_csv_path:
        export_opportunities_csv(ranked, paths.output_csv_path)
    if paths.json_store_path:
        JsonRepositoryStore(paths.json_store_path).save(repo)
    if paths.sqlite_store_path:
        SQLiteRepositoryStore(paths.sqlite_store_path).save(repo)

    return RankBatchResult(
        repo=repo,
        ranked_product_ids=[snapshot.product_id for snapshot in ranked],
    )


def _read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
