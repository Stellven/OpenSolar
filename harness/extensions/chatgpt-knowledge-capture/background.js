const ENDPOINTS = ["http://127.0.0.1:8788", "http://127.0.0.1:8765"];

chrome.action.onClicked.addListener(async (tab) => {
  await setBadge("...", "#666666");
  try {
    if (!tab.id) throw new Error("No active tab");
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: capturePage,
    });
    if (!result || !result.ok) throw new Error(result?.error || "Capture failed");

    const response = result.kind === "chatgpt"
      ? await postJson("/chatgpt-import", result.payload)
      : await postForm("/capture", {
          title: result.payload.title,
          source_url: result.payload.url,
          content: result.payload.content,
        });

    if (!response.ok) throw new Error(response.error || "Solar capture failed");
    await setBadge("OK", "#1f7a3a");
    console.log("Solar Knowledge Capture OK", response);
  } catch (error) {
    await setBadge("ERR", "#b42318");
    console.error("Solar Knowledge Capture failed", error);
  } finally {
    setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);
  }
});

async function setBadge(text, color) {
  await chrome.action.setBadgeText({ text });
  await chrome.action.setBadgeBackgroundColor({ color });
}

async function postJson(path, payload) {
  let lastError = "";
  for (const base of ENDPOINTS) {
    try {
      const res = await fetch(base + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok && data.ok) return data;
      lastError = data.error || `${res.status} ${res.statusText}`;
    } catch (error) {
      lastError = String(error);
    }
  }
  return { ok: false, error: lastError || "Solar capture server is not running" };
}

async function postForm(path, fields) {
  let lastError = "";
  const body = new URLSearchParams(fields);
  for (const base of ENDPOINTS) {
    try {
      const res = await fetch(base + path, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      const data = await res.json();
      if (res.ok && data.ok) return data;
      lastError = data.error || `${res.status} ${res.statusText}`;
    } catch (error) {
      lastError = String(error);
    }
  }
  return { ok: false, error: lastError || "Solar capture server is not running" };
}

function capturePage() {
  const clean = (value) => String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  const url = location.href;
  const title = document.title || "Untitled Page";
  const nodes = Array.from(document.querySelectorAll("[data-message-author-role]"));
  const messages = nodes.map((node) => ({
    role: node.getAttribute("data-message-author-role"),
    text: clean(node.innerText || node.textContent || ""),
  })).filter((item) => item.role && item.text);

  if (messages.length) {
    return {
      ok: true,
      kind: "chatgpt",
      payload: {
        source: "chrome-extension",
        url,
        title,
        captured_at: new Date().toISOString(),
        messages,
      },
    };
  }

  const content = clean(document.body?.innerText || "");
  if (!content) return { ok: false, error: "No page text found" };
  return {
    ok: true,
    kind: "web",
    payload: {
      source: "chrome-extension",
      url,
      title,
      captured_at: new Date().toISOString(),
      content,
    },
  };
}
