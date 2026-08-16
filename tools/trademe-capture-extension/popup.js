const API_BASE = "http://127.0.0.1:8000";
const state = {capture: null, entries: []};

const statusNode = document.getElementById("status");
const previewNode = document.getElementById("preview");
const saveButton = document.getElementById("save");
const rescanButton = document.getElementById("rescan");

function setStatus(message, kind = "") {
  statusNode.textContent = message;
  statusNode.className = `status ${kind}`.trim();
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function localDate() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function clusterFor(query) {
  const normalized = query.toLowerCase();
  if (/matariki/.test(normalized)) return "matariki";
  if (/gift|necklace|poster|print|jewellery|jewelry/.test(normalized)) return "astronomy_gifts";
  if (/stem|education|school|kids?/.test(normalized)) return "education_stem";
  if (/adapter|spacer|bracket|dust cap|filter case|bahtinov|nosepiece/.test(normalized)) return "functional_accessories";
  if (/telescope|astronomy|astrophotography|eyepiece/.test(normalized)) return "core_astronomy";
  return normalized
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80) || "trademe_market";
}

function selectedPrices() {
  return state.entries.map((entry) => Number(entry.price)).filter(Number.isFinite);
}

function render() {
  const capture = state.capture;
  if (!capture) return;
  const prices = selectedPrices();
  const sampleCount = state.entries.length;
  document.getElementById("sample-count").textContent = String(sampleCount);
  document.getElementById("active-count").textContent = String(Math.max(capture.active_listing_count || 0, sampleCount));
  const midpoint = median(prices);
  document.getElementById("median-price").textContent = midpoint === null ? "-" : `NZ$${midpoint.toFixed(2)}`;

  const chips = document.getElementById("price-chips");
  chips.innerHTML = "";
  for (const entry of state.entries) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "price-chip";
    button.textContent = `NZ$${Number(entry.price).toFixed(2)}`;
    button.title = entry.title || "点击排除此价格";
    button.addEventListener("click", () => {
      state.entries = state.entries.filter((candidate) => candidate.key !== entry.key);
      render();
    });
    chips.appendChild(button);
  }
  if (!state.entries.length) chips.textContent = "当前没有可保存的价格样本。";
  saveButton.disabled = !sampleCount;
}

function entriesFromCapture(capture) {
  if (capture.items?.length) {
    return capture.items.map((item, index) => ({...item, key: item.id || item.url || `item-${index}`}));
  }
  return (capture.fallback?.prices || []).map((price, index) => ({
    key: `fallback-${index}`,
    title: "Visible price",
    price,
    seller: "",
    buyNow: false,
    bidCount: 0,
    freeShipping: false,
    inTrade: false,
  }));
}

async function scanCurrentPage() {
  previewNode.hidden = true;
  saveButton.textContent = "保存到 Product Scout";
  saveButton.disabled = true;
  setStatus("正在读取当前 Trade Me 页面...");
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.id || !tab.url) throw new Error("未找到当前浏览器页面。");
    const hostname = new URL(tab.url).hostname.toLowerCase();
    if (!(hostname === "trademe.co.nz" || hostname.endsWith(".trademe.co.nz"))) {
      throw new Error("请先打开 Trade Me 搜索结果页。");
    }
    const results = await chrome.scripting.executeScript({
      target: {tabId: tab.id},
      func: extractTradeMeCapture,
    });
    const capture = results[0]?.result;
    if (!capture) throw new Error("当前页面没有返回采集结果。");
    state.capture = capture;
    state.entries = entriesFromCapture(capture);
    if (!state.entries.length) throw new Error("当前页没有识别到商品价格，请确认页面已经加载完成。");

    document.getElementById("search-query").value = capture.search_query || "";
    document.getElementById("query-cluster").value = clusterFor(capture.search_query || "");
    previewNode.hidden = false;
    render();
    const mode = capture.items?.length ? "商品卡片" : "页面文字";
    setStatus(`已从${mode}识别 ${state.entries.length} 个当前页商品，请检查价格后保存。`, "success");
  } catch (error) {
    setStatus(error.message || String(error), "error");
  }
}

function buildSnapshot() {
  const capture = state.capture;
  const entries = state.entries;
  const prices = selectedPrices();
  const sampleCount = entries.length;
  const sellers = new Set(entries.map((entry) => entry.seller).filter(Boolean));
  const inTradeSellers = new Set(entries.filter((entry) => entry.inTrade && entry.seller).map((entry) => entry.seller));
  const fallback = capture.fallback || {};
  const usingCards = Boolean(capture.items?.length);
  const bidListingCount = usingCards
    ? entries.filter((entry) => entry.bidCount > 0).length
    : Math.min(fallback.bid_listing_count || 0, sampleCount);
  const totalBidCount = usingCards
    ? entries.reduce((sum, entry) => sum + (entry.bidCount || 0), 0)
    : Math.max(fallback.total_bid_count || 0, bidListingCount);

  return {
    query_cluster: document.getElementById("query-cluster").value.trim(),
    search_query: document.getElementById("search-query").value.trim(),
    observed_at: localDate(),
    source_url: capture.source_url,
    active_listing_count: Math.max(capture.active_listing_count || 0, sampleCount),
    sampled_listing_count: sampleCount,
    unique_seller_count: sellers.size,
    min_price_nzd: prices.length ? Math.min(...prices).toFixed(2) : null,
    median_price_nzd: prices.length ? median(prices).toFixed(2) : null,
    max_price_nzd: prices.length ? Math.max(...prices).toFixed(2) : null,
    buy_now_listing_count: usingCards
      ? entries.filter((entry) => entry.buyNow).length
      : Math.min(fallback.buy_now_listing_count || 0, sampleCount),
    bid_listing_count: bidListingCount,
    total_bid_count: totalBidCount,
    in_trade_seller_count: inTradeSellers.size,
    free_shipping_listing_count: usingCards
      ? entries.filter((entry) => entry.freeShipping).length
      : Math.min(fallback.free_shipping_listing_count || 0, sampleCount),
    notes: `User-initiated Chrome extension capture of the current visible page; ${sampleCount} listings reviewed.`,
  };
}

async function saveSnapshot() {
  const payload = buildSnapshot();
  if (!payload.search_query || !payload.query_cluster) {
    setStatus("请确认查询词和机会簇不为空。", "error");
    return;
  }
  saveButton.disabled = true;
  setStatus("正在保存到 Product Scout...");
  try {
    const response = await fetch(`${API_BASE}/dashboard/trademe/snapshots`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `保存失败 (${response.status})`);
    }
    setStatus("保存成功。Product Scout 页面刷新后即可看到这条快照。", "success");
    saveButton.textContent = "已保存";
  } catch (error) {
    setStatus(`${error.message || error} 请确认 Product Scout 正在本机 8000 端口运行。`, "error");
    saveButton.disabled = false;
  }
}

document.getElementById("search-query").addEventListener("change", (event) => {
  document.getElementById("query-cluster").value = clusterFor(event.target.value);
});
saveButton.addEventListener("click", saveSnapshot);
rescanButton.addEventListener("click", scanCurrentPage);
scanCurrentPage();
