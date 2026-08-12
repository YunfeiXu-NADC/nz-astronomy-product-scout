from __future__ import annotations

import csv
from pathlib import Path
from typing import TextIO

from .models import ScoreSnapshot
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

