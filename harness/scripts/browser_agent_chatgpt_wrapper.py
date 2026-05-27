#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
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
    composer.value = prompt;
    composer.dispatchEvent(new Event("input", { bubbles: true }));
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


def _prompt_from_stdin() -> str:
    prompt = sys.stdin.read()
    if not prompt.strip():
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
    filled = False
    try:
        focused = json.loads(await page.evaluate(FOCUS_COMPOSER_JS))
        if focused.get("ok"):
            session_id = await page._ensure_session()
            await page._client.send.Input.insertText({"text": prompt}, session_id=session_id)
            filled = True
    except Exception:
        filled = False
    if not filled:
        result = json.loads(await page.evaluate(SET_PROMPT_JS, prompt))
        if not result.get("ok"):
            raise RuntimeError(result.get("error") or "prompt_injection_failed")
    await asyncio.sleep(0.6)
    submit_note = {"mode": "unknown"}
    clicked = False
    try:
        for selector in (
            "form button[type='submit']",
            "button[type='submit']",
            "button.composer-submit-button-color",
        ):
            buttons = await page.get_elements_by_css_selector(selector)
            if not buttons:
                continue
            try:
                await buttons[0].click()
                clicked = True
                submit_note = {"mode": "element_click", "selector": selector}
                break
            except Exception:
                continue
    except Exception:
        clicked = False
    if not clicked:
        submit_result = json.loads(await page.evaluate(SUBMIT_JS))
        if not submit_result.get("ok"):
            await page.press("Enter")
            submit_note = {"mode": "enter_key"}
        else:
            submit_note = {"mode": "js_submit", **submit_result}
    await asyncio.sleep(2.0)
    post_submit = json.loads(await page.evaluate(CAPTURE_JS))
    post_submit["_submit_note"] = submit_note
    return post_submit


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


async def _run(prompt: str) -> int:
    request_dir = _request_dir()
    expected = str(os.environ.get("BROWSER_AGENT_EXPECTED_OUTPUT") or "markdown").strip().lower()
    model = str(os.environ.get("CHATGPT_MODEL") or "chatgpt-5.5").strip()
    reasoning_effort = str(os.environ.get("CHATGPT_REASONING_EFFORT") or "high").strip().lower()
    profile_directory = str(os.environ.get("BROWSER_AGENT_PROFILE_DIRECTORY") or DEFAULT_PROFILE_DIRECTORY)
    user_data_dir = Path(os.environ.get("BROWSER_AGENT_USER_DATA_DIR") or str(DEFAULT_USER_DATA_DIR)).expanduser()
    target_url = str(os.environ.get("BROWSER_AGENT_CHATGPT_URL") or DEFAULT_URL)
    timeout_s = int(os.environ.get("BROWSER_AGENT_CHATGPT_TIMEOUT") or "1200")
    project_name = str(os.environ.get("BROWSER_AGENT_CHATGPT_PROJECT_NAME") or "").strip()
    require_project = str(os.environ.get("BROWSER_AGENT_CHATGPT_REQUIRE_PROJECT") or "false").strip().lower() in {"1", "true", "yes", "on"}
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
        "profile_directory": profile_directory,
        "headless": headless,
        "allowed_domains": allowed_domains,
        "project_name": project_name,
        "require_project": require_project,
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
        baseline_assistant_count = int(ready.get("assistant_count") or 0)
        post_submit = await _submit_prompt(page, prompt)
        _write_json(request_dir / "post-submit-state.json", post_submit)
        final_data = await _wait_for_answer(page, baseline_assistant_count, timeout_s=timeout_s)
        html = await page.evaluate(HTML_JS)
        page_text = await page.evaluate(TEXT_JS)
        title = await page.get_title()
        final_url = await page.get_url()
        screenshot_b64 = await page.screenshot(format="png")

        latest = str(final_data.get("latest_assistant_text") or "").strip()
        if not latest:
            raise RuntimeError("chatgpt_latest_assistant_text_empty")

        (request_dir / "prompt.md").write_text(prompt, encoding="utf-8")
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
            "model": model,
            "reasoning_effort": reasoning_effort,
        })
        if screenshot_b64:
            (request_dir / "screenshot.png").write_bytes(base64.b64decode(screenshot_b64))

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
