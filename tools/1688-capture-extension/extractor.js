function extract1688Capture() {
  const clean = (value) => (value || "").replace(/\s+/g, " ").trim();
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
  const findCard = (element) => {
    let current = element;
    let best = element;
    for (let depth = 0; current && depth < 8; depth += 1, current = current.parentElement) {
      const text = clean(current.innerText || current.textContent);
      if (text.length > 20 && text.length < 2500) best = current;
      if (/(?:¥|￥|\d+(?:\.\d+)?\s*元)/.test(text) && text.length > 40) {
        return current;
      }
    }
    return best;
  };
  const resolveOfferUrl = (element) => {
    const offerId = element.getAttribute("data-offer-id") ||
      element.getAttribute("data-offerid");
    const rawUrl = element.href || element.getAttribute("data-href") ||
      element.getAttribute("data-url") ||
      (offerId ? `https://detail.1688.com/offer/${offerId}.html` : "");
    if (!rawUrl) return null;
    try {
      const parsed = new URL(rawUrl, location.href);
      const is1688 = parsed.hostname === "1688.com" || parsed.hostname.endsWith(".1688.com");
      if (!is1688 || !/\/offer\/\d+/.test(parsed.pathname)) return null;
      return parsed.href.split("?")[0];
    } catch (_) {
      return null;
    }
  };
  const extractItem = (element, sourceUrl) => {
    const card = findCard(element);
    const text = clean(card.innerText || card.textContent);
    const segments = leafTexts(card);
    const image = card.querySelector("img") || element.querySelector("img");
    const titleNode = card.querySelector('[title], [class*="title"], [class*="name"]');
    const title = clean(
      element.getAttribute("title") ||
      (titleNode && titleNode.getAttribute("title")) ||
      (titleNode && titleNode.textContent) ||
      (image && image.getAttribute("alt")) ||
      element.textContent
    );
    const priceMatch = firstMatch(segments, [
      /(?:¥|￥)\s*(\d+(?:\.\d+)?)/,
      /(\d+(?:\.\d+)?)\s*元/,
    ]) || text.match(/(?:¥|￥)\s*(\d+(?:\.\d{1,2})?)/) ||
      text.match(/(\d+(?:\.\d{1,2})?)\s*元/);
    if (!title || !priceMatch) return null;
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
    return {
      title,
      price: priceMatch[1],
      moq: moqMatch ? parseInt(moqMatch[1], 10) : 1,
      detailUrl: sourceUrl,
      supplier: clean(supplierNode && supplierNode.textContent) || "Unknown supplier",
      saleQuantity: salesMatch ? salesMatch[1] : null,
      imageUrl: image && (image.currentSrc || image.src) || null,
    };
  };

  const candidates = Array.from(document.querySelectorAll([
    'a[href*="/offer/"]',
    '[data-href*="/offer/"]',
    '[data-url*="/offer/"]',
    '[data-offer-id]',
    '[data-offerid]',
  ].join(',')));
  const items = new Map();
  for (const candidate of candidates) {
    const sourceUrl = resolveOfferUrl(candidate);
    if (!sourceUrl || items.has(sourceUrl)) continue;
    const item = extractItem(candidate, sourceUrl);
    if (item) items.set(sourceUrl, item);
  }

  if (items.size === 0 && /\/offer\/\d+/.test(location.pathname)) {
    const item = extractItem(document.body, location.href.split("?")[0]);
    if (item) items.set(item.detailUrl, item);
  }

  return {
    source: "1688_chrome_extension",
    source_url: location.href,
    page_title: document.title,
    captured_at: new Date().toISOString(),
    items: Array.from(items.values()),
  };
}
