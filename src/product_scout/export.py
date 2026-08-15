from __future__ import annotations

import csv
from pathlib import Path
from typing import TextIO

from .models import KeywordMetric, ScoreSnapshot
from .scoring import rank_opportunities


OPPORTUNITY_COLUMNS = [
    "rank",
    "product_id",
    "sku",
    "product_name",
    "prelaunch_score",
    "confidence",
    "status",
    "search_demand_score",
    "import_evidence_score",
    "unit_economics_score",
    "logistics_score",
    "supply_quality_score",
    "product_risk_fit_score",
    "rejection_reasons",
]

KEYWORD_METRIC_COLUMNS = [
    "product_id",
    "keyword",
    "keyword_cluster",
    "monthly_searches",
    "monthly_history",
    "competition_index",
    "bid_low",
    "bid_high",
]


def export_opportunities_csv(
    snapshots: list[ScoreSnapshot], destination: str | Path | TextIO
) -> None:
    should_close = False
    if hasattr(destination, "write"):
        handle = destination
    else:
        handle = Path(destination).open("w", newline="", encoding="utf-8")
        should_close = True
    try:
        writer = csv.DictWriter(handle, fieldnames=OPPORTUNITY_COLUMNS)
        writer.writeheader()
        for rank, snapshot in enumerate(rank_opportunities(snapshots), start=1):
            writer.writerow(
                {
                    "rank": rank,
                    "product_id": snapshot.product_id,
                    "sku": snapshot.sku,
                    "product_name": snapshot.product_name,
                    "prelaunch_score": snapshot.prelaunch_score,
                    "confidence": snapshot.confidence,
                    "status": snapshot.status,
                    "search_demand_score": snapshot.search_demand_score,
                    "import_evidence_score": snapshot.import_evidence_score,
                    "unit_economics_score": snapshot.unit_economics_score,
                    "logistics_score": snapshot.logistics_score,
                    "supply_quality_score": snapshot.supply_quality_score,
                    "product_risk_fit_score": snapshot.product_risk_fit_score,
                    "rejection_reasons": "|".join(snapshot.rejection_reasons),
                }
            )
    finally:
        if should_close:
            handle.close()


def export_keyword_metrics_csv(
    metrics: list[KeywordMetric], destination: str | Path | TextIO
) -> None:
    should_close = False
    if hasattr(destination, "write"):
        handle = destination
    else:
        handle = Path(destination).open("w", newline="", encoding="utf-8")
        should_close = True
    try:
        writer = csv.DictWriter(handle, fieldnames=KEYWORD_METRIC_COLUMNS)
        writer.writeheader()
        for metric in sorted(metrics, key=lambda item: (item.product_id, item.keyword)):
            writer.writerow(
                {
                    "product_id": metric.product_id,
                    "keyword": metric.keyword,
                    "keyword_cluster": metric.keyword_cluster,
                    "monthly_searches": _blank_if_none(metric.monthly_searches),
                    "monthly_history": "|".join(str(value) for value in metric.monthly_history),
                    "competition_index": _blank_if_none(metric.competition_index),
                    "bid_low": _blank_if_none(metric.bid_low),
                    "bid_high": _blank_if_none(metric.bid_high),
                }
            )
    finally:
        if should_close:
            handle.close()


def _blank_if_none(value) -> str:
    return "" if value is None else str(value)
