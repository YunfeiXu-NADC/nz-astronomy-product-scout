from product_scout.google_ads import (
    GoogleAdsCredentialConfig,
    GoogleAdsKeywordRefreshService,
    GoogleKeywordPlanMetric,
    _geo_target_resource_name,
    _language_resource_name,
    _metric_from_rest_result,
    load_google_ads_config,
)
from product_scout.models import ProductCandidate


class RecordingKeywordPlannerClient:
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
                keyword="m48 t2 adapter",
                monthly_searches=210,
                monthly_history=[160, 170, 180, 190, 200, 210, 210, 220, 225, 230, 235, 240],
                competition_index=42,
                bid_low="0.30",
                bid_high="1.20",
            )
        ]


def test_google_ads_refresh_enforces_new_zealand_english_and_clusters_synonyms():
    product = ProductCandidate(
        id="prod_1",
        canonical_name="M48 Female to T2 Male Adapter",
        sku="M48-T2",
        category="adapter",
        subcategory="thread adapter",
        product_type="thread_adapter",
        weight_g=32,
        length_mm=48,
        width_mm=48,
        height_mm=12,
        hs_code="9002900000",
        expected_sell_price_nzd="29.90",
    )
    client = RecordingKeywordPlannerClient()
    service = GoogleAdsKeywordRefreshService(client)

    metrics = service.refresh(
        [product],
        {"prod_1": ["m48 t2 adapter", "telescope t adapter"]},
        {"m48 t2 adapter": "m48_t2_adapter", "telescope t adapter": "m48_t2_adapter"},
    )

    assert client.calls == [
        {
            "keywords": ["m48 t2 adapter", "telescope t adapter"],
            "location": "New Zealand",
            "language": "English",
        }
    ]
    assert metrics[0].product_id == "prod_1"
    assert metrics[0].keyword_cluster == "m48_t2_adapter"
    assert metrics[0].monthly_searches == 210


def test_load_google_ads_config_reads_dotenv_and_normalizes_customer_ids(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "GOOGLE_ADS_DEVELOPER_TOKEN=dev-token",
                "GOOGLE_ADS_CLIENT_ID=client-id",
                "GOOGLE_ADS_CLIENT_SECRET=client-secret",
                "GOOGLE_ADS_REFRESH_TOKEN=refresh-token",
                "GOOGLE_ADS_CUSTOMER_ID=250-282-4242",
                "GOOGLE_ADS_LOGIN_CUSTOMER_ID=770-615-0693",
                "GOOGLE_ADS_GEO_TARGET=New Zealand",
                "GOOGLE_ADS_LANGUAGE=English",
            ]
        ),
        encoding="utf-8",
    )

    config = load_google_ads_config(env_path)

    assert config == GoogleAdsCredentialConfig(
        developer_token="dev-token",
        client_id="client-id",
        client_secret="client-secret",
        refresh_token="refresh-token",
        customer_id="2502824242",
        login_customer_id="7706150693",
        geo_target="New Zealand",
        language="English",
    )


def test_google_ads_resource_helpers_support_v1_new_zealand_english_defaults():
    assert _geo_target_resource_name("New Zealand") == "geoTargetConstants/2554"
    assert _geo_target_resource_name("2554") == "geoTargetConstants/2554"
    assert _language_resource_name("English") == "languageConstants/1000"
    assert _language_resource_name("1000") == "languageConstants/1000"


def test_google_ads_rest_result_parser_preserves_month_order_and_bids():
    metric = _metric_from_rest_result(
        {
            "text": "Bahtinov Mask",
            "keywordMetrics": {
                "avgMonthlySearches": "70",
                "competitionIndex": "34",
                "lowTopOfPageBidMicros": "500000",
                "highTopOfPageBidMicros": "1250000",
                "monthlySearchVolumes": [
                    {"year": "2025", "month": "FEBRUARY", "monthlySearches": "60"},
                    {"year": "2025", "month": "JANUARY", "monthlySearches": "50"},
                ],
            },
        }
    )

    assert metric.keyword == "bahtinov mask"
    assert metric.monthly_searches == 70
    assert metric.monthly_history == [50, 60]
    assert metric.competition_index == 34
    assert str(metric.bid_low) == "0.5"
    assert str(metric.bid_high) == "1.25"
