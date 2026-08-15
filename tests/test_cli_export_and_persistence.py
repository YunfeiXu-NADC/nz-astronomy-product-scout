import csv
import json
import sqlite3
from decimal import Decimal

from product_scout.batch import KeywordRefreshBatchPaths, run_keyword_refresh_batch
from product_scout.cli import main
from product_scout.csv_import import CSVValidationError, import_product_candidates_csv
from product_scout.google_ads import GoogleKeywordPlanMetric
from product_scout.persistence import JsonRepositoryStore, SQLiteRepositoryStore
from product_scout.pipeline import recalculate_repository
from product_scout.repository import InMemoryRepository


class FakeKeywordPlannerClient:
    def __init__(self):
        self.calls = []

    def historical_metrics(self, *, keywords, location, language):
        self.calls.append(
            {
                "keywords": keywords,
                "location": location,
                "language": language,
            }
        )
        return [
            GoogleKeywordPlanMetric(
                keyword=keyword,
                monthly_searches=30 if "bahtinov" in keyword else 10,
                monthly_history=[10, 20, 30],
                competition_index=50,
                bid_low="0.25",
                bid_high="1.00",
            )
            for keyword in keywords
        ]


def test_product_candidate_csv_import_parses_low_risk_candidates():
    products = import_product_candidates_csv(
        """id,canonical_name,sku,category,subcategory,product_type,weight_g,length_mm,width_mm,height_mm,hs_code,expected_sell_price_nzd
prod_1,M48 Female to T2 Male Adapter,M48-T2,adapter,thread adapter,thread_adapter,32,48,48,12,9002900000,29.90
"""
    )

    assert products[0].id == "prod_1"
    assert products[0].expected_sell_price_nzd == Decimal("29.90")
    assert products[0].battery is False


def test_cli_rank_writes_sorted_opportunities_csv(tmp_path):
    products = tmp_path / "products.csv"
    suppliers = tmp_path / "supplier_offers.csv"
    shipping = tmp_path / "shipping_rates.csv"
    imports = tmp_path / "imports.csv"
    keywords = tmp_path / "keywords.csv"
    output = tmp_path / "opportunities.csv"

    products.write_text(
        """id,canonical_name,sku,category,subcategory,product_type,weight_g,length_mm,width_mm,height_mm,hs_code,expected_sell_price_nzd
prod_1,M48 Female to T2 Male Adapter,M48-T2,adapter,thread adapter,thread_adapter,32,48,48,12,9002900000,29.90
prod_2,Obscure Bracket,ODD-BRACKET,bracket,mechanical bracket,bracket,120,80,50,20,9002900000,79.90
""",
        encoding="utf-8",
    )
    suppliers.write_text(
        """source_url,product_name,sku,unit_price_cny,moq,weight_g,length_mm,width_mm,height_mm,domestic_shipping_cny,supplier,monthly_sales_ref,lead_time_days
https://1688.example/m48,M48 Female to T2 Male Adapter,M48-T2,12.40,10,32,48,48,12,4.50,Astronomy CNC,120,5
https://1688.example/bracket,Obscure Bracket,ODD-BRACKET,18.00,10,120,80,50,20,5.00,Metal Parts Co,30,7
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
prod_2,obscure astronomy bracket,obscure_bracket,0,"0|0|0|0|0|0|0|0|0|0|0|0",10,0.10,0.20
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "rank",
            "--products",
            str(products),
            "--suppliers",
            str(suppliers),
            "--shipping",
            str(shipping),
            "--imports",
            str(imports),
            "--keywords",
            str(keywords),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert rows[0]["sku"] == "M48-T2"
    assert rows[0]["prelaunch_score"]
    assert rows[0]["confidence"]
    assert int(rows[0]["rank"]) == 1


def test_keyword_refresh_batch_writes_metrics_csv_from_seed_csv(tmp_path):
    products = tmp_path / "products.csv"
    seeds = tmp_path / "keyword_seeds.csv"
    output = tmp_path / "keyword_metrics.csv"
    products.write_text(
        """id,canonical_name,sku,category,subcategory,product_type,weight_g,length_mm,width_mm,height_mm,hs_code,expected_sell_price_nzd
prod_1,Bahtinov Mask,BMASK,passive,focus mask,bahtinov_mask,40,90,90,2,9002900000,24.90
""",
        encoding="utf-8",
    )
    seeds.write_text(
        """product_id,keyword,keyword_cluster
prod_1,bahtinov mask,bahtinov_mask
prod_1,telescope focus mask,bahtinov_mask
""",
        encoding="utf-8",
    )
    client = FakeKeywordPlannerClient()

    result = run_keyword_refresh_batch(
        KeywordRefreshBatchPaths(
            products_csv_path=products,
            keyword_seeds_csv_path=seeds,
            output_csv_path=output,
        ),
        client,
    )

    assert result.refreshed_keywords == 2
    assert client.calls == [
        {
            "keywords": ["bahtinov mask", "telescope focus mask"],
            "location": "New Zealand",
            "language": "English",
        }
    ]
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert rows[0]["product_id"] == "prod_1"
    assert rows[0]["keyword_cluster"] == "bahtinov_mask"
    assert rows[0]["monthly_history"] == "10|20|30"
    assert rows[0]["bid_low"] == "0.25"


def test_keyword_refresh_batch_rejects_unknown_product_ids(tmp_path):
    products = tmp_path / "products.csv"
    seeds = tmp_path / "keyword_seeds.csv"
    output = tmp_path / "keyword_metrics.csv"
    products.write_text(
        """id,canonical_name,sku,category,subcategory,product_type,weight_g,length_mm,width_mm,height_mm,hs_code,expected_sell_price_nzd
prod_1,Dust Cap,DUST-CAP,passive,dust cap,dust_cap,20,40,40,10,9005900000,14.90
""",
        encoding="utf-8",
    )
    seeds.write_text(
        """product_id,keyword,keyword_cluster
missing_product,dust cap,dust_cap
""",
        encoding="utf-8",
    )

    try:
        run_keyword_refresh_batch(
            KeywordRefreshBatchPaths(
                products_csv_path=products,
                keyword_seeds_csv_path=seeds,
                output_csv_path=output,
            ),
            FakeKeywordPlannerClient(),
        )
    except CSVValidationError as exc:
        assert "missing_product" in str(exc)
    else:
        raise AssertionError("Expected CSVValidationError")


def test_json_repository_store_round_trips_pipeline_state(tmp_path):
    repo = InMemoryRepository()
    products = import_product_candidates_csv(
        """id,canonical_name,sku,category,subcategory,product_type,weight_g,length_mm,width_mm,height_mm,hs_code,expected_sell_price_nzd
prod_1,Dust Cap,DUST-CAP,passive,dust cap,dust_cap,20,40,40,10,9005900000,14.90
"""
    )
    repo.import_products(products, [], [])
    recalculate_repository(repo)

    store_path = tmp_path / "repo.json"
    JsonRepositoryStore(store_path).save(repo)
    loaded = JsonRepositoryStore(store_path).load()

    assert loaded.products["prod_1"].sku == "DUST-CAP"
    assert loaded.score_snapshots["prod_1"].product_id == "prod_1"
    assert json.loads(store_path.read_text(encoding="utf-8"))["products"][0]["sku"] == "DUST-CAP"


def test_sqlite_repository_store_round_trips_with_entity_tables(tmp_path):
    repo = InMemoryRepository()
    products = import_product_candidates_csv(
        """id,canonical_name,sku,category,subcategory,product_type,weight_g,length_mm,width_mm,height_mm,hs_code,expected_sell_price_nzd
prod_1,M48 Female to T2 Male Adapter,M48-T2,adapter,thread adapter,thread_adapter,32,48,48,12,9002900000,39.90
"""
    )
    repo.import_products(products, [], [])
    recalculate_repository(repo)

    sqlite_path = tmp_path / "scout.db"
    store = SQLiteRepositoryStore(sqlite_path)
    store.save(repo)
    loaded = store.load()

    assert loaded.products["prod_1"].canonical_name == "M48 Female to T2 Male Adapter"
    assert loaded.score_snapshots["prod_1"].sku == "M48-T2"
    with sqlite3.connect(sqlite_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"product_candidate", "score_snapshot"}.issubset(tables)
        assert (
            connection.execute("SELECT COUNT(*) FROM product_candidate").fetchone()[0]
            == 1
        )
