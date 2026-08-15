from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .browser_capture import (
    BrowserCaptureResult,
    capture_1688_browser_page,
    timestamped_capture_dir,
)

from .csv_import import (
    CSVValidationError,
    import_keyword_metrics_csv,
    import_keyword_seeds_csv,
    import_product_candidates_csv,
    import_shipping_rates_csv,
    import_stats_nz_csv,
    import_supplier_offers_csv,
)
from .discovery import (
    DiscoverySourceError,
    build_discovery_result,
    fetch_1688_html,
    parse_1688_html,
    parse_1688_json_payload,
)
from .export import (
    export_keyword_metrics_csv,
    export_keyword_seeds_csv,
    export_opportunities_csv,
    export_products_csv,
    export_supplier_offers_csv,
)
from .google_ads import GoogleAdsKeywordRefreshService, KeywordPlannerClient
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


@dataclass(frozen=True)
class KeywordRefreshBatchPaths:
    products_csv_path: str | Path
    keyword_seeds_csv_path: str | Path
    output_csv_path: str | Path


@dataclass(frozen=True)
class KeywordRefreshBatchResult:
    refreshed_keywords: int
    output_csv_path: str | Path


@dataclass(frozen=True)
class Discover1688BatchPaths:
    output_products_csv_path: str | Path
    output_supplier_offers_csv_path: str | Path
    output_keyword_seeds_csv_path: str | Path
    source_html_path: str | Path | None = None
    source_json_path: str | Path | None = None
    source_url: str | None = None
    limit: int = 100


@dataclass(frozen=True)
class Discover1688BatchResult:
    discovered_listings: int
    output_products_csv_path: str | Path
    output_supplier_offers_csv_path: str | Path
    output_keyword_seeds_csv_path: str | Path


@dataclass(frozen=True)
class Capture1688BatchPaths:
    output_root_dir: str | Path = "output/1688-captures"
    profile_dir: str | Path = ".local/1688-browser-profile"
    url: str = "https://www.1688.com/"
    browser_channel: str | None = "msedge"
    limit: int = 100
    wait_for_user: bool = True
    headless: bool = False
    save_html: bool = False


@dataclass(frozen=True)
class Capture1688BatchResult:
    discovered_listings: int
    capture: BrowserCaptureResult
    products_csv_path: Path
    supplier_offers_csv_path: Path
    keyword_seeds_csv_path: Path


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


def run_keyword_refresh_batch(
    paths: KeywordRefreshBatchPaths,
    client: KeywordPlannerClient,
    *,
    location: str = "New Zealand",
    language: str = "English",
) -> KeywordRefreshBatchResult:
    products = import_product_candidates_csv(_read_text(paths.products_csv_path))
    seeds = import_keyword_seeds_csv(_read_text(paths.keyword_seeds_csv_path))
    product_ids = {product.id for product in products}
    unknown_product_ids = sorted({seed.product_id for seed in seeds} - product_ids)
    if unknown_product_ids:
        raise CSVValidationError(
            "Keyword seeds reference unknown product ids: " + ", ".join(unknown_product_ids)
        )

    keywords_by_product: dict[str, list[str]] = {}
    cluster_by_keyword: dict[str, str] = {}
    for seed in seeds:
        keywords_by_product.setdefault(seed.product_id, []).append(seed.keyword)
        cluster_by_keyword[_normalize_keyword(seed.keyword)] = seed.keyword_cluster

    service = GoogleAdsKeywordRefreshService(
        client,
        location=location,
        language=language,
    )
    metrics = service.refresh(products, keywords_by_product, cluster_by_keyword)
    export_keyword_metrics_csv(metrics, paths.output_csv_path)
    return KeywordRefreshBatchResult(
        refreshed_keywords=len(metrics),
        output_csv_path=paths.output_csv_path,
    )


def run_1688_discovery_batch(paths: Discover1688BatchPaths) -> Discover1688BatchResult:
    source_count = sum(
        bool(value)
        for value in [paths.source_html_path, paths.source_json_path, paths.source_url]
    )
    if source_count != 1:
        raise DiscoverySourceError(
            "Provide exactly one 1688 source: source_html_path, source_json_path, or source_url"
        )

    if paths.source_html_path:
        listings = parse_1688_html(
            _read_text(paths.source_html_path),
            source_url=str(paths.source_html_path),
            limit=paths.limit,
        )
    elif paths.source_json_path:
        import json

        listings = parse_1688_json_payload(
            json.loads(_read_text(paths.source_json_path)),
            source_url=str(paths.source_json_path),
            limit=paths.limit,
        )
    else:
        assert paths.source_url is not None
        listings = parse_1688_html(
            fetch_1688_html(paths.source_url),
            source_url=paths.source_url,
            limit=paths.limit,
        )

    if not listings:
        raise DiscoverySourceError("No parseable 1688 listings found in the source")

    result = build_discovery_result(listings)
    export_products_csv(result.products, paths.output_products_csv_path)
    export_supplier_offers_csv(result.supplier_offers, paths.output_supplier_offers_csv_path)
    export_keyword_seeds_csv(result.keyword_seeds, paths.output_keyword_seeds_csv_path)
    return Discover1688BatchResult(
        discovered_listings=len(result.listings),
        output_products_csv_path=paths.output_products_csv_path,
        output_supplier_offers_csv_path=paths.output_supplier_offers_csv_path,
        output_keyword_seeds_csv_path=paths.output_keyword_seeds_csv_path,
    )


def run_1688_browser_capture(paths: Capture1688BatchPaths) -> Capture1688BatchResult:
    capture_dir = timestamped_capture_dir(paths.output_root_dir)
    capture = capture_1688_browser_page(
        url=paths.url,
        profile_dir=paths.profile_dir,
        artifact_dir=capture_dir,
        browser_channel=paths.browser_channel,
        limit=paths.limit,
        wait_for_user=paths.wait_for_user,
        headless=paths.headless,
        save_html=paths.save_html,
    )
    result = build_discovery_result(capture.listings)
    products_path = capture_dir / "products.csv"
    suppliers_path = capture_dir / "supplier_offers.csv"
    seeds_path = capture_dir / "keyword_seeds.csv"
    export_products_csv(result.products, products_path)
    export_supplier_offers_csv(result.supplier_offers, suppliers_path)
    export_keyword_seeds_csv(result.keyword_seeds, seeds_path)
    return Capture1688BatchResult(
        discovered_listings=len(result.listings),
        capture=capture,
        products_csv_path=products_path,
        supplier_offers_csv_path=suppliers_path,
        keyword_seeds_csv_path=seeds_path,
    )


def _read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def _normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.lower().split())
