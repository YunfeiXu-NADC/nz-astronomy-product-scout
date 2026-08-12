from decimal import Decimal

import pytest

from product_scout.csv_import import (
    CSVValidationError,
    import_hs_mapping_csv,
    import_shipping_rates_csv,
    import_stats_nz_csv,
    import_supplier_offers_csv,
)
from product_scout.economics import ChinaDirectCostEngine, EconomicsAssumptions
from product_scout.models import ProductCandidate


def test_import_supplier_offers_validates_required_fields_and_duplicate_skus():
    missing_price = """source_url,product_name,sku,moq,weight_g,length_mm,width_mm,height_mm,domestic_shipping_cny,supplier,monthly_sales_ref,lead_time_days
https://1688.example/m48,M48 to T2 Adapter,M48-T2,10,32,48,48,12,4.50,Astronomy CNC,120,5
"""
    duplicate_sku = """source_url,product_name,sku,unit_price_cny,moq,weight_g,length_mm,width_mm,height_mm,domestic_shipping_cny,supplier,monthly_sales_ref,lead_time_days
https://1688.example/m48,M48 to T2 Adapter,M48-T2,12.40,10,32,48,48,12,4.50,Astronomy CNC,120,5
https://1688.example/m48b,M48 to T2 Adapter,M48-T2,13.10,10,32,48,48,12,4.50,Optics Parts Co,90,7
"""

    with pytest.raises(CSVValidationError, match="unit_price_cny"):
        import_supplier_offers_csv(missing_price)

    with pytest.raises(CSVValidationError, match="Duplicate sku"):
        import_supplier_offers_csv(duplicate_sku)


def test_import_supplier_offers_parses_numeric_fields_and_rejects_invalid_values():
    csv_text = """source_url,product_name,sku,unit_price_cny,moq,weight_g,length_mm,width_mm,height_mm,domestic_shipping_cny,supplier,monthly_sales_ref,lead_time_days
https://1688.example/m48,M48 to T2 Adapter,M48-T2,12.40,10,32,48,48,12,4.50,Astronomy CNC,120,5
"""
    bad_weight = csv_text.replace(",32,", ",-32,")

    offers = import_supplier_offers_csv(csv_text)

    assert offers[0].sku == "M48-T2"
    assert offers[0].unit_price_cny == Decimal("12.40")
    assert offers[0].weight_g == 32
    assert offers[0].package_dimensions.length_mm == 48

    with pytest.raises(CSVValidationError, match="weight_g"):
        import_supplier_offers_csv(bad_weight)


def test_shipping_import_and_china_direct_economics_use_chargeable_weight():
    shipping_csv = """provider,route,min_weight_g,max_weight_g,volumetric_divisor,base_fee_cny,fee_per_kg_cny,delivery_days
CN Express,china_to_nz_direct,0,500,6000,28,60,8
"""
    [rate] = import_shipping_rates_csv(shipping_csv)
    product = ProductCandidate(
        id="prod_1",
        canonical_name="M48 Female to T2 Male Adapter",
        sku="M48-T2",
        category="adapter",
        subcategory="thread adapter",
        product_type="thread_adapter",
        weight_g=32,
        length_mm=120,
        width_mm=120,
        height_mm=120,
        thread_a="M48x0.75 female",
        thread_b="T2 male",
        hs_code="9002900000",
        expected_sell_price_nzd=Decimal("29.90"),
    )
    offer = import_supplier_offers_csv(
        """source_url,product_name,sku,unit_price_cny,moq,weight_g,length_mm,width_mm,height_mm,domestic_shipping_cny,supplier,monthly_sales_ref,lead_time_days
https://1688.example/m48,M48 to T2 Adapter,M48-T2,12.40,10,32,120,120,120,4.50,Astronomy CNC,120,5
"""
    )[0]
    engine = ChinaDirectCostEngine(
        [rate],
        assumptions=EconomicsAssumptions(
            cny_to_nzd=Decimal("0.23"),
            trade_me_fee_rate=Decimal("0.079"),
            payment_fee_rate=Decimal("0.025"),
            packaging_nzd=Decimal("0.50"),
            refund_reserve_rate=Decimal("0.030"),
        ),
    )

    result = engine.calculate(product, offer)

    assert result.chargeable_weight_g == 288
    assert result.international_shipping_nzd == Decimal("10.41")
    assert result.landed_cost_nzd == Decimal("14.80")
    assert result.contribution_profit_nzd == Decimal("10.99")
    assert result.contribution_margin == Decimal("0.3676")
    assert result.status == "REJECT"
    assert result.rejection_reasons == ["contribution_profit_below_15_nzd"]


def test_hs_mapping_marks_low_confidence_for_manual_confirmation():
    mappings = import_hs_mapping_csv(
        """product_id,hs_code,mapping_confidence,analyst_notes
prod_1,9002900000,65,chapter 90 candidate but needs broker review
prod_2,9005900000,90,confirmed from tariff note
"""
    )

    assert mappings[0].requires_manual_confirmation is True
    assert mappings[1].requires_manual_confirmation is False


def test_stats_nz_csv_import_supports_hs_country_monthly_metrics():
    metrics = import_stats_nz_csv(
        """hs_code,year,month,origin_country,import_nzd,quantity,unit
9002900000,2025,1,China,22000,190,EA
9002900000,2025,1,World,40000,350,EA
"""
    )

    assert len(metrics) == 2
    assert metrics[0].hs_code == "9002900000"
    assert metrics[0].import_nzd == Decimal("22000")
    assert metrics[0].quantity == Decimal("190")
