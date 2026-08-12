from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel

from .models import KeywordMetric, ProductCandidate


class GoogleKeywordPlanMetric(BaseModel):
    keyword: str
    monthly_searches: int
    monthly_history: list[int]
    competition_index: int | None = None
    bid_low: Decimal | None = None
    bid_high: Decimal | None = None


class KeywordPlannerClient(Protocol):
    def historical_metrics(
        self,
        *,
        keywords: list[str],
        location: str,
        language: str,
    ) -> list[GoogleKeywordPlanMetric]:
        ...


class GoogleAdsKeywordRefreshService:
    """Refreshes Google Keyword Planner metrics with the V1 NZ/English scope."""

    def __init__(
        self,
        client: KeywordPlannerClient,
        *,
        location: str = "New Zealand",
        language: str = "English",
    ) -> None:
        self.client = client
        self.location = location
        self.language = language

    def refresh(
        self,
        products: list[ProductCandidate],
        keywords_by_product: dict[str, list[str]],
        cluster_by_keyword: dict[str, str],
    ) -> list[KeywordMetric]:
        metrics: list[KeywordMetric] = []
        products_by_id = {product.id: product for product in products}
        for product_id, keywords in keywords_by_product.items():
            if product_id not in products_by_id:
                continue
            clean_keywords = [_normalize_keyword(keyword) for keyword in keywords if keyword.strip()]
            if not clean_keywords:
                continue
            google_metrics = self.client.historical_metrics(
                keywords=clean_keywords,
                location=self.location,
                language=self.language,
            )
            for google_metric in google_metrics:
                normalized_keyword = _normalize_keyword(google_metric.keyword)
                metrics.append(
                    KeywordMetric(
                        product_id=product_id,
                        keyword=normalized_keyword,
                        keyword_cluster=cluster_by_keyword.get(
                            normalized_keyword,
                            normalized_keyword.replace(" ", "_"),
                        ),
                        monthly_searches=google_metric.monthly_searches,
                        monthly_history=google_metric.monthly_history,
                        competition_index=google_metric.competition_index,
                        bid_low=google_metric.bid_low,
                        bid_high=google_metric.bid_high,
                    )
                )
        return metrics


def _normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.lower().split())

