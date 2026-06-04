from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_browser_agent_wrappers_default_to_headless_true_and_kill_browser():
    expectations = {
        "scripts/browser_agent_chatgpt_wrapper.py": [
            '_env_flag("BROWSER_AGENT_HEADLESS", default=True)',
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
        "scripts/browser_agent_gemini_deep_research_wrapper.py": [
            'os.environ.get("BROWSER_AGENT_HEADLESS") or "true"',
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
        "scripts/browser_agent_youtube_transcript_wrapper.py": [
            'os.environ.get("BROWSER_AGENT_HEADLESS") or "true"',
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
        "scripts/browser_agent_technology_diagram_painter_wrapper.py": [
            'os.environ.get("BROWSER_AGENT_HEADLESS") or "true"',
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
        "scripts/browser_agent_notebooklm_wrapper.py": [
            'os.environ.get("BROWSER_AGENT_HEADLESS") or "true"',
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
    }
    for rel, patterns in expectations.items():
        source = _read(rel)
        for pattern in patterns:
            assert pattern in source, f"{rel} missing pattern: {pattern}"

