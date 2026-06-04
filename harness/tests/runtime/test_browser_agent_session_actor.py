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
        assert results[0]["pool_slot_id"].startswith("slot-")
        assert results[0]["pool_session_lineage"].startswith("browser-agent-session:chatgpt:slot-")
        assert Path(results[0]["task_dir"]).exists()
        slot_file = Path(results[0]["task_dir"]) / "browser-agent-session-slot.json"
        assert slot_file.exists()
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


def test_browser_agent_session_actor_submit_then_collect(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "actors"
        lease_dir = Path(td) / "run" / "actor-leases"
        mailbox = ActorMailbox("browser_agent_session", base)
        envelope = {
            "task_id": "task-async",
            "logical_operator": "DeepResearchBrowser",
            "chatgpt_browser_agent_request": {
                "prompt": "异步研究任务",
                "expected_output": "markdown",
                "model": "chatgpt-5.5",
                "reasoning_effort": "high",
                "project_name": "杂项",
                "action": "submit",
            },
        }
        mailbox.submit_task(envelope)
        wrapper = Path(td) / "fake_wrapper_async.py"
        wrapper.write_text(
            "import json, os, pathlib\n"
            "request_dir = pathlib.Path(os.environ['BROWSER_AGENT_REQUEST_DIR'])\n"
            "request_dir.mkdir(parents=True, exist_ok=True)\n"
            "counter = request_dir / 'collect-count.txt'\n"
            "action = os.environ.get('BROWSER_AGENT_CHATGPT_ACTION', 'run')\n"
            "if action == 'submit':\n"
            "    print(json.dumps({'status': 'submitted', 'url': 'https://chatgpt.com/c/async-demo', 'conversation_id': 'async-demo'}, ensure_ascii=False))\n"
            "elif action == 'collect':\n"
            "    value = int(counter.read_text() or '0') if counter.exists() else 0\n"
            "    counter.write_text(str(value + 1))\n"
            "    if value == 0:\n"
            "        print(json.dumps({'status': 'running', 'url': 'https://chatgpt.com/c/async-demo', 'conversation_id': 'async-demo'}, ensure_ascii=False))\n"
            "    else:\n"
            "        print('final async answer')\n"
            "else:\n"
            "    print('unexpected action')\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("TECH_HOTSPOT_BROWSER_CHATGPT_CMD", f"{sys.executable} {wrapper}")
        monkeypatch.setenv("BROWSER_AGENT_CHATGPT_PROFILE_POLICY_DISABLED", "true")
        monkeypatch.setenv("HARNESS_DIR", str(Path(td)))

        rc1 = drain_once(
            actor_id="browser_agent_session",
            mailbox_base=base,
            lease_dir=lease_dir,
        )
        assert rc1 == 0
        active_dir = Path(td) / "run" / "browser-agent-session-active" / "chatgpt"
        manifests = sorted(active_dir.glob("*.json"))
        assert len(manifests) == 1
        first_results = mailbox.read_results("task-async")
        assert any(item["status"] == "submitted" for item in first_results)

        rc2 = drain_once(
            actor_id="browser_agent_session",
            mailbox_base=base,
            lease_dir=lease_dir,
        )
        assert rc2 == 0
        manifests = sorted(active_dir.glob("*.json"))
        assert len(manifests) == 1
        second_results = mailbox.read_results("task-async")
        assert not any(item["status"] == "completed" for item in second_results)

        rc3 = drain_once(
            actor_id="browser_agent_session",
            mailbox_base=base,
            lease_dir=lease_dir,
        )
        assert rc3 == 0
        manifests = sorted(active_dir.glob("*.json"))
        assert manifests == []
        final_results = mailbox.read_results("task-async")
        assert any(item["status"] == "completed" for item in final_results)
