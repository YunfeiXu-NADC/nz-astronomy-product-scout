const state = {
  language: localStorage.getItem("product-scout-language") || "zh",
  overview: null,
  market: { summaries: [], metrics: [] },
  trademe: { snapshots: [], summary: {}, policy: {} },
  opportunities: { items: [], source: "none" },
  targets: null,
  tradeMePrices: [],
};

const translations = {
  zh: {
    refresh: "刷新市场数据",
    overview: "总览",
    market: "市场需求",
    trademe: "Trade Me 验证",
    opportunities: "候选机会",
    inventory: "库存测试",
    loading: "正在加载研究数据…",
    executiveConclusion: "总体结论",
    marketShape: "市场结构",
    viewDetails: "查看明细",
    marketDemand: "市场需求分析",
    marketSubtitle: "按需求簇去重，避免把同义词搜索量重复相加。",
    keyword: "关键词",
    segment: "领域",
    monthlySearches: "月搜索量",
    trend12m: "12个月趋势",
    competition: "竞争指数",
    bidRange: "Bid 区间",
    trademeValidation: "Trade Me 市场验证",
    trademeSubtitle: "记录人工观察的活跃商品样本；不抓取，也不把下架直接视为成交。",
    manualEvidence: "仅限人工证据",
    recordObservation: "记录市场观察",
    reset: "重置",
    saveSnapshot: "保存快照",
    marketplaceRead: "平台证据结论",
    snapshotHistory: "快照历史",
    candidateOpportunities: "候选商品机会",
    provisional: "当前数据为初步结果，重量、兼容性与样品仍需验证。",
    minConfidence: "最低置信度",
    product: "商品 / SKU",
    score: "综合得分",
    confidence: "置信度",
    contribution: "单单贡献",
    margin: "贡献率",
    status: "状态",
    inventoryRisk: "库存风险计算",
    inventorySubtitle: "按落地成本和计划数量检查首批库存，不使用零售价估算风险。",
    plannedCommitments: "计划采购",
    addSku: "添加 SKU",
    landedUnitCost: "单件落地成本",
    units: "数量",
    calculateRisk: "计算库存风险",
  },
  en: {
    refresh: "Refresh market data",
    overview: "Overview",
    market: "Market demand",
    trademe: "Trade Me validation",
    opportunities: "Opportunities",
    inventory: "Inventory test",
    loading: "Loading research data…",
    executiveConclusion: "Executive conclusion",
    marketShape: "Market structure",
    viewDetails: "View details",
    marketDemand: "Market demand analysis",
    marketSubtitle: "Intent clusters prevent close synonyms from being added together.",
    keyword: "Keyword",
    segment: "Segment",
    monthlySearches: "Monthly searches",
    trend12m: "12-month trend",
    competition: "Competition",
    bidRange: "Bid range",
    trademeValidation: "Trade Me market validation",
    trademeSubtitle: "Record manually observed active listings; no scraping and no assumption that removed listings were sold.",
    manualEvidence: "Manual evidence only",
    recordObservation: "Record market observation",
    reset: "Reset",
    saveSnapshot: "Save snapshot",
    marketplaceRead: "Marketplace evidence read",
    snapshotHistory: "Snapshot history",
    candidateOpportunities: "Candidate opportunities",
    provisional: "Results are provisional; weight, compatibility, and samples still require verification.",
    minConfidence: "Min confidence",
    product: "Product / SKU",
    score: "Score",
    confidence: "Confidence",
    contribution: "Contribution",
    margin: "Margin",
    status: "Status",
    inventoryRisk: "Inventory risk",
    inventorySubtitle: "Check initial inventory using landed costs and planned units, not retail value.",
    plannedCommitments: "Planned commitments",
    addSku: "Add SKU",
    landedUnitCost: "Landed unit cost",
    units: "Units",
    calculateRisk: "Calculate risk",
  },
};

document.addEventListener("DOMContentLoaded", () => {
  bindNavigation();
  bindLanguage();
  bindFilters();
  bindInventory();
  bindTradeMe();
  applyLanguage();
  loadDashboard();
});

async function loadDashboard() {
  setLoading(true);
  try {
    const [overview, market, trademe, opportunities, targets] = await Promise.all([
      fetchJson("/dashboard/overview"),
      fetchJson("/dashboard/market"),
      fetchJson("/dashboard/trademe"),
      fetchJson("/dashboard/opportunities"),
      fetchJson("/business/targets"),
    ]);
    state.overview = overview;
    state.market = market;
    state.trademe = trademe;
    state.opportunities = opportunities;
    state.targets = targets;
    renderAll();
    document.querySelector("#data-state").textContent = "Live data · 已连接";
  } catch (error) {
    document.querySelector("#data-state").textContent = "Data error · 数据错误";
    showToast(error.message, true);
  } finally {
    setLoading(false);
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `${response.status} ${response.statusText}`);
  }
  return data;
}

function renderAll() {
  renderReport();
  renderTargets();
  renderSegmentOverview();
  renderMarketBars();
  populateSegmentFilter();
  renderKeywordTable();
  renderTradeMe();
  renderOpportunityTable();
  renderInventoryDefaults();
  refreshIcons();
}

function renderReport() {
  if (!state.overview) return;
  const report = state.overview.report;
  document.querySelector("#decision-copy").innerHTML = bilingual(report.decision);
  document.querySelector("#positioning-copy").innerHTML = bilingual(report.positioning);
  document.querySelector("#finding-list").innerHTML = report.findings
    .map((item, index) => `<div class="finding" data-index="${index + 1}">${bilingual(item)}</div>`)
    .join("");
  document.querySelector("#next-list").innerHTML = report.next_steps
    .map((item) => `<li>${escapeHtml(item.zh)}<span>${escapeHtml(item.en)}</span></li>`)
    .join("");
  const updated = state.market.updated_at ? new Date(state.market.updated_at) : null;
  document.querySelector("#overview-updated").textContent = updated
    ? `Google Ads · ${updated.toLocaleString()}`
    : "Google Ads · no timestamp";
}

function renderTargets() {
  if (!state.targets) return;
  const items = [
    ["月贡献利润 / Monthly contribution", money(state.targets.monthly_contribution_profit_nzd), "目标 / target"],
    ["每单贡献 / Per order", `≥ ${money(state.targets.min_contribution_profit_per_order_nzd)}`, "硬门槛 / hard gate"],
    ["月订单量 / Monthly orders", number(state.targets.required_monthly_orders), `${state.targets.required_daily_orders} / day`],
    ["首批库存风险 / Initial inventory", `≤ ${money(state.targets.max_initial_inventory_risk_nzd)}`, `${state.targets.min_sku_test_days}–${state.targets.max_sku_test_days} days / SKU`],
  ];
  document.querySelector("#kpi-strip").innerHTML = items
    .map(([label, value, note]) => `<div class="kpi"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`)
    .join("");
}

function renderSegmentOverview() {
  const summaries = state.market.summaries || [];
  document.querySelector("#segment-overview").innerHTML = summaries
    .map((item) => {
      const statusClass = statusClassName(item.status);
      return `<article class="segment-item ${statusClass}">
        <span class="status-chip ${statusClass}">${escapeHtml(item.status)}</span>
        <strong>${number(item.conservative_demand_index)}</strong>
        <span>${escapeHtml(primarySegmentLabel(item))}</span>
        <small>${escapeHtml(secondarySegmentLabel(item))}</small>
      </article>`;
    })
    .join("");
}

function renderMarketBars() {
  const summaries = state.market.summaries || [];
  const max = Math.max(...summaries.map((item) => toNumber(item.conservative_demand_index)), 1);
  document.querySelector("#market-bars").innerHTML = summaries
    .map((item) => {
      const value = toNumber(item.conservative_demand_index);
      const width = Math.max(1, (value / max) * 100);
      const statusClass = statusClassName(item.status);
      return `<div class="market-bar-row ${statusClass}">
        <div class="market-bar-label"><strong>${escapeHtml(primarySegmentLabel(item))}</strong><small>${escapeHtml(secondarySegmentLabel(item))}</small></div>
        <div class="bar-track" title="Conservative demand index: ${value}"><span style="width:${width}%"></span></div>
        <div class="bar-value">${number(value)}</div>
        <span class="status-chip ${statusClass}">${escapeHtml(item.status)}</span>
      </div>`;
    })
    .join("");
}

function populateSegmentFilter() {
  const select = document.querySelector("#keyword-segment");
  const current = select.value;
  const options = [`<option value="">${state.language === "zh" ? "全部领域" : "All segments"}</option>`]
    .concat(
      (state.market.summaries || []).map(
        (item) => `<option value="${escapeAttr(item.segment)}">${escapeHtml(primarySegmentLabel(item))}</option>`,
      ),
    );
  select.innerHTML = options.join("");
  select.value = current;
}

function renderKeywordTable() {
  const query = document.querySelector("#keyword-search").value.trim().toLowerCase();
  const segment = document.querySelector("#keyword-segment").value;
  const rows = (state.market.metrics || [])
    .filter((item) => !segment || item.segment === segment)
    .filter((item) => !query || `${item.keyword} ${item.intent_cluster}`.toLowerCase().includes(query))
    .sort((a, b) => toNumber(b.monthly_searches) - toNumber(a.monthly_searches));
  document.querySelector("#keyword-count").textContent = `${rows.length} ${state.language === "zh" ? "个关键词" : "keywords"}`;
  document.querySelector("#keyword-table").innerHTML = rows.length
    ? rows.map((item) => {
      const summary = (state.market.summaries || []).find((entry) => entry.segment === item.segment) || {};
      const bid = item.bid_low && item.bid_high ? `${money(item.bid_low)}–${money(item.bid_high)}` : "—";
      return `<tr>
        <td><span class="keyword-primary">${escapeHtml(item.keyword)}</span><span class="product-secondary">${escapeHtml(item.intent_cluster)}</span></td>
        <td>${escapeHtml(primarySegmentLabel(summary))}</td>
        <td class="numeric"><strong>${number(item.monthly_searches)}</strong></td>
        <td>${sparkline(item.monthly_history)}</td>
        <td class="numeric">${item.competition_index || "—"}</td>
        <td class="numeric">${bid}</td>
      </tr>`;
    }).join("")
    : emptyRow(6);
}

function renderOpportunityTable() {
  const query = document.querySelector("#opportunity-search").value.trim().toLowerCase();
  const status = document.querySelector("#status-filter").value;
  const minConfidence = toNumber(document.querySelector("#confidence-filter").value);
  document.querySelector("#confidence-output").textContent = String(minConfidence);
  const rows = (state.opportunities.items || [])
    .filter((item) => !status || item.status === status)
    .filter((item) => toNumber(item.confidence) >= minConfidence)
    .filter((item) => !query || `${item.sku || ""} ${item.product_name || ""}`.toLowerCase().includes(query));
  document.querySelector("#opportunity-count").textContent = `${rows.length} ${state.language === "zh" ? "个候选" : "candidates"}`;
  document.querySelector("#opportunity-source").textContent = state.language === "zh"
    ? `数据源：${state.opportunities.source || "none"}`
    : `Source: ${state.opportunities.source || "none"}`;
  document.querySelector("#opportunity-table").innerHTML = rows.length
    ? rows.map((item, index) => {
      const itemStatus = item.status || "CANDIDATE";
      return `<tr>
        <td>${item.rank || index + 1}</td>
        <td><span class="product-primary">${escapeHtml(item.sku || "—")}</span><span class="product-secondary" title="${escapeAttr(item.product_name || "")}">${escapeHtml(item.product_name || "")}</span></td>
        <td class="numeric"><strong>${formatDecimal(item.prelaunch_score)}</strong></td>
        <td class="numeric">${number(item.confidence)}</td>
        <td class="numeric">${item.contribution_profit_nzd ? money(item.contribution_profit_nzd) : "—"}</td>
        <td class="numeric">${item.contribution_margin ? percent(item.contribution_margin) : "—"}</td>
        <td><span class="status-chip ${statusClassName(itemStatus)}">${escapeHtml(itemStatus)}</span></td>
      </tr>`;
    }).join("")
    : emptyRow(7);
}

function bindTradeMe() {
  const form = document.querySelector("#trademe-form");
  form.addEventListener("submit", saveTradeMeSnapshot);
  form.addEventListener("reset", () => setTimeout(resetTradeMeCapture, 0));
  document.querySelector("#paste-trademe-page").addEventListener("click", pasteAndAnalyzeTradeMe);
  document.querySelector("#analyze-trademe-page").addEventListener("click", analyzeTradeMePageText);
  document.querySelector('[name="source_url"]').addEventListener("input", inferTradeMeContextFromUrl);
  document.querySelector("#trademe-search").addEventListener("input", renderTradeMeTable);
  document.querySelector("#trademe-cluster-filter").addEventListener("input", renderTradeMeTable);
  setTradeMeDateDefault();
}

async function saveTradeMeSnapshot(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!state.tradeMePrices.length && document.querySelector("#trademe-page-paste").value.trim()) {
    analyzeTradeMePageText();
  }
  const button = document.querySelector("#save-trademe-snapshot");
  const payload = Object.fromEntries(new FormData(form).entries());
  [
    "active_listing_count",
    "sampled_listing_count",
    "unique_seller_count",
    "buy_now_listing_count",
    "bid_listing_count",
    "total_bid_count",
    "in_trade_seller_count",
    "free_shipping_listing_count",
  ].forEach((field) => { payload[field] = Number(payload[field]); });
  ["min_price_nzd", "median_price_nzd", "max_price_nzd"].forEach((field) => {
    payload[field] = payload[field] === "" ? null : payload[field];
  });
  button.disabled = true;
  try {
    await fetchJson("/dashboard/trademe/snapshots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.trademe = await fetchJson("/dashboard/trademe");
    renderTradeMe();
    form.reset();
    resetTradeMeCapture();
    showToast(state.language === "zh" ? "Trade Me 快照已保存" : "Trade Me snapshot saved");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    refreshIcons();
  }
}

async function pasteAndAnalyzeTradeMe() {
  try {
    const text = await navigator.clipboard.readText();
    if (!text.trim()) throw new Error(state.language === "zh" ? "剪贴板中没有文本" : "Clipboard has no text");
    document.querySelector("#trademe-page-paste").value = text;
    analyzeTradeMePageText();
  } catch (error) {
    document.querySelector("#trademe-page-paste").focus();
    showToast(error.message || (state.language === "zh" ? "无法读取剪贴板，请直接粘贴" : "Clipboard unavailable; paste directly"), true);
  }
}

function analyzeTradeMePageText() {
  const text = document.querySelector("#trademe-page-paste").value;
  const signals = extractTradeMeSignals(text);
  state.tradeMePrices = signals.prices;
  applyTradeMeSignals(signals);
  renderTradeMePriceChips();
}

function extractTradeMeSignals(text) {
  const prices = [...String(text).matchAll(/(?:NZ\s*)?\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)/gi)]
    .map((match) => Number(match[1].replaceAll(",", "")))
    .filter((value) => Number.isFinite(value) && value >= 0.01 && value <= 100000);
  const resultPatterns = [
    /showing\s+[\d,]+\s*(?:-|–|to)\s*[\d,]+\s+of\s+([\d,]+)\+?/i,
    /([\d,]+)\+?\s+(?:results|listings)\b/i,
  ];
  let activeListings = null;
  for (const pattern of resultPatterns) {
    const match = String(text).match(pattern);
    if (match) {
      activeListings = Number(match[1].replaceAll(",", ""));
      break;
    }
  }
  const bidCounts = [...String(text).matchAll(/\b(\d+)\s+bids?\b/gi)].map((match) => Number(match[1]));
  return {
    prices,
    activeListings,
    bidListingCount: bidCounts.length,
    totalBidCount: bidCounts.reduce((total, value) => total + value, 0),
    buyNowCount: (String(text).match(/\bbuy now\b/gi) || []).length,
    freeShippingCount: (String(text).match(/\bfree shipping\b/gi) || []).length,
  };
}

function applyTradeMeSignals(signals) {
  const sample = signals.prices.length;
  const activeField = document.querySelector('[name="active_listing_count"]');
  const active = signals.activeListings == null ? Math.max(toNumber(activeField.value), sample) : signals.activeListings;
  activeField.value = String(active);
  document.querySelector('[name="sampled_listing_count"]').value = String(sample);
  document.querySelector('[name="buy_now_listing_count"]').value = String(Math.min(sample, signals.buyNowCount));
  document.querySelector('[name="bid_listing_count"]').value = String(Math.min(sample, signals.bidListingCount));
  document.querySelector('[name="total_bid_count"]').value = String(signals.totalBidCount);
  document.querySelector('[name="free_shipping_listing_count"]').value = String(Math.min(sample, signals.freeShippingCount));
  updateTradeMePriceFields();
  const extraction = document.querySelector("#trademe-extraction");
  if (!sample) {
    extraction.innerHTML = `<span class="status-chip low">${state.language === "zh" ? "没有识别到价格" : "No prices detected"}</span>`;
    return;
  }
  extraction.innerHTML = `
    <strong>${number(sample)} ${state.language === "zh" ? "个价格" : "prices"}</strong>
    <span>${state.language === "zh" ? "中位价" : "Median"} ${money(medianValue(state.tradeMePrices))}</span>
    <span>${number(Math.min(sample, signals.bidListingCount))} ${state.language === "zh" ? "个有竞价" : "with bids"}</span>`;
}

function renderTradeMePriceChips() {
  const container = document.querySelector("#trademe-price-chips");
  container.innerHTML = state.tradeMePrices.map((value, index) => `
    <button type="button" class="price-chip" data-price-index="${index}" title="Remove detected price / 删除误识别价格">
      ${money(value)}<i data-lucide="x"></i>
    </button>`).join("");
  container.querySelectorAll(".price-chip").forEach((button) => {
    button.addEventListener("click", () => {
      state.tradeMePrices.splice(Number(button.dataset.priceIndex), 1);
      document.querySelector('[name="sampled_listing_count"]').value = String(state.tradeMePrices.length);
      clampTradeMeSampleCounts();
      updateTradeMePriceFields();
      renderTradeMePriceChips();
      const extraction = document.querySelector("#trademe-extraction");
      extraction.innerHTML = state.tradeMePrices.length
        ? `<strong>${number(state.tradeMePrices.length)} ${state.language === "zh" ? "个价格" : "prices"}</strong><span>${state.language === "zh" ? "中位价" : "Median"} ${money(medianValue(state.tradeMePrices))}</span>`
        : `<span class="status-chip low">${state.language === "zh" ? "没有保留价格" : "No prices retained"}</span>`;
    });
  });
  refreshIcons();
}

function clampTradeMeSampleCounts() {
  const sample = state.tradeMePrices.length;
  ["buy_now_listing_count", "bid_listing_count", "free_shipping_listing_count"].forEach((name) => {
    const field = document.querySelector(`[name="${name}"]`);
    field.value = String(Math.min(sample, toNumber(field.value)));
  });
}

function updateTradeMePriceFields() {
  const sorted = [...state.tradeMePrices].sort((a, b) => a - b);
  const values = sorted.length ? [sorted[0], medianValue(sorted), sorted[sorted.length - 1]] : ["", "", ""];
  ["min_price_nzd", "median_price_nzd", "max_price_nzd"].forEach((name, index) => {
    document.querySelector(`[name="${name}"]`).value = values[index] === "" ? "" : Number(values[index]).toFixed(2);
  });
}

function inferTradeMeContextFromUrl(event) {
  try {
    const url = new URL(event.currentTarget.value);
    const query = url.searchParams.get("search_string") || url.searchParams.get("searchString") || url.searchParams.get("q");
    const queryField = document.querySelector('[name="search_query"]');
    if (query && !queryField.value.trim()) {
      queryField.value = query.replaceAll("+", " ").trim();
      document.querySelector('[name="query_cluster"]').value = inferTradeMeCluster(queryField.value);
    }
  } catch (_) {
    // Native URL validation will report malformed input on submit.
  }
}

function inferTradeMeCluster(query) {
  const clean = query.toLowerCase();
  if (/matariki/.test(clean)) return "matariki";
  if (/gift|lamp|projector|star map|poster/.test(clean)) return "astronomy_gifts";
  if (/stem|education|solar system|model/.test(clean)) return "education_stem";
  if (/astrophoto|camera/.test(clean)) return "astrophotography";
  if (/adapter|eyepiece|filter|mask|mount|tripod|accessor/.test(clean)) return "compatibility_accessories";
  return "beginner_telescope";
}

function medianValue(values) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function resetTradeMeCapture() {
  state.tradeMePrices = [];
  document.querySelector("#trademe-page-paste").value = "";
  document.querySelector("#trademe-extraction").innerHTML = "";
  document.querySelector("#trademe-price-chips").innerHTML = "";
  document.querySelector(".advanced-evidence").open = false;
  setTradeMeDateDefault();
}

function renderTradeMe() {
  const summary = state.trademe.summary || {};
  const summaryItems = [
    [state.language === "zh" ? "快照数" : "Snapshots", number(summary.snapshot_count)],
    [state.language === "zh" ? "已覆盖机会簇" : "Clusters covered", number(summary.cluster_count)],
    [state.language === "zh" ? "每簇活跃商品中位数" : "Median active / cluster", number(summary.median_active_listings_per_cluster)],
    [state.language === "zh" ? "平均竞价商品占比" : "Average bid-active share", percent(summary.average_bid_listing_share)],
  ];
  document.querySelector("#trademe-summary").innerHTML = summaryItems
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${value}</strong></div>`)
    .join("");
  document.querySelector("#trademe-conclusion").innerHTML = bilingual(summary.conclusion || { zh: "—", en: "—" });
  const policy = state.trademe.policy || {};
  document.querySelector("#trademe-policy").innerHTML = `${escapeHtml(policy.zh || "")}<span>${escapeHtml(policy.en || "")}</span>`;
  renderTradeMeTable();
}

function renderTradeMeTable() {
  const query = document.querySelector("#trademe-search").value.trim().toLowerCase();
  const cluster = document.querySelector("#trademe-cluster-filter").value;
  const rows = (state.trademe.snapshots || [])
    .filter((item) => !cluster || item.query_cluster === cluster)
    .filter((item) => !query || `${item.search_query} ${item.query_cluster} ${item.notes}`.toLowerCase().includes(query));
  document.querySelector("#trademe-count").textContent = `${rows.length} ${state.language === "zh" ? "条快照" : "snapshots"}`;
  document.querySelector("#trademe-table").innerHTML = rows.length
    ? rows.map((item) => `<tr>
        <td>${escapeHtml(item.observed_at)}</td>
        <td><span class="product-primary">${escapeHtml(item.search_query)}</span><span class="product-secondary">${escapeHtml(tradeMeClusterLabel(item.query_cluster))}</span></td>
        <td class="numeric">${number(item.active_listing_count)}</td>
        <td class="numeric">${number(item.sampled_listing_count)}</td>
        <td class="numeric">${number(item.unique_seller_count)}</td>
        <td class="numeric">${item.median_price_nzd == null ? "—" : money(item.median_price_nzd)}</td>
        <td class="numeric">${percent(item.bid_listing_share)}</td>
        <td><span class="status-chip ${statusClassName(item.confidence_label)}">${escapeHtml(item.confidence_label)} · ${number(item.confidence)}</span></td>
        <td class="snapshot-actions">
          <a class="icon-button" href="${escapeAttr(item.source_url)}" target="_blank" rel="noreferrer" title="Open Trade Me source / 打开来源"><i data-lucide="external-link"></i></a>
          <button class="icon-button delete-snapshot" type="button" data-snapshot-id="${escapeAttr(item.id)}" title="Delete snapshot / 删除快照"><i data-lucide="trash-2"></i></button>
        </td>
      </tr>`).join("")
    : emptyRow(9);
  document.querySelectorAll(".delete-snapshot").forEach((button) => {
    button.addEventListener("click", () => deleteTradeMeSnapshot(button.dataset.snapshotId));
  });
  refreshIcons();
}

async function deleteTradeMeSnapshot(snapshotId) {
  const message = state.language === "zh" ? "删除这条 Trade Me 快照？" : "Delete this Trade Me snapshot?";
  if (!window.confirm(message)) return;
  try {
    await fetchJson(`/dashboard/trademe/snapshots/${encodeURIComponent(snapshotId)}`, { method: "DELETE" });
    state.trademe = await fetchJson("/dashboard/trademe");
    renderTradeMe();
    showToast(state.language === "zh" ? "快照已删除" : "Snapshot deleted");
  } catch (error) {
    showToast(error.message, true);
  }
}

function setTradeMeDateDefault() {
  const field = document.querySelector("#trademe-observed-at");
  const today = localIsoDate(new Date());
  field.max = today;
  if (!field.value) field.value = today;
}

function tradeMeClusterLabel(value) {
  const labels = {
    beginner_telescope: "Beginner telescope / 入门望远镜",
    astrophotography: "Astrophotography / 天文摄影",
    compatibility_accessories: "Compatibility accessories / 兼容配件",
    astronomy_gifts: "Astronomy gifts / 天文礼品",
    education_stem: "Education & STEM / 教育",
    matariki: "Matariki",
    other: "Other / 其他",
  };
  return labels[value] || value;
}

function localIsoDate(value) {
  const offset = value.getTimezoneOffset() * 60000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 10);
}

function bindNavigation() {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
  document.querySelectorAll("[data-goto]").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.goto));
  });
  document.querySelector("#refresh-market").addEventListener("click", refreshMarket);
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item.dataset.tab === name));
  document.querySelectorAll(".view").forEach((item) => item.classList.toggle("active", item.id === `view-${name}`));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function bindLanguage() {
  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.addEventListener("click", () => {
      state.language = button.dataset.lang;
      localStorage.setItem("product-scout-language", state.language);
      applyLanguage();
      if (state.overview) renderAll();
    });
  });
}

function applyLanguage() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-lang]").forEach((button) => button.classList.toggle("active", button.dataset.lang === state.language));
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    if (translations[state.language][key]) element.textContent = translations[state.language][key];
  });
}

function bindFilters() {
  ["keyword-search", "keyword-segment"].forEach((id) => document.querySelector(`#${id}`).addEventListener("input", renderKeywordTable));
  ["opportunity-search", "status-filter", "confidence-filter"].forEach((id) => document.querySelector(`#${id}`).addEventListener("input", renderOpportunityTable));
}

async function refreshMarket() {
  const button = document.querySelector("#refresh-market");
  button.disabled = true;
  button.querySelector("span").textContent = state.language === "zh" ? "刷新中…" : "Refreshing…";
  try {
    state.market = await fetchJson("/dashboard/market/refresh", { method: "POST" });
    state.overview = await fetchJson("/dashboard/overview");
    renderReport();
    renderSegmentOverview();
    renderMarketBars();
    populateSegmentFilter();
    renderKeywordTable();
    showToast(state.language === "zh" ? "Google Ads 市场数据已刷新" : "Google Ads market data refreshed");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = translations[state.language].refresh;
    refreshIcons();
  }
}

function bindInventory() {
  document.querySelector("#add-inventory-row").addEventListener("click", () => addInventoryRow());
  document.querySelector("#calculate-risk").addEventListener("click", calculateInventoryRisk);
}

function renderInventoryDefaults() {
  const container = document.querySelector("#inventory-rows");
  if (container.children.length) return;
  addInventoryRow("FILTER-CASE", "15.00", "10");
  addInventoryRow("DUST-CAP", "10.00", "10");
  addInventoryRow("BAHTINOV-MASK", "18.00", "5");
}

function addInventoryRow(sku = "", landedCost = "", units = "") {
  const row = document.createElement("div");
  row.className = "inventory-grid inventory-row";
  row.innerHTML = `
    <input class="inventory-sku" type="text" value="${escapeAttr(sku)}" placeholder="SKU" aria-label="SKU">
    <input class="inventory-cost" type="number" min="0.01" step="0.01" value="${escapeAttr(landedCost)}" placeholder="0.00" aria-label="Landed unit cost NZD">
    <input class="inventory-units" type="number" min="1" step="1" value="${escapeAttr(units)}" placeholder="1" aria-label="Units">
    <button type="button" class="icon-button" title="Remove SKU / 删除 SKU"><i data-lucide="trash-2"></i><span class="sr-only">Remove</span></button>`;
  row.querySelector("button").addEventListener("click", () => row.remove());
  document.querySelector("#inventory-rows").appendChild(row);
  refreshIcons();
}

async function calculateInventoryRisk() {
  const commitments = [...document.querySelectorAll(".inventory-row")].map((row) => ({
    sku: row.querySelector(".inventory-sku").value.trim(),
    landed_unit_cost_nzd: row.querySelector(".inventory-cost").value,
    units: Number(row.querySelector(".inventory-units").value),
  })).filter((item) => item.sku && Number(item.landed_unit_cost_nzd) > 0 && item.units > 0);
  if (!commitments.length) {
    showToast(state.language === "zh" ? "请至少填写一个有效 SKU" : "Add at least one valid SKU", true);
    return;
  }
  try {
    const result = await fetchJson("/business/inventory-risk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ commitments }),
    });
    renderRiskResult(result);
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderRiskResult(result) {
  const panel = document.querySelector("#risk-result");
  const total = toNumber(result.planned_inventory_risk_nzd);
  const cap = toNumber(result.max_initial_inventory_risk_nzd) || 1;
  const ratio = Math.min(100, (total / cap) * 100);
  panel.classList.toggle("rejected", result.status === "REJECT");
  panel.querySelector("strong").textContent = money(total);
  panel.querySelector(".risk-meter span").style.width = `${ratio}%`;
  document.querySelector("#risk-breakdown").innerHTML = `
    <div><span>${state.language === "zh" ? "状态" : "Status"}</span><b class="status-chip ${statusClassName(result.status)}">${result.status}</b></div>
    <div><span>${state.language === "zh" ? "风险上限" : "Risk cap"}</span><b>${money(cap)}</b></div>
    <div><span>${state.language === "zh" ? "剩余额度" : "Headroom"}</span><b>${money(result.remaining_headroom_nzd)}</b></div>
    <div><span>SKU</span><b>${result.sku_count}</b></div>`;
}

function bilingual(item) {
  return `<p>${escapeHtml(item.zh)}</p><p class="secondary">${escapeHtml(item.en)}</p>`;
}

function primarySegmentLabel(item) {
  return state.language === "zh" ? item.label_zh || item.segment || "" : item.label_en || item.segment || "";
}

function secondarySegmentLabel(item) {
  return state.language === "zh" ? item.label_en || "" : item.label_zh || "";
}

function sparkline(history) {
  const values = String(history || "").split("|").map(Number).filter(Number.isFinite);
  if (!values.length) return "—";
  const width = 150;
  const height = 34;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
    const y = height - 4 - ((value - min) / span) * (height - 8);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="12 month history"><line class="baseline" x1="0" y1="${height - 3}" x2="${width}" y2="${height - 3}"></line><polyline points="${points}"></polyline></svg>`;
}

function statusClassName(status) {
  return String(status || "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function money(value) {
  const parsed = toNumber(value);
  return `NZ$${parsed.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function number(value) {
  return toNumber(value).toLocaleString();
}

function percent(value) {
  return `${(toNumber(value) * 100).toFixed(1)}%`;
}

function formatDecimal(value) {
  return toNumber(value).toFixed(2);
}

function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function emptyRow(columns) {
  return `<tr><td class="empty-row" colspan="${columns}">${state.language === "zh" ? "没有符合条件的数据" : "No matching data"}</td></tr>`;
}

function setLoading(loading) {
  document.querySelector("#loading").classList.toggle("hidden", !loading);
}

function showToast(message, isError = false) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3600);
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function escapeAttr(value) {
  return escapeHtml(value);
}
