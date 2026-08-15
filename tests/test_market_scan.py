from decimal import Decimal
from io import StringIO

import pytest

from product_scout.google_ads import GoogleKeywordPlanMetric
from product_scout.market_scan import (
    MarketSeedValidationError,
    export_market_summary_csv,
    import_market_seeds_csv,
    run_market_scan,
    summarize_market_segments,
)


class FakeKeywordPlannerClient:
    def historical_metrics(self, *, keywords, location, language):
        assert location == "New Zealand"
        assert language == "English"
        values = {
            "telescope": (2900, [2400, 3600]),
            "telescopes nz": (1600, [1300, 1900]),
            "telescope eyepiece": (30, [20, 40]),
        }
        return [
            GoogleKeywordPlanMetric(
                keyword=keyword,
                monthly_searches=values[keyword][0],
                monthly_history=values[keyword][1],
                competition_index=80,
            )
            for keyword in keywords
            if keyword in values
        ]


def test_market_scan_does_not_sum_synonyms_in_the_same_cluster():
    seeds = import_market_seeds_csv(
        "segment,intent_cluster,keyword,role\n"
        "core,telescope,telescope,head\n"
        "core,telescope,telescopes nz,local_modifier\n"
        "accessory,eyepiece,telescope eyepiece,commercial\n"
        "accessory,missing,unknown accessory,commercial\n"
    )
    rows = run_market_scan(seeds, FakeKeywordPlannerClient())
    summaries = {item.segment: item for item in summarize_market_segments(rows)}

    assert summaries["core"].conservative_demand_index == 2900
    assert summaries["core"].intent_clusters == 1
    assert summaries["accessory"].conservative_demand_index == 30
    assert summaries["accessory"].nonzero_cluster_share == Decimal("50.0")
    assert next(row for row in rows if row.seed.keyword == "unknown accessory").metric.monthly_searches == 0


def test_market_seed_import_rejects_duplicate_keywords():
    with pytest.raises(MarketSeedValidationError, match="repeats keyword"):
        import_market_seeds_csv(
            "segment,intent_cluster,keyword,role\n"
            "core,telescope,telescope,head\n"
            "core,telescope,Telescope,head\n"
        )


def test_market_summary_export_has_auditable_fields():
    seeds = import_market_seeds_csv(
        "segment,intent_cluster,keyword,role\n"
        "core,telescope,telescope,head\n"
    )
    rows = run_market_scan(seeds, FakeKeywordPlannerClient())
    destination = StringIO()

    export_market_summary_csv(summarize_market_segments(rows), destination)

    output = destination.getvalue()
    assert "conservative_demand_index" in output
    assert "core,1,1,100.0,2900" in output
