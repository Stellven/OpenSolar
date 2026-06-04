from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_browser_agent_wrappers_default_to_headless_true_and_kill_browser():
    expectations = {
        "scripts/browser_agent_chatgpt_wrapper.py": [
            '_env_flag("BROWSER_AGENT_HEADLESS", default=True)',
            "return DEFAULT_BROWSER_CHANNEL",
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
        "scripts/browser_agent_gemini_deep_research_wrapper.py": [
            'os.environ.get("BROWSER_AGENT_HEADLESS") or "true"',
            'channel="chrome"',
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
        "scripts/browser_agent_youtube_transcript_wrapper.py": [
            'os.environ.get("BROWSER_AGENT_HEADLESS") or "true"',
            'channel="chrome"',
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
        "scripts/browser_agent_technology_diagram_painter_wrapper.py": [
            'os.environ.get("BROWSER_AGENT_HEADLESS") or "true"',
            'channel="chrome"',
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
        "scripts/browser_agent_notebooklm_wrapper.py": [
            'os.environ.get("BROWSER_AGENT_HEADLESS") or "true"',
            'channel="chrome"',
            "await asyncio.wait_for(browser.kill(), timeout=20)",
        ],
    }
    for rel, patterns in expectations.items():
        source = _read(rel)
        for pattern in patterns:
            assert pattern in source, f"{rel} missing pattern: {pattern}"


def test_browser_agent_callers_default_to_headless_true():
    expectations = {
        "scripts/youtube_influence_digest.py": 'env["BROWSER_AGENT_HEADLESS"] = "true"',
        "tools/youtube_transcript_operator.py": 'env["BROWSER_AGENT_HEADLESS"] = "true"',
        "tools/technology_diagram_painter_operator.py": 'env["BROWSER_AGENT_HEADLESS"] = "true"',
        "scripts/run_youtube_daily_previous_day_collect.sh": 'BROWSER_AGENT_HEADLESS="${BROWSER_AGENT_HEADLESS:-true}"',
    }
    for rel, pattern in expectations.items():
        source = _read(rel)
        assert pattern in source, f"{rel} missing pattern: {pattern}"


def test_browser_job_runtime_forces_chrome_channel():
    expectations = {
        "lib/browser_job_runtime.py": 'channel="chrome"',
        "tools/browser_job_runtime.py": 'channel="chrome"',
    }
    for rel, pattern in expectations.items():
        source = _read(rel)
        assert pattern in source, f"{rel} missing pattern: {pattern}"
