function extractTradeMeCapture() {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visible = (element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  };
  const pricesFromText = (text) => {
    const prices = [];
    const expression = /(?:NZ\s*)?\$\s*([\d,]+(?:\.\d{1,2})?)/gi;
    for (const match of clean(text).matchAll(expression)) {
      const price = Number(match[1].replace(/,/g, ""));
      if (Number.isFinite(price) && price >= 0 && price < 10000000) prices.push(price);
    }
    return prices;
  };
  const parseResultCount = (text) => {
    const patterns = [
      /showing\s+[\d,]+\s*(?:-|to)\s*[\d,]+\s+of\s+([\d,]+)\s+(?:results?|listings?)/i,
      /([\d,]+)\s+(?:results?|listings?)\b/i,
    ];
    for (const pattern of patterns) {
      const match = clean(text).match(pattern);
      if (match) return Number(match[1].replace(/,/g, ""));
    }
    return 0;
  };
  const parseBidCount = (text) => {
    const match = clean(text).match(/([\d,]+)\s*bids?/i);
    return match ? Number(match[1].replace(/,/g, "")) : 0;
  };
  const listingUrl = (anchor) => {
    try {
      const url = new URL(anchor.href, location.href);
      return /\/listing\/\d+(?:\/|$)/i.test(url.pathname) ? `${url.origin}${url.pathname}` : null;
    } catch (_) {
      return null;
    }
  };
  const findCard = (anchor, url) => {
    let current = anchor;
    let best = anchor;
    for (let depth = 0; current && depth < 9; depth += 1, current = current.parentElement) {
      const text = clean(current.innerText || current.textContent);
      if (text.length < 20 || text.length > 3000) continue;
      const urls = new Set(
        Array.from(current.querySelectorAll('a[href*="/listing/"]'))
          .map(listingUrl)
          .filter(Boolean)
      );
      if (urls.has(url) && pricesFromText(text).length) best = current;
      if (urls.size === 1 && urls.has(url) && pricesFromText(text).length) return current;
    }
    return best;
  };
  const sellerFromCard = (card, text) => {
    const node = card.querySelector([
      '[data-testid*="seller"]',
      '[class*="seller"]',
      '[class*="member"]',
      '[class*="store-name"]',
    ].join(","));
    if (node) return clean(node.textContent);
    const match = text.match(/(?:listed\s+by|seller|member)\s*:?\s*([^|\n]{2,80})/i);
    return match ? clean(match[1]) : "";
  };
  const titleFromCard = (anchor, card) => {
    const labelled = anchor.getAttribute("aria-label") || anchor.getAttribute("title");
    const heading = card.querySelector("h2, h3, h4, [data-testid*='title'], [class*='title']");
    const image = anchor.querySelector("img") || card.querySelector("img");
    return clean(labelled || heading?.textContent || image?.alt || anchor.textContent);
  };

  const pageText = clean(document.body?.innerText || "");
  const anchors = Array.from(document.querySelectorAll('a[href*="/listing/"]')).filter(visible);
  const items = new Map();
  for (const anchor of anchors) {
    const url = listingUrl(anchor);
    if (!url || items.has(url)) continue;
    const card = findCard(anchor, url);
    const text = clean(card.innerText || card.textContent);
    const prices = pricesFromText(text);
    if (!prices.length) continue;
    const title = titleFromCard(anchor, card);
    if (!title) continue;
    const seller = sellerFromCard(card, text);
    items.set(url, {
      id: url.match(/\/listing\/(\d+)/i)?.[1] || url,
      title,
      price: prices[0],
      url,
      seller,
      buyNow: /buy\s*now/i.test(text),
      bidCount: parseBidCount(text),
      freeShipping: /free\s*(?:shipping|delivery)/i.test(text),
      inTrade: /in\s*trade/i.test(text),
    });
  }

  const url = new URL(location.href);
  const queryKeys = ["search_string", "searchString", "query", "keyword", "q"];
  let searchQuery = "";
  for (const key of queryKeys) {
    if (url.searchParams.get(key)) {
      searchQuery = clean(url.searchParams.get(key));
      break;
    }
  }
  if (!searchQuery) {
    const heading = Array.from(document.querySelectorAll("h1"))
      .filter(visible)
      .map((element) => clean(element.textContent))
      .find((text) => text && text.length <= 160);
    searchQuery = heading || clean(document.title.split("|")[0]).slice(0, 160);
  }

  const fallbackPrices = items.size ? [] : pricesFromText(pageText).slice(0, 100);
  const sampledCount = items.size || fallbackPrices.length;
  const activeListingCount = Math.max(parseResultCount(pageText), sampledCount);
  return {
    source: "trademe_chrome_extension",
    source_url: location.href,
    page_title: document.title,
    captured_at: new Date().toISOString(),
    search_query: searchQuery,
    active_listing_count: activeListingCount,
    items: Array.from(items.values()),
    fallback: {
      prices: fallbackPrices,
      buy_now_listing_count: Math.min((pageText.match(/buy\s*now/gi) || []).length, sampledCount),
      bid_listing_count: Math.min((pageText.match(/[\d,]+\s*bids?/gi) || []).length, sampledCount),
      total_bid_count: Array.from(pageText.matchAll(/([\d,]+)\s*bids?/gi))
        .reduce((sum, match) => sum + Number(match[1].replace(/,/g, "")), 0),
      free_shipping_listing_count: Math.min((pageText.match(/free\s*(?:shipping|delivery)/gi) || []).length, sampledCount),
    },
    diagnostics: {
      listing_anchors: anchors.length,
      listing_cards: items.size,
      fallback_prices: fallbackPrices.length,
    },
  };
}
