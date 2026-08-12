from decimal import Decimal
import csv

from fastapi.testclient import TestClient

from product_scout.api import create_app


def test_api_imports_products_and_returns_economics_and_opportunities():
    client = TestClient(create_app())
    payload = {
        "supplier_offers_csv": """source_url,product_name,sku,unit_price_cny,moq,weight_g,length_mm,width_mm,height_mm,domestic_shipping_cny,supplier,monthly_sales_ref,lead_time_days
https://1688.example/m48,M48 Female to T2 Male Adapter,M48-T2,12.40,10,32,48,48,12,4.50,Astronomy CNC,120,5
""",
        "shipping_rates_csv": """provider,route,min_weight_g,max_weight_g,volumetric_divisor,base_fee_cny,fee_per_kg_cny,delivery_days
CN Express,china_to_nz_direct,0,500,6000,28,60,8
""",
        "products": [
            {
                "id": "prod_1",
                "canonical_name": "M48 Female to T2 Male Adapter",
                "sku": "M48-T2",
                "category": "adapter",
                "subcategory": "thread adapter",
                "product_type": "thread_adapter",
                "weight_g": 32,
                "length_mm": 48,
                "width_mm": 48,
                "height_mm": 12,
                "hs_code": "9002900000",
                "expected_sell_price_nzd": "29.90",
            }
        ],
    }

    response = client.post("/products/import", json=payload)

    assert response.status_code == 200
    assert response.json()["imported_products"] == 1

    economics = client.get("/products/prod_1/economics")
    assert economics.status_code == 200
    assert Decimal(economics.json()["contribution_margin"]) > Decimal("0.30")

    keyword_refresh = client.post(
        "/keywords/refresh",
        json={
            "metrics": [
                {
                    "product_id": "prod_1",
                    "keyword": "m48 t2 adapter",
                    "keyword_cluster": "m48_t2_adapter",
                    "monthly_searches": 210,
                    "monthly_history": [160, 170, 180, 190, 200, 210, 210, 220, 225, 230, 235, 240],
                }
            ]
        },
    )
    assert keyword_refresh.status_code == 200
    assert keyword_refresh.json()["updated_products"] == 1

    imports_refresh = client.post(
        "/imports/refresh",
        json={
            "metrics": [
                {"hs_code": "9002900000", "year": 2024, "month": 1, "origin_country": "World", "import_nzd": "30000", "quantity": 280, "unit": "EA"},
                {"hs_code": "9002900000", "year": 2025, "month": 1, "origin_country": "China", "import_nzd": "22000", "quantity": 190, "unit": "EA"},
                {"hs_code": "9002900000", "year": 2025, "month": 1, "origin_country": "World", "import_nzd": "40000", "quantity": 350, "unit": "EA"},
            ]
        },
    )
    assert imports_refresh.status_code == 200

    opportunities = client.get("/opportunities")
    assert opportunities.status_code == 200
    assert opportunities.json()[0]["product_id"] == "prod_1"
    assert "confidence" in opportunities.json()[0]

    detail = client.get("/opportunities/prod_1")
    assert detail.status_code == 200
    assert detail.json()["product"]["sku"] == "M48-T2"


def test_product_crud_endpoints_create_list_get_and_update_candidates():
    client = TestClient(create_app())
    product = {
        "id": "prod_2",
        "canonical_name": "Dust Cap",
        "sku": "DUST-CAP",
        "category": "passive",
        "subcategory": "dust cap",
        "product_type": "dust_cap",
        "weight_g": 20,
        "length_mm": 40,
        "width_mm": 40,
        "height_mm": 10,
        "hs_code": "9005900000",
        "expected_sell_price_nzd": "14.90",
    }

    created = client.post("/products", json=product)
    assert created.status_code == 200
    assert created.json()["sku"] == "DUST-CAP"

    listed = client.get("/products")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == "prod_2"

    updated = client.patch("/products/prod_2", json={"status": "QUALIFIED"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "QUALIFIED"

    fetched = client.get("/products/prod_2")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "QUALIFIED"


def test_api_batch_rank_reads_csv_paths_and_writes_outputs(tmp_path):
    client = TestClient(create_app())
    products = tmp_path / "products.csv"
    suppliers = tmp_path / "supplier_offers.csv"
    shipping = tmp_path / "shipping_rates.csv"
    imports = tmp_path / "imports.csv"
    keywords = tmp_path / "keywords.csv"
    output = tmp_path / "opportunities.csv"
    store = tmp_path / "repository_state.sqlite"

    products.write_text(
        """id,canonical_name,sku,category,subcategory,product_type,weight_g,length_mm,width_mm,height_mm,hs_code,expected_sell_price_nzd
prod_1,M48 Female to T2 Male Adapter,M48-T2,adapter,thread adapter,thread_adapter,32,48,48,12,9002900000,39.90
""",
        encoding="utf-8",
    )
    suppliers.write_text(
        """source_url,product_name,sku,unit_price_cny,moq,weight_g,length_mm,width_mm,height_mm,domestic_shipping_cny,supplier,monthly_sales_ref,lead_time_days
https://1688.example/m48,M48 Female to T2 Male Adapter,M48-T2,12.40,10,32,48,48,12,4.50,Astronomy CNC,120,5
""",
        encoding="utf-8",
    )
    shipping.write_text(
        """provider,route,min_weight_g,max_weight_g,volumetric_divisor,base_fee_cny,fee_per_kg_cny,delivery_days
CN Express,china_to_nz_direct,0,500,6000,28,60,8
""",
        encoding="utf-8",
    )
    imports.write_text(
        """hs_code,year,month,origin_country,import_nzd,quantity,unit
9002900000,2025,1,World,40000,350,EA
9002900000,2025,1,China,22000,190,EA
""",
        encoding="utf-8",
    )
    keywords.write_text(
        """product_id,keyword,keyword_cluster,monthly_searches,monthly_history,competition_index,bid_low,bid_high
prod_1,m48 t2 adapter,m48_t2_adapter,210,"160|170|180|190|200|210|210|220|225|230|235|240",42,0.30,1.20
""",
        encoding="utf-8",
    )

    response = client.post(
        "/batches/rank",
        json={
            "products_csv_path": str(products),
            "supplier_offers_csv_path": str(suppliers),
            "shipping_rates_csv_path": str(shipping),
            "stats_nz_csv_path": str(imports),
            "keyword_metrics_csv_path": str(keywords),
            "output_csv_path": str(output),
            "sqlite_store_path": str(store),
        },
    )

    assert response.status_code == 200
    assert response.json()["ranked_products"] == 1
    assert response.json()["top_sku"] == "M48-T2"
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert rows[0]["status"] == "QUALIFIED"
    assert store.exists()
