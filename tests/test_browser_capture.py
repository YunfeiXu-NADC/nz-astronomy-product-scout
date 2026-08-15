from decimal import Decimal

from product_scout.browser_capture import listings_from_browser_snapshot


def test_browser_snapshot_merges_embedded_and_visible_listings():
    html = """
    <script>
      window.__DATA__ = {
        "items": [{
          "title": "M48 to T2 telescope adapter",
          "price": "12.40",
          "detailUrl": "https://detail.1688.com/offer/100.html",
          "companyName": "CNC Optics"
        }]
      };
    </script>
    """
    dom_items = [
        {
            "title": "M48 to T2 telescope adapter duplicate",
            "price": "12.40",
            "detailUrl": "https://detail.1688.com/offer/100.html?spm=test",
        },
        {
            "title": "Bahtinov focus mask",
            "price": "8.80",
            "moq": 5,
            "detailUrl": "https://detail.1688.com/offer/101.html",
            "supplier": "Focus Parts",
        },
    ]

    listings = listings_from_browser_snapshot(
        html=html,
        dom_items=dom_items,
        source_url="https://s.1688.com/selloffer/offer_search.htm",
    )

    assert len(listings) == 2
    assert listings[0].unit_price_cny == Decimal("12.40")
    assert listings[0].supplier == "CNC Optics"
    assert listings[1].title == "Bahtinov focus mask"
    assert listings[1].moq == 5


def test_browser_snapshot_limits_merged_results():
    dom_items = [
        {
            "title": f"Telescope adapter {index}",
            "price": "10.00",
            "detailUrl": f"https://detail.1688.com/offer/{index}.html",
        }
        for index in range(5)
    ]

    listings = listings_from_browser_snapshot(
        html="<html></html>",
        dom_items=dom_items,
        source_url="https://s.1688.com/selloffer/offer_search.htm",
        limit=3,
    )

    assert len(listings) == 3
