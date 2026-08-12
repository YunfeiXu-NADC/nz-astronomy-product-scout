from __future__ import annotations

from .models import ProductCandidate, RiskAssessment


BLOCKED_TERMS = {
    "solar": "solar_observation",
    "laser": "laser",
    "battery": "battery",
    "powered": "powered_electronics",
    "mains": "mains_electricity",
}

LOW_RISK_TYPES = {
    "thread_adapter",
    "spacer",
    "nosepiece_adapter",
    "camera_adapter",
    "bracket",
    "dust_cap",
    "filter_case",
    "bahtinov_mask",
}


def evaluate_product_risk(product: ProductCandidate) -> RiskAssessment:
    text = " ".join(
        [
            product.canonical_name,
            product.sku,
            product.category,
            product.subcategory,
            product.product_type,
            product.safety_risk or "",
        ]
    ).lower()
    reasons: list[str] = []
    for term, reason in BLOCKED_TERMS.items():
        if term in text:
            reasons.append(reason)
    if product.solar_observation:
        reasons.append("solar_observation")
    if product.laser:
        reasons.append("laser")
    if product.battery or product.electrical:
        reasons.append("battery_or_powered_electronics")

    if reasons:
        return RiskAssessment(status="BLOCKED", reasons=sorted(set(reasons)), score=0)
    if product.product_type in LOW_RISK_TYPES:
        return RiskAssessment(status="LOW", reasons=[], score=100)
    return RiskAssessment(status="MEDIUM", reasons=["manual_review_recommended"], score=70)

