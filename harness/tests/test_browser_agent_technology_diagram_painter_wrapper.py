from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "browser_agent_technology_diagram_painter_wrapper.py"
SOURCE = SCRIPT.read_text(encoding="utf-8")


def _load_namespace():
    browser_use = types.ModuleType("browser_use")
    browser_use_browser = types.ModuleType("browser_use.browser")
    browser_use_browser_profile = types.ModuleType("browser_use.browser.profile")
    browser_use_browser_session = types.ModuleType("browser_use.browser.session")
    playwright_async_api = types.ModuleType("playwright.async_api")

    class _DummyProfile:
        pass

    class _DummySession:
        pass

    async def _dummy_async_playwright():  # pragma: no cover - stub only
        return None

    browser_use_browser_profile.BrowserProfile = _DummyProfile
    browser_use_browser_session.BrowserSession = _DummySession
    playwright_async_api.async_playwright = _dummy_async_playwright

    prev_modules = {
        name: sys.modules.get(name)
        for name in (
            "browser_use",
            "browser_use.browser",
            "browser_use.browser.profile",
            "browser_use.browser.session",
            "playwright.async_api",
        )
    }
    sys.modules["browser_use"] = browser_use
    sys.modules["browser_use.browser"] = browser_use_browser
    sys.modules["browser_use.browser.profile"] = browser_use_browser_profile
    sys.modules["browser_use.browser.session"] = browser_use_browser_session
    sys.modules["playwright.async_api"] = playwright_async_api
    try:
        ns = {"__file__": str(SCRIPT), "__name__": "browser_agent_technology_diagram_painter_wrapper_test"}
        code = compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")
        exec(code, ns)
        return types.SimpleNamespace(**ns)
    finally:
        for name, module in prev_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def test_painter_wrapper_waits_for_chat_ready_before_submit() -> None:
    assert "async def _wait_for_chat_ready" in SOURCE
    assert "async def _capture_state(" in SOURCE
    assert "await _wait_for_chat_ready(playwright_page, timeout_s=60)" in SOURCE
    assert "await _wait_for_chat_ready(playwright_page, timeout_s=45)" in SOURCE
    assert 'state = await _capture_state(page, timeout_s=8.0, default=last_state, label="wait_for_chat_ready")' in SOURCE
    assert 'raise RuntimeError("chatgpt_cloudflare_challenge_detected")' in SOURCE
    assert "await page.reload()" in SOURCE


def test_painter_wrapper_uses_dom_fill_and_submit_fallbacks() -> None:
    assert "SET_PROMPT_JS" in SOURCE
    assert "COMPOSER_STATE_JS" in SOURCE
    assert "SUBMIT_JS" in SOURCE
    assert "SUBMIT_FALLBACK_JS" in SOURCE
    assert "form.requestSubmit()" in SOURCE
    assert "submit_result = json.loads(await page.evaluate(SUBMIT_JS))" in SOURCE
    assert "submit_result = json.loads(await page.evaluate(SUBMIT_FALLBACK_JS))" in SOURCE


def test_painter_wrapper_reuses_chatgpt_runtime_session_when_available() -> None:
    assert "brtc.initialize_runtime_contract(" in SOURCE
    assert "active_session = brtc.read_active_session(control_ctx, require_lineage_match=False)" in SOURCE
    assert 'cdp_url=str(active_session.get("cdp_url") or "").strip()' in SOURCE
    assert "brtc.activate_reusable_session(" in SOURCE


def test_painter_wrapper_promotes_original_capture_before_ui_timeout() -> None:
    assert "async def _maybe_promote_original_capture" in SOURCE
    assert "Promoted captured original image response as final result." in SOURCE
    assert "capture_state=original_capture" in SOURCE


def test_painter_wrapper_forces_exit_after_success() -> None:
    assert "def _force_wrapper_exit" in SOURCE
    assert "_force_wrapper_exit(0)" in SOURCE


def test_painter_capture_state_times_out_to_default() -> None:
    ns = _load_namespace()

    class _NeverReturnsPage:
        async def evaluate(self, script):  # pragma: no cover - async stub
            await asyncio.sleep(2.0)
            return "{}"

    result = asyncio.run(
        ns._capture_state(
            _NeverReturnsPage(),
            timeout_s=0.01,
            default={"composer_ready": True},
            label="wait_for_chat_ready",
        )
    )
    assert result["composer_ready"] is True
    assert result["_capture_timeout"] == "wait_for_chat_ready"
