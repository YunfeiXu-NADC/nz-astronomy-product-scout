import csv
import json
from decimal import Decimal

from product_scout.batch import Discover1688BatchPaths, run_1688_discovery_batch
from product_scout.csv_import import (
    import_keyword_seeds_csv,
    import_product_candidates_csv,
    import_supplier_offers_csv,
)
from product_scout.discovery import (
    build_discovery_result,
    infer_product_metadata,
    parse_1688_html,
    parse_1688_json_payload,
)


def test_parse_1688_html_extracts_listings_from_embedded_json():
    html = """
    <html><body>
      <script>
        window.__INITIAL_STATE__ = {
          "data": {
            "items": [
              {
                "subject": "M48 to T2 telescope adapter",
                "price": "12.40",
                "beginAmount": 10,
                "detailUrl": "//detail.1688.com/offer/1.html",
                "companyName": "Astronomy CNC",
                "saleQuantity": 120,
                "package": {"weightG": 32, "lengthMm": 48, "widthMm": 48, "heightMm": 12}
              }
            ]
          }
        };
      </script>
    </body></html>
    """

    listings = parse_1688_html(html, source_url="https://s.1688.com/selloffer/offer_search.htm")

    assert len(listings) == 1
    assert listings[0].source_url == "https://detail.1688.com/offer/1.html"
    assert listings[0].title == "M48 to T2 telescope adapter"
    assert listings[0].unit_price_cny == Decimal("12.40")
    assert listings[0].supplier == "Astronomy CNC"
    assert listings[0].weight_g == 32


def test_discovery_result_builds_products_supplier_offers_and_keyword_seeds():
    listings = parse_1688_json_payload(
        {
            "items": [
                {
                    "title": "Bahtinov mask telescope focus mask",
                    "unit_price_cny": "9.80",
                    "moq": 5,
                    "source_url": "https://detail.1688.com/offer/2.html",
                    "supplier": "Focus Parts",
                    "weight_g": 40,
                    "length_mm": 90,
                    "width_mm": 90,
                    "height_mm": 2,
                },
                {
                    "title": "Solar telescope filter with battery heater",
                    "price": "19.00",
                    "url": "https://detail.1688.com/offer/3.html",
                },
            ]
        },
        source_url="fixture.json",
    )

    result = build_discovery_result(listings)

    assert len(result.products) == 2
    assert result.products[0].product_type == "bahtinov_mask"
    assert result.products[0].expected_sell_price_nzd >= Decimal("14.90")
    assert result.supplier_offers[0].sku == result.products[0].sku
    assert result.keyword_seeds[0].product_id == result.products[0].id
    assert result.products[1].solar_observation is True
    assert result.products[1].battery is True
    assert result.products[1].safety_risk == "solar_observation,battery,powered_electronics"


def test_1688_discovery_batch_writes_pipeline_ready_csvs(tmp_path):
    source = tmp_path / "1688.json"
    products = tmp_path / "products.csv"
    suppliers = tmp_path / "supplier_offers.csv"
    seeds = tmp_path / "keyword_seeds.csv"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "title": "T2 5mm spacer extension ring",
                        "price": "8.20",
                        "moq": 20,
                        "source_url": "https://detail.1688.com/offer/4.html",
                        "supplier": "Optics Parts Co",
                        "weight_g": 18,
                        "length_mm": 42,
                        "width_mm": 42,
                        "height_mm": 5,
                        "domestic_shipping_cny": "4.00",
                        "lead_time_days": 6,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_1688_discovery_batch(
        Discover1688BatchPaths(
            source_json_path=source,
            output_products_csv_path=products,
            output_supplier_offers_csv_path=suppliers,
            output_keyword_seeds_csv_path=seeds,
        )
    )

    assert result.discovered_listings == 1
    parsed_products = import_product_candidates_csv(products.read_text(encoding="utf-8"))
    parsed_suppliers = import_supplier_offers_csv(suppliers.read_text(encoding="utf-8"))
    parsed_seeds = import_keyword_seeds_csv(seeds.read_text(encoding="utf-8"))
    assert parsed_products[0].product_type == "spacer"
    assert parsed_suppliers[0].unit_price_cny == Decimal("8.20")
    assert parsed_seeds[0].keyword_cluster == "spacer"
    assert list(csv.DictReader(products.open(encoding="utf-8")))[0]["sku"]


def test_infer_product_metadata_identifies_low_risk_target_categories():
    assert infer_product_metadata("M48 camera adapter")["product_type"] == "camera_adapter"
    assert infer_product_metadata("1.25 inch dust cap")["product_type"] == "dust_cap"
    assert infer_product_metadata("telescope mounting bracket")["product_type"] == "bracket"
