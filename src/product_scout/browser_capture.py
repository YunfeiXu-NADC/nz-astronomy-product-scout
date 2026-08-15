from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .discovery import (
    DiscoverySourceError,
    parse_1688_html,
    parse_1688_json_payload,
)
from .models import SourceListing


DEFAULT_1688_URL = "https://www.1688.com/"


class BrowserCaptureError(DiscoverySourceError):
    pass


@dataclass(frozen=True)
class BrowserCaptureResult:
    source_url: str
    page_title: str
    captured_at: str
    listings: list[SourceListing]
    artifact_dir: Path
    evidence_json_path: Path
    screenshot_path: Path
    html_path: Path | None = None


def capture_1688_browser_page(
    *,
    url: str = DEFAULT_1688_URL,
    profile_dir: str | Path = ".local/1688-browser-profile",
    artifact_dir: str | Path,
    browser_channel: str | None = "msedge",
    limit: int = 100,
    wait_for_user: bool = True,
    headless: bool = False,
    save_html: bool = False,
    prompt: Callable[[str], str] = input,
    require_1688_host: bool = True,
) -> BrowserCaptureResult:
    """Capture a page after the user completes normal login and navigation."""

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise BrowserCaptureError(
            'Playwright is required. Install it with: pip install -e ".[browser]"'
        ) from exc

    profile_path = Path(profile_dir).resolve()
    capture_path = Path(artifact_dir).resolve()
    profile_path.mkdir(parents=True, exist_ok=True)
    capture_path.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {
                "headless": headless,
                "viewport": {"width": 1440, "height": 1000},
                "locale": "zh-CN",
            }
            if browser_channel:
                launch_options["channel"] = browser_channel
            try:
                context = playwright.chromium.launch_persistent_context(
                    str(profile_path),
                    **launch_options,
                )
            except PlaywrightError as exc:
                channel_hint = (
                    f" using browser channel '{browser_channel}'" if browser_channel else ""
                )
                raise BrowserCaptureError(
                    "Could not start the browser"
                    f"{channel_hint}. Install Microsoft Edge/Chrome or run "
                    "`playwright install chromium` and pass `--browser-channel chromium`."
                ) from exc

            try:
                return _capture_from_context(
                    context=context,
                    url=url,
                    capture_path=capture_path,
                    limit=limit,
                    wait_for_user=wait_for_user,
                    save_html=save_html,
                    prompt=prompt,
                    require_1688_host=require_1688_host,
                )
            finally:
                context.close()
    except BrowserCaptureError:
        raise
    except KeyboardInterrupt as exc:
        raise BrowserCaptureError("1688 browser capture was cancelled") from exc
    except Exception as exc:
        raise BrowserCaptureError(f"1688 browser capture failed: {exc}") from exc


def _capture_from_context(
    *,
    context: Any,
    url: str,
    capture_path: Path,
    limit: int,
    wait_for_user: bool,
    save_html: bool,
    prompt: Callable[[str], str],
    require_1688_host: bool,
) -> BrowserCaptureResult:
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    if wait_for_user:
        prompt(
            "Browser opened. Log in normally, navigate to a 1688 search or product "
            "page, then press Enter here to capture it..."
        )
        open_pages = [candidate for candidate in context.pages if not candidate.is_closed()]
        if open_pages:
            page = open_pages[-1]
    page.wait_for_timeout(1200)

    source_url = page.url
    if require_1688_host and not _is_1688_url(source_url):
        if (urlparse(source_url).hostname or "").lower() == "login.taobao.com":
            raise BrowserCaptureError(
                "1688 login is not complete. Finish the login in the browser, return to a "
                "1688 search or product page, and capture again."
            )
        raise BrowserCaptureError(f"The active page is not a 1688 page: {source_url}")

    page_title = page.title()
    html = page.content()
    dom_items = page.evaluate(_DOM_LISTING_SCRIPT)
    listings = listings_from_browser_snapshot(
        html=html,
        dom_items=dom_items,
        source_url=source_url,
        limit=limit,
    )

    captured_at = datetime.now(timezone.utc).isoformat()
    screenshot_path = capture_path / "source.png"
    evidence_json_path = capture_path / "capture.json"
    html_path = capture_path / "source.html" if save_html else None

    page.screenshot(path=str(screenshot_path), full_page=False)
    evidence_json_path.write_text(
        json.dumps(
            {
                "source": "1688_browser",
                "source_url": source_url,
                "page_title": page_title,
                "captured_at": captured_at,
                "browser_items": dom_items,
                "parsed_listings": [
                    listing.model_dump(mode="json") for listing in listings
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if html_path:
        html_path.write_text(html, encoding="utf-8")

    if not listings:
        raise BrowserCaptureError(
            "No parseable 1688 listings were found. Capture artifacts were saved to "
            f"{capture_path}. Open a search-results or product-detail page and retry."
        )

    return BrowserCaptureResult(
        source_url=source_url,
        page_title=page_title,
        captured_at=captured_at,
        listings=listings,
        artifact_dir=capture_path,
        evidence_json_path=evidence_json_path,
        screenshot_path=screenshot_path,
        html_path=html_path,
    )


def listings_from_browser_snapshot(
    *,
    html: str,
    dom_items: Any,
    source_url: str,
    limit: int = 100,
) -> list[SourceListing]:
    embedded = parse_1688_html(html, source_url=source_url, limit=limit)
    if "/offer/" not in urlparse(source_url).path:
        embedded = [listing for listing in embedded if listing.source_url != source_url]
    visible = parse_1688_json_payload(
        {"items": dom_items if isinstance(dom_items, list) else []},
        source_url=source_url,
        limit=limit,
    )
    return _merge_listings(embedded, visible, limit=limit)


def timestamped_capture_dir(root: str | Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = Path(root) / timestamp
    counter = 2
    while candidate.exists():
        candidate = Path(root) / f"{timestamp}-{counter}"
        counter += 1
    return candidate


def _merge_listings(
    primary: list[SourceListing], secondary: list[SourceListing], *, limit: int
) -> list[SourceListing]:
    merged: list[SourceListing] = []
    seen: set[str] = set()
    for listing in [*primary, *secondary]:
        key = _listing_key(listing)
        if key in seen:
            continue
        seen.add(key)
        merged.append(listing)
        if len(merged) >= limit:
            break
    return merged


def _listing_key(listing: SourceListing) -> str:
    parsed = urlparse(listing.source_url)
    normalized_url = f"{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
    return normalized_url or listing.title.lower().strip()


def _is_1688_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return hostname == "1688.com" or hostname.endswith(".1688.com")


_DOM_LISTING_SCRIPT = r"""
() => {
  const clean = (value) => (value || "").replace(/\s+/g, " ").trim();
  const number = (value) => {
    const match = clean(value).replace(/,/g, "").match(/\d+(?:\.\d+)?/);
    return match ? match[0] : null;
  };
  const leafTexts = (root) => Array.from(root.querySelectorAll("*"))
    .filter((element) => element.children.length === 0)
    .map((element) => clean(element.textContent))
    .filter(Boolean);
  const firstMatch = (segments, expressions) => {
    for (const segment of segments) {
      for (const expression of expressions) {
        const match = segment.match(expression);
        if (match) return match;
      }
    }
    return null;
  };
  const findCard = (anchor) => {
    let current = anchor;
    let best = anchor;
    for (let depth = 0; current && depth < 7; depth += 1, current = current.parentElement) {
      const text = clean(current.innerText || current.textContent);
      if (text.length > 20 && text.length < 2500) best = current;
      if (/(?:¥|￥|\bRMB\b|\d+(?:\.\d+)?\s*元)/i.test(text) && text.length > 40) {
        return current;
      }
    }
    return best;
  };
  const results = new Map();
  const anchors = Array.from(document.querySelectorAll([
    'a[href*="/offer/"]',
    '[data-href*="/offer/"]',
    '[data-url*="/offer/"]',
    '[data-offer-id]',
    '[data-offerid]',
  ].join(',')));
  for (const anchor of anchors) {
    let href;
    try {
      const offerId = anchor.getAttribute("data-offer-id") ||
        anchor.getAttribute("data-offerid");
      const rawHref = anchor.href || anchor.getAttribute("data-href") ||
        anchor.getAttribute("data-url") ||
        (offerId ? `https://detail.1688.com/offer/${offerId}.html` : "");
      const parsedHref = new URL(rawHref, location.href);
      if (!(parsedHref.hostname === "1688.com" || parsedHref.hostname.endsWith(".1688.com"))) {
        continue;
      }
      if (!/\/offer\/\d+/.test(parsedHref.pathname)) continue;
      href = parsedHref.href;
    } catch (_) {
      continue;
    }
    const canonical = href.split("?")[0];
    if (results.has(canonical)) continue;
    const card = findCard(anchor);
    const text = clean(card.innerText || card.textContent);
    const segments = leafTexts(card);
    const image = card.querySelector("img") || anchor.querySelector("img");
    const titleNode = card.querySelector('[title], [class*="title"], [class*="name"]');
    const title = clean(
      anchor.getAttribute("title") ||
      (titleNode && titleNode.getAttribute("title")) ||
      (titleNode && titleNode.textContent) ||
      (image && image.getAttribute("alt")) ||
      anchor.textContent
    );
    const priceMatch = firstMatch(segments, [
      /(?:¥|￥)\s*(\d+(?:\.\d+)?)/,
      /(\d+(?:\.\d+)?)\s*元/,
    ]) || text.match(/(?:¥|￥)\s*(\d+(?:\.\d{1,2})?)/) ||
      text.match(/(\d+(?:\.\d{1,2})?)\s*元/);
    if (!title || !priceMatch) continue;
    const moqMatch = firstMatch(segments, [
      /(\d+)\s*(?:件|个|套|只|支|盒|包)\s*(?:起|起批)/,
      /起批\s*(\d+)/,
    ]) || text.match(/(\d+)\s*(?:件|个|套|只|支|盒|包)\s*(?:起|起批)/) ||
      text.match(/起批\s*(\d+)/);
    const salesMatch = firstMatch(segments, [
      /(?:成交|已售|销量|付款)\s*([\d,.万+]+)/,
    ]) || text.match(/(?:成交|已售|销量|付款)\s*([\d,.万+]+)/);
    const supplierNode = card.querySelector(
      '[class*="company"], [class*="supplier"], [class*="shop"], [class*="seller"]'
    );
    results.set(canonical, {
      title,
      price: number(priceMatch[1]),
      moq: moqMatch ? parseInt(moqMatch[1], 10) : 1,
      detailUrl: canonical,
      supplier: clean(supplierNode && supplierNode.textContent) || "Unknown supplier",
      saleQuantity: salesMatch ? salesMatch[1] : null,
      imageUrl: image && (image.currentSrc || image.src) || null,
    });
  }

  if (results.size === 0 && /\/offer\/\d+/.test(location.pathname)) {
    const text = clean(document.body.innerText);
    const segments = leafTexts(document.body);
    const heading = document.querySelector('h1, [class*="title"], meta[property="og:title"]');
    const title = clean(
      (heading && (heading.content || heading.getAttribute("content") || heading.textContent)) ||
      document.title
    );
    const priceMatch = firstMatch(segments, [
      /(?:¥|￥)\s*(\d+(?:\.\d+)?)/,
      /(\d+(?:\.\d+)?)\s*元/,
    ]) || text.match(/(?:¥|￥)\s*(\d+(?:\.\d{1,2})?)/) ||
      text.match(/(\d+(?:\.\d{1,2})?)\s*元/);
    const moqMatch = firstMatch(segments, [
      /(\d+)\s*(?:件|个|套|只|支|盒|包)\s*(?:起|起批)/,
      /起批\s*(\d+)/,
    ]) || text.match(/(\d+)\s*(?:件|个|套|只|支|盒|包)\s*(?:起|起批)/) ||
      text.match(/起批\s*(\d+)/);
    const image = document.querySelector('meta[property="og:image"], img');
    if (title && priceMatch) {
      results.set(location.href.split("?")[0], {
        title,
        price: number(priceMatch[1]),
        moq: moqMatch ? parseInt(moqMatch[1], 10) : 1,
        detailUrl: location.href.split("?")[0],
        supplier: "Unknown supplier",
        imageUrl: image && (image.content || image.currentSrc || image.src) || null,
      });
    }
  }
  return Array.from(results.values());
}
"""
