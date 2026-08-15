const captureButton = document.getElementById("capture");
const statusNode = document.getElementById("status");

function setStatus(message, kind = "") {
  statusNode.textContent = message;
  statusNode.className = `status ${kind}`.trim();
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
    const [{result}] = await chrome.scripting.executeScript({
      target: {tabId: tab.id},
      func: extract1688Capture,
    });
    if (!result || !Array.isArray(result.items)) {
      throw new Error("当前页面未返回有效的采集结果。");
    }
    if (result.items.length === 0) {
      throw new Error("没有找到商品，请打开搜索结果页或商品详情页后重试。");
    }

    const blob = new Blob([JSON.stringify(result, null, 2)], {type: "application/json"});
    const downloadUrl = URL.createObjectURL(blob);
    const timestamp = result.captured_at.replace(/[:.]/g, "-");
    await chrome.downloads.download({
      url: downloadUrl,
      filename: `1688-capture-${timestamp}.json`,
      saveAs: false,
    });
    setStatus(`已采集 ${result.items.length} 个商品，文件已保存到下载目录。`, "success");
  } catch (error) {
    setStatus(error.message || String(error), "error");
  } finally {
    captureButton.disabled = false;
  }
});
