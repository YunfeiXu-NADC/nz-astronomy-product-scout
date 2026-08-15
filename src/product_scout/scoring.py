from __future__ import annotations

from decimal import Decimal

from .models import ConfidenceInputs, ProductCandidate, ScoreSnapshot


def build_score_snapshot(
    product: ProductCandidate,
    *,
    search_score: Decimal | int | float,
    import_score: Decimal | int | float,
    unit_economics_score: Decimal | int | float,
    logistics_score: Decimal | int | float,
    supply_quality_score: Decimal | int | float,
    risk_fit_score: Decimal | int | float,
    confidence_inputs: ConfidenceInputs,
    status: str | None = None,
    rejection_reasons: list[str] | None = None,
) -> ScoreSnapshot:
    search = _decimal(search_score)
    import_evidence = _decimal(import_score)
    economics = _decimal(unit_economics_score)
    logistics = _decimal(logistics_score)
    supply = _decimal(supply_quality_score)
    risk = _decimal(risk_fit_score)
    prelaunch = (
        Decimal("0.25") * search
        + Decimal("0.10") * import_evidence
        + Decimal("0.30") * economics
        + Decimal("0.15") * logistics
        + Decimal("0.10") * supply
        + Decimal("0.10") * risk
    )
    resolved_status = status or ("QUALIFIED" if prelaunch >= 70 and risk > 0 else "REJECT")
    resolved_reasons = list(rejection_reasons or [])
    if not status and resolved_status == "REJECT" and not resolved_reasons:
        if risk <= 0:
            resolved_reasons.append("risk_fit_score_zero")
        elif prelaunch < 70:
            resolved_reasons.append("prelaunch_score_below_70")
    return ScoreSnapshot(
        product_id=product.id,
        sku=product.sku,
        product_name=product.canonical_name,
        search_demand_score=_score(search),
        import_evidence_score=_score(import_evidence),
        unit_economics_score=_score(economics),
        logistics_score=_score(logistics),
        supply_quality_score=_score(supply),
        product_risk_fit_score=_score(risk),
        prelaunch_score=_score(prelaunch),
        confidence=_confidence(confidence_inputs),
        status=resolved_status,
        rejection_reasons=resolved_reasons,
    )


def rank_opportunities(snapshots: list[ScoreSnapshot]) -> list[ScoreSnapshot]:
    return sorted(
        snapshots,
        key=lambda snapshot: (
            snapshot.status == "BLOCKED",
            -snapshot.prelaunch_score,
            -snapshot.confidence,
            snapshot.sku,
        ),
    )


def supply_quality_score(supplier_count: int, price_cv: Decimal | None = None) -> Decimal:
    depth = min(Decimal("100"), Decimal(supplier_count) / Decimal("3") * Decimal("100"))
    stability = Decimal("75")
    if price_cv is not None:
        stability = max(Decimal("0"), Decimal("100") - price_cv * Decimal("100"))
    return _score(Decimal("0.50") * depth + Decimal("0.50") * stability)


def _confidence(inputs: ConfidenceInputs) -> int:
    score = 0
    if inputs.has_google_keyword_data:
        score += 25
    if inputs.has_stats_nz_data:
        score += 20
    if inputs.supplier_count >= 3:
        score += 20
    elif inputs.supplier_count > 0:
        score += 7 * inputs.supplier_count
    if inputs.has_shipping_quote:
        score += 20
    if inputs.has_trade_me_own_sales:
        score += 10
    if inputs.has_30_day_experiment:
        score += 5
    return min(100, score)


def _decimal(value: Decimal | int | float) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _score(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value)).quantize(Decimal("0.01"))
