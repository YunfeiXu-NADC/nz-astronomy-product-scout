from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .batch import RankBatchPaths, run_rank_batch
from .google_ads import (
    GoogleAdsKeywordPlannerClient,
    GoogleAdsRestKeywordPlannerClient,
    load_google_ads_config,
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
