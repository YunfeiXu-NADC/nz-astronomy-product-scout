from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel

from .models import EconomicsResult, ProductCandidate, ShippingQuote, ShippingRate, SupplierOffer
from .targets import DEFAULT_BUSINESS_TARGETS


MONEY = Decimal("0.01")
RATIO = Decimal("0.0001")


class EconomicsAssumptions(BaseModel):
    cny_to_nzd: Decimal = Decimal("0.23")
    trade_me_fee_rate: Decimal = Decimal("0.079")
    payment_fee_rate: Decimal = Decimal("0.025")
    payment_fixed_nzd: Decimal = Decimal("0.10")
    packaging_nzd: Decimal = Decimal("0.50")
    refund_reserve_rate: Decimal = Decimal("0.030")
    min_contribution_margin: Decimal = DEFAULT_BUSINESS_TARGETS.min_contribution_margin
    min_contribution_profit_nzd: Decimal = (
        DEFAULT_BUSINESS_TARGETS.min_contribution_profit_per_order_nzd
    )


class ChinaDirectCostEngine:
    def __init__(
        self,
        shipping_rates: list[ShippingRate],
        assumptions: EconomicsAssumptions | None = None,
    ) -> None:
        self.shipping_rates = shipping_rates
        self.assumptions = assumptions or EconomicsAssumptions()

    def calculate(self, product: ProductCandidate, offer: SupplierOffer) -> EconomicsResult:
        quote = self.quote_shipping(product, offer)
        revenue = _money(product.expected_sell_price_nzd)
        purchase_cost = _money(offer.unit_price_cny * self.assumptions.cny_to_nzd)
        domestic_shipping = _money(
            offer.domestic_shipping_cny * self.assumptions.cny_to_nzd
        )
        international_shipping = _money(
            quote.shipping_cny * self.assumptions.cny_to_nzd
        )
        packaging = _money(self.assumptions.packaging_nzd)
        trade_me_fee = _money(revenue * self.assumptions.trade_me_fee_rate)
        payment_fee = _money(
            revenue * self.assumptions.payment_fee_rate
            + self.assumptions.payment_fixed_nzd
        )
        refund_reserve = _money(revenue * self.assumptions.refund_reserve_rate)
        landed_cost = _money(
            purchase_cost + domestic_shipping + international_shipping + packaging
        )
        contribution_profit = _money(
            revenue - landed_cost - trade_me_fee - payment_fee - refund_reserve
        )
        contribution_margin = _ratio(contribution_profit / revenue) if revenue else Decimal("0")
        shipping_ratio = _ratio(international_shipping / revenue) if revenue else Decimal("0")
        break_even_price = _money(
            landed_cost
            / (
                Decimal("1")
                - self.assumptions.trade_me_fee_rate
                - self.assumptions.payment_fee_rate
                - self.assumptions.refund_reserve_rate
            )
        )

        rejection_reasons: list[str] = []
        if contribution_margin < self.assumptions.min_contribution_margin:
            rejection_reasons.append("contribution_margin_below_30_percent")
        if contribution_profit < self.assumptions.min_contribution_profit_nzd:
            rejection_reasons.append("contribution_profit_below_20_nzd")

        return EconomicsResult(
            product_id=product.id,
            sku=product.sku,
            revenue_nzd=revenue,
            purchase_cost_nzd=purchase_cost,
            china_domestic_shipping_nzd=domestic_shipping,
            international_shipping_nzd=international_shipping,
            packaging_nzd=packaging,
            trade_me_fee_nzd=trade_me_fee,
            payment_fee_nzd=payment_fee,
            refund_reserve_nzd=refund_reserve,
            landed_cost_nzd=landed_cost,
            contribution_profit_nzd=contribution_profit,
            contribution_margin=contribution_margin,
            shipping_ratio=shipping_ratio,
            break_even_price_nzd=break_even_price,
            chargeable_weight_g=quote.chargeable_weight_g,
            status="REJECT" if rejection_reasons else "QUALIFIED",
            rejection_reasons=rejection_reasons,
        )

    def quote_shipping(
        self, product: ProductCandidate, offer: SupplierOffer
    ) -> ShippingQuote:
        actual_weight_g = max(product.weight_g, offer.weight_g)
        dimensions = offer.package_dimensions
        volumetric_weight_g = int(
            (
                Decimal(dimensions.length_mm)
                / Decimal("10")
                * Decimal(dimensions.width_mm)
                / Decimal("10")
                * Decimal(dimensions.height_mm)
                / Decimal("10")
                / Decimal("6000")
                * Decimal("1000")
            ).to_integral_value(rounding=ROUND_HALF_UP)
        )
        chargeable_weight_g = max(actual_weight_g, volumetric_weight_g)
        rate = self._select_rate("china_to_nz_direct", chargeable_weight_g)
        shipping_cny = _money(
            rate.base_fee_cny
            + Decimal(chargeable_weight_g) / Decimal("1000") * rate.fee_per_kg_cny
        )
        return ShippingQuote(
            product_id=product.id,
            route=rate.route,
            provider=rate.provider,
            actual_weight_g=actual_weight_g,
            volumetric_weight_g=volumetric_weight_g,
            chargeable_weight_g=chargeable_weight_g,
            shipping_cny=shipping_cny,
            delivery_days=rate.delivery_days,
        )

    def _select_rate(self, route: str, chargeable_weight_g: int) -> ShippingRate:
        for rate in self.shipping_rates:
            if rate.supports(route, chargeable_weight_g):
                return rate
        raise ValueError(f"No shipping rate for {route} at {chargeable_weight_g}g")


def unit_economics_score(result: EconomicsResult) -> Decimal:
    if result.status != "QUALIFIED":
        profit_component = max(
            Decimal("0"), result.contribution_profit_nzd / Decimal("20") * 50
        )
        margin_component = max(Decimal("0"), result.contribution_margin / Decimal("0.30") * 50)
        return min(Decimal("69"), _score(profit_component + margin_component))
    profit_score = min(Decimal("50"), result.contribution_profit_nzd / Decimal("40") * 50)
    margin_score = min(Decimal("50"), result.contribution_margin / Decimal("0.50") * 50)
    return _score(profit_score + margin_score)


def logistics_score(chargeable_weight_g: int, product: ProductCandidate) -> Decimal:
    if chargeable_weight_g <= 250:
        score = Decimal("100")
    elif chargeable_weight_g <= 500:
        score = Decimal("90")
    elif chargeable_weight_g <= 1000:
        score = Decimal("75")
    elif chargeable_weight_g <= 2000:
        score = Decimal("50")
    else:
        score = Decimal("20")
    if product.battery:
        score -= Decimal("25")
    if product.laser:
        score -= Decimal("30")
    if product.solar_observation:
        score -= Decimal("30")
    return _score(score)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO, rounding=ROUND_HALF_UP)


def _score(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value)).quantize(Decimal("0.01"))
