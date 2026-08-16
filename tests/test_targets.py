from decimal import Decimal

import pytest

from product_scout.targets import (
    BusinessTargets,
    InventoryCommitment,
    assess_initial_inventory_risk,
)


def test_business_targets_calculate_required_order_run_rate():
    targets = BusinessTargets(
        monthly_contribution_profit_nzd=Decimal("3000"),
        min_contribution_profit_per_order_nzd=Decimal("20"),
    )

    assert targets.required_monthly_orders == 150
    assert targets.required_daily_orders == Decimal("5.0")


def test_business_targets_round_order_requirement_up():
    targets = BusinessTargets(
        monthly_contribution_profit_nzd=Decimal("3000"),
        min_contribution_profit_per_order_nzd=Decimal("22"),
    )

    assert targets.required_monthly_orders == 137


def test_business_targets_reject_invalid_test_window():
    with pytest.raises(ValueError, match="minimum SKU test days"):
        BusinessTargets(min_sku_test_days=61, max_sku_test_days=60)


def test_inventory_risk_rejects_commitments_above_the_cap():
    commitments = [
        InventoryCommitment(
            sku="FILTER-CASE",
            landed_unit_cost_nzd=Decimal("16"),
            units=100,
        )
    ]

    result = assess_initial_inventory_risk(commitments)

    assert result["planned_inventory_risk_nzd"] == "1600.00"
    assert result["remaining_headroom_nzd"] == "0.00"
    assert result["status"] == "REJECT"
