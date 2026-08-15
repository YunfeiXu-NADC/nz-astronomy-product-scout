const captureButton = document.getElementById("capture");
const statusNode = document.getElementById("status");

function setStatus(message, kind = "") {
  statusNode.textContent = message;
  statusNode.className = `status ${kind}`.trim();
}

async function downloadJson(payload, filename) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
  const downloadUrl = URL.createObjectURL(blob);
  try {
    await chrome.downloads.download({url: downloadUrl, filename, saveAs: false});
  } finally {
    setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
  }
}

captureButton.addEventListener("click", async () => {
  captureButton.disabled = true;
  setStatus("正在读取页面中的商品...");
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab || !tab.id || !tab.url) throw new Error("未找到当前浏览器页面。");
    const hostname = new URL(tab.url).hostname.toLowerCase();
    if (!(hostname === "1688.com" || hostname.endsWith(".1688.com"))) {
      throw new Error("请先打开一个 1688 页面。");
    }
    const frameResults = await chrome.scripting.executeScript({
      target: {tabId: tab.id, allFrames: true},
      func: extract1688Capture,
    });
    const captures = frameResults.map((entry) => entry.result)
      .filter((entry) => entry && Array.isArray(entry.items));
    if (captures.length === 0) {
      throw new Error("当前页面未返回有效的采集结果。");
    }
    const itemMap = new Map();
    for (const capture of captures) {
      for (const item of capture.items) {
        if (item && item.detailUrl && !itemMap.has(item.detailUrl)) {
          itemMap.set(item.detailUrl, item);
        }
      }
    }
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const result = {
      ...captures[0],
      source_url: tab.url,
      page_title: tab.title || captures[0].page_title,
      items: Array.from(itemMap.values()),
      frame_diagnostics: captures.map((capture) => capture.diagnostics),
    };
    if (result.items.length === 0) {
      await downloadJson(result, `1688-capture-debug-${timestamp}.json`);
      throw new Error("没有找到商品，诊断文件已保存到下载目录。");
    }

    await downloadJson(result, `1688-capture-${timestamp}.json`);
    setStatus(`已采集 ${result.items.length} 个商品，文件已保存到下载目录。`, "success");
  } catch (error) {
    setStatus(error.message || String(error), "error");
  } finally {
    captureButton.disabled = false;
  }
});
