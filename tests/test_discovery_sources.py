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


def test_discovery_adapter_keywords_remain_product_specific():
    listings = parse_1688_json_payload(
        {
            "items": [
                {
                    "title": "M48 to M54 telescope adapter",
                    "price": "12.40",
                    "url": "https://detail.1688.com/offer/9002.html",
                }
            ]
        },
        source_url="fixture.json",
    )

    seeds = build_discovery_result(listings).keyword_seeds

    assert [seed.keyword for seed in seeds] == [
        "m48 to m54 telescope adapter",
    ]
    assert all(seed.keyword != "telescope adapter" for seed in seeds)


def test_chrome_extension_capture_is_compatible_with_discovery_parser():
    listings = parse_1688_json_payload(
        {
            "source": "1688_chrome_extension",
            "source_url": "https://s.1688.com/selloffer/offer_search.htm",
            "items": [
                {
                    "title": "M48 telescope camera adapter",
                    "price": "12.40",
                    "moq": 10,
                    "detailUrl": "https://detail.1688.com/offer/9001.html",
                    "supplier": "Astronomy CNC",
                    "saleQuantity": "120",
                    "imageUrl": "https://cbu01.alicdn.com/img/ibank/example.jpg",
                }
            ],
        },
        source_url="extension-capture.json",
    )

    assert len(listings) == 1
    assert listings[0].title == "M48 telescope camera adapter"
    assert listings[0].unit_price_cny == Decimal("12.40")
    assert listings[0].moq == 10
    assert listings[0].monthly_sales_ref == 120
    assert listings[0].source_url == "https://detail.1688.com/offer/9001.html"


def test_chinese_sales_units_are_expanded():
    listings = parse_1688_json_payload(
        {
            "items": [
                {"title": "Finder bracket", "price": "26.32", "saleQuantity": "1万+"},
                {"title": "Dust cap", "price": "5.50", "saleQuantity": "1.2万+"},
            ]
        },
        source_url="extension-capture.json",
    )

    assert listings[0].monthly_sales_ref == 10000
    assert listings[1].monthly_sales_ref == 12000


def test_extension_detail_capture_uses_page_title_for_current_product():
    listings = parse_1688_json_payload(
        {
            "source": "1688_chrome_extension",
            "page_title": "天文望远镜 M48 M42 转接环 - 阿里巴巴",
            "items": [
                {
                    "captureContext": "current_product",
                    "title": "徐州天缘星美光学仪器有限公司",
                    "price": "7.37",
                    "detailUrl": "https://detail.1688.com/offer/744155041744.html",
                },
                {
                    "captureContext": "related_product",
                    "title": "M42 相机转接环",
                    "price": "8.42",
                    "detailUrl": "https://detail.1688.com/offer/563641416894.html",
                },
            ],
        },
        source_url="extension-capture.json",
    )

    assert listings[0].title == "天文望远镜 M48 M42 转接环"
    assert listings[1].title == "M42 相机转接环"


def test_extension_capture_removes_ui_noise_and_cleans_labels():
    listings = parse_1688_json_payload(
        {
            "source": "1688_chrome_extension",
            "items": [
                {
                    "title": "反馈",
                    "price": "19",
                    "detailUrl": "https://detail.1688.com/offer/1349447356.html",
                },
                {
                    "title": "M48 转 M54 转接环 @",
                    "price": "13",
                    "supplier": "南阳市宇瑾光电科技有限公司旺旺在线",
                    "detailUrl": "https://detail.1688.com/offer/1070782759608.html",
                },
            ],
        },
        source_url="extension-capture.json",
    )

    assert len(listings) == 1
    assert listings[0].title == "M48 转 M54 转接环"
    assert listings[0].supplier == "南阳市宇瑾光电科技有限公司"


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
