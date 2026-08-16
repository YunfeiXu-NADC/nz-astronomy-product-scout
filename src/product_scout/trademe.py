from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import mean, median
from threading import Lock
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class TradeMeSnapshotCreate(BaseModel):
    query_cluster: str = Field(min_length=1, max_length=80)
    search_query: str = Field(min_length=1, max_length=160)
    observed_at: date
    source_url: str = Field(min_length=1, max_length=2000)
    active_listing_count: int = Field(ge=0)
    sampled_listing_count: int = Field(ge=0)
    unique_seller_count: int = Field(ge=0)
    min_price_nzd: Decimal | None = Field(default=None, ge=0)
    median_price_nzd: Decimal | None = Field(default=None, ge=0)
    max_price_nzd: Decimal | None = Field(default=None, ge=0)
    buy_now_listing_count: int = Field(default=0, ge=0)
    bid_listing_count: int = Field(default=0, ge=0)
    total_bid_count: int = Field(default=0, ge=0)
    in_trade_seller_count: int = Field(default=0, ge=0)
    free_shipping_listing_count: int = Field(default=0, ge=0)
    notes: str = Field(default="", max_length=2000)

    @field_validator("query_cluster", "search_query", "notes")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_url")
    @classmethod
    def validate_trade_me_url(cls, value: str) -> str:
        clean = value.strip()
        parsed = urlparse(clean)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not (
            host == "trademe.co.nz" or host.endswith(".trademe.co.nz")
        ):
            raise ValueError("source_url must be a Trade Me http(s) URL")
        return clean

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("observed_at cannot be in the future")
        return value

    @model_validator(mode="after")
    def validate_sample(self) -> "TradeMeSnapshotCreate":
        if self.sampled_listing_count > self.active_listing_count:
            raise ValueError("sampled_listing_count cannot exceed active_listing_count")
        for field_name in (
            "unique_seller_count",
            "buy_now_listing_count",
            "bid_listing_count",
            "free_shipping_listing_count",
        ):
            if getattr(self, field_name) > self.sampled_listing_count:
                raise ValueError(
                    f"{field_name} cannot exceed sampled_listing_count"
                )
        if self.in_trade_seller_count > self.unique_seller_count:
            raise ValueError(
                "in_trade_seller_count cannot exceed unique_seller_count"
            )
        if self.total_bid_count < self.bid_listing_count:
            raise ValueError(
                "total_bid_count cannot be less than bid_listing_count"
            )
        prices = (
            self.min_price_nzd,
            self.median_price_nzd,
            self.max_price_nzd,
        )
        if any(value is not None for value in prices) and not all(
            value is not None for value in prices
        ):
            raise ValueError("min, median, and max prices must be supplied together")
        if all(value is not None for value in prices):
            low, middle, high = prices
            if not low <= middle <= high:  # type: ignore[operator]
                raise ValueError("prices must satisfy min <= median <= max")
        return self


class TradeMeSnapshot(TradeMeSnapshotCreate):
    id: str
    created_at: datetime


class TradeMeSnapshotStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def list(self) -> list[TradeMeSnapshot]:
        with self._lock:
            snapshots = self._load_unlocked()
        return sorted(
            snapshots,
            key=lambda item: (item.observed_at, item.created_at),
            reverse=True,
        )

    def create(self, payload: TradeMeSnapshotCreate) -> TradeMeSnapshot:
        snapshot = TradeMeSnapshot(
            **payload.model_dump(),
            id=f"tm_{uuid4().hex[:12]}",
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            snapshots = self._load_unlocked()
            snapshots.append(snapshot)
            self._save_unlocked(snapshots)
        return snapshot

    def delete(self, snapshot_id: str) -> bool:
        with self._lock:
            snapshots = self._load_unlocked()
            remaining = [item for item in snapshots if item.id != snapshot_id]
            if len(remaining) == len(snapshots):
                return False
            self._save_unlocked(remaining)
        return True

    def _load_unlocked(self) -> list[TradeMeSnapshot]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        rows = payload.get("snapshots", []) if isinstance(payload, dict) else payload
        return [TradeMeSnapshot.model_validate(item) for item in rows]

    def _save_unlocked(self, snapshots: list[TradeMeSnapshot]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        payload = {
            "version": 1,
            "snapshots": [
                item.model_dump(mode="json") for item in snapshots
            ],
        }
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self.path)


def snapshot_metrics(snapshot: TradeMeSnapshot) -> dict[str, Any]:
    sample = snapshot.sampled_listing_count
    sellers = snapshot.unique_seller_count
    confidence = _confidence_score(snapshot)
    return {
        **snapshot.model_dump(mode="json"),
        "sample_coverage": _ratio(sample, snapshot.active_listing_count),
        "buy_now_share": _ratio(snapshot.buy_now_listing_count, sample),
        "bid_listing_share": _ratio(snapshot.bid_listing_count, sample),
        "free_shipping_share": _ratio(
            snapshot.free_shipping_listing_count, sample
        ),
        "in_trade_seller_share": _ratio(
            snapshot.in_trade_seller_count, sellers
        ),
        "sampled_listings_per_seller": _ratio(sample, sellers),
        "confidence": confidence,
        "confidence_label": (
            "HIGH" if confidence >= 75 else "MEDIUM" if confidence >= 50 else "LOW"
        ),
        "evidence_status": (
            "INSUFFICIENT"
            if sample < 10
            else "OBSERVED"
            if confidence < 75
            else "STRONG_SAMPLE"
        ),
    }


def summarize_snapshots(snapshots: list[TradeMeSnapshot]) -> dict[str, Any]:
    latest_by_cluster: dict[str, TradeMeSnapshot] = {}
    for snapshot in snapshots:
        current = latest_by_cluster.get(snapshot.query_cluster)
        if current is None or (snapshot.observed_at, snapshot.created_at) > (
            current.observed_at,
            current.created_at,
        ):
            latest_by_cluster[snapshot.query_cluster] = snapshot

    latest = list(latest_by_cluster.values())
    active_counts = [item.active_listing_count for item in latest]
    prices = [
        float(item.median_price_nzd)
        for item in latest
        if item.median_price_nzd is not None
    ]
    bid_shares = [
        _ratio(item.bid_listing_count, item.sampled_listing_count)
        for item in latest
        if item.sampled_listing_count
    ]
    confidences = [_confidence_score(item) for item in latest]
    return {
        "snapshot_count": len(snapshots),
        "cluster_count": len(latest),
        "median_active_listings_per_cluster": (
            float(median(active_counts)) if active_counts else 0
        ),
        "median_price_nzd": float(median(prices)) if prices else None,
        "average_bid_listing_share": mean(bid_shares) if bid_shares else 0,
        "average_confidence": round(mean(confidences), 1) if confidences else 0,
        "latest_observed_at": (
            max(item.observed_at for item in latest).isoformat() if latest else None
        ),
        "conclusion": _conclusion(len(latest), confidences),
    }


def _confidence_score(snapshot: TradeMeSnapshot) -> int:
    score = 20  # A dated Trade Me source URL and query are mandatory.
    if snapshot.sampled_listing_count >= 25:
        score += 30
    elif snapshot.sampled_listing_count >= 10:
        score += 20
    elif snapshot.sampled_listing_count:
        score += 8
    if snapshot.unique_seller_count >= 5:
        score += 15
    elif snapshot.unique_seller_count:
        score += 8
    if all(
        value is not None
        for value in (
            snapshot.min_price_nzd,
            snapshot.median_price_nzd,
            snapshot.max_price_nzd,
        )
    ):
        score += 20
    if snapshot.notes:
        score += 10
    return min(score, 100)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0


def _conclusion(cluster_count: int, confidences: list[int]) -> dict[str, str]:
    if not cluster_count:
        return {
            "zh": "尚无 Trade Me 市场快照，不能判断平台供给或交易活跃度。",
            "en": "No Trade Me snapshots yet; marketplace supply and activity remain unknown.",
        }
    high_confidence = sum(score >= 75 for score in confidences)
    if cluster_count < 3 or high_confidence < 2:
        return {
            "zh": "已有初步活跃商品样本，但覆盖范围不足，不能据此推断销量。",
            "en": "Initial active-listing evidence exists, but coverage is too limited to infer sales.",
        }
    return {
        "zh": "已覆盖多个查询簇，可用于比较供给和价格；成交能力仍需第一方店铺数据验证。",
        "en": "Multiple query clusters are covered for supply and price comparison; sales potential still requires first-party store data.",
    }
