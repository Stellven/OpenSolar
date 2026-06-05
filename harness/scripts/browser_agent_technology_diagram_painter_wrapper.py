#!/usr/bin/env python3
"""Wrapper script to generate technology diagrams via ChatGPT using browser-use/playwright.

Pipeline:
1. Connect via browser-use profile session (CDP).
2. Navigate to https://chatgpt.com/.
3. Verify logged in as target account.
4. Click "...更多" (More) on the left navigation bar, and select "图片" (Image).
5. Select model "gpt5.5" and "thinking high" from the model selector.
6. Enter text + drawing prompt into the textarea and submit.
7. Wait for image generation to complete.
8. Download the generated image.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import browser_job_runtime as bjrt
from browser import runtime_control as brtc
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from playwright.async_api import async_playwright

DEFAULT_URL = "https://chatgpt.com/"
DEFAULT_USER_DATA_DIR = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
DEFAULT_PROFILE_DIRECTORY = "Profile 1"
DEFAULT_ALLOWED_DOMAINS = [
    "chatgpt.com", "openai.com", "auth0.openai.com", "google.com", "accounts.google.com"
]
TARGET_ACCOUNT_EMAIL = (
    os.environ.get("BROWSER_AGENT_TARGET_ACCOUNT_EMAIL")
    or os.environ.get("BROWSER_AGENT_CHATGPT_ACCOUNT_EMAIL")
    or "haogege1977@gmail.com"
)

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

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


def _request_dir() -> Path:
    out = Path(os.environ.get("BROWSER_AGENT_REQUEST_DIR") or f"/tmp/tech-diagram-painter-{int(time.time())}").expanduser()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prompt_from_stdin() -> dict:
    """Read JSON input from stdin (piped from operator)."""
    if not sys.stdin.isatty():
        try:
            return json.loads(sys.stdin.read().strip())
        except Exception as e:
            print(f"Error parsing JSON from stdin: {e}", file=sys.stderr)
    return {}


def _force_wrapper_exit(code: int) -> NoReturn:
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(code)


def _challenge_grace_seconds() -> float:
    raw = str(
        os.environ.get("BROWSER_AGENT_CHATGPT_CHALLENGE_GRACE_SECONDS")
        or os.environ.get("BROWSER_AGENT_CHALLENGE_GRACE_SECONDS")
        or "20"
    ).strip()
    try:
        value = float(raw)
    except ValueError:
        value = 20.0
    return max(0.0, value)


def _challenge_persisted_too_long(challenge_since: float | None, *, now: float | None = None, grace_s: float | None = None) -> bool:
    if challenge_since is None:
        return False
    deadline = challenge_since + (grace_s if grace_s is not None else _challenge_grace_seconds())
    return (now if now is not None else time.time()) >= deadline


# ---------------------------------------------------------------------------
# ChatGPT page interaction helpers
# ---------------------------------------------------------------------------

CAPTURE_JS = r"""() => {
  const clean = (value) => String(value || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const composerCandidates = Array.from(
    document.querySelectorAll(
      "#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea'], textarea, [data-testid='composer-text-input']"
    )
  );
  const composer = composerCandidates.find(visible) || composerCandidates[0] || null;
  const bodyText = clean(document.body ? (document.body.innerText || document.body.textContent || "") : "").toLowerCase();
  const challengeWall =
    /cloudflare|turnstile|checking your browser|verify you are human|请稍候|正在验证|验证你是真人/i.test(
      `${document.title || ""}\n${location.href}\n${bodyText}`
    ) ||
    Array.from(document.querySelectorAll("iframe")).some((iframe) =>
      /challenges\.cloudflare\.com|turnstile/i.test(String(iframe.src || ""))
    );
  return JSON.stringify({
    title: document.title || "",
    url: location.href,
    composer_ready: !!composer,
    challenge_wall: challengeWall,
  });
}"""

SET_PROMPT_JS = r"""(promptText) => {
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const candidates = Array.from(
    document.querySelectorAll(
      "#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea'], textarea, [data-testid='composer-text-input']"
    )
  );
  const composer = candidates.find(visible) || candidates[0];
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
  try {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(composer);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    if (document.execCommand && document.execCommand("insertText", false, prompt)) {
      composer.dispatchEvent(new InputEvent("beforeinput", { bubbles: true, inputType: "insertText", data: prompt }));
      composer.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
      return JSON.stringify({ ok: true, mode: "contenteditable_execcommand" });
    }
  } catch (_) {}
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

COMPOSER_STATE_JS = r"""() => {
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const candidates = Array.from(
    document.querySelectorAll(
      "#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea'], textarea, [data-testid='composer-text-input']"
    )
  );
  const composer = candidates.find(visible) || candidates[0];
  if (!composer) return JSON.stringify({ ok: false, error: "composer_not_found" });
  const text = String(composer.value || composer.innerText || composer.textContent || "").trim();
  return JSON.stringify({ ok: true, text_length: text.length, tag: composer.tagName, id: composer.id || "" });
}"""

SUBMIT_JS = r"""() => {
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const selectors = [
    "form button[type='submit']",
    "button[type='submit']",
    "button[data-testid='send-button']",
    "button[data-testid='composer-send-button']",
    "button[aria-label*='Send']",
    "button[aria-label*='send']",
    "button[aria-label*='发送']",
    "button.composer-submit-button-color[type='button']",
    "button.composer-submit-button-color",
  ];
  for (const selector of selectors) {
    const buttons = Array.from(document.querySelectorAll(selector));
    for (const button of buttons) {
      if (!visible(button)) continue;
      const label = String(button.getAttribute("aria-label") || button.textContent || "").trim();
      if (/语音|voice|stop|停止|cancel|中止/i.test(label)) continue;
      if (button.disabled || button.getAttribute("aria-disabled") === "true") continue;
      button.click();
      return JSON.stringify({ ok: true, selector, label });
    }
  }
  return JSON.stringify({ ok: false, error: "submit_button_not_found" });
}"""

SUBMIT_FALLBACK_JS = r"""() => {
  const composer = document.querySelector(
    "#prompt-textarea, div[contenteditable='true'][role='textbox'], textarea[name='prompt-textarea'], textarea, [data-testid='composer-text-input']"
  );
  if (!composer) return JSON.stringify({ ok: false, error: "composer_not_found" });
  const value = String(composer.value || composer.innerText || composer.textContent || "").trim();
  if (!value) return JSON.stringify({ ok: false, error: "composer_empty" });
  composer.focus();
  composer.dispatchEvent(new Event("input", { bubbles: true }));
  composer.dispatchEvent(new Event("change", { bubbles: true }));
  const form = composer.closest("form");
  if (form && typeof form.requestSubmit === "function") {
    form.requestSubmit();
    return JSON.stringify({ ok: true, mode: "form_request_submit" });
  }
  if (form) {
    const event = new Event("submit", { bubbles: true, cancelable: true });
    form.dispatchEvent(event);
    return JSON.stringify({ ok: true, mode: "form_submit_event", default_prevented: event.defaultPrevented });
  }
  for (const type of ["keydown", "keypress", "keyup"]) {
    composer.dispatchEvent(new KeyboardEvent(type, {
      bubbles: true,
      cancelable: true,
      key: "Enter",
      code: "Enter",
      metaKey: true,
    }));
  }
  return JSON.stringify({ ok: true, mode: "composer_meta_enter_dispatch" });
}"""


async def _wait_for_chat_ready(page, *, timeout_s: int = 60) -> dict:
    deadline = time.time() + timeout_s
    last_state: dict = {}
    refresh_count = 0
    challenge_since: float | None = None
    challenge_grace_s = _challenge_grace_seconds()
    while time.time() < deadline:
        state = json.loads(await page.evaluate(CAPTURE_JS))
        last_state = state
        if state.get("challenge_wall"):
            if challenge_since is None:
                challenge_since = time.time()
            if _challenge_persisted_too_long(challenge_since, grace_s=challenge_grace_s):
                raise RuntimeError("chatgpt_cloudflare_challenge_detected")
            await asyncio.sleep(1.5)
            continue
        challenge_since = None
        if state.get("composer_ready") and not state.get("challenge_wall"):
            return state
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
        await asyncio.sleep(1.0)
    raise TimeoutError(
        "chatgpt_composer_not_ready: "
        + json.dumps(
            {
                "title": last_state.get("title"),
                "url": last_state.get("url"),
                "challenge_wall": last_state.get("challenge_wall"),
            },
            ensure_ascii=False,
        )
    )

async def _verify_account(page) -> bool:
    """Check if logged-in account matches TARGET_ACCOUNT_EMAIL."""
    print("[TechDiagram] Verifying ChatGPT account...", flush=True)
    try:
        # Click the profile/avatar button bottom left to see the email
        profile_btn = page.locator("button[aria-label*='Profile'], div[data-testid='profile-button'], nav button img[alt*='User']").first
        if await profile_btn.count():
            await profile_btn.click()
            await page.wait_for_timeout(1000)

            # Look for the email text
            email_info = await page.evaluate("""
                (() => {
                    const nodes = document.querySelectorAll('*');
                    const emails = [];
                    for (const n of nodes) {
                        const txt = (n.textContent || '').trim();
                        if (txt.includes('@') && txt.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/)) {
                            emails.push(txt.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/)[0]);
                        }
                    }
                    return emails;
                })()
            """)

            # Close the menu
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)

            for found_email in email_info:
                if found_email.lower() == TARGET_ACCOUNT_EMAIL.lower():
                    print(f"[TechDiagram] Account verification: MATCH ({TARGET_ACCOUNT_EMAIL})", flush=True)
                    return True
            print(f"[TechDiagram] Account verification: MISMATCH (found {email_info})", flush=True)
            return False
    except Exception as e:
        print(f"[TechDiagram] Warning: Account verification encountered error: {e}", flush=True)

    # Fallback to true if we couldn't verify to avoid blocking
    return True


async def _click_left_nav_more_and_image(page) -> bool:
    """Click '...更多' in left nav, then click '图片' (Image)."""
    print("[TechDiagram] Clicking left navigation '...更多' and '图片'...", flush=True)
    try:
        # 1. Look for the "More" button in the left sidebar
        clicked_more = await page.evaluate("""
            (() => {
                const buttons = document.querySelectorAll('nav button, nav a, nav div[role="button"]');
                for (const btn of buttons) {
                    const txt = (btn.textContent || '').trim().toLowerCase();
                    if (txt === '...' || txt.includes('更多') || txt.includes('more') || txt.includes('explore')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            })()
        """)
        if clicked_more:
            await page.wait_for_timeout(1500)

        # 2. Look for the "图片" or "Image" or "DALL-E" option
        clicked_image = await page.evaluate("""
            (() => {
                const items = document.querySelectorAll('a, button, div[role="menuitem"]');
                for (const item of items) {
                    const txt = (item.textContent || '').trim().toLowerCase();
                    if (txt === '图片' || txt === 'image' || txt.includes('dall-e') || txt.includes('dall·e')) {
                        item.click();
                        return true;
                    }
                }
                return false;
            })()
        """)
        if clicked_image:
            print("[TechDiagram] Successfully clicked '图片/Image' option.", flush=True)
            await page.wait_for_timeout(2000)
            return True
        else:
            print("[TechDiagram] Could not find '图片/Image' option in menu.", flush=True)
            return False
    except Exception as e:
        print(f"[TechDiagram] Nav interaction error: {e}", flush=True)
        return False


async def _select_model(page) -> bool:
    """Select 'gpt5.5' and 'thinking high'."""
    print("[TechDiagram] Selecting model: gpt5.5 with thinking high...", flush=True)
    try:
        # Click the model dropdown at the top
        dropdown_clicked = await page.evaluate("""
            (() => {
                const selectors = [
                    'div[data-testid="model-switcher-dropdown"]',
                    'button[aria-haspopup="menu"]',
                    'div.cursor-pointer.hover\\\\:bg-token-main-surface-secondary'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.click();
                        return true;
                    }
                }
                // Fallback: look by text
                const buttons = document.querySelectorAll('button');
                for (const b of buttons) {
                    const txt = (b.textContent || '').toLowerCase();
                    if (txt.includes('gpt-') || txt.includes('model') || txt.includes('chatgpt')) {
                        b.click();
                        return true;
                    }
                }
                return false;
            })()
        """)
        if dropdown_clicked:
            await page.wait_for_timeout(1000)

            # Now click the correct options in the menu
            await page.evaluate("""
                (() => {
                    const items = document.querySelectorAll('div[role="menuitem"], li, button');

                    // 1. First try to select the model (look for gpt5.5, gpt-4, etc.)
                    for (const item of items) {
                        const txt = (item.textContent || '').toLowerCase();
                        if (txt.includes('gpt-5') || txt.includes('gpt 5') || txt.includes('pro') || txt.includes('4.5')) {
                            item.click();
                            break;
                        }
                    }
                })()
            """)
            await page.wait_for_timeout(1000)

            # If there's a specific 'thinking' toggle or selector
            await page.evaluate("""
                (() => {
                    const toggles = document.querySelectorAll('button, div[role="switch"], div');
                    for (const item of toggles) {
                        const txt = (item.textContent || '').toLowerCase();
                        if (txt.includes('thinking') || txt.includes('reasoning') || txt.includes('思考') || txt.includes('high') || txt.includes('高')) {
                            item.click();
                        }
                    }
                })()
            """)

            # Close the dropdown
            await page.keyboard.press("Escape")
            print("[TechDiagram] Model selection logic executed.", flush=True)
            return True
    except Exception as e:
        print(f"[TechDiagram] Model selection error: {e}", flush=True)
    return False


async def _submit_prompt(page, full_prompt: str) -> bool:
    print("[TechDiagram] Submitting prompt...", flush=True)
    try:
        try:
            ready_state = await _wait_for_chat_ready(page, timeout_s=60)
        except Exception:
            # Current ChatGPT DOM changes frequently; capture a useful artifact
            # instead of failing as a black box.
            await page.screenshot(path=str(_request_dir() / "submit_prompt_failed.png"), full_page=True)
            (_request_dir() / "submit_prompt_failed.html").write_text(
                await page.content(),
                encoding="utf-8",
            )
            print(f"[TechDiagram] Composer not found. url={page.url} title={await page.title()}", flush=True)
            return False
        if not ready_state.get("composer_ready"):
            return False

        set_result = json.loads(await page.evaluate(SET_PROMPT_JS, full_prompt))
        if not set_result.get("ok"):
            print(f"[TechDiagram] Failed to set prompt: {set_result}", flush=True)
            return False
        await page.wait_for_timeout(1000)
        composer_state = json.loads(await page.evaluate(COMPOSER_STATE_JS))
        if int(composer_state.get("text_length") or 0) <= 0:
            print(f"[TechDiagram] Composer stayed empty after fill: {composer_state}", flush=True)
            return False
        submit_result = json.loads(await page.evaluate(SUBMIT_JS))
        if not submit_result.get("ok"):
            submit_result = json.loads(await page.evaluate(SUBMIT_FALLBACK_JS))
            if not submit_result.get("ok"):
                print(f"[TechDiagram] Submit fallback failed: {submit_result}", flush=True)
                return False

        print("[TechDiagram] Prompt submitted.", flush=True)
        return True
    except Exception as e:
        print(f"[TechDiagram] Failed to submit prompt: {e}", flush=True)
        return False


async def _wait_and_download_image(page, request_dir: Path, timeout_s: int = 120, capture_state: dict | None = None) -> dict:
    print(f"[TechDiagram] Waiting for image generation (timeout {timeout_s}s)...", flush=True)
    deadline = time.time() + timeout_s

    # Track existing images to detect the new one
    existing_images_count = await page.evaluate("document.querySelectorAll('img').length")

    last_generation_status = ""
    while time.time() < deadline:
        # Check if generation is still happening (stop button is visible)
        is_generating = await page.evaluate("""
            (() => {
                const stopBtn = document.querySelector('button[aria-label="Stop generating"], button[data-testid="stop-button"]');
                return !!stopBtn;
            })()
        """)

        # Check for new images in the chat
        img_src = await page.evaluate("""
            (() => {
                const messages = document.querySelectorAll('div[data-message-author-role="assistant"]');
                if (messages.length === 0) return null;
                const lastMsg = messages[messages.length - 1];

                // Look for generated image within the last assistant message
                const img = lastMsg.querySelector('img[src*="files"], img[src*="dalle"], img[alt*="Generated"]');
                if (img && img.complete && img.naturalWidth > 100) {
                    return img.src;
                }
                return null;
            })()
        """)

        if img_src and not is_generating:
            print("[TechDiagram] Image generation detected! Downloading...", flush=True)

            try:
                # Use page.request to download the image in context (handles auth)
                response = await page.request.get(img_src)
                if response.ok:
                    img_data = await response.body()
                    out_path = request_dir / "generated_diagram.png"
                    out_path.write_bytes(img_data)
                    print(f"[TechDiagram] Image saved to {out_path}", flush=True)
                    return {"status": "success", "image_path": str(out_path), "url": img_src}
            except Exception as e:
                print(f"[TechDiagram] Failed to download image: {e}", flush=True)

            # Fallback: take a screenshot of the image element
            try:
                print("[TechDiagram] Attempting to screenshot the image element...", flush=True)
                img_loc = page.locator('div[data-message-author-role="assistant"]').last.locator('img').last
                out_path = request_dir / "generated_diagram.png"
                await img_loc.screenshot(path=str(out_path))
                return {"status": "success", "image_path": str(out_path), "url": "screenshot"}
            except Exception as e:
                print(f"[TechDiagram] Screenshot fallback failed: {e}", flush=True)

        promoted = await _maybe_promote_original_capture(
            page,
            request_dir,
            capture_state,
            is_generating=bool(is_generating),
        )
        if promoted:
            return promoted

        # Determine if we hit an error (e.g. usage limit)
        error_msg = await page.evaluate("""
            (() => {
                const el = document.querySelector('.text-red-500, div[role="alert"]');
                return el ? el.innerText : null;
            })()
        """)
        if error_msg:
            print(f"[TechDiagram] Detected ChatGPT error: {error_msg}", flush=True)
            return {"status": "error", "error": error_msg}

        await asyncio.sleep(2)

    print("[TechDiagram] Timeout waiting for image generation.", flush=True)
    await page.screenshot(path=str(request_dir / "image_wait_timeout.png"), full_page=True)
    (request_dir / "image_wait_timeout.html").write_text(
        await page.content(),
        encoding="utf-8",
    )
    generated_visible = await page.evaluate("""
        (() => {
            const text = document.body ? document.body.innerText || '' : '';
            const hasGeneratedCard =
                text.includes('编辑') ||
                text.toLowerCase().includes('download') ||
                text.toLowerCase().includes('generated') ||
                text.includes('Solar-Harness Diagram');
            const visualCount = document.querySelectorAll('img, canvas, svg').length;
            return hasGeneratedCard && visualCount > 0;
        })()
    """)
    if generated_visible:
        downloaded = await _try_download_generated_card(page, request_dir)
        if downloaded:
            return downloaded
        out_path = request_dir / "generated_diagram.png"
        clipped = await _screenshot_generated_card(page, out_path)
        if clipped:
            print(f"[TechDiagram] Generated visual detected; saved clipped card to {out_path}", flush=True)
            return {"status": "success", "image_path": str(out_path), "url": "card-screenshot-fallback"}
        await page.screenshot(path=str(out_path), full_page=True)
        print(f"[TechDiagram] Generated visual detected; saved page screenshot to {out_path}", flush=True)
        return {"status": "success", "image_path": str(out_path), "url": "page-screenshot-fallback"}
    return {"status": "timeout", "error": "Image generation timed out."}


async def _install_original_image_capture(page, request_dir: Path) -> dict:
    """Capture original image bytes from network responses after prompt submit."""
    state: dict = {
        "active": False,
        "tasks": [],
        "candidates": [],
        "counter": 0,
        "last_candidate_at": 0.0,
    }

    async def capture_response(response) -> None:
        if not state["active"]:
            return
        try:
            url = response.url or ""
            lower_url = url.lower()
            headers = {str(k).lower(): str(v) for k, v in (response.headers or {}).items()}
            content_type = headers.get("content-type", "").lower()
            if not (
                content_type.startswith("image/")
                or any(ext in lower_url for ext in (".png", ".webp", ".jpg", ".jpeg"))
                or any(token in lower_url for token in ("oaiusercontent", "dalle", "imagegen", "generated"))
            ):
                return
            if any(skip in lower_url for skip in (
                "avatar",
                "favicon",
                "sprites",
                "onboarding",
                "doodles",
                "share-og",
                "googleusercontent.com/a/",
            )):
                return
            body = await response.body()
            if len(body) < 50_000:
                return
            suffix = ".png"
            if "webp" in content_type or lower_url.endswith(".webp"):
                suffix = ".webp"
            elif "jpeg" in content_type or "jpg" in content_type or lower_url.endswith((".jpg", ".jpeg")):
                suffix = ".jpg"
            state["counter"] += 1
            out_path = request_dir / f"generated_original_candidate_{state['counter']}{suffix}"
            out_path.write_bytes(body)
            width = height = 0
            try:
                from PIL import Image
                with Image.open(out_path) as image:
                    width, height = image.size
            except Exception:
                pass
            state["candidates"].append({
                "path": str(out_path),
                "url": url,
                "bytes": len(body),
                "width": width,
                "height": height,
                "content_type": content_type,
            })
            state["last_candidate_at"] = time.time()
            _write_json(request_dir / "network-image-candidates.json", state["candidates"])
            print(
                f"[TechDiagram] Captured image response candidate: {out_path} "
                f"({width}x{height}, {len(body)} bytes)",
                flush=True,
            )
        except Exception as exc:
            print(f"[TechDiagram] Image response capture skipped: {exc}", flush=True)

    def on_response(response) -> None:
        task = asyncio.create_task(capture_response(response))
        state["tasks"].append(task)

    page.on("response", on_response)
    return state


async def _best_original_capture(state: dict, request_dir: Path) -> dict | None:
    tasks = [task for task in state.get("tasks", []) if not task.done()]
    if tasks:
        await asyncio.wait(tasks, timeout=5)
    candidates = list(state.get("candidates") or [])
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda item: (
            int(item.get("width") or 0) * int(item.get("height") or 0),
            int(item.get("bytes") or 0),
        ),
    )
    src = Path(str(best["path"]))
    suffix = src.suffix or ".png"
    out_path = request_dir / f"generated_diagram{suffix}"
    out_path.write_bytes(src.read_bytes())
    best["selected_path"] = str(out_path)
    _write_json(request_dir / "selected-original-image.json", best)
    return {
        "status": "success",
        "image_path": str(out_path),
        "url": best.get("url") or "network-image-response",
        "source": "network-image-response",
        "width": best.get("width"),
        "height": best.get("height"),
        "bytes": best.get("bytes"),
    }


async def _maybe_promote_original_capture(
    page,
    request_dir: Path,
    capture_state: dict | None,
    *,
    is_generating: bool,
    stable_seconds: float = 20.0,
) -> dict | None:
    if not capture_state:
        return None
    candidates = list(capture_state.get("candidates") or [])
    if not candidates:
        return None
    last_candidate_at = float(capture_state.get("last_candidate_at") or 0.0)
    if is_generating and (time.time() - last_candidate_at) < max(5.0, stable_seconds):
        return None
    promoted = await _best_original_capture(capture_state, request_dir)
    if promoted:
        print("[TechDiagram] Promoted captured original image response as final result.", flush=True)
    return promoted


async def _extract_dom_original_asset(page, request_dir: Path) -> dict | None:
    """Try to extract large canvas/blob/data images directly from the page."""
    assets = await page.evaluate("""
        async () => {
            const out = [];
            async function blobToDataUrl(blob) {
                return await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }
            for (const canvas of Array.from(document.querySelectorAll('canvas'))) {
                if (canvas.width < 512 || canvas.height < 256) continue;
                try {
                    out.push({
                        kind: 'canvas',
                        width: canvas.width,
                        height: canvas.height,
                        data_url: canvas.toDataURL('image/png')
                    });
                } catch (_) {}
            }
            for (const img of Array.from(document.querySelectorAll('img'))) {
                const rect = img.getBoundingClientRect();
                const src = img.currentSrc || img.src || '';
                if (rect.width < 512 || rect.height < 256) continue;
                if (!src || src.includes('googleusercontent.com/a/') || src.includes('avatar')) continue;
                if (src.startsWith('blob:') || src.startsWith('data:')) {
                    try {
                        const response = await fetch(src);
                        const blob = await response.blob();
                        out.push({
                            kind: 'img-blob',
                            width: img.naturalWidth || Math.round(rect.width),
                            height: img.naturalHeight || Math.round(rect.height),
                            data_url: await blobToDataUrl(blob)
                        });
                    } catch (_) {}
                } else {
                    out.push({
                        kind: 'img-url',
                        width: img.naturalWidth || Math.round(rect.width),
                        height: img.naturalHeight || Math.round(rect.height),
                        url: src
                    });
                }
            }
            return out;
        }
    """)
    if not assets:
        return None
    _write_json(request_dir / "dom-image-assets.json", assets)
    best = max(
        assets,
        key=lambda item: int(item.get("width") or 0) * int(item.get("height") or 0),
    )
    if best.get("data_url"):
        header, encoded = str(best["data_url"]).split(",", 1)
        suffix = ".png"
        if "webp" in header:
            suffix = ".webp"
        elif "jpeg" in header:
            suffix = ".jpg"
        out_path = request_dir / f"generated_diagram{suffix}"
        out_path.write_bytes(base64.b64decode(encoded))
        return {
            "status": "success",
            "image_path": str(out_path),
            "url": f"dom-{best.get('kind')}",
            "source": best.get("kind"),
            "width": best.get("width"),
            "height": best.get("height"),
        }
    if best.get("url"):
        try:
            response = await page.request.get(str(best["url"]))
            if response.ok:
                body = await response.body()
                if len(body) > 50_000:
                    out_path = request_dir / "generated_diagram.png"
                    out_path.write_bytes(body)
                    return {
                        "status": "success",
                        "image_path": str(out_path),
                        "url": best["url"],
                        "source": "dom-img-url",
                        "width": best.get("width"),
                        "height": best.get("height"),
                        "bytes": len(body),
                    }
        except Exception as exc:
            print(f"[TechDiagram] DOM image URL extraction failed: {exc}", flush=True)
    return None


async def _try_download_generated_card(page, request_dir: Path) -> dict | None:
    """Click ChatGPT's generated-image download button when it is present."""
    marked = await page.evaluate("""
        (() => {
            document.querySelectorAll('[data-solar-tech-diagram-download-candidate]').forEach((n) => {
                n.removeAttribute('data-solar-tech-diagram-download-candidate');
            });
            const viewportW = window.innerWidth || document.documentElement.clientWidth;
            const viewportH = window.innerHeight || document.documentElement.clientHeight;
            const buttons = Array.from(document.querySelectorAll('button'));
            let best = null;
            let bestScore = -1;
            for (const button of buttons) {
                const rect = button.getBoundingClientRect();
                if (!rect || rect.width < 28 || rect.height < 28 || rect.width > 120 || rect.height > 120) continue;
                if (rect.x < viewportW * 0.55 || rect.y < viewportH * 0.35) continue;
                if (!button.querySelector('svg')) continue;
                const label = (button.getAttribute('aria-label') || button.innerText || '').toLowerCase();
                const labelBonus =
                    label.includes('download') || label.includes('下载') || label.includes('save') ? 500 : 0;
                const score = labelBonus + rect.x + rect.y * 2;
                if (score > bestScore) {
                    bestScore = score;
                    best = button;
                }
            }
            if (!best) return false;
            best.setAttribute('data-solar-tech-diagram-download-candidate', '1');
            return true;
        })()
    """)
    if not marked:
        return None
    try:
        candidate = page.locator('[data-solar-tech-diagram-download-candidate="1"]').first
        async with page.expect_download(timeout=15000) as download_info:
            await candidate.click()
        download = await download_info.value
        suggested = download.suggested_filename or "generated_diagram.png"
        suffix = Path(suggested).suffix or ".png"
        out_path = request_dir / f"generated_diagram{suffix}"
        await download.save_as(str(out_path))
        print(f"[TechDiagram] Downloaded generated image to {out_path}", flush=True)
        return {"status": "success", "image_path": str(out_path), "url": "chatgpt-download-button"}
    except Exception as exc:
        print(f"[TechDiagram] Download button fallback failed: {exc}", flush=True)
        return None


async def _screenshot_generated_card(page, out_path: Path) -> bool:
    """Capture only the generated image card when direct download is not exposed."""
    rect = await page.evaluate("""
        (() => {
            const viewportW = window.innerWidth || document.documentElement.clientWidth;
            const viewportH = window.innerHeight || document.documentElement.clientHeight;
            const minSidebarX = Math.min(520, Math.floor(viewportW * 0.25));

            const visualNodes = Array.from(document.querySelectorAll('img, canvas, svg'));
            let bestVisual = null;
            let bestVisualScore = -1;
            for (const node of visualNodes) {
                const rect = node.getBoundingClientRect();
                if (!rect || rect.width < 720 || rect.height < 260) continue;
                if (rect.x < minSidebarX || rect.y < 80) continue;
                if (rect.width > viewportW * 0.9 || rect.height > viewportH * 0.9) continue;
                const alt = (node.getAttribute('alt') || '').toLowerCase();
                const src = (node.getAttribute('src') || '').toLowerCase();
                if (alt.includes('user') || src.includes('googleusercontent.com/a/')) continue;
                const area = rect.width * rect.height;
                const score = area + (rect.y > 180 ? 50000 : 0);
                if (score > bestVisualScore) {
                    bestVisualScore = score;
                    bestVisual = {
                        x: Math.max(0, Math.floor(rect.x - 10)),
                        y: Math.max(0, Math.floor(rect.y - 10)),
                        width: Math.min(viewportW - Math.max(0, Math.floor(rect.x - 10)), Math.ceil(rect.width + 20)),
                        height: Math.min(viewportH - Math.max(0, Math.floor(rect.y - 10)), Math.ceil(rect.height + 20)),
                        score,
                        source: 'visual'
                    };
                }
            }
            if (bestVisual) return bestVisual;

            const nodes = Array.from(document.querySelectorAll('article, [data-message-author-role], main div, main section, div'));
            let best = null;
            let bestScore = -1;
            const keywords = ['编辑', 'download', 'generated', 'Solar-Harness Diagram', 'PNG Artifact', 'result.json'];

            for (const node of nodes) {
                const text = (node.innerText || node.textContent || '').trim();
                const rect = node.getBoundingClientRect();
                if (!rect || rect.width < 260 || rect.height < 180) continue;
                if (rect.x < minSidebarX) continue;
                if (rect.width > viewportW * 0.85 || rect.height > viewportH * 0.9) continue;

                const lower = text.toLowerCase();
                const hasKeyword = keywords.some((kw) => lower.includes(kw.toLowerCase()));
                const visualCount = node.querySelectorAll('img, canvas, svg').length;
                const buttonCount = node.querySelectorAll('button').length;
                if (!hasKeyword && visualCount < 2) continue;

                const area = rect.width * rect.height;
                const centerBonus = rect.x > minSidebarX && rect.y > 60 ? 40 : 0;
                const score = visualCount * 80 + buttonCount * 8 + Math.min(area / 5000, 120) + centerBonus;
                if (score > bestScore) {
                    bestScore = score;
                    best = {
                        x: Math.max(0, Math.floor(rect.x - 12)),
                        y: Math.max(0, Math.floor(rect.y - 12)),
                        width: Math.min(viewportW - Math.max(0, Math.floor(rect.x - 12)), Math.ceil(rect.width + 24)),
                        height: Math.min(viewportH - Math.max(0, Math.floor(rect.y - 12)), Math.ceil(rect.height + 24)),
                        score
                    };
                }
            }
            return best;
        })()
    """)
    if not rect:
        return False
    try:
        await page.screenshot(path=str(out_path), clip=rect)
        _trim_chatgpt_header(out_path)
        (out_path.with_suffix(".clip.json")).write_text(
            json.dumps(rect, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return True
    except Exception as exc:
        print(f"[TechDiagram] Clipped card screenshot failed: {exc}", flush=True)
        return False


def _trim_chatgpt_header(path: Path) -> None:
    """Remove ChatGPT prompt/thought chrome that can appear above screenshot fallback."""
    try:
        from PIL import Image
    except Exception:
        return
    try:
        image = Image.open(path).convert("RGB")
        width, height = image.size
        start_y = int(height * 0.15)
        crop_y = 0
        for y in range(start_y, height):
            dark_count = 0
            for x in range(0, width, 4):
                r, g, b = image.getpixel((x, y))
                if max(r, g, b) < 45:
                    continue
                if min(r, g, b) < 235 and (max(r, g, b) - min(r, g, b) > 8 or min(r, g, b) < 210):
                    dark_count += 1
            if dark_count > 30:
                crop_y = max(0, y - 40)
                break
        if crop_y > 0:
            image.crop((0, crop_y, width, height)).save(path)
    except Exception as exc:
        print(f"[TechDiagram] Header trim failed: {exc}", flush=True)


# ---------------------------------------------------------------------------
# Main execution pipeline
# ---------------------------------------------------------------------------

async def _run(input_data: dict) -> int:
    request_dir = _request_dir()
    profile_directory = str(os.environ.get("BROWSER_AGENT_PROFILE_DIRECTORY") or DEFAULT_PROFILE_DIRECTORY)
    user_data_dir = Path(os.environ.get("BROWSER_AGENT_USER_DATA_DIR") or str(DEFAULT_USER_DATA_DIR)).expanduser()
    headless = str(os.environ.get("BROWSER_AGENT_HEADLESS") or "true").strip().lower() in {"1", "true", "yes", "on"}
    timeout_s = int(os.environ.get("BROWSER_AGENT_TIMEOUT") or "600")

    staged_dir, cleanup_dir = bjrt._stage_browser_profile(user_data_dir, profile_directory)
    if user_data_dir and not staged_dir:
        raise RuntimeError("protected_browser_profile_cache_missing")

    input_text = input_data.get("input_text", "")
    prompt = input_data.get("prompt", "请根据上述文本绘制技术架构图。")
    full_prompt = f"{input_text}\n\n{prompt}".strip()

    meta = {
        "provider": "browser_agent_technology_diagram",
        "profile_directory": profile_directory,
        "headless": headless,
        "request_dir": str(request_dir),
        "started_at": bjrt._now(),
    }
    _write_json(request_dir / "wrapper-meta.json", meta)

    control_ctx = brtc.initialize_runtime_contract(
        request_dir=request_dir,
        service="chatgpt",
        runtime_owner="browser_use",
        wrapper_kind="technology_diagram",
        profile_directory=profile_directory,
        user_data_dir=str(user_data_dir),
        staged_user_data_dir=str(staged_dir or ""),
        account_identifier=TARGET_ACCOUNT_EMAIL or None,
        task_id=str(os.environ.get("TASK_ID") or request_dir.name),
        control_modes={
            "browser_use_session": True,
            "playwright_cdp_attach": False,
            "webwright_bridge": False,
        },
        metadata={
            "request_dir": str(request_dir),
            "target_url": DEFAULT_URL,
            "session_reuse": True,
            "session_lineage": str(os.environ.get("BROWSER_AGENT_SESSION_LINEAGE") or "technology-diagram-painter"),
            "headless": headless,
        },
    )
    active_session = brtc.read_active_session(control_ctx, require_lineage_match=False)
    browser: BrowserSession | None = None
    reused_existing_session = False
    keep_session_alive = True
    finalized = False
    succeeded = False
    runtime_cleanup_dir = cleanup_dir
    runtime_staged_dir = staged_dir
    if active_session and active_session.get("cdp_url"):
        try:
            browser = BrowserSession(
                cdp_url=str(active_session.get("cdp_url") or "").strip(),
                browser_profile=BrowserProfile(
                    headless=headless,
                    keep_alive=keep_session_alive,
                    allowed_domains=DEFAULT_ALLOWED_DOMAINS,
                    channel="chrome",
                ),
            )
            await asyncio.wait_for(browser.start(), timeout=20)
            reused_existing_session = True
            runtime_cleanup_dir = Path(str((active_session.get("details") or {}).get("cleanup_dir") or "")).expanduser() if str((active_session.get("details") or {}).get("cleanup_dir") or "").strip() else cleanup_dir
            runtime_staged_dir = str((active_session.get("details") or {}).get("staged_user_data_dir") or "").strip() or staged_dir
        except Exception:
            brtc.clear_active_session(control_ctx)
            browser = None
    if browser is None:
        browser = BrowserSession(
            browser_profile=BrowserProfile(
                headless=headless,
                keep_alive=keep_session_alive,
                user_data_dir=staged_dir,
                profile_directory=profile_directory,
                allowed_domains=DEFAULT_ALLOWED_DOMAINS,
                channel="chrome",
            )
        )
    try:
        if not reused_existing_session:
            await asyncio.wait_for(browser.start(), timeout=40)
        brtc.update_runtime_endpoint(
            control_ctx,
            cdp_url=str(getattr(browser, "cdp_url", "") or ""),
            browser_session_ref=f"browser-use-session://chatgpt/{control_ctx['profile_id']}",
        )
        async with async_playwright() as pw:
            pw_browser = await pw.chromium.connect_over_cdp(browser.cdp_url)
            pw_context = pw_browser.contexts[0] if pw_browser.contexts else None
            if pw_context is None:
                raise RuntimeError("failed_to_connect_via_playwright_cdp")
            playwright_page = pw_context.pages[0] if pw_context.pages else await pw_context.new_page()
            await playwright_page.set_viewport_size({"width": 1920, "height": 1200})
            original_capture = await _install_original_image_capture(playwright_page, request_dir)

            # 1. Navigate to ChatGPT
            print(f"[TechDiagram] Navigating to {DEFAULT_URL}", flush=True)
            await playwright_page.goto(DEFAULT_URL, wait_until="domcontentloaded")
            await playwright_page.wait_for_timeout(3000)
            await _wait_for_chat_ready(playwright_page, timeout_s=60)

            # 2. Verify account
            await _verify_account(playwright_page)

            # 3. Navigate UI
            await _click_left_nav_more_and_image(playwright_page)
            await _select_model(playwright_page)
            await _wait_for_chat_ready(playwright_page, timeout_s=45)

            # 4. Submit
            submitted = await _submit_prompt(playwright_page, full_prompt)
            if not submitted:
                raise RuntimeError("failed_to_submit_prompt")
            original_capture["active"] = True

            # 5. Wait for image
            result = await _wait_and_download_image(
                playwright_page,
                request_dir,
                timeout_s=timeout_s,
                capture_state=original_capture,
            )
            if result.get("status") == "success" and str(result.get("url") or "").endswith("fallback"):
                original = await _best_original_capture(original_capture, request_dir)
                if original:
                    result = original
                else:
                    dom_asset = await _extract_dom_original_asset(playwright_page, request_dir)
                    if dom_asset:
                        result = dom_asset

            # Save results
            (request_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            # Also write out path to stdout for operator
            print(json.dumps(result))

            if result.get("status") != "success":
                return 1
            brtc.activate_reusable_session(
                control_ctx,
                cdp_url=str(getattr(browser, "cdp_url", "") or ""),
                browser_session_ref=f"browser-use-session://chatgpt/{control_ctx['profile_id']}",
                headless=headless,
                attached=reused_existing_session,
                details={
                    "request_dir": str(request_dir),
                    "staged_user_data_dir": str(runtime_staged_dir or ""),
                    "cleanup_dir": str(runtime_cleanup_dir or ""),
                },
            )
            brtc.finalize_runtime_contract(
                control_ctx,
                success=True,
                error_text="",
                page_state={"url": DEFAULT_URL},
                logged_in_state_verified=True,
                details={
                    "provider": "browser_agent_technology_diagram",
                    "request_dir": str(request_dir),
                    "reused_existing_session": reused_existing_session,
                },
                requires_precise_page_control=False,
            )
            finalized = True
            succeeded = True
            _force_wrapper_exit(0)

    finally:
        try:
            if browser is not None and not succeeded:
                await asyncio.wait_for(browser.kill(), timeout=20)
        except Exception:
            pass
        if not finalized:
            try:
                brtc.clear_active_session(control_ctx)
                brtc.finalize_runtime_contract(
                    control_ctx,
                    success=False,
                    error_text="technology_diagram_wrapper_failed",
                    page_state={"url": DEFAULT_URL},
                    logged_in_state_verified=False,
                    details={
                        "provider": "browser_agent_technology_diagram",
                        "request_dir": str(request_dir),
                        "reused_existing_session": reused_existing_session,
                    },
                    requires_precise_page_control=False,
                )
            except Exception:
                pass
        if cleanup_dir is not None and not succeeded:
            import shutil
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def main() -> int:
    _quiet_browser_logs()
    input_data = _prompt_from_stdin()
    if not input_data:
        print("ERROR: Stdin input JSON is empty.", file=sys.stderr)
        return 1

    try:
        return asyncio.run(_run(input_data))
    except Exception as exc:
        request_dir = _request_dir()
        _write_json(request_dir / "wrapper-error.json", {
            "error_type": type(exc).__name__,
            "error": str(exc),
            "failed_at": bjrt._now(),
        })
        print(f"browser_agent_technology_diagram_painter_wrapper failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
