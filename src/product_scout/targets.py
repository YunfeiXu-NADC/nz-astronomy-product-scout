from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

from pydantic import BaseModel, field_validator, model_validator


MONEY = Decimal("0.01")


class BusinessTargets(BaseModel):
    monthly_contribution_profit_nzd: Decimal = Decimal("3000.00")
    min_contribution_profit_per_order_nzd: Decimal = Decimal("20.00")
    min_contribution_margin: Decimal = Decimal("0.30")
    max_initial_inventory_risk_nzd: Decimal = Decimal("1500.00")
    min_sku_test_days: int = 30
    max_sku_test_days: int = 60

    @field_validator(
        "monthly_contribution_profit_nzd",
        "min_contribution_profit_per_order_nzd",
        "min_contribution_margin",
        "max_initial_inventory_risk_nzd",
    )
    @classmethod
    def decimal_targets_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("business target must be positive")
        return value

    @field_validator("min_sku_test_days", "max_sku_test_days")
    @classmethod
    def test_days_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("SKU test days must be positive")
        return value

    @model_validator(mode="after")
    def test_window_must_be_ordered(self) -> "BusinessTargets":
        if self.min_sku_test_days > self.max_sku_test_days:
            raise ValueError("minimum SKU test days cannot exceed maximum SKU test days")
        if self.min_contribution_margin > Decimal("1"):
            raise ValueError("minimum contribution margin cannot exceed 1")
        return self

    @property
    def required_monthly_orders(self) -> int:
        return int(
            (
                self.monthly_contribution_profit_nzd
                / self.min_contribution_profit_per_order_nzd
            ).to_integral_value(rounding=ROUND_CEILING)
        )

    @property
    def required_daily_orders(self) -> Decimal:
        return (Decimal(self.required_monthly_orders) / Decimal("30")).quantize(
            Decimal("0.1")
        )

    def summary(self) -> dict[str, str | int]:
        return {
            **self.model_dump(mode="json"),
            "required_monthly_orders": self.required_monthly_orders,
            "required_daily_orders": str(self.required_daily_orders),
        }


DEFAULT_BUSINESS_TARGETS = BusinessTargets()


class InventoryCommitment(BaseModel):
    sku: str
    landed_unit_cost_nzd: Decimal
    units: int

    @field_validator("landed_unit_cost_nzd")
    @classmethod
    def landed_cost_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("landed unit cost must be positive")
        return value

    @field_validator("units")
    @classmethod
    def units_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("inventory units must be positive")
        return value


def assess_initial_inventory_risk(
    commitments: list[InventoryCommitment],
    targets: BusinessTargets = DEFAULT_BUSINESS_TARGETS,
) -> dict[str, str | int]:
    total = sum(
        (item.landed_unit_cost_nzd * item.units for item in commitments),
        start=Decimal("0"),
    ).quantize(MONEY)
    headroom = (targets.max_initial_inventory_risk_nzd - total).quantize(MONEY)
    return {
        "sku_count": len({item.sku for item in commitments}),
        "planned_inventory_risk_nzd": str(total),
        "max_initial_inventory_risk_nzd": str(
            targets.max_initial_inventory_risk_nzd
        ),
        "remaining_headroom_nzd": str(
            max(Decimal("0"), headroom).quantize(MONEY)
        ),
        "status": "QUALIFIED" if headroom >= 0 else "REJECT",
    }
