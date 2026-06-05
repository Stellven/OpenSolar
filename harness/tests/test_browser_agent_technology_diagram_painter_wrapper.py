from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts" / "browser_agent_technology_diagram_painter_wrapper.py").read_text(
    encoding="utf-8"
)


def test_painter_wrapper_waits_for_chat_ready_before_submit() -> None:
    assert "async def _wait_for_chat_ready" in SOURCE
    assert "await _wait_for_chat_ready(playwright_page, timeout_s=60)" in SOURCE
    assert "await _wait_for_chat_ready(playwright_page, timeout_s=45)" in SOURCE
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
