from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .models import ImportEvidenceScore, ImportMetric


def calculate_import_evidence_score(
    hs_code: str,
    metrics: list[ImportMetric],
    *,
    low_value_accessory: bool = False,
) -> ImportEvidenceScore:
    relevant = [metric for metric in metrics if metric.hs_code == hs_code]
    if not relevant:
        return ImportEvidenceScore(
            hs_code=hs_code,
            import_value_12m_nzd=Decimal("0"),
            import_quantity_12m=None,
            china_share=Decimal("0.0000"),
            cagr_3y=Decimal("0.0000"),
            score=Decimal("0"),
            confidence=0,
        )

    latest_year = max(metric.year for metric in relevant)
    latest_world = _sum_imports(relevant, latest_year, "World")
    latest_china = _sum_imports(relevant, latest_year, "China")
    latest_quantity = _sum_quantity(relevant, latest_year, "World")
    china_share = (
        (latest_china / latest_world).quantize(Decimal("0.0001"))
        if latest_world
        else Decimal("0.0000")
    )

    yearly_world = _world_totals_by_year(relevant)
    cagr = _cagr(yearly_world)
    import_scale = min(Decimal("100"), latest_world / Decimal("100000") * Decimal("100"))
    china_share_score = china_share * Decimal("100")
    growth_score = min(Decimal("100"), max(Decimal("0"), Decimal("50") + cagr * Decimal("100")))
    score = (
        Decimal("0.40") * import_scale
        + Decimal("0.30") * china_share_score
        + Decimal("0.30") * growth_score
    )
    if low_value_accessory:
        score = min(score, Decimal("70"))
    return ImportEvidenceScore(
        hs_code=hs_code,
        import_value_12m_nzd=latest_world,
        import_quantity_12m=latest_quantity,
        china_share=china_share,
        cagr_3y=cagr.quantize(Decimal("0.0001")),
        score=_score(score),
        confidence=100,
    )


def _sum_imports(metrics: list[ImportMetric], year: int, country: str) -> Decimal:
    return sum(
        (metric.import_nzd for metric in metrics if metric.year == year and metric.origin_country.lower() == country.lower()),
        Decimal("0"),
    )


def _sum_quantity(metrics: list[ImportMetric], year: int, country: str) -> Decimal | None:
    quantities = [
        metric.quantity
        for metric in metrics
        if metric.year == year and metric.origin_country.lower() == country.lower()
    ]
    if not quantities:
        return None
    return sum((quantity or Decimal("0") for quantity in quantities), Decimal("0"))


def _world_totals_by_year(metrics: list[ImportMetric]) -> dict[int, Decimal]:
    yearly: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for metric in metrics:
        if metric.origin_country.lower() == "world":
            yearly[metric.year] += metric.import_nzd
    return dict(yearly)


def _cagr(yearly_world: dict[int, Decimal]) -> Decimal:
    if len(yearly_world) < 2:
        return Decimal("0")
    years = sorted(yearly_world)
    start_year = years[0]
    end_year = years[-1]
    start = yearly_world[start_year]
    end = yearly_world[end_year]
    periods = end_year - start_year
    if start <= 0 or end <= 0 or periods <= 0:
        return Decimal("0")
    return Decimal(str((float(end / start) ** (1 / periods)) - 1))


def _score(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value)).quantize(Decimal("0.01"))

