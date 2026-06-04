from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "tools"))

from actor_mailbox import ActorMailbox
from actor_lease import LeaseBroker
from browser_agent_session_actor import drain_once


def test_browser_agent_session_actor_processes_deepresearch_task(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "actors"
        lease_dir = Path(td) / "run" / "actor-leases"
        mailbox = ActorMailbox("browser_agent_session", base)
        envelope = {
            "task_id": "task-1",
            "logical_operator": "DeepResearchBrowser",
            "chatgpt_browser_agent_request": {
                "prompt": "写一个测试摘要",
                "expected_output": "markdown",
                "model": "chatgpt-5.5",
                "reasoning_effort": "high",
                "project_name": "杂项",
            },
        }
        mailbox.submit_task(envelope)
        wrapper = Path(td) / "fake_wrapper.py"
        wrapper.write_text("print('browser actor ok')\n", encoding="utf-8")
        monkeypatch.setenv("TECH_HOTSPOT_BROWSER_CHATGPT_CMD", f"{sys.executable} {wrapper}")
        monkeypatch.setenv("BROWSER_AGENT_CHATGPT_PROFILE_POLICY_DISABLED", "true")
        monkeypatch.setenv("HARNESS_DIR", str(Path(td)))

        rc = drain_once(
            actor_id="browser_agent_session",
            mailbox_base=base,
            lease_dir=lease_dir,
        )
        assert rc == 0
        results = mailbox.read_results("task-1")
        assert len(results) == 1
        assert results[0]["status"] == "completed"
        assert Path(results[0]["task_dir"]).exists()
        assert mailbox.read_inbox() == []
        lease = LeaseBroker(lease_dir).get("browser_agent_session")
        assert lease is None or lease.state == "READY"


def test_browser_agent_session_actor_reports_unsupported_operator():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "actors"
        lease_dir = Path(td) / "run" / "actor-leases"
        mailbox = ActorMailbox("browser_agent_session", base)
        envelope = {
            "task_id": "task-unsupported",
            "logical_operator": "SomeOtherBrowserThing",
        }
        mailbox.submit_task(envelope)
        rc = drain_once(
            actor_id="browser_agent_session",
            mailbox_base=base,
            lease_dir=lease_dir,
        )
        assert rc == 0
        results = mailbox.read_results("task-unsupported")
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "unsupported_browser_agent_session_logical_operator" in results[0]["error"]
