from fastapi.testclient import TestClient

from product_scout.api import create_app


def _snapshot_payload() -> dict:
    return {
        "query_cluster": "beginner_telescope",
        "search_query": "beginner telescope",
        "observed_at": "2026-08-16",
        "source_url": "https://www.trademe.co.nz/a/marketplace/search?search_string=telescope",
        "active_listing_count": 84,
        "sampled_listing_count": 25,
        "unique_seller_count": 11,
        "min_price_nzd": "39.00",
        "median_price_nzd": "129.00",
        "max_price_nzd": "499.00",
        "buy_now_listing_count": 22,
        "bid_listing_count": 4,
        "total_bid_count": 13,
        "in_trade_seller_count": 8,
        "free_shipping_listing_count": 6,
        "notes": "First page manual sample; active listings only.",
    }


def test_trademe_snapshot_is_persisted_and_summarized(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))

    created = client.post("/dashboard/trademe/snapshots", json=_snapshot_payload())
    result = client.get("/dashboard/trademe")

    assert created.status_code == 201
    assert created.json()["confidence_label"] == "HIGH"
    assert created.json()["bid_listing_share"] == 0.16
    assert result.status_code == 200
    assert result.json()["summary"]["snapshot_count"] == 1
    assert result.json()["summary"]["median_active_listings_per_cluster"] == 84
    assert result.json()["snapshots"][0]["search_query"] == "beginner telescope"

    reloaded = TestClient(create_app(data_root=tmp_path)).get("/dashboard/trademe")
    assert reloaded.json()["summary"]["snapshot_count"] == 1


def test_trademe_snapshot_rejects_inconsistent_sample_counts(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    payload = _snapshot_payload()
    payload["bid_listing_count"] = 26

    response = client.post("/dashboard/trademe/snapshots", json=payload)

    assert response.status_code == 422
    assert "cannot exceed sampled_listing_count" in response.text

    payload = _snapshot_payload()
    payload["total_bid_count"] = 3
    response = client.post("/dashboard/trademe/snapshots", json=payload)
    assert response.status_code == 422
    assert "cannot be less than bid_listing_count" in response.text


def test_trademe_snapshot_requires_trade_me_source_and_can_be_deleted(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    invalid = _snapshot_payload()
    invalid["source_url"] = "https://example.com/search"

    assert client.post("/dashboard/trademe/snapshots", json=invalid).status_code == 422

    snapshot_id = client.post(
        "/dashboard/trademe/snapshots", json=_snapshot_payload()
    ).json()["id"]
    deleted = client.delete(f"/dashboard/trademe/snapshots/{snapshot_id}")

    assert deleted.status_code == 200
    assert client.get("/dashboard/trademe").json()["snapshots"] == []
    assert client.delete(f"/dashboard/trademe/snapshots/{snapshot_id}").status_code == 404


def test_trademe_zero_result_observation_does_not_require_prices(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    payload = _snapshot_payload()
    payload.update(
        {
            "active_listing_count": 0,
            "sampled_listing_count": 0,
            "unique_seller_count": 0,
            "min_price_nzd": None,
            "median_price_nzd": None,
            "max_price_nzd": None,
            "buy_now_listing_count": 0,
            "bid_listing_count": 0,
            "total_bid_count": 0,
            "in_trade_seller_count": 0,
            "free_shipping_listing_count": 0,
            "notes": "No active results observed.",
        }
    )

    response = client.post("/dashboard/trademe/snapshots", json=payload)

    assert response.status_code == 201
    assert response.json()["evidence_status"] == "INSUFFICIENT"
    assert response.json()["median_price_nzd"] is None
