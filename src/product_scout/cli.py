from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .batch import (
    Capture1688BatchPaths,
    Discover1688BatchPaths,
    KeywordRefreshBatchPaths,
    RankBatchPaths,
    run_1688_discovery_batch,
    run_1688_browser_capture,
    run_keyword_refresh_batch,
    run_rank_batch,
)
from .csv_import import CSVValidationError
from .discovery import DiscoverySourceError
from .google_ads import (
    GoogleAdsKeywordPlannerClient,
    GoogleAdsRestKeywordPlannerClient,
    load_google_ads_config,
)
from .market_scan import (
    MarketSeedValidationError,
    export_market_metrics_csv,
    export_market_summary_csv,
    import_market_seeds_csv,
    run_market_scan,
    summarize_market_segments,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nz-product-scout")
    subparsers = parser.add_subparsers(dest="command", required=True)

    rank_parser = subparsers.add_parser("rank")
    rank_parser.add_argument("--products", required=True)
    rank_parser.add_argument("--suppliers", required=True)
    rank_parser.add_argument("--shipping", required=True)
    rank_parser.add_argument("--imports")
    rank_parser.add_argument("--keywords")
    rank_parser.add_argument("--output", required=True)
    rank_parser.add_argument("--store")
    rank_parser.add_argument("--sqlite-store")

    google_ads_parser = subparsers.add_parser("google-ads-smoke")
    google_ads_parser.add_argument("--env-file", default=".env")
    google_ads_parser.add_argument("--keyword", action="append", dest="keywords")
    google_ads_parser.add_argument("--location")
    google_ads_parser.add_argument("--language")
    google_ads_parser.add_argument("--transport", choices=["rest", "grpc"], default="rest")
    google_ads_parser.add_argument("--timeout-seconds", type=int, default=30)

    market_scan_parser = subparsers.add_parser("market-scan")
    market_scan_parser.add_argument("--seeds", required=True)
    market_scan_parser.add_argument("--output", required=True)
    market_scan_parser.add_argument("--summary", required=True)
    market_scan_parser.add_argument("--env-file", default=".env")
    market_scan_parser.add_argument("--location")
    market_scan_parser.add_argument("--language")
    market_scan_parser.add_argument("--transport", choices=["rest", "grpc"], default="rest")
    market_scan_parser.add_argument("--timeout-seconds", type=int, default=30)

    keyword_refresh_parser = subparsers.add_parser("keywords-refresh")
    keyword_refresh_parser.add_argument("--products", required=True)
    keyword_refresh_parser.add_argument("--keyword-seeds", required=True)
    keyword_refresh_parser.add_argument("--output", required=True)
    keyword_refresh_parser.add_argument("--env-file", default=".env")
    keyword_refresh_parser.add_argument("--location")
    keyword_refresh_parser.add_argument("--language")
    keyword_refresh_parser.add_argument("--transport", choices=["rest", "grpc"], default="rest")
    keyword_refresh_parser.add_argument("--timeout-seconds", type=int, default=30)

    discover_parser = subparsers.add_parser("discover-1688")
    discover_source = discover_parser.add_mutually_exclusive_group(required=True)
    discover_source.add_argument("--source-url")
    discover_source.add_argument("--source-html")
    discover_source.add_argument("--source-json")
    discover_parser.add_argument("--output-products", required=True)
    discover_parser.add_argument("--output-suppliers", required=True)
    discover_parser.add_argument("--output-keyword-seeds", required=True)
    discover_parser.add_argument("--limit", type=int, default=100)

    capture_parser = subparsers.add_parser("capture-1688")
    capture_parser.add_argument("--url", default="https://www.1688.com/")
    capture_parser.add_argument("--output-root", default="output/1688-captures")
    capture_parser.add_argument("--profile-dir", default=".local/1688-browser-profile")
    capture_parser.add_argument("--browser-channel", default="msedge")
    capture_parser.add_argument("--limit", type=int, default=100)
    capture_parser.add_argument("--save-html", action="store_true")
    capture_parser.add_argument("--capture-now", action="store_true")
    capture_parser.add_argument("--headless", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "rank":
        sqlite_store = args.sqlite_store
        json_store = args.store
        if args.store and args.store.lower().endswith((".sqlite", ".sqlite3", ".db")):
            sqlite_store = args.store
            json_store = None
        run_rank_batch(
            RankBatchPaths(
                products_csv_path=args.products,
                supplier_offers_csv_path=args.suppliers,
                shipping_rates_csv_path=args.shipping,
                stats_nz_csv_path=args.imports,
                keyword_metrics_csv_path=args.keywords,
                output_csv_path=args.output,
                json_store_path=json_store,
                sqlite_store_path=sqlite_store,
            )
        )
        return 0
    if args.command == "google-ads-smoke":
        config = load_google_ads_config(args.env_file)
        client = (
            GoogleAdsKeywordPlannerClient(config)
            if args.transport == "grpc"
            else GoogleAdsRestKeywordPlannerClient(
                config, timeout_seconds=args.timeout_seconds
            )
        )
        keywords = args.keywords or ["telescope adapter", "bahtinov mask"]
        try:
            metrics = client.historical_metrics(
                keywords=keywords,
                location=args.location or config.geo_target,
                language=args.language or config.language,
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                [metric.model_dump(mode="json") for metric in metrics],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "market-scan":
        try:
            config = load_google_ads_config(args.env_file)
            client = (
                GoogleAdsKeywordPlannerClient(config)
                if args.transport == "grpc"
                else GoogleAdsRestKeywordPlannerClient(
                    config, timeout_seconds=args.timeout_seconds
                )
            )
            with open(args.seeds, encoding="utf-8") as handle:
                seeds = import_market_seeds_csv(handle.read())
            rows = run_market_scan(
                seeds,
                client,
                location=args.location or config.geo_target,
                language=args.language or config.language,
            )
            summaries = summarize_market_segments(rows)
            export_market_metrics_csv(rows, args.output)
            export_market_summary_csv(summaries, args.summary)
        except (MarketSeedValidationError, OSError, RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "keywords": len(rows),
                    "segments": len(summaries),
                    "output_csv_path": args.output,
                    "summary_csv_path": args.summary,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "keywords-refresh":
        try:
            config = load_google_ads_config(args.env_file)
            client = (
                GoogleAdsKeywordPlannerClient(config)
                if args.transport == "grpc"
                else GoogleAdsRestKeywordPlannerClient(
                    config, timeout_seconds=args.timeout_seconds
                )
            )
            result = run_keyword_refresh_batch(
                KeywordRefreshBatchPaths(
                    products_csv_path=args.products,
                    keyword_seeds_csv_path=args.keyword_seeds,
                    output_csv_path=args.output,
                ),
                client,
                location=args.location or config.geo_target,
                language=args.language or config.language,
            )
        except (CSVValidationError, RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "refreshed_keywords": result.refreshed_keywords,
                    "output_csv_path": str(result.output_csv_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "discover-1688":
        try:
            result = run_1688_discovery_batch(
                Discover1688BatchPaths(
                    source_url=args.source_url,
                    source_html_path=args.source_html,
                    source_json_path=args.source_json,
                    output_products_csv_path=args.output_products,
                    output_supplier_offers_csv_path=args.output_suppliers,
                    output_keyword_seeds_csv_path=args.output_keyword_seeds,
                    limit=args.limit,
                )
            )
        except (DiscoverySourceError, OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "discovered_listings": result.discovered_listings,
                    "products_csv_path": str(result.output_products_csv_path),
                    "supplier_offers_csv_path": str(result.output_supplier_offers_csv_path),
                    "keyword_seeds_csv_path": str(result.output_keyword_seeds_csv_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "capture-1688":
        try:
            result = run_1688_browser_capture(
                Capture1688BatchPaths(
                    output_root_dir=args.output_root,
                    profile_dir=args.profile_dir,
                    url=args.url,
                    browser_channel=None
                    if args.browser_channel.lower() == "chromium"
                    else args.browser_channel,
                    limit=args.limit,
                    wait_for_user=not args.capture_now,
                    headless=args.headless,
                    save_html=args.save_html,
                )
            )
        except (DiscoverySourceError, OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "discovered_listings": result.discovered_listings,
                    "source_url": result.capture.source_url,
                    "capture_dir": str(result.capture.artifact_dir),
                    "evidence_json_path": str(result.capture.evidence_json_path),
                    "screenshot_path": str(result.capture.screenshot_path),
                    "products_csv_path": str(result.products_csv_path),
                    "supplier_offers_csv_path": str(result.supplier_offers_csv_path),
                    "keyword_seeds_csv_path": str(result.keyword_seeds_csv_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
