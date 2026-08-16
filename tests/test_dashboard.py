from pathlib import Path

from fastapi.testclient import TestClient

from product_scout.api import create_app


def _write_dashboard_data(root: Path) -> None:
    research = root / "research"
    samples = root / "sample_data"
    research.mkdir()
    samples.mkdir()
    (research / "nz_astronomy_market_summary.csv").write_text(
        "segment,intent_clusters,nonzero_clusters,nonzero_cluster_share,"
        "conservative_demand_index,median_cluster_searches,top_keyword,"
        "top_keyword_searches,peak_to_average_ratio\n"
        "core_market,4,4,100.0,6720,1750.0,telescope,2900,1.20\n",
        encoding="utf-8",
    )
    (research / "nz_astronomy_market_metrics.csv").write_text(
        "segment,intent_cluster,keyword,role,monthly_searches,monthly_history,"
        "competition_index,bid_low,bid_high\n"
        "core_market,telescope,telescope,head,2900,2400|2900,100,1.28,8.44\n",
        encoding="utf-8",
    )
    (samples / "opportunities.csv").write_text(
        "rank,product_id,sku,product_name,prelaunch_score,confidence,status,"
        "search_demand_score,import_evidence_score,unit_economics_score,"
        "logistics_score,supply_quality_score,product_risk_fit_score,"
        "rejection_reasons\n"
        "1,p1,M42-T2,M42 to T2 adapter,75,60,QUALIFIED,70,0,80,100,50,100,\n",
        encoding="utf-8",
    )


def test_dashboard_serves_bilingual_workspace_and_market_data(tmp_path):
    _write_dashboard_data(tmp_path)
    client = TestClient(create_app(data_root=tmp_path))

    page = client.get("/")
    market = client.get("/dashboard/market")
    overview = client.get("/dashboard/overview")

    assert page.status_code == 200
    assert "Product Scout · 选品研究台" in page.text
    assert market.status_code == 200
    assert market.json()["summaries"][0]["label_zh"] == "核心天文市场"
    assert market.json()["metrics"][0]["monthly_searches"] == "2900"
    assert overview.json()["report"]["decision"]["zh"].startswith("进入需求机会簇")
    assert overview.json()["opportunity_counts"]["qualified"] == 1


def test_dashboard_opportunity_endpoint_uses_latest_available_csv(tmp_path):
    _write_dashboard_data(tmp_path)
    client = TestClient(create_app(data_root=tmp_path))

    response = client.get("/dashboard/opportunities")

    assert response.status_code == 200
    assert response.json()["items"][0]["sku"] == "M42-T2"
    assert Path(response.json()["source"]).name == "opportunities.csv"


def test_dashboard_static_assets_are_packaged(tmp_path):
    _write_dashboard_data(tmp_path)
    client = TestClient(create_app(data_root=tmp_path))

    script = client.get("/static/app.js")
    stylesheet = client.get("/static/styles.css")

    assert script.status_code == 200
    assert "calculateInventoryRisk" in script.text
    assert stylesheet.status_code == 200
    assert ".inventory-layout" in stylesheet.text
