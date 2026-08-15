from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import TextIO

from .google_ads import GoogleKeywordPlanMetric, KeywordPlannerClient


MARKET_SEED_COLUMNS = ["segment", "intent_cluster", "keyword", "role"]
MARKET_METRIC_COLUMNS = [
    "segment",
    "intent_cluster",
    "keyword",
    "role",
    "monthly_searches",
    "monthly_history",
    "competition_index",
    "bid_low",
    "bid_high",
]
MARKET_SUMMARY_COLUMNS = [
    "segment",
    "intent_clusters",
    "nonzero_clusters",
    "nonzero_cluster_share",
    "conservative_demand_index",
    "median_cluster_searches",
    "top_keyword",
    "top_keyword_searches",
    "peak_to_average_ratio",
]


class MarketSeedValidationError(ValueError):
    pass


@dataclass(frozen=True)
class MarketKeywordSeed:
    segment: str
    intent_cluster: str
    keyword: str
    role: str = "supporting"


@dataclass(frozen=True)
class MarketMetricRow:
    seed: MarketKeywordSeed
    metric: GoogleKeywordPlanMetric


@dataclass(frozen=True)
class MarketSegmentSummary:
    segment: str
    intent_clusters: int
    nonzero_clusters: int
    nonzero_cluster_share: Decimal
    conservative_demand_index: int
    median_cluster_searches: Decimal
    top_keyword: str
    top_keyword_searches: int
    peak_to_average_ratio: Decimal | None


def import_market_seeds_csv(text: str) -> list[MarketKeywordSeed]:
    reader = csv.DictReader(text.splitlines())
    missing = [column for column in MARKET_SEED_COLUMNS if column not in (reader.fieldnames or [])]
    if missing:
        raise MarketSeedValidationError(
            "Market seed CSV is missing columns: " + ", ".join(missing)
        )

    seeds: list[MarketKeywordSeed] = []
    seen_keywords: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        segment = _normalize_label(row.get("segment", ""))
        intent_cluster = _normalize_label(row.get("intent_cluster", ""))
        keyword = _normalize_keyword(row.get("keyword", ""))
        role = _normalize_label(row.get("role", "")) or "supporting"
        if not segment or not intent_cluster or not keyword:
            raise MarketSeedValidationError(
                f"Market seed CSV row {row_number} requires segment, intent_cluster, and keyword"
            )
        if keyword in seen_keywords:
            raise MarketSeedValidationError(
                f"Market seed CSV row {row_number} repeats keyword: {keyword}"
            )
        seen_keywords.add(keyword)
        seeds.append(
            MarketKeywordSeed(
                segment=segment,
                intent_cluster=intent_cluster,
                keyword=keyword,
                role=role,
            )
        )
    if not seeds:
        raise MarketSeedValidationError("Market seed CSV has no data rows")
    return seeds


def run_market_scan(
    seeds: list[MarketKeywordSeed],
    client: KeywordPlannerClient,
    *,
    location: str = "New Zealand",
    language: str = "English",
) -> list[MarketMetricRow]:
    metrics = client.historical_metrics(
        keywords=[seed.keyword for seed in seeds],
        location=location,
        language=language,
    )
    metrics_by_keyword = {_normalize_keyword(metric.keyword): metric for metric in metrics}
    rows: list[MarketMetricRow] = []
    for seed in seeds:
        metric = metrics_by_keyword.get(seed.keyword)
        if metric is None:
            metric = GoogleKeywordPlanMetric(
                keyword=seed.keyword,
                monthly_searches=0,
                monthly_history=[],
            )
        rows.append(MarketMetricRow(seed=seed, metric=metric))
    return rows


def summarize_market_segments(rows: list[MarketMetricRow]) -> list[MarketSegmentSummary]:
    rows_by_segment: dict[str, list[MarketMetricRow]] = {}
    for row in rows:
        rows_by_segment.setdefault(row.seed.segment, []).append(row)

    summaries: list[MarketSegmentSummary] = []
    for segment, segment_rows in rows_by_segment.items():
        representative_by_cluster: dict[str, MarketMetricRow] = {}
        for row in segment_rows:
            current = representative_by_cluster.get(row.seed.intent_cluster)
            if current is None or _metric_sort_key(row) > _metric_sort_key(current):
                representative_by_cluster[row.seed.intent_cluster] = row

        representatives = list(representative_by_cluster.values())
        searches = [row.metric.monthly_searches for row in representatives]
        nonzero_clusters = sum(value > 0 for value in searches)
        top = max(segment_rows, key=_metric_sort_key)
        monthly_totals = _monthly_totals(representatives)
        monthly_average = sum(monthly_totals) / len(monthly_totals) if monthly_totals else 0
        peak_ratio = (
            Decimal(str(max(monthly_totals) / monthly_average)).quantize(Decimal("0.01"))
            if monthly_average
            else None
        )
        cluster_count = len(representatives)
        summaries.append(
            MarketSegmentSummary(
                segment=segment,
                intent_clusters=cluster_count,
                nonzero_clusters=nonzero_clusters,
                nonzero_cluster_share=(
                    Decimal(nonzero_clusters * 100) / Decimal(cluster_count)
                ).quantize(Decimal("0.1")),
                conservative_demand_index=sum(searches),
                median_cluster_searches=Decimal(str(median(searches))).quantize(
                    Decimal("0.1")
                ),
                top_keyword=top.seed.keyword,
                top_keyword_searches=top.metric.monthly_searches,
                peak_to_average_ratio=peak_ratio,
            )
        )
    return sorted(
        summaries,
        key=lambda item: (-item.conservative_demand_index, item.segment),
    )


def export_market_metrics_csv(
    rows: list[MarketMetricRow], destination: str | Path | TextIO
) -> None:
    handle, should_close = _open_destination(destination)
    try:
        writer = csv.DictWriter(handle, fieldnames=MARKET_METRIC_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "segment": row.seed.segment,
                    "intent_cluster": row.seed.intent_cluster,
                    "keyword": row.seed.keyword,
                    "role": row.seed.role,
                    "monthly_searches": row.metric.monthly_searches,
                    "monthly_history": "|".join(
                        str(value) for value in row.metric.monthly_history
                    ),
                    "competition_index": _blank_if_none(row.metric.competition_index),
                    "bid_low": _blank_if_none(row.metric.bid_low),
                    "bid_high": _blank_if_none(row.metric.bid_high),
                }
            )
    finally:
        if should_close:
            handle.close()


def export_market_summary_csv(
    summaries: list[MarketSegmentSummary], destination: str | Path | TextIO
) -> None:
    handle, should_close = _open_destination(destination)
    try:
        writer = csv.DictWriter(handle, fieldnames=MARKET_SUMMARY_COLUMNS)
        writer.writeheader()
        for summary in summaries:
            writer.writerow(
                {
                    "segment": summary.segment,
                    "intent_clusters": summary.intent_clusters,
                    "nonzero_clusters": summary.nonzero_clusters,
                    "nonzero_cluster_share": summary.nonzero_cluster_share,
                    "conservative_demand_index": summary.conservative_demand_index,
                    "median_cluster_searches": summary.median_cluster_searches,
                    "top_keyword": summary.top_keyword,
                    "top_keyword_searches": summary.top_keyword_searches,
                    "peak_to_average_ratio": _blank_if_none(
                        summary.peak_to_average_ratio
                    ),
                }
            )
    finally:
        if should_close:
            handle.close()


def _metric_sort_key(row: MarketMetricRow) -> tuple[int, str]:
    return row.metric.monthly_searches, row.seed.keyword


def _monthly_totals(rows: list[MarketMetricRow]) -> list[int]:
    history_length = max((len(row.metric.monthly_history) for row in rows), default=0)
    if history_length == 0:
        return []
    totals = [0] * history_length
    for row in rows:
        history = row.metric.monthly_history
        offset = history_length - len(history)
        for index, value in enumerate(history):
            totals[index + offset] += value
    return totals


def _normalize_keyword(value: str) -> str:
    return " ".join(value.lower().split())


def _normalize_label(value: str) -> str:
    return "_".join(value.lower().replace("-", " ").split())


def _blank_if_none(value) -> str:
    return "" if value is None else str(value)


def _open_destination(destination: str | Path | TextIO) -> tuple[TextIO, bool]:
    if hasattr(destination, "write"):
        return destination, False
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("w", newline="", encoding="utf-8"), True
