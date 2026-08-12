from __future__ import annotations

import argparse
from typing import Sequence

from .batch import RankBatchPaths, run_rank_batch


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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
