from product_scout.google_ads import (
    GoogleAdsKeywordRefreshService,
    GoogleKeywordPlanMetric,
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
