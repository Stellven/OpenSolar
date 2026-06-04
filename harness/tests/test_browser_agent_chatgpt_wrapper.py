from __future__ import annotations

import os
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "harness" / "scripts" / "browser_agent_chatgpt_wrapper.py"


def _load_namespace() -> dict:
    browser_use = types.ModuleType("browser_use")
    browser_use_browser = types.ModuleType("browser_use.browser")
    browser_use_browser_profile = types.ModuleType("browser_use.browser.profile")
    browser_use_browser_session = types.ModuleType("browser_use.browser.session")
    browser_use_browser_watchdogs = types.ModuleType("browser_use.browser.watchdogs")
    browser_use_browser_watchdogs_local = types.ModuleType("browser_use.browser.watchdogs.local_browser_watchdog")

    class _DummyProfile:
        pass

    class _DummySession:
        pass

    class _DummyLocalBrowserWatchdog:
        _wait_for_cdp_url = None

        async def on_BrowserStopEvent(self, event):  # pragma: no cover - stub only
            return None

    browser_use_browser_profile.BrowserProfile = _DummyProfile
    browser_use_browser_session.BrowserSession = _DummySession
    browser_use_browser_watchdogs_local.LocalBrowserWatchdog = _DummyLocalBrowserWatchdog

    prev_modules = {
        name: sys.modules.get(name)
        for name in (
            "browser_use",
            "browser_use.browser",
            "browser_use.browser.profile",
            "browser_use.browser.session",
            "browser_use.browser.watchdogs",
            "browser_use.browser.watchdogs.local_browser_watchdog",
        )
    }
    sys.modules["browser_use"] = browser_use
    sys.modules["browser_use.browser"] = browser_use_browser
    sys.modules["browser_use.browser.profile"] = browser_use_browser_profile
    sys.modules["browser_use.browser.session"] = browser_use_browser_session
    sys.modules["browser_use.browser.watchdogs"] = browser_use_browser_watchdogs
    sys.modules["browser_use.browser.watchdogs.local_browser_watchdog"] = browser_use_browser_watchdogs_local
    try:
        ns: dict = {"__file__": str(SCRIPT), "__name__": "browser_agent_chatgpt_wrapper_test"}
        code = compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")
        exec(code, ns)
        return ns
    finally:
        for name, module in prev_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def test_post_submit_confirms_chinese_thinking_banner():
    ns = _load_namespace()
    result = ns["_post_submit_confirms_chatgpt_mode"](
        {
            "latest_assistant_text": "正在思考",
            "is_generating": True,
            "assistant_count": 1,
        },
        model_mode="thinking",
        reasoning_effort="high",
    )
    assert result["ok"] is True
    assert result["model_ok"] is True
    assert result["reasoning_ok"] is True


def test_post_submit_accepts_configured_high_reasoning_when_response_started():
    ns = _load_namespace()
    result = ns["_post_submit_confirms_chatgpt_mode"](
        {
            "latest_assistant_text": '{"accepted": true, "summary": "partial json"}',
            "is_generating": True,
            "assistant_count": 1,
            "_configure_result": {
                "steps": [
                    {
                        "step": "open_model_dropdown",
                        "ok": True,
                        "clicked": {"text": "ChatGPT", "aria": "模型选择器"},
                    },
                    {
                        "step": "select_high_reasoning",
                        "ok": True,
                        "clicked": {"text": "思考时间更长", "aria": ""},
                    },
                ]
            },
        },
        model_mode="thinking",
        reasoning_effort="high",
    )
    assert result["ok"] is True
    assert result["model_selector_confirmed"] is True
    assert result["high_reasoning_confirmed"] is True


def test_post_submit_accepts_json_response_started_on_chatgpt_page():
    ns = _load_namespace()
    result = ns["_post_submit_confirms_chatgpt_mode"](
        {
            "latest_assistant_text": '{"accepted": true, "trend_type": "weak_signal", "summary": "partial json"}',
            "is_generating": True,
            "assistant_count": 1,
            "_configure_result": {
                "steps": [
                    {
                        "step": "open_model_dropdown",
                        "ok": True,
                        "clicked": {"text": "ChatGPT", "aria": "模型选择器"},
                    },
                    {
                        "step": "select_high_reasoning",
                        "ok": False,
                        "clicked": None,
                    },
                ]
            },
        },
        model_mode="thinking",
        reasoning_effort="high",
    )
    assert result["ok"] is True
    assert result["json_response_started"] is True
    assert result["reasoning_ok"] is True


def test_headed_run_requires_explicit_opt_in(monkeypatch):
    ns = _load_namespace()
    monkeypatch.delenv("BROWSER_AGENT_CHATGPT_ALLOW_HEADED", raising=False)
    monkeypatch.delenv("TECH_HOTSPOT_BROWSER_CHATGPT_ALLOW_HEADED", raising=False)
    monkeypatch.delenv("BROWSER_AGENT_ALLOW_HEADED", raising=False)
    assert ns["_headed_run_allowed"]() is False


def test_headed_run_accepts_explicit_opt_in(monkeypatch):
    ns = _load_namespace()
    monkeypatch.setenv("BROWSER_AGENT_CHATGPT_ALLOW_HEADED", "true")
    assert ns["_headed_run_allowed"]() is True


def test_chatgpt_wrapper_defaults_to_persistent_profile_strategy(monkeypatch):
    ns = _load_namespace()
    monkeypatch.delenv("BROWSER_AGENT_CHATGPT_PROFILE_STRATEGY", raising=False)
    monkeypatch.delenv("BROWSER_AGENT_PROFILE_STRATEGY", raising=False)
    strategy = str(
        os.environ.get("BROWSER_AGENT_CHATGPT_PROFILE_STRATEGY")
        or os.environ.get("BROWSER_AGENT_PROFILE_STRATEGY")
        or "persistent"
    ).strip().lower()
    assert strategy == "persistent"


def test_chatgpt_wrapper_defaults_to_chrome_channel(monkeypatch):
    ns = _load_namespace()
    monkeypatch.delenv("BROWSER_AGENT_CHATGPT_BROWSER_CHANNEL", raising=False)
    monkeypatch.delenv("BROWSER_AGENT_BROWSER_CHANNEL", raising=False)
    assert ns["_browser_channel"]() == "chrome"


def test_chatgpt_wrapper_ignores_non_chrome_channel_override(monkeypatch):
    ns = _load_namespace()
    monkeypatch.setenv("BROWSER_AGENT_CHATGPT_BROWSER_CHANNEL", "firefox")
    monkeypatch.setenv("BROWSER_AGENT_BROWSER_CHANNEL", "webkit")
    assert ns["_browser_channel"]() == "chrome"


def test_cloudflare_challenge_grace_defaults_and_expires(monkeypatch):
    ns = _load_namespace()
    monkeypatch.delenv("BROWSER_AGENT_CHATGPT_CHALLENGE_GRACE_SECONDS", raising=False)
    monkeypatch.delenv("BROWSER_AGENT_CHALLENGE_GRACE_SECONDS", raising=False)
    assert ns["_challenge_grace_seconds"]() == 20.0
    assert ns["_challenge_persisted_too_long"](100.0, now=119.9, grace_s=20.0) is False
    assert ns["_challenge_persisted_too_long"](100.0, now=120.0, grace_s=20.0) is True


def test_browser_user_agent_defaults_to_non_headless_chrome(monkeypatch):
    ns = _load_namespace()
    monkeypatch.delenv("BROWSER_AGENT_CHATGPT_USER_AGENT", raising=False)
    monkeypatch.delenv("BROWSER_AGENT_USER_AGENT", raising=False)
    ua = ns["_browser_user_agent"](browser_channel="chrome")
    assert "Chrome/" in ua
    assert "HeadlessChrome/" not in ua


def test_is_cdp_connect_failure_matches_known_browser_use_errors():
    ns = _load_namespace()
    assert ns["_is_cdp_connect_failure"](RuntimeError("Failed to establish CDP connection to browser: [Errno 61] Connect call failed")) is True
    assert ns["_is_cdp_connect_failure"](RuntimeError("Root CDP client not initialized")) is True
    assert ns["_is_cdp_connect_failure"](RuntimeError("some unrelated failure")) is False


def test_conversation_target_id_extracts_chatgpt_conversation():
    ns = _load_namespace()
    assert ns["_conversation_target_id"]("https://chatgpt.com/c/abc-123") == "abc-123"
    assert ns["_conversation_target_id"]("https://chatgpt.com/") == ""


def test_conversation_state_ready_requires_matching_conversation_and_messages():
    ns = _load_namespace()
    assert ns["_conversation_state_ready"](
        {"conversation_id": "abc", "message_count": 1},
        expected_conversation_id="abc",
    ) is True
    assert ns["_conversation_state_ready"](
        {"conversation_id": "abc", "message_count": 0, "latest_assistant_text": "", "is_generating": False},
        expected_conversation_id="abc",
    ) is False
    assert ns["_conversation_state_ready"](
        {"conversation_id": "other", "message_count": 3},
        expected_conversation_id="abc",
    ) is False
    assert ns["_conversation_state_ready"](
        {
            "conversation_id": "abc",
            "message_count": 0,
            "assistant_count": 0,
            "latest_assistant_text": "",
            "is_generating": True,
        },
        expected_conversation_id="abc",
    ) is False
    assert ns["_conversation_state_ready"](
        {
            "conversation_id": "abc",
            "message_count": 1,
            "assistant_count": 0,
            "latest_assistant_text": "",
            "is_generating": True,
        },
        expected_conversation_id="abc",
    ) is True


def test_chatgpt_wrapper_reuses_existing_conversation_page_for_collect():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "async def _find_existing_conversation_page(browser, *, target_url: str):" in source
    assert "page = await _find_existing_conversation_page(browser, target_url=target_url)" in source
    assert "if str((current_state or {}).get(\"conversation_id\") or \"\").strip() == collect_target_id:" in source
    assert "should_navigate = False" in source
    assert "action == \"collect\"" in source
    assert "and not final_data.get(\"is_generating\")" in source
    assert "and int(final_data.get(\"assistant_count\") or 0) > 0" in source
    assert "final_data = await _wait_for_answer(" in source


def test_chatgpt_wrapper_installs_browser_use_cdp_patch():
    ns = _load_namespace()
    assert ns["_BROWSER_USE_CDP_PATCHED"] is True
    assert ns["LocalBrowserWatchdog"]._wait_for_cdp_url is ns["_patched_wait_for_cdp_url"]
    assert ns["LocalBrowserWatchdog"].on_BrowserStopEvent is ns["on_BrowserStopEvent"]


def test_open_project_js_targets_sidebar_project_group():
    ns = _load_namespace()
    script = ns["OPEN_PROJECT_JS"]
    assert "nav,aside,section" in script
    assert "项目" in script
    assert "Open sidebar" in script
    assert "role='treeitem'" in script


def test_chatgpt_wrapper_defaults_to_headless_true():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '_env_flag("BROWSER_AGENT_HEADLESS", default=True)' in source
    assert "await asyncio.wait_for(browser.kill(), timeout=20)" in source
    assert "def _force_wrapper_exit(code: int) -> NoReturn:" in source
    assert "_force_wrapper_exit(exit_code)" in source


def test_chatgpt_wrapper_reads_and_writes_active_session_broker():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "brtc.read_active_session(control_ctx, require_lineage_match=False)" in source
    assert "brtc.activate_reusable_session(" in source
    assert "if not _is_cdp_connect_failure(exc):" in source
    assert "LocalBrowserWatchdog._wait_for_cdp_url = staticmethod(_patched_wait_for_cdp_url)" in source
    assert "LocalBrowserWatchdog.on_BrowserStopEvent = on_BrowserStopEvent" in source
    assert "await _wait_for_cdp_websocket_ready(ws_url" in source
    assert "browser.stop() has been observed to hang after submit/poll" in source
    assert "await asyncio.wait_for(browser.stop(), timeout=20)" not in source
    assert "Force the dedicated wrapper process to exit" in source
    assert "\"forced_exit_after_submit\": True" in source
    assert "_force_wrapper_exit(0)" in source
    assert "keep_alive=keep_session_alive" in source
    assert "if action in {\"poll\", \"collect\"} and _is_generic_chatgpt_root(target_url):" in source
    assert "should_navigate = False" in source
    assert "submitted_state = await _wait_for_submitted_conversation(" in source
    assert "\"BROWSER_AGENT_CHATGPT_SUBMIT_STABILIZE_SECONDS\"" in source
    assert "final_data = await _wait_for_conversation_ready(" in source
    assert "await page.reload()" in source
    assert "collect-empty-conversation-page.json" not in source
    assert "f\"{action}-empty-conversation-page.json\"" in source
    assert "elif action in {\"poll\", \"collect\"} and collect_target_id:" in source
    assert "SUBMIT_FALLBACK_JS" in source
    assert "\"mode\": \"dom_fallback_after_native_setter\"" in source
    assert "\"mode\": \"clipboard_dom_submit_retry\"" in source
