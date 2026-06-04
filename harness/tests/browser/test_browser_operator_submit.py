from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "harness" / "lib"))

from browser_operator_submit import build_chatgpt_operator_env
from browser_operator_submit import browser_agent_chatgpt_cmd
from browser_operator_submit import derive_chatgpt_session_lineage
from browser_operator_submit import submit_chatgpt_operator_request


def test_browser_agent_chatgpt_cmd_uses_reasoner_browser_agent_cmd(monkeypatch):
    monkeypatch.delenv("TECH_HOTSPOT_BROWSER_CHATGPT_CMD", raising=False)
    monkeypatch.delenv("BROWSER_AGENT_CHATGPT_CMD", raising=False)
    cmd = browser_agent_chatgpt_cmd(
        {
            "youtube": {
                "phase_report_reasoner": {
                    "browser_agent_cmd": "python3 /tmp/reasoner-wrapper.py",
                }
            }
        }
    )
    assert cmd == ["python3", "/tmp/reasoner-wrapper.py"]


def test_derive_chatgpt_session_lineage_groups_report_chapters():
    lineage = derive_chatgpt_session_lineage(
        "ai-influence-report-chapter-2026-06-03-agent-memory-landscape-intro"
    )
    assert lineage == "ai-influence-report:2026-06-03:agent-memory-landscape"


def test_build_chatgpt_operator_env_sets_broker_fields():
    env = build_chatgpt_operator_env(
        model="chatgpt-5.5",
        reasoning_effort="high",
        expected="markdown",
        request_dir="/tmp/request-dir",
        purpose="hf-paper-report-plan-2026-06-03",
        session_lineage="hf-paper-report:2026-06-03",
        session_reuse=True,
        operator_kind="planner",
        target_url="https://chatgpt.com",
        headless=True,
        profile_directory="Default",
        target_account_email="browser-agent@example.com",
        scrub_client_state=True,
        open_project_first=True,
        require_project=True,
        force_new_chat=True,
        require_isolated_conversation=True,
        project_name="杂项",
        base_env={"EXISTING": "1"},
    )
    assert env["EXISTING"] == "1"
    assert env["BROWSER_AGENT_SESSION_LINEAGE"] == "hf-paper-report:2026-06-03"
    assert env["SOLAR_BROWSER_SESSION_REUSE"] == "true"
    assert env["CHATGPT_REPORT_OPERATOR_KIND"] == "planner"
    assert env["BROWSER_AGENT_CHATGPT_PROJECT_NAME"] == "杂项"
    assert env["BROWSER_AGENT_TARGET_ACCOUNT_EMAIL"] == "browser-agent@example.com"


def test_submit_chatgpt_operator_request_writes_stdout(tmp_path):
    wrapper = tmp_path / "fake_wrapper.py"
    wrapper.write_text(
        "import json\n"
        "print(json.dumps({'body': 'x' * 1200}, ensure_ascii=False))\n",
        encoding="utf-8",
    )
    result = submit_chatgpt_operator_request(
        cmd=[sys.executable, str(wrapper)],
        prompt="demo prompt",
        timeout=30,
        env={},
        request_dir=tmp_path / "request",
        expected="markdown",
    )
    assert result["latency_ms"] >= 0
    payload = json.loads(result["output"])
    assert len(payload["body"]) == 1200
    assert (tmp_path / "request" / "stdout.txt").exists()
