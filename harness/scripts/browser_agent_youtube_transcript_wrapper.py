#!/usr/bin/env python3
"""Wrapper script to extract YouTube video transcripts via browser-use/playwright.

Pipeline:
1. Connect via browser-use profile session (CDP).
2. Navigate to the YouTube video URL.
3. Verify logged in as target account (haogege1977@gmail.com).
4. Expand video description if collapsed.
5. Click "显示转写文稿" / "Show transcript" button to open transcript panel.
6. Wait for transcript segments to load.
7. Scroll through transcript panel and extract all text segments.
8. Save transcript to output directory.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
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
from playwright.async_api import async_playwright

DEFAULT_URL = "https://www.youtube.com"
DEFAULT_USER_DATA_DIR = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
DEFAULT_PROFILE_DIRECTORY = "Profile 1"
DEFAULT_ALLOWED_DOMAINS = [
    "www.youtube.com", "youtube.com", "accounts.google.com",
    "google.com", "m.youtube.com",
]
TARGET_ACCOUNT_EMAIL = "haogege1977@gmail.com"

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
    out = Path(os.environ.get("BROWSER_AGENT_REQUEST_DIR") or f"/tmp/yt-transcript-wrapper-{int(time.time())}").expanduser()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prompt_from_stdin() -> str:
    """Read YouTube URL from stdin (piped from operator)."""
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


# ---------------------------------------------------------------------------
# YouTube page interaction helpers
# ---------------------------------------------------------------------------

async def _verify_account(page) -> bool:
    """Check if logged-in account matches TARGET_ACCOUNT_EMAIL.

    Returns True if verified, False otherwise.
    Never logs the actual email — only reports match/mismatch.
    """
    js_code = """
    (() => {
        // Method 1: avatar button aria-label or tooltip
        const avatarBtn = document.querySelector(
            'button#avatar-btn, button[aria-label*="@"], ' +
            'yt-img-shadow#avatar, #avatar-btn img'
        );
        if (avatarBtn) {
            const label = avatarBtn.getAttribute('aria-label') || '';
            const emailMatch = label.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/);
            if (emailMatch) return { email: emailMatch[0], method: 'avatar_aria' };
        }

        // Method 2: page source contains the email in a data attribute
        const allElements = document.querySelectorAll('[data-email]');
        for (const el of allElements) {
            const email = el.getAttribute('data-email');
            if (email && email.includes('@')) return { email, method: 'data_email' };
        }

        // Method 3: ytInitialData or ytcfg in page scripts
        try {
            if (typeof ytcfg !== 'undefined') {
                const data = ytcfg.data_;
                if (data && data.DELEGATED_SESSION_ID) {
                    return { email: '__session_present__', method: 'ytcfg_session' };
                }
            }
        } catch(e) {}

        // Method 4: check account switcher menu items
        const accountItems = document.querySelectorAll(
            'yt-multi-page-menu-section-renderer tp-yt-paper-item, ' +
            '#account-name, .channel-name'
        );
        for (const item of accountItems) {
            const text = (item.textContent || '').trim();
            const emailMatch = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/);
            if (emailMatch) return { email: emailMatch[0], method: 'account_menu' };
        }

        return { email: null, method: 'not_found' };
    })()
    """
    result = await page.evaluate(js_code)
    email = result.get("email")
    if email and email != "__session_present__":
        matches = email.lower() == TARGET_ACCOUNT_EMAIL.lower()
        # Security: don't log actual email, only match result
        print(f"[YT Transcript] Account verification: {'MATCH' if matches else 'MISMATCH'} (method: {result.get('method')})", flush=True)
        return matches

    # If we can't find email directly, try clicking avatar to open account panel
    try:
        avatar_btn = page.locator("button#avatar-btn, #avatar-btn, #button.yt-icon-button").first
        if await avatar_btn.count():
            await avatar_btn.click()
            await page.wait_for_timeout(1500)

            # Look for email in the opened menu
            account_info = await page.evaluate("""
                (() => {
                    const emails = [];
                    const textNodes = document.querySelectorAll(
                        '#account-name, .account-name, ' +
                        'yt-formatted-string.style-scope.ytd-active-account-header-renderer, ' +
                        '#email, .email'
                    );
                    for (const node of textNodes) {
                        const text = (node.textContent || '').trim();
                        if (text.includes('@')) emails.push(text);
                    }
                    return { emails };
                })()
            """)

            # Close the menu by pressing Escape
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)

            for found_email in account_info.get("emails", []):
                if found_email.lower() == TARGET_ACCOUNT_EMAIL.lower():
                    print("[YT Transcript] Account verification: MATCH (method: avatar_menu_click)", flush=True)
                    return True

            if account_info.get("emails"):
                print("[YT Transcript] Account verification: MISMATCH (method: avatar_menu_click)", flush=True)
                return False
    except Exception:
        pass

    # If session is present but we can't verify the exact email, proceed with warning
    if email == "__session_present__":
        print("[YT Transcript] Account verification: SESSION_PRESENT (cannot confirm exact email, proceeding)", flush=True)
        return True

    print("[YT Transcript] Account verification: NOT_LOGGED_IN", flush=True)
    return False


async def _expand_description(page) -> None:
    """Expand the video description section if it is collapsed."""
    print("[YT Transcript] Expanding video description...", flush=True)

    # Click "...more" / "...展开" / "展开" / "more" button
    expand_btn = page.locator(
        "tp-yt-paper-button#expand, "
        "#expand, "
        "tp-yt-paper-button#snippet-text, "
        "#description-inline-expander tp-yt-paper-button, "
        "#description-inline-expander #expand, "
        "button:has-text('展开'), "
        "button:has-text('more'), "
        "span:has-text('展开'), "
        "span:has-text('...more'), "
        "#description-inline-expander [class*='expand'], "
        "ytd-text-inline-expander #expand"
    ).first

    for attempt in range(3):
        try:
            if await expand_btn.count():
                is_visible = await expand_btn.is_visible()
                if is_visible:
                    await expand_btn.click()
                    await page.wait_for_timeout(1000)
                    print("[YT Transcript] Description expanded successfully.", flush=True)
                    return
        except Exception:
            pass
        await page.wait_for_timeout(1000)

    # Fallback: try scrolling to description area and clicking
    try:
        await page.evaluate("""
            document.querySelector('#description-inline-expander, #description')
                ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        """)
        await page.wait_for_timeout(1000)

        # Try clicking the expander via JS
        clicked = await page.evaluate("""
            (() => {
                const expander = document.querySelector(
                    'tp-yt-paper-button#expand, #expand, ' +
                    'ytd-text-inline-expander #expand'
                );
                if (expander) { expander.click(); return true; }
                return false;
            })()
        """)
        if clicked:
            print("[YT Transcript] Description expanded via JS fallback.", flush=True)
            await page.wait_for_timeout(1000)
            return
    except Exception:
        pass

    print("[YT Transcript] Warning: Could not expand description (may already be expanded).", flush=True)


async def _click_show_transcript(page) -> bool:
    """Click the 'Show transcript' / '显示转写文稿' / '显示文稿' button.

    Returns True if transcript panel opened.
    """
    print("[YT Transcript] Looking for 'Show transcript' button...", flush=True)

    # Scroll down to the description area first
    await page.evaluate("""
        document.querySelector('#description-inline-expander, #description, #info-container')
            ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    """)
    await page.wait_for_timeout(1000)

    # Try multiple strategies to find and click the transcript button
    # Strategy 1: Direct button/link selectors
    transcript_selectors = [
        "button:has-text('显示转写文稿')",
        "button:has-text('显示文稿')",
        "button:has-text('Show transcript')",
        "button:has-text('内容转文字')",
        "button:has-text('转写文稿')",
        "ytd-button-renderer:has-text('显示转写文稿')",
        "ytd-button-renderer:has-text('显示文稿')",
        "ytd-button-renderer:has-text('Show transcript')",
        "ytd-button-renderer:has-text('内容转文字')",
    ]

    for selector in transcript_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.count() and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(2000)
                print(f"[YT Transcript] Clicked transcript button via: {selector}", flush=True)
                return True
        except Exception:
            continue

    # Strategy 2: Find via aria-label
    aria_selectors = [
        "button[aria-label*='转写'], button[aria-label*='transcript'], "
        "button[aria-label*='文稿'], button[aria-label*='Transcript']",
    ]
    for sel in aria_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.count() and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(2000)
                print(f"[YT Transcript] Clicked transcript button via aria-label.", flush=True)
                return True
        except Exception:
            continue

    # Strategy 3: JavaScript-based click
    clicked = await page.evaluate("""
        (() => {
            // Look for buttons with transcript-related text
            const allButtons = document.querySelectorAll(
                'button, ytd-button-renderer, tp-yt-paper-button'
            );
            const transcriptTerms = [
                '显示转写文稿', '显示文稿', 'Show transcript', 'show transcript',
                '内容转文字', '转写文稿', 'transcript'
            ];
            for (const btn of allButtons) {
                const text = (btn.textContent || '').trim().toLowerCase();
                const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                for (const term of transcriptTerms) {
                    if (text.includes(term.toLowerCase()) || ariaLabel.includes(term.toLowerCase())) {
                        btn.click();
                        return true;
                    }
                }
            }
            return false;
        })()
    """)
    if clicked:
        await page.wait_for_timeout(2000)
        print("[YT Transcript] Clicked transcript button via JS scan.", flush=True)
        return True

    # Strategy 4: Look in the 3-dot menu below the video
    print("[YT Transcript] Trying 3-dot menu fallback...", flush=True)
    try:
        # Click the "..." / more actions button below the video
        more_btn = page.locator(
            "button[aria-label*='其他操作'], "
            "button[aria-label*='More actions'], "
            "ytd-menu-renderer button.yt-icon-button, "
            "#button-shape button[aria-label*='更多']"
        ).first
        if await more_btn.count() and await more_btn.is_visible():
            await more_btn.click()
            await page.wait_for_timeout(1000)

            # Look for transcript option in the dropdown
            transcript_menu = page.locator(
                "ytd-menu-service-item-renderer:has-text('转写文稿'), "
                "ytd-menu-service-item-renderer:has-text('Transcript'), "
                "ytd-menu-service-item-renderer:has-text('显示转写文稿'), "
                "tp-yt-paper-item:has-text('转写文稿'), "
                "tp-yt-paper-item:has-text('Transcript')"
            ).first
            if await transcript_menu.count() and await transcript_menu.is_visible():
                await transcript_menu.click()
                await page.wait_for_timeout(2000)
                print("[YT Transcript] Opened transcript from 3-dot menu.", flush=True)
                return True

            # Close menu if transcript not found
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
    except Exception:
        pass

    print("[YT Transcript] ERROR: Could not find transcript button.", flush=True)
    return False


async def _wait_for_transcript_panel(page, timeout_s: int = 30) -> bool:
    """Wait for the transcript panel/segments to appear."""
    print("[YT Transcript] Waiting for transcript segments to load...", flush=True)
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        has_segments = await page.evaluate("""
            (() => {
                // Check for transcript segments
                const segments = document.querySelectorAll(
                    'ytd-transcript-segment-renderer, ' +
                    'ytd-transcript-segment-list-renderer, ' +
                    '#segments-container ytd-transcript-segment-renderer, ' +
                    'yt-formatted-string.segment-text'
                );
                return segments.length > 0;
            })()
        """)
        if has_segments:
            print("[YT Transcript] Transcript segments detected.", flush=True)
            return True
        await asyncio.sleep(1)

    print("[YT Transcript] Warning: Transcript segments did not appear within timeout.", flush=True)
    return False


async def _scroll_and_extract_transcript(page) -> dict:
    """Scroll through the transcript panel and extract all segments.

    Returns dict with:
      - segments: list of {timestamp, text}
      - full_text: concatenated plain text
      - segment_count: number of segments
    """
    print("[YT Transcript] Extracting transcript segments...", flush=True)

    # First, scroll the transcript panel to load all segments
    await page.evaluate("""
        (() => {
            const panel = document.querySelector(
                'ytd-transcript-renderer, ' +
                'ytd-transcript-search-panel-renderer, ' +
                '#segments-container, ' +
                'ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-searchable-transcript"]'
            );
            if (panel) {
                // Scroll to bottom multiple times to load lazy-loaded segments
                const scrollContainer = panel.querySelector(
                    '#body, #content, .ytd-transcript-renderer'
                ) || panel;
                for (let i = 0; i < 20; i++) {
                    scrollContainer.scrollTop = scrollContainer.scrollHeight;
                }
            }
        })()
    """)
    await page.wait_for_timeout(2000)

    # Now extract all transcript segments
    result = await page.evaluate("""
        (() => {
            const segments = [];
            const segmentNodes = document.querySelectorAll(
                'ytd-transcript-segment-renderer'
            );

            for (const node of segmentNodes) {
                // Extract timestamp
                const timeEl = node.querySelector(
                    '.segment-timestamp, ' +
                    'div.segment-start-offset, ' +
                    'yt-formatted-string.segment-timestamp'
                );
                const timestamp = timeEl
                    ? (timeEl.textContent || '').trim()
                    : '';

                // Extract text
                const textEl = node.querySelector(
                    '.segment-text, ' +
                    'yt-formatted-string.segment-text'
                );
                const text = textEl
                    ? (textEl.textContent || '').trim()
                    : (node.textContent || '').replace(timestamp, '').trim();

                if (text) {
                    segments.push({ timestamp, text });
                }
            }

            // If standard selector yields nothing, try alternative DOM structure
            if (segments.length === 0) {
                const altNodes = document.querySelectorAll(
                    '#segments-container > *, ' +
                    'ytd-transcript-segment-list-renderer *[class*="segment"]'
                );
                for (const node of altNodes) {
                    const text = (node.textContent || '').trim();
                    if (text && text.length > 1) {
                        // Try to split timestamp from text
                        const match = text.match(/^(\\d{1,2}:\\d{2}(?::\\d{2})?)\\s*(.+)/s);
                        if (match) {
                            segments.push({ timestamp: match[1], text: match[2].trim() });
                        } else {
                            segments.push({ timestamp: '', text });
                        }
                    }
                }
            }

            const fullText = segments.map(s => {
                if (s.timestamp) return `[${s.timestamp}] ${s.text}`;
                return s.text;
            }).join('\\n');

            return {
                segments,
                full_text: fullText,
                segment_count: segments.length,
            };
        })()
    """)

    segment_count = result.get("segment_count", 0)
    print(f"[YT Transcript] Extracted {segment_count} transcript segments.", flush=True)

    if segment_count == 0:
        # Last resort: try to get any text in the transcript panel
        fallback = await page.evaluate("""
            (() => {
                const panel = document.querySelector(
                    'ytd-transcript-renderer, ' +
                    'ytd-engagement-panel-section-list-renderer[target-id*="transcript"]'
                );
                if (panel) {
                    return {
                        segments: [{ timestamp: '', text: panel.innerText || '' }],
                        full_text: panel.innerText || '',
                        segment_count: panel.innerText ? 1 : 0,
                    };
                }
                return { segments: [], full_text: '', segment_count: 0 };
            })()
        """)
        if fallback.get("segment_count", 0) > 0:
            print(f"[YT Transcript] Fallback extraction: got {len(fallback.get('full_text', ''))} chars.", flush=True)
            return fallback

    return result


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return ""


async def _get_video_metadata(page) -> dict:
    """Extract basic video metadata from the page."""
    return await page.evaluate("""
        (() => {
            const title = document.querySelector(
                'h1.ytd-watch-metadata yt-formatted-string, ' +
                '#title h1 yt-formatted-string, ' +
                'h1.title yt-formatted-string'
            );
            const channel = document.querySelector(
                '#channel-name yt-formatted-string a, ' +
                'ytd-channel-name yt-formatted-string a'
            );
            const viewCount = document.querySelector(
                '#info-container ytd-video-view-count-renderer span, ' +
                'ytd-video-view-count-renderer .view-count'
            );
            return {
                title: title ? title.textContent.trim() : document.title || '',
                channel: channel ? channel.textContent.trim() : '',
                view_count: viewCount ? viewCount.textContent.trim() : '',
                url: location.href,
            };
        })()
    """)


# ---------------------------------------------------------------------------
# Main execution pipeline
# ---------------------------------------------------------------------------

async def _run(youtube_url: str) -> int:
    request_dir = _request_dir()
    profile_directory = str(os.environ.get("BROWSER_AGENT_PROFILE_DIRECTORY") or DEFAULT_PROFILE_DIRECTORY)
    user_data_dir = Path(os.environ.get("BROWSER_AGENT_USER_DATA_DIR") or str(DEFAULT_USER_DATA_DIR)).expanduser()
    headless = str(os.environ.get("BROWSER_AGENT_HEADLESS") or "false").strip().lower() in {"1", "true", "yes", "on"}
    allowed_domains = DEFAULT_ALLOWED_DOMAINS
    timeout_s = int(os.environ.get("BROWSER_AGENT_YT_TIMEOUT") or "300")

    staged_dir, cleanup_dir = bjrt._stage_browser_profile(user_data_dir, profile_directory)
    if user_data_dir and not staged_dir:
        raise RuntimeError("protected_browser_profile_cache_missing")

    video_id = _extract_video_id(youtube_url)
    meta = {
        "provider": "browser_agent_youtube_transcript",
        "target_url": youtube_url,
        "video_id": video_id,
        "profile_directory": profile_directory,
        "headless": headless,
        "allowed_domains": allowed_domains,
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
            channel="chrome",
        )
    )
    try:
        await asyncio.wait_for(browser.start(), timeout=40)
        async with async_playwright() as pw:
            pw_browser = await pw.chromium.connect_over_cdp(browser.cdp_url)
            pw_context = pw_browser.contexts[0] if pw_browser.contexts else None
            if pw_context is None:
                raise RuntimeError("failed_to_connect_via_playwright_cdp")
            playwright_page = pw_context.pages[0] if pw_context.pages else await pw_context.new_page()

            # -----------------------------------------------------------------
            # Stage 1: Navigate to YouTube video
            # -----------------------------------------------------------------
            print(f"[YT Transcript] Navigating to YouTube video: {youtube_url}", flush=True)
            await playwright_page.goto(youtube_url, wait_until="domcontentloaded")
            await playwright_page.wait_for_timeout(3000)

            # Handle cookie consent if present
            try:
                consent_btn = playwright_page.locator(
                    "button:has-text('Accept all'), button:has-text('全部接受'), "
                    "button:has-text('同意'), button[aria-label*='Accept']"
                ).first
                if await consent_btn.count() and await consent_btn.is_visible():
                    await consent_btn.click()
                    await playwright_page.wait_for_timeout(1000)
                    print("[YT Transcript] Dismissed cookie consent.", flush=True)
            except Exception:
                pass

            # -----------------------------------------------------------------
            # Stage 2: Verify account
            # -----------------------------------------------------------------
            print("[YT Transcript] Verifying account...", flush=True)
            account_ok = await _verify_account(playwright_page)
            if not account_ok:
                # Don't raise immediately — still attempt extraction
                print("[YT Transcript] WARNING: Account verification failed. Continuing with extraction attempt.", flush=True)

            # -----------------------------------------------------------------
            # Stage 3: Expand description
            # -----------------------------------------------------------------
            await _expand_description(playwright_page)
            await playwright_page.wait_for_timeout(1000)

            # -----------------------------------------------------------------
            # Stage 4: Click "Show transcript" button
            # -----------------------------------------------------------------
            transcript_opened = await _click_show_transcript(playwright_page)
            if not transcript_opened:
                raise RuntimeError("youtube_transcript_button_not_found")

            # -----------------------------------------------------------------
            # Stage 5: Wait for transcript panel
            # -----------------------------------------------------------------
            panel_ready = await _wait_for_transcript_panel(playwright_page, timeout_s=30)
            if not panel_ready:
                raise RuntimeError("youtube_transcript_panel_not_loaded")

            # -----------------------------------------------------------------
            # Stage 6: Scroll and extract all transcript segments
            # -----------------------------------------------------------------
            transcript_data = await _scroll_and_extract_transcript(playwright_page)
            full_text = transcript_data.get("full_text", "").strip()
            segments = transcript_data.get("segments", [])
            segment_count = transcript_data.get("segment_count", 0)

            if not full_text:
                raise RuntimeError("youtube_transcript_empty")

            # Get video metadata
            video_meta = await _get_video_metadata(playwright_page)

            # Take screenshot of the transcript panel
            screenshot_bytes = await playwright_page.screenshot(type="png")

            # -----------------------------------------------------------------
            # Stage 7: Save outputs
            # -----------------------------------------------------------------
            print(f"[YT Transcript] Saving {segment_count} segments ({len(full_text)} chars)...", flush=True)

            # assistant-response.txt — the primary output (required by operator)
            (request_dir / "assistant-response.txt").write_text(full_text + "\n", encoding="utf-8")

            # Structured transcript JSON
            transcript_output = {
                "video_id": video_id,
                "video_url": youtube_url,
                "video_title": video_meta.get("title", ""),
                "channel": video_meta.get("channel", ""),
                "segment_count": segment_count,
                "segments": segments,
                "full_text": full_text,
                "extracted_at": bjrt._now(),
            }
            _write_json(request_dir / "transcript.json", transcript_output)

            # page.json — metadata (required by operator)
            _write_json(request_dir / "page.json", {
                "title": video_meta.get("title", ""),
                "url": youtube_url,
                "video_id": video_id,
                "channel": video_meta.get("channel", ""),
                "segment_count": segment_count,
                "text_length": len(full_text),
            })

            if screenshot_bytes:
                (request_dir / "screenshot.png").write_bytes(screenshot_bytes)

            # Print transcript to stdout (operator reads this)
            print(full_text)
            return 0

    finally:
        try:
            await asyncio.wait_for(browser.stop(), timeout=20)
        except Exception:
            pass
        if cleanup_dir is not None:
            import shutil
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def main() -> int:
    _quiet_browser_logs()
    youtube_url = _prompt_from_stdin()
    if not youtube_url:
        print("ERROR: Stdin input (YouTube URL) is empty.", file=sys.stderr)
        return 1
    # Validate URL
    if not re.match(r"https?://(www\.)?(youtube\.com|youtu\.be)/", youtube_url):
        print(f"ERROR: Invalid YouTube URL: {youtube_url}", file=sys.stderr)
        return 1
    try:
        return asyncio.run(_run(youtube_url))
    except Exception as exc:
        request_dir = _request_dir()
        _write_json(request_dir / "wrapper-error.json", {
            "error_type": type(exc).__name__,
            "error": str(exc),
            "failed_at": bjrt._now(),
        })
        print(f"browser_agent_youtube_transcript_wrapper failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
