#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import subprocess
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import browser_job_runtime as bjrt
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession


DEFAULT_URL = "https://chatgpt.com/"
DEFAULT_USER_DATA_DIR = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
DEFAULT_PROFILE_DIRECTORY = "Profile 1"
DEFAULT_ALLOWED_DOMAINS = ["chatgpt.com", "auth.openai.com", "challenges.cloudflare.com"]

CAPTURE_JS = r"""() => {
  const clean = (value) => String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  const stripNoise = (value) => clean(value).split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !/^(share|copy|edit|regenerate|try again|read aloud|chatgpt can make mistakes|check important info)$/i.test(line))
    .join("\n");
  const textFrom = (node) => clean(node && (node.innerText || node.textContent || ""));
  const messageText = (node) => {
    const candidates = [
      node.querySelector("[data-message-content]"),
      node.querySelector(".markdown"),
      node.querySelector("[class*='markdown']"),
      node.querySelector(".whitespace-pre-wrap"),
      node
    ].filter(Boolean);
    return candidates.map((item) => stripNoise(textFrom(item))).filter(Boolean).sort((a, b) => b.length - a.length)[0] || "";
  };
  const nodes = Array.from(document.querySelectorAll("[data-message-author-role]"));
  const seen = new Set();
  const messages = [];
  for (const node of nodes) {
    const role = node.getAttribute("data-message-author-role");
    if (!["user", "assistant"].includes(role)) continue;
    const text = messageText(node);
    const key = role + "\n" + text;
    if (!text || seen.has(key)) continue;
    seen.add(key);
    messages.push({ role, text, turn_index: messages.length + 1 });
  }
  const latestAssistant = [...messages].reverse().find((item) => item.role === "assistant") || null;
  const lowered = stripNoise(textFrom(document.body)).toLowerCase();
  const loginWall = [
    "log in",
    "sign in",
    "continue with google",
    "continue with apple",
    "登录",
    "注册",
    "使用 google 账户继续",
    "使用 apple 账户继续"
  ].some((cue) => lowered.includes(cue));
  const composer = document.querySelector("#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea']");
  const stopButton = Array.from(document.querySelectorAll("button")).find((btn) => {
    const label = clean(btn.getAttribute("aria-label") || btn.textContent || "");
    return /(stop|停止|停止生成|中止|cancel)/i.test(label);
  });
  const conversationMatch = location.pathname.match(/\/c\/([^/?#]+)/);
  return JSON.stringify({
    title: document.title || "",
    url: location.href,
    canonical_url: document.querySelector("link[rel='canonical']")?.href || location.href,
    conversation_id: conversationMatch ? decodeURIComponent(conversationMatch[1]) : "",
    login_wall: loginWall,
    composer_ready: !!composer,
    is_generating: !!stopButton,
    message_count: messages.length,
    assistant_count: messages.filter((item) => item.role === "assistant").length,
    latest_assistant_text: latestAssistant ? latestAssistant.text : "",
    messages
  });
}"""

SET_PROMPT_JS = r"""(promptText) => {
  const composer = document.querySelector("#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea']");
  if (!composer) {
    return JSON.stringify({ ok: false, error: "composer_not_found" });
  }
  const prompt = String(promptText || "").replace(/\r\n/g, "\n");
  const lines = prompt.split("\n");
  composer.focus();
  if (composer.tagName === "TEXTAREA") {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set;
    if (setter) {
      setter.call(composer, prompt);
    } else {
      composer.value = prompt;
    }
    composer.dispatchEvent(new InputEvent("beforeinput", { bubbles: true, inputType: "insertText", data: prompt }));
    composer.dispatchEvent(new Event("input", { bubbles: true }));
    composer.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
    composer.dispatchEvent(new Event("change", { bubbles: true }));
    return JSON.stringify({ ok: true, mode: "textarea" });
  }
  composer.innerHTML = "";
  for (const line of lines) {
    const p = document.createElement("p");
    if (line.length) {
      p.textContent = line;
    } else {
      p.appendChild(document.createElement("br"));
    }
    composer.appendChild(p);
  }
  composer.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
  return JSON.stringify({ ok: true, mode: "contenteditable" });
}"""

FOCUS_COMPOSER_JS = r"""() => {
  const composer = document.querySelector("#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea']");
  if (!composer) {
    return JSON.stringify({ ok: false, error: "composer_not_found" });
  }
  composer.focus();
  return JSON.stringify({ ok: true, tag: composer.tagName, id: composer.id || "" });
}"""

COMPOSER_STATE_JS = r"""() => {
  const composer = document.querySelector("#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea']");
  if (!composer) return JSON.stringify({ ok: false, error: "composer_not_found" });
  const text = String(composer.value || composer.innerText || composer.textContent || "").trim();
  return JSON.stringify({ ok: true, text_length: text.length, tag: composer.tagName, id: composer.id || "" });
}"""

SUBMIT_JS = r"""() => {
  const candidates = [
    "form button[type='submit']",
    "button[type='submit']",
    "button[data-testid='send-button']",
    "button.composer-submit-button-color[type='button']",
    "button.composer-submit-button-color",
  ];
  for (const selector of candidates) {
    const buttons = Array.from(document.querySelectorAll(selector));
    for (const button of buttons) {
      const label = String(button.getAttribute("aria-label") || button.textContent || "").trim();
      if (/语音|voice/i.test(label)) continue;
      const disabled = button.disabled || button.getAttribute("aria-disabled") === "true";
      if (disabled) continue;
      button.click();
      return JSON.stringify({ ok: true, selector, label });
    }
  }
  const composer = document.querySelector("#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea']");
  const form = composer ? composer.closest("form") : null;
  if (form && typeof form.requestSubmit === "function") {
    form.requestSubmit();
    return JSON.stringify({ ok: true, selector: "form.requestSubmit", label: "" });
  }
  return JSON.stringify({ ok: false, error: "submit_button_not_found" });
}"""

HTML_JS = r"""() => document.documentElement.outerHTML"""
TEXT_JS = r"""() => (document.body && (document.body.innerText || document.body.textContent) || "").trim()"""

MOVE_TO_PROJECT_JS = r"""(projectName) => {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const clickBy = (predicate) => {
    const nodes = Array.from(document.querySelectorAll("button,a,div,[role='button'],[role='menuitem']"));
    const node = nodes.find((el) => visible(el) && predicate(el, clean(el.innerText || el.textContent || ""), clean(el.getAttribute("aria-label") || "")));
    if (!node) return null;
    node.click();
    return { text: clean(node.innerText || node.textContent || ""), aria: clean(node.getAttribute("aria-label") || ""), tag: node.tagName };
  };
  const topOptions = clickBy((el, text, aria) => aria === "打开对话选项" || aria === "Open conversation options");
  if (!topOptions) return JSON.stringify({ ok: false, step: "open_options", error: "conversation_options_not_found" });
  return JSON.stringify({ ok: true, step: "open_options", clicked: topOptions, project_name: String(projectName || "") });
}"""

MOVE_TO_PROJECT_MENU_JS = r"""() => {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const items = Array.from(document.querySelectorAll("[role='menuitem'],button,a,div"));
  const item = items.find((el) => {
    if (!visible(el)) return false;
    const text = clean(el.innerText || el.textContent || "");
    return text === "移至项目" || text === "Move to project";
  });
  if (!item) return JSON.stringify({ ok: false, step: "move_menu", error: "move_to_project_not_found" });
  item.click();
  return JSON.stringify({ ok: true, step: "move_menu", clicked: clean(item.innerText || item.textContent || "") });
}"""

SELECT_PROJECT_JS = r"""(projectName) => {
  const target = String(projectName || "").trim();
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const items = Array.from(document.querySelectorAll("[role='menuitem'],button,a,div"));
  const item = items.find((el) => visible(el) && clean(el.innerText || el.textContent || "") === target);
  if (!item) {
    const candidates = items
      .filter((el) => visible(el))
      .map((el) => clean(el.innerText || el.textContent || ""))
      .filter(Boolean)
      .slice(0, 80);
    return JSON.stringify({ ok: false, step: "select_project", error: "project_not_found", project_name: target, candidates });
  }
  item.click();
  return JSON.stringify({ ok: true, step: "select_project", project_name: target, clicked: clean(item.innerText || item.textContent || "") });
}"""

OPEN_PROJECT_JS = r"""(projectName) => {
  const target = String(projectName || "").trim();
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const nodes = Array.from(document.querySelectorAll("a,button,[role='button'],div"));
  const project = nodes.find((el) => visible(el) && clean(el.innerText || el.textContent || "") === target);
  if (!project) {
    const expanders = nodes.filter((el) => {
      if (!visible(el)) return false;
      const text = clean(el.innerText || el.textContent || "");
      const aria = clean(el.getAttribute("aria-label") || "");
      return /^(更多|More)$/.test(text) || /(show more|更多|展开|projects|项目)/i.test(aria);
    }).slice(0, 5);
    for (const item of expanders) {
      try { item.click(); } catch (_) {}
    }
    return JSON.stringify({ ok: false, step: "open_project", error: "project_not_found", project_name: target });
  }
  project.click();
  return JSON.stringify({ ok: true, step: "open_project", project_name: target });
}"""

NEW_CHAT_JS = r"""() => {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const nodes = Array.from(document.querySelectorAll("a,button,[role='button']"));
  const item = nodes.find((el) => {
    if (!visible(el)) return false;
    const text = clean(el.innerText || el.textContent || "");
    const aria = clean(el.getAttribute("aria-label") || "");
    return /^(New chat|新聊天|新建聊天|新对话)$/.test(text) || /(New chat|新聊天|新建聊天|新对话)/.test(aria);
  });
  if (!item) return JSON.stringify({ ok: false, step: "new_chat", error: "new_chat_not_found" });
  item.click();
  return JSON.stringify({ ok: true, step: "new_chat" });
}"""

CONFIGURE_CHATGPT_UI_JS = r"""(settings) => new Promise(async (resolve) => {
  const cfg = settings || {};
  const modelMode = String(cfg.model_mode || "").toLowerCase();
  const reasoningEffort = String(cfg.reasoning_effort || "").toLowerCase();
  const toolMode = String(cfg.tool_mode || "").toLowerCase();
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const isActionNode = (el) => {
    const role = clean(el.getAttribute("role") || "");
    return el.tagName === "BUTTON" || el.tagName === "A" || ["button", "menuitem", "menuitemradio", "menuitemcheckbox", "option"].includes(role);
  };
  const rejectChromeNoise = (text, aria) => {
    const joined = `${text} ${aria}`;
    return /(项目选项|project options|conversation options|打开 .*项目选项|历史聊天记录|最近|sidebar|侧边栏|个人资料|profile|项目|project)/i.test(joined);
  };
  const clickFirst = (predicate, selector = "button,a,[role='button'],[role='menuitem'],[role='menuitemradio'],[role='menuitemcheckbox'],[role='option']") => {
    const nodes = Array.from(document.querySelectorAll(selector));
    const node = nodes.find((el) => visible(el) && predicate(clean(el.innerText || el.textContent || ""), clean(el.getAttribute("aria-label") || ""), el));
    if (!node) return null;
    node.scrollIntoView({ block: "center", inline: "center" });
    for (const type of ["pointerdown", "mousedown", "pointerup", "mouseup"]) {
      node.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
    }
    node.click();
    return { text: clean(node.innerText || node.textContent || ""), aria: clean(node.getAttribute("aria-label") || ""), tag: node.tagName };
  };
  const snapshotCandidates = (selector = "button,a,[role='button'],[role='menuitem'],[role='menuitemradio'],[role='menuitemcheckbox'],[role='option']") =>
    Array.from(document.querySelectorAll(selector))
      .filter(visible)
      .map((el) => ({
        text: clean(el.innerText || el.textContent || ""),
        aria: clean(el.getAttribute("aria-label") || ""),
        role: clean(el.getAttribute("role") || ""),
        tag: el.tagName,
      }))
      .filter((item) => (item.text || item.aria) && `${item.text} ${item.aria}`.length < 260)
      .slice(0, 120);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const steps = [];
  const snapshots = {};
  const dropdown = clickFirst((text, aria, el) => {
    if (!isActionNode(el) || rejectChromeNoise(text, aria)) return false;
    return /^(ChatGPT|GPT-|GPT|模型|Model)(\s|$)/i.test(text) || /(^|\s)(model|模型|ChatGPT)(\s|$)/i.test(aria);
  }, "button,[role='button']");
  steps.push({ step: "open_model_dropdown", ok: !!dropdown, clicked: dropdown });
  if (dropdown) {
    await sleep(700);
    snapshots.model_menu = snapshotCandidates();
    const modelMatches = (text, aria, el) => {
      const role = clean(el.getAttribute("role") || "");
      const joined = `${text} ${aria}`;
      if (modelMode === "pro") {
        if (!["menuitem", "menuitemradio", "option"].includes(role)) return false;
        return /(^|\s)Pro(\s|$)|研究级智能模型|专业版模型/i.test(joined);
      }
      return /(Thinking|思考|GPT-5|5\.5)/i.test(joined);
    };
    const selected = clickFirst((text, aria, el) => {
      if (!isActionNode(el) || rejectChromeNoise(text, aria)) return false;
      if ((text + " " + aria).length > 180) return false;
      if (/个人资料|profile|Li Sihao Pro/i.test(text + " " + aria)) return false;
      return modelMatches(text, aria, el);
    });
    steps.push({ step: "select_model_mode", mode: modelMode || "thinking", ok: !!selected, clicked: selected });
  }
  if (reasoningEffort === "high" || reasoningEffort === "deep_research") {
    await sleep(500);
    const plus = clickFirst((text, aria, el) => {
      if (!isActionNode(el) || rejectChromeNoise(text, aria)) return false;
      return text === "+" || /attach|tools|工具|添加|plus|\+/.test(aria) || /^(工具|添加)$/.test(text);
    }, "button,[role='button']");
    steps.push({ step: "open_tools_or_plus", ok: !!plus, clicked: plus });
    if (plus) await sleep(700);
    snapshots.tools_menu = snapshotCandidates();
    if (reasoningEffort === "high") {
      const high = clickFirst((text, aria, el) => {
        if (!isActionNode(el) || rejectChromeNoise(text, aria)) return false;
        if ((text + " " + aria).length > 180) return false;
        return /(High|高|更长|Think longer|思考深度|深度思考)/i.test(text) || /(High|高|Think longer|思考深度)/i.test(aria);
      });
      steps.push({ step: "select_high_reasoning", ok: !!high, clicked: high });
    }
    if (toolMode === "deep_research" || reasoningEffort === "deep_research") {
      const deep = clickFirst((text, aria, el) => {
        if (!isActionNode(el) || rejectChromeNoise(text, aria)) return false;
        if ((text + " " + aria).length > 220) return false;
        return /^(Deep Research|深度研究|深入研究)$/i.test(text) || /^(Deep Research|深度研究|深入研究)$/i.test(aria);
      });
      steps.push({ step: "select_deep_research", ok: !!deep, clicked: deep });
    }
  }
  resolve(JSON.stringify({ ok: true, settings: cfg, steps, snapshots }));
})"""

DEEP_RESEARCH_STATE_JS = r"""() => {
  const clean = (value) => String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const looksDeepResearch = (value) => /(Deep Research|深度研究|深入研究)/i.test(clean(value));
  const stateToken = (el) => clean([
    el.getAttribute("aria-pressed"),
    el.getAttribute("aria-selected"),
    el.getAttribute("aria-checked"),
    el.getAttribute("data-state"),
    el.getAttribute("data-selected"),
    el.getAttribute("data-active"),
    el.getAttribute("class"),
  ].filter(Boolean).join(" "));
  const selectedTokens = /\b(true|checked|selected|active)\b/i;

  const controls = Array.from(document.querySelectorAll(
    "button,[role='button'],[role='menuitemradio'],[role='menuitemcheckbox'],[aria-pressed],[aria-selected],[aria-checked],[data-state],[data-testid]"
  )).filter(visible).map((el) => {
    const text = clean(el.innerText || el.textContent || "");
    const aria = clean(el.getAttribute("aria-label") || "");
    const token = stateToken(el);
    return { text, aria, token, tag: el.tagName };
  });

  const explicitSelected = controls.filter((item) =>
    (looksDeepResearch(item.text) || looksDeepResearch(item.aria)) && selectedTokens.test(item.token)
  );

  const composer = document.querySelector("#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea']");
  const composerRoot = composer ? (composer.closest("form") || composer.closest("[data-testid]") || composer.parentElement) : null;
  const localText = clean(composerRoot ? (composerRoot.innerText || composerRoot.textContent || "") : "");
  const localDeepResearchChip = !!composerRoot && looksDeepResearch(localText);

  const deepResearchDialog = Array.from(document.querySelectorAll("[role='dialog'],[data-testid]"))
    .filter(visible)
    .map((el) => clean(el.innerText || el.textContent || ""))
    .find((text) =>
      looksDeepResearch(text) &&
      /(research plan|researching|start research|开始研究|研究计划|正在研究|继续研究|clarify|澄清)/i.test(text)
    ) || "";

  const menuStillOpen = Array.from(document.querySelectorAll("[role='menu'],[role='listbox']"))
    .filter(visible)
    .some((el) => looksDeepResearch(el.innerText || el.textContent || ""));

  const ok = explicitSelected.length > 0 || localDeepResearchChip;
  return JSON.stringify({
    ok,
    explicit_selected_count: explicitSelected.length,
    local_deep_research_chip: localDeepResearchChip,
    deep_research_dialog: !!deepResearchDialog,
    menu_still_open: menuStillOpen,
    local_text_sample: localText.slice(0, 300),
    selected_controls: explicitSelected.slice(0, 10),
    deep_research_dialog_sample: deepResearchDialog.slice(0, 500),
  });
}"""

CHATGPT_MODE_STATE_JS = r"""(settings) => {
  const cfg = settings || {};
  const modelMode = String(cfg.model_mode || "").toLowerCase();
  const reasoningEffort = String(cfg.reasoning_effort || "").toLowerCase();
  const clean = (value) => String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const tokenOf = (el) => clean([
    el.getAttribute("aria-pressed"),
    el.getAttribute("aria-selected"),
    el.getAttribute("aria-checked"),
    el.getAttribute("data-state"),
    el.getAttribute("data-selected"),
    el.getAttribute("data-active"),
    el.getAttribute("class"),
  ].filter(Boolean).join(" "));
  const selectedTokens = /\b(true|checked|selected|active)\b/i;
  const controls = Array.from(document.querySelectorAll(
    "button,[role='button'],[role='menuitemradio'],[role='menuitemcheckbox'],[aria-pressed],[aria-selected],[aria-checked],[data-state],[data-testid]"
  )).filter(visible).map((el) => {
    const text = clean(el.innerText || el.textContent || "");
    const aria = clean(el.getAttribute("aria-label") || "");
    const token = tokenOf(el);
    return { text, aria, token, tag: el.tagName };
  });
  const composer = document.querySelector("#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea']");
  const composerRoot = composer ? (composer.closest("form") || composer.closest("[data-testid]") || composer.parentElement) : null;
  const composerText = clean(composerRoot ? (composerRoot.innerText || composerRoot.textContent || "") : "");
  const modelSelector = Array.from(document.querySelectorAll("button,[role='button']"))
    .filter(visible)
    .map((el) => ({
      text: clean(el.innerText || el.textContent || ""),
      aria: clean(el.getAttribute("aria-label") || ""),
      token: tokenOf(el),
      tag: el.tagName,
    }))
    .find((item) => /模型选择器|model selector/i.test(item.aria) || /^(ChatGPT|GPT-|GPT|模型|Model)(\s|$)/i.test(item.text)) || null;
  const selected = (regex) => controls.filter((item) =>
    regex.test(item.text + " " + item.aria) && selectedTokens.test(item.token)
  );
  const thinkingControls = selected(/(Thinking|思考|ChatGPT 5\.5|GPT-5\.5|GPT-5)/i);
  const highControls = selected(/(High|高|深入|深度思考|Think longer|思考深度)/i);
  const thinkingChip = /(Thinking|思考|ChatGPT 5\.5|GPT-5\.5|GPT-5)/i.test(composerText);
  const highChip = /(High|高|深入|深度思考|Think longer|思考深度)/i.test(composerText);
  const modelSelectorLooksChatGPT = !!modelSelector && /ChatGPT/i.test(modelSelector.text + " " + modelSelector.aria);
  const modelOk = modelMode !== "thinking" || thinkingControls.length > 0 || thinkingChip || (modelSelectorLooksChatGPT && highChip);
  const reasoningOk = reasoningEffort !== "high" || highControls.length > 0 || highChip;
  return JSON.stringify({
    ok: modelOk && reasoningOk,
    model_mode: modelMode,
    reasoning_effort: reasoningEffort,
    model_ok: modelOk,
    reasoning_ok: reasoningOk,
    thinking_selected_count: thinkingControls.length,
    high_selected_count: highControls.length,
    thinking_chip: thinkingChip,
    high_chip: highChip,
    model_selector: modelSelector,
    model_selector_looks_chatgpt: modelSelectorLooksChatGPT,
    composer_text_sample: composerText.slice(0, 300),
    thinking_controls: thinkingControls.slice(0, 10),
    high_controls: highControls.slice(0, 10),
  });
}"""


def _request_dir() -> Path:
    out = Path(os.environ.get("BROWSER_AGENT_REQUEST_DIR") or tempfile_dir_fallback()).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _quiet_browser_logs() -> None:
    logging.getLogger().setLevel(logging.ERROR)
    for name in (
        "BrowserSession",
        "cdp_use.client",
        "browser_use",
        "browser_use.browser.session",
        "browser_use.browser.profile",
    ):
        logging.getLogger(name).setLevel(logging.ERROR)


def tempfile_dir_fallback() -> str:
    return str(Path("/tmp") / f"browser-agent-chatgpt-wrapper-{int(time.time())}")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _kill_browser_profile_processes(profile_dir: Path | None) -> None:
    if not profile_dir:
        return
    raw = str(profile_dir)
    if not raw or raw == "/" or "browser-use-user-data-dir-" not in raw:
        return
    candidates = {raw, raw.replace("/var/", "/private/var/"), raw.replace("/private/var/", "/var/")}
    try:
        time.sleep(0.5)
        for candidate in candidates:
            subprocess.run(["pkill", "-f", candidate], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        time.sleep(0.5)
        for candidate in candidates:
            subprocess.run(["pkill", "-9", "-f", candidate], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass


def _prompt_from_stdin() -> str:
    prompt = sys.stdin.read()
    action = str(os.environ.get("BROWSER_AGENT_CHATGPT_ACTION") or "run").strip().lower()
    if not prompt.strip() and action not in {"poll", "collect"}:
        raise SystemExit("stdin prompt is empty")
    return prompt


async def _wait_for_ready(page, *, timeout_s: int = 60) -> dict:
    deadline = time.time() + timeout_s
    last_data = {}
    refresh_count = 0
    while time.time() < deadline:
        data = json.loads(await page.evaluate(CAPTURE_JS))
        last_data = data
        if data.get("login_wall"):
            raise RuntimeError("chatgpt_login_wall_detected")
        if data.get("composer_ready"):
            return data
        remaining = deadline - time.time()
        if refresh_count == 0 and remaining < max(10, timeout_s - 25):
            try:
                await page.goto(DEFAULT_URL)
                refresh_count += 1
            except Exception:
                pass
        elif refresh_count == 1 and remaining < max(5, timeout_s - 55):
            try:
                await page.reload()
                refresh_count += 1
            except Exception:
                pass
        await asyncio.sleep(1.5)
    raise TimeoutError(
        "chatgpt_composer_not_ready: "
        + json.dumps(
            {
                "title": last_data.get("title"),
                "url": last_data.get("url"),
                "login_wall": last_data.get("login_wall"),
                "message_count": last_data.get("message_count"),
            },
            ensure_ascii=False,
        )
    )


async def _submit_prompt(page, prompt: str) -> dict:
    baseline = json.loads(await page.evaluate(CAPTURE_JS))
    baseline_message_count = int(baseline.get("message_count") or 0)
    result = await _keyboard_insert_prompt(page, prompt)
    if not result.get("ok"):
        result = json.loads(await page.evaluate(SET_PROMPT_JS, prompt))
        if not result.get("ok"):
            raise RuntimeError(result.get("error") or "prompt_injection_failed")
    composer_state = json.loads(await page.evaluate(COMPOSER_STATE_JS))
    if int(composer_state.get("text_length") or 0) < max(10, min(len(prompt.strip()), 80)):
        try:
            focused = json.loads(await page.evaluate(FOCUS_COMPOSER_JS))
            if focused.get("ok"):
                session_id = await page._ensure_session()
                await page._client.send.Input.insertText({"text": prompt}, session_id=session_id)
        except Exception:
            pass
        composer_state = json.loads(await page.evaluate(COMPOSER_STATE_JS))
    if int(composer_state.get("text_length") or 0) < 10:
        raise RuntimeError(f"prompt_injection_no_visible_text:{composer_state}")
    await asyncio.sleep(1.2)
    submit_note = {"mode": "unknown"}
    submit_result = json.loads(await page.evaluate(SUBMIT_JS))
    if not submit_result.get("ok"):
        await page.press("Meta+Enter")
        submit_note = {"mode": "meta_enter_key", "js_error": submit_result.get("error")}
    else:
        submit_note = {"mode": "js_submit", **submit_result}
    await asyncio.sleep(2.0)
    post_submit = json.loads(await page.evaluate(CAPTURE_JS))
    if int(post_submit.get("message_count") or 0) <= baseline_message_count and not post_submit.get("is_generating"):
        try:
            clipboard_note = await _clipboard_paste_and_submit(page, prompt)
            submit_note = {**submit_note, "retry": "clipboard_paste_enter_after_no_message", "clipboard": clipboard_note}
            await asyncio.sleep(2.0)
            post_submit = json.loads(await page.evaluate(CAPTURE_JS))
        except Exception as exc:
            submit_note = {**submit_note, "retry_error": f"{type(exc).__name__}: {exc}"}
    post_submit["_submit_note"] = submit_note
    post_submit["_composer_state_before_submit"] = composer_state
    return post_submit


async def _keyboard_insert_prompt(page, prompt: str) -> dict:
    try:
        focused = json.loads(await page.evaluate(FOCUS_COMPOSER_JS))
        if not focused.get("ok"):
            return {"ok": False, "error": focused.get("error") or "composer_focus_failed"}
        await page.press("Meta+A")
        await asyncio.sleep(0.1)
        await page.press("Backspace")
        await asyncio.sleep(0.2)
        session_id = await page._ensure_session()
        await page._client.send.Input.insertText({"text": prompt}, session_id=session_id)
        await asyncio.sleep(0.8)
        state = json.loads(await page.evaluate(COMPOSER_STATE_JS))
        return {"ok": int(state.get("text_length") or 0) > 0, "composer_state": state}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _clipboard_paste_and_submit(page, prompt: str) -> dict:
    old_clip = ""
    restored = False
    try:
        old_clip = subprocess.run(["pbpaste"], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=3).stdout
    except Exception:
        old_clip = ""
    try:
        subprocess.run(["pbcopy"], input=prompt, text=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        focused = json.loads(await page.evaluate(FOCUS_COMPOSER_JS))
        if not focused.get("ok"):
            raise RuntimeError(f"composer_focus_failed:{focused}")
        await page.press("Meta+A")
        await asyncio.sleep(0.2)
        await page.press("Meta+V")
        await asyncio.sleep(0.8)
        state = json.loads(await page.evaluate(COMPOSER_STATE_JS))
        await page.press("Enter")
        return {"ok": True, "composer_state_after_paste": state}
    finally:
        try:
            subprocess.run(["pbcopy"], input=old_clip, text=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            restored = True
        except Exception:
            restored = False
        if not restored:
            pass


async def _wait_for_answer(page, baseline_assistant_count: int, *, timeout_s: int = 900) -> dict:
    deadline = time.time() + timeout_s
    last_text = ""
    stable = 0
    first_response_seen = False
    stable_required = int(os.environ.get("BROWSER_AGENT_STABLE_POLLS") or "8")
    while time.time() < deadline:
        data = json.loads(await page.evaluate(CAPTURE_JS))
        if data.get("login_wall"):
            raise RuntimeError("chatgpt_login_wall_detected")
        assistant_count = int(data.get("assistant_count") or 0)
        latest_text = str(data.get("latest_assistant_text") or "").strip()
        if assistant_count > baseline_assistant_count and latest_text:
            first_response_seen = True
            if latest_text == last_text:
                stable += 1
            else:
                stable = 0
                last_text = latest_text
            if not data.get("is_generating") and stable >= stable_required:
                return data
        await asyncio.sleep(3)
    if first_response_seen:
        return json.loads(await page.evaluate(CAPTURE_JS))
    raise TimeoutError("chatgpt_response_timeout")


async def _write_conversation_artifacts(
    page,
    request_dir: Path,
    final_data: dict,
    *,
    model: str,
    reasoning_effort: str,
    prompt: str | None = None,
) -> str:
    html = await page.evaluate(HTML_JS)
    page_text = await page.evaluate(TEXT_JS)
    title = await page.get_title()
    final_url = await page.get_url()
    screenshot_b64 = await page.screenshot(format="png")
    latest = str(final_data.get("latest_assistant_text") or "").strip()
    if prompt is not None:
        (request_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    if latest:
        (request_dir / "assistant-response.txt").write_text(latest + "\n", encoding="utf-8")
    (request_dir / "page.html").write_text(str(html or ""), encoding="utf-8")
    (request_dir / "page.txt").write_text(str(page_text or "") + "\n", encoding="utf-8")
    (request_dir / "conversation.json").write_text(json.dumps(final_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = []
    for msg in final_data.get("messages") or []:
        role = str(msg.get("role") or "").upper()
        text = str(msg.get("text") or "").strip()
        lines.append(f"[{role}]\n{text}\n")
    (request_dir / "conversation.txt").write_text("\n".join(lines), encoding="utf-8")
    _write_json(request_dir / "page.json", {
        "title": title,
        "url": final_url,
        "conversation_id": final_data.get("conversation_id"),
        "message_count": final_data.get("message_count"),
        "assistant_count": final_data.get("assistant_count"),
        "is_generating": final_data.get("is_generating"),
        "model": model,
        "reasoning_effort": reasoning_effort,
    })
    if screenshot_b64:
        (request_dir / "screenshot.png").write_bytes(base64.b64decode(screenshot_b64))
    return latest


async def _move_current_conversation_to_project(page, project_name: str, *, timeout_s: int = 45) -> dict:
    project_name = str(project_name or "").strip()
    if not project_name:
        return {"ok": False, "skipped": True, "error": "empty_project_name"}
    result: dict[str, object] = {
        "ok": False,
        "project_name": project_name,
        "started_at": bjrt._now(),
        "steps": [],
    }
    deadline = time.time() + timeout_s
    try:
        step = json.loads(await page.evaluate(MOVE_TO_PROJECT_JS, project_name))
        result["steps"].append(step)
        if not step.get("ok"):
            result["error"] = step.get("error") or "open_options_failed"
            return result
        await asyncio.sleep(0.6)
        step = json.loads(await page.evaluate(MOVE_TO_PROJECT_MENU_JS))
        result["steps"].append(step)
        if not step.get("ok"):
            result["error"] = step.get("error") or "move_menu_failed"
            return result
        while time.time() < deadline:
            await asyncio.sleep(0.5)
            step = json.loads(await page.evaluate(SELECT_PROJECT_JS, project_name))
            if step.get("ok"):
                result["steps"].append(step)
                await asyncio.sleep(1.5)
                final_state = json.loads(await page.evaluate(CAPTURE_JS))
                result.update({
                    "ok": True,
                    "finished_at": bjrt._now(),
                    "conversation_id": final_state.get("conversation_id"),
                    "url": final_state.get("url"),
                    "title": final_state.get("title"),
                })
                return result
            last_step = step
        result["steps"].append(last_step if "last_step" in locals() else {"ok": False, "error": "project_menu_timeout"})
        result["error"] = "project_not_found_or_menu_timeout"
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["finished_at"] = bjrt._now()
        return result


async def _open_project_new_chat(page, project_name: str) -> dict:
    project_name = str(project_name or "").strip()
    result: dict[str, Any] = {"ok": False, "project_name": project_name, "steps": []}
    if not project_name:
        result["error"] = "empty_project_name"
        return result
    try:
        step: dict[str, object] = {"ok": False, "error": "not_attempted"}
        for _ in range(8):
            step = json.loads(await page.evaluate(OPEN_PROJECT_JS, project_name))
            result["steps"].append(step)
            if step.get("ok"):
                break
            await asyncio.sleep(1.0)
        if not step.get("ok"):
            result["error"] = step.get("error") or "open_project_failed"
            return result
        await asyncio.sleep(1.5)
        step = json.loads(await page.evaluate(NEW_CHAT_JS))
        result["steps"].append(step)
        # Some project pages already open a blank composer; failure to find a
        # New Chat button is not fatal as long as the composer is ready.
        ready = json.loads(await page.evaluate(CAPTURE_JS))
        if ready.get("composer_ready"):
            result.update({"ok": True, "url": ready.get("url"), "conversation_id": ready.get("conversation_id")})
            return result
        result["error"] = step.get("error") or "composer_not_ready_after_project_open"
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


async def _configure_chatgpt_ui(page, *, model_mode: str, reasoning_effort: str, tool_mode: str) -> dict:
    try:
        result = json.loads(await page.evaluate(
            CONFIGURE_CHATGPT_UI_JS,
            {
                "model_mode": model_mode,
                "reasoning_effort": reasoning_effort,
                "tool_mode": tool_mode,
            },
        ))
        return result
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _verify_deep_research_enabled(page, *, timeout_s: int = 12) -> dict:
    deadline = time.time() + timeout_s
    last: dict[str, object] = {"ok": False, "error": "not_checked"}
    while time.time() < deadline:
        try:
            last = json.loads(await page.evaluate(DEEP_RESEARCH_STATE_JS))
            if last.get("ok"):
                return last
        except Exception as exc:
            last = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        await asyncio.sleep(0.75)
    return last


async def _verify_chatgpt_mode_enabled(page, *, model_mode: str, reasoning_effort: str, timeout_s: int = 12) -> dict:
    deadline = time.time() + timeout_s
    last: dict[str, object] = {"ok": False, "error": "not_checked"}
    while time.time() < deadline:
        try:
            last = json.loads(await page.evaluate(
                CHATGPT_MODE_STATE_JS,
                {"model_mode": model_mode, "reasoning_effort": reasoning_effort},
            ))
            if last.get("ok"):
                return last
        except Exception as exc:
            last = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        await asyncio.sleep(0.75)
    return last


async def _run(prompt: str) -> int:
    request_dir = _request_dir()
    expected = str(os.environ.get("BROWSER_AGENT_EXPECTED_OUTPUT") or "markdown").strip().lower()
    model = str(os.environ.get("CHATGPT_MODEL") or "chatgpt-5.5").strip()
    reasoning_effort = str(os.environ.get("CHATGPT_REASONING_EFFORT") or "high").strip().lower()
    profile_directory = str(os.environ.get("BROWSER_AGENT_PROFILE_DIRECTORY") or DEFAULT_PROFILE_DIRECTORY)
    user_data_dir = Path(os.environ.get("BROWSER_AGENT_USER_DATA_DIR") or str(DEFAULT_USER_DATA_DIR)).expanduser()
    target_url = str(os.environ.get("BROWSER_AGENT_CHATGPT_URL") or DEFAULT_URL)
    action = str(os.environ.get("BROWSER_AGENT_CHATGPT_ACTION") or "run").strip().lower()
    collect_url = str(os.environ.get("BROWSER_AGENT_CHATGPT_CONVERSATION_URL") or "").strip()
    if action in {"poll", "collect"} and collect_url:
        target_url = collect_url
    timeout_s = int(os.environ.get("BROWSER_AGENT_CHATGPT_TIMEOUT") or "1200")
    project_name = str(os.environ.get("BROWSER_AGENT_CHATGPT_PROJECT_NAME") or "").strip()
    require_project = str(os.environ.get("BROWSER_AGENT_CHATGPT_REQUIRE_PROJECT") or "false").strip().lower() in {"1", "true", "yes", "on"}
    open_project_first = str(os.environ.get("BROWSER_AGENT_CHATGPT_OPEN_PROJECT_FIRST") or "false").strip().lower() in {"1", "true", "yes", "on"}
    model_mode = str(os.environ.get("BROWSER_AGENT_CHATGPT_MODEL_MODE") or "thinking").strip().lower()
    tool_mode = str(os.environ.get("BROWSER_AGENT_CHATGPT_TOOL_MODE") or "none").strip().lower()
    require_deep_research = str(os.environ.get("BROWSER_AGENT_CHATGPT_REQUIRE_DEEP_RESEARCH") or "false").strip().lower() in {"1", "true", "yes", "on"}
    require_ui_mode = str(os.environ.get("BROWSER_AGENT_CHATGPT_REQUIRE_UI_MODE") or "false").strip().lower() in {"1", "true", "yes", "on"}
    account_email = str(os.environ.get("BROWSER_AGENT_CHATGPT_ACCOUNT_EMAIL") or "").strip()
    headless = str(os.environ.get("BROWSER_AGENT_HEADLESS") or "false").strip().lower() in {"1", "true", "yes", "on"}
    allowed_domains = [
        item.strip()
        for item in str(os.environ.get("BROWSER_AGENT_ALLOWED_DOMAINS") or ",".join(DEFAULT_ALLOWED_DOMAINS)).split(",")
        if item.strip()
    ]

    staged_dir, cleanup_dir = bjrt._stage_browser_profile(user_data_dir, profile_directory)
    if user_data_dir and not staged_dir:
        raise RuntimeError("protected_browser_profile_cache_missing")

    meta = {
        "provider": "browser_agent_chatgpt",
        "model": model,
        "reasoning_effort": reasoning_effort,
        "expected_output": expected,
        "target_url": target_url,
        "action": action,
        "profile_directory": profile_directory,
        "headless": headless,
        "allowed_domains": allowed_domains,
        "project_name": project_name,
        "require_project": require_project,
        "open_project_first": open_project_first,
        "model_mode": model_mode,
        "tool_mode": tool_mode,
        "require_deep_research": require_deep_research,
        "require_ui_mode": require_ui_mode,
        "account_email_hint_present": bool(account_email),
        "request_dir": str(request_dir),
        "started_at": bjrt._now(),
    }
    _write_json(request_dir / "wrapper-meta.json", meta)

    browser = BrowserSession(
        browser_profile=BrowserProfile(
            headless=headless,
            user_data_dir=staged_dir,
            profile_directory=profile_directory,
            allowed_domains=allowed_domains,
        )
    )
    try:
        await asyncio.wait_for(browser.start(), timeout=40)
        page = await asyncio.wait_for(browser.get_current_page(), timeout=15)
        if page is None:
            page = await asyncio.wait_for(browser.new_page(), timeout=15)
        try:
            await asyncio.wait_for(page.goto(target_url), timeout=30)
        except Exception:
            await asyncio.wait_for(page.navigate(target_url), timeout=30)
        try:
            ready = await _wait_for_ready(page, timeout_s=90)
        except Exception:
            try:
                html = await page.evaluate(HTML_JS)
                page_text = await page.evaluate(TEXT_JS)
                title = await page.get_title()
                final_url = await page.get_url()
                screenshot_b64 = await page.screenshot(format="png")
                (request_dir / "debug-ready-page.html").write_text(str(html or ""), encoding="utf-8")
                (request_dir / "debug-ready-page.txt").write_text(str(page_text or "") + "\n", encoding="utf-8")
                _write_json(request_dir / "debug-ready-page.json", {"title": title, "url": final_url})
                if screenshot_b64:
                    (request_dir / "debug-ready-page.png").write_bytes(base64.b64decode(screenshot_b64))
            except Exception:
                pass
            raise
        _write_json(request_dir / "ready-state.json", ready)
        if action in {"poll", "collect"}:
            final_data = json.loads(await page.evaluate(CAPTURE_JS))
            if final_data.get("is_generating") or not str(final_data.get("latest_assistant_text") or "").strip():
                _write_json(request_dir / f"{action}-state.json", {
                    "ok": True,
                    "status": "running" if final_data.get("is_generating") else "submitted",
                    "url": final_data.get("url"),
                    "conversation_id": final_data.get("conversation_id"),
                    "assistant_count": final_data.get("assistant_count"),
                    "message_count": final_data.get("message_count"),
                    "checked_at": bjrt._now(),
                })
                print(json.dumps({
                    "status": "running" if final_data.get("is_generating") else "submitted",
                    "url": final_data.get("url"),
                    "conversation_id": final_data.get("conversation_id"),
                }, ensure_ascii=False))
                return 0
            if action == "collect":
                try:
                    final_data = await _wait_for_answer(
                        page,
                        -1,
                        timeout_s=int(os.environ.get("BROWSER_AGENT_CHATGPT_COLLECT_TIMEOUT") or "45"),
                    )
                except TimeoutError:
                    final_data = json.loads(await page.evaluate(CAPTURE_JS))
            latest = await _write_conversation_artifacts(
                page,
                request_dir,
                final_data,
                model=model,
                reasoning_effort=reasoning_effort,
                prompt=None,
            )
            if latest and not final_data.get("is_generating"):
                _write_json(request_dir / f"{action}-state.json", {
                    "ok": True,
                    "status": "done",
                    "url": final_data.get("url"),
                    "conversation_id": final_data.get("conversation_id"),
                    "assistant_count": final_data.get("assistant_count"),
                    "message_count": final_data.get("message_count"),
                    "checked_at": bjrt._now(),
                })
                print(latest)
                return 0
            _write_json(request_dir / f"{action}-state.json", {
                "ok": True,
                "status": "running",
                "url": final_data.get("url"),
                "conversation_id": final_data.get("conversation_id"),
                "checked_at": bjrt._now(),
            })
            print(json.dumps({
                "status": "running",
                "url": final_data.get("url"),
                "conversation_id": final_data.get("conversation_id"),
            }, ensure_ascii=False))
            return 0
        if open_project_first and project_name:
            project_open = await _open_project_new_chat(page, project_name)
            _write_json(request_dir / "project-open-result.json", project_open)
            if require_project and not project_open.get("ok"):
                raise RuntimeError(f"chatgpt_project_open_failed: {project_open.get('error')}")
            if project_open.get("ok"):
                ready = await _wait_for_ready(page, timeout_s=45)
                _write_json(request_dir / "ready-state-after-project-open.json", ready)
        configure_result = await _configure_chatgpt_ui(
            page,
            model_mode=model_mode,
            reasoning_effort=reasoning_effort,
            tool_mode=tool_mode,
        )
        _write_json(request_dir / "chatgpt-ui-configure-result.json", configure_result)
        if require_ui_mode:
            mode_state = await _verify_chatgpt_mode_enabled(
                page,
                model_mode=model_mode,
                reasoning_effort=reasoning_effort,
            )
            _write_json(request_dir / "chatgpt-mode-state.json", mode_state)
            if not mode_state.get("ok"):
                raise RuntimeError(
                    "chatgpt_required_ui_mode_not_confirmed: "
                    + json.dumps(mode_state, ensure_ascii=False)
                )
        if require_deep_research or tool_mode == "deep_research" or reasoning_effort == "deep_research":
            deep_research_state = await _verify_deep_research_enabled(page)
            _write_json(request_dir / "deep-research-state.json", deep_research_state)
            if not deep_research_state.get("ok"):
                raise RuntimeError(
                    "chatgpt_deep_research_not_confirmed: "
                    + json.dumps(deep_research_state, ensure_ascii=False)
                )
        baseline_assistant_count = int(ready.get("assistant_count") or 0)
        post_submit = await _submit_prompt(page, prompt)
        _write_json(request_dir / "post-submit-state.json", post_submit)
        if action == "submit":
            submitted = {
                "ok": True,
                "status": "running" if post_submit.get("is_generating") else "submitted",
                "url": post_submit.get("url"),
                "conversation_id": post_submit.get("conversation_id"),
                "message_count": post_submit.get("message_count"),
                "assistant_count": post_submit.get("assistant_count"),
                "submitted_at": bjrt._now(),
            }
            _write_json(request_dir / "submitted-run.json", submitted)
            print(json.dumps(submitted, ensure_ascii=False))
            return 0
        final_data = await _wait_for_answer(page, baseline_assistant_count, timeout_s=timeout_s)
        latest = await _write_conversation_artifacts(
            page,
            request_dir,
            final_data,
            model=model,
            reasoning_effort=reasoning_effort,
            prompt=prompt,
        )
        if not latest:
            raise RuntimeError("chatgpt_latest_assistant_text_empty")

        if project_name:
            project_result = await _move_current_conversation_to_project(page, project_name)
            _write_json(request_dir / "project-archive-result.json", project_result)
            if require_project and not project_result.get("ok"):
                raise RuntimeError(f"chatgpt_project_archive_failed: {project_result.get('error')}")

        print(latest)
        return 0
    finally:
        try:
            await asyncio.wait_for(browser.stop(), timeout=20)
        except Exception:
            pass
        _kill_browser_profile_processes(staged_dir)
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def main() -> int:
    _quiet_browser_logs()
    prompt = _prompt_from_stdin()
    try:
        return asyncio.run(_run(prompt))
    except Exception as exc:
        request_dir = _request_dir()
        try:
            (request_dir / "debug-note.txt").write_text(
                "Wrapper failed before final response completion. Inspect ready-state.json / page.* / conversation.* if present.\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        _write_json(request_dir / "wrapper-error.json", {
            "error_type": type(exc).__name__,
            "error": str(exc),
            "failed_at": bjrt._now(),
        })
        print(f"browser_agent_chatgpt_wrapper failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
