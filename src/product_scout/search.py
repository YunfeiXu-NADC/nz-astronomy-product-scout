from __future__ import annotations

import math
from decimal import Decimal

from .models import KeywordMetric, KeywordSearchScore, ProductCandidate


def calculate_search_demand_scores(
    products: list[ProductCandidate], metrics: list[KeywordMetric]
) -> dict[str, KeywordSearchScore]:
    by_product: dict[str, list[KeywordMetric]] = {product.id: [] for product in products}
    for metric in metrics:
        by_product.setdefault(metric.product_id, []).append(metric)

    cluster_totals: dict[str, dict[str, int]] = {}
    log_values: dict[str, float] = {}
    for product in products:
        clusters: dict[str, int] = {}
        for metric in by_product.get(product.id, []):
            if metric.monthly_searches is None:
                continue
            previous = clusters.get(metric.keyword_cluster, 0)
            clusters[metric.keyword_cluster] = max(previous, metric.monthly_searches)
        cluster_totals[product.id] = clusters
        log_values[product.id] = math.log1p(sum(clusters.values()))

    non_zero_logs = [value for value in log_values.values() if value > 0]
    min_log = min(non_zero_logs) if non_zero_logs else 0.0
    max_log = max(non_zero_logs) if non_zero_logs else 0.0

    scores: dict[str, KeywordSearchScore] = {}
    for product in products:
        product_metrics = by_product.get(product.id, [])
        clusters = cluster_totals[product.id]
        total_searches = sum(clusters.values())
        if total_searches == 0:
            scores[product.id] = KeywordSearchScore(
                product_id=product.id,
                cluster_monthly_searches={},
                total_cluster_searches=0,
                yoy_growth_score=Decimal("0"),
                stability_score=Decimal("0"),
                search_volume_percentile=Decimal("0"),
                score=Decimal("0"),
                confidence=0,
            )
            continue
        if max_log == min_log:
            volume_percentile = Decimal("100")
        else:
            volume_percentile = Decimal(
                str((log_values[product.id] - min_log) / (max_log - min_log) * 100)
            )
        growth_score = _growth_score(product_metrics)
        stability = _stability_score(product_metrics)
        score = (
            Decimal("0.60") * volume_percentile
            + Decimal("0.25") * growth_score
            + Decimal("0.15") * stability
        )
        scores[product.id] = KeywordSearchScore(
            product_id=product.id,
            cluster_monthly_searches=clusters,
            total_cluster_searches=total_searches,
            yoy_growth_score=_score(growth_score),
            stability_score=_score(stability),
            search_volume_percentile=_score(volume_percentile),
            score=_score(score),
            confidence=100,
        )
    return scores


def _growth_score(metrics: list[KeywordMetric]) -> Decimal:
    histories = [m.monthly_history for m in metrics if len(m.monthly_history) >= 12]
    if not histories:
        return Decimal("0")
    first_half = sum(sum(history[:6]) / 6 for history in histories)
    last_half = sum(sum(history[-6:]) / 6 for history in histories)
    if first_half == 0:
        return Decimal("50")
    growth = Decimal(str((last_half - first_half) / first_half))
    return _score(Decimal("50") + growth * Decimal("100"))


def _stability_score(metrics: list[KeywordMetric]) -> Decimal:
    values = [
        value
        for metric in metrics
        for value in metric.monthly_history
        if value is not None
    ]
    if not values:
        return Decimal("0")
    mean = sum(values) / len(values)
    if mean == 0:
        return Decimal("0")
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    cv = math.sqrt(variance) / mean
    return _score(Decimal("100") - Decimal(str(cv * 100)))


def _score(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value)).quantize(Decimal("0.01"))

