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
  const isChatGPT = /(^|\.)chatgpt\.com$|(^|\.)chat\.openai\.com$/.test(location.hostname);
  const roleNodes = Array.from(document.querySelectorAll("[data-message-author-role]"));
  let captureMethod = "chatgpt-role-attribute";
  let messages = roleNodes.map((node) => ({
    role: node.getAttribute("data-message-author-role"),
    text: clean(node.innerText || node.textContent || ""),
  })).filter((item) => item.role && item.text);

  if (isChatGPT && !messages.length) {
    captureMethod = "chatgpt-turn-fallback";
    messages = collectChatGPTTurns(clean);
  }

  if (messages.length) {
    return {
      ok: true,
      kind: "chatgpt",
      payload: {
        source: "chrome-extension",
        url,
        title,
        captured_at: new Date().toISOString(),
        capture_method: captureMethod,
        message_count: messages.length,
        messages,
      },
    };
  }

  const content = collectReadablePageText(clean);
  if (!content) return { ok: false, error: "No page text found" };
  return {
    ok: true,
    kind: "web",
    payload: {
      source: "chrome-extension",
      url,
      title,
      captured_at: new Date().toISOString(),
      capture_method: "readable-dom",
      content,
    },
  };
}

function collectChatGPTTurns(clean) {
  const turnSelectors = [
    "[data-testid*='conversation-turn']",
    "article",
    "main [class*='group']",
  ];
  const seen = new Set();
  const turns = [];
  for (const selector of turnSelectors) {
    for (const node of Array.from(document.querySelectorAll(selector))) {
      if (!node || seen.has(node)) continue;
      seen.add(node);
      const text = clean(node.innerText || node.textContent || "");
      if (text.length < 20) continue;
      const lower = text.slice(0, 80).toLowerCase();
      let role = "assistant";
      if (lower.startsWith("you") || lower.startsWith("user") || node.matches("[data-testid*='user']")) {
        role = "user";
      }
      turns.push({ role, text });
    }
    if (turns.length) break;
  }
  return turns;
}

function collectReadablePageText(clean) {
  const selectors = ["article", "main", "[role='main']", "body"];
  const candidates = selectors
    .map((selector) => clean(Array.from(document.querySelectorAll(selector))
      .map((node) => node.innerText || node.textContent || "")
      .join("\n\n")))
    .filter(Boolean);
  return candidates.sort((a, b) => b.length - a.length)[0] || "";
}
