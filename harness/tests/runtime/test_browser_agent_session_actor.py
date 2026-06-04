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
from browser_agent_session_actor import drain_once, ensure_supervisor_running, supervise_loop


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


def test_browser_agent_session_actor_processes_gemini_task(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "actors"
        lease_dir = Path(td) / "run" / "actor-leases"
        mailbox = ActorMailbox("browser_agent_session", base)
        envelope = {
            "task_id": "task-gemini",
            "logical_operator": "DeepResearchGemini",
            "gemini_deep_research_request": {
                "prompt": "研究 gemini task",
                "expected_output": "markdown",
                "project_name": "杂项",
            },
        }
        mailbox.submit_task(envelope)
        operator = Path(td) / "fake_gemini_operator.py"
        operator.write_text(
            "import json, os\n"
            "from pathlib import Path\n"
            "task_dir = Path(os.environ['TASK_DIR'])\n"
            "request_dir = task_dir / 'gemini-deep-research-request'\n"
            "request_dir.mkdir(parents=True, exist_ok=True)\n"
            "(request_dir / 'assistant-response.txt').write_text('gemini actor ok', encoding='utf-8')\n"
            "(request_dir / 'page.json').write_text(json.dumps({'title': 'Gemini', 'url': 'https://gemini.google.com/app/1', 'conversation_id': '1', 'citations': []}), encoding='utf-8')\n"
            "(task_dir / 'gemini-deep-research-result.json').write_text(json.dumps({'ok': True, 'text': 'gemini actor ok', 'request_dir': str(request_dir), 'project_name': '杂项', 'expected_output': 'markdown'}, ensure_ascii=False), encoding='utf-8')\n"
            "print('gemini actor ok')\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("HARNESS_DIR", str(Path(td)))
        monkeypatch.setattr("browser_agent_session_actor.resolve_command", lambda envelope: [sys.executable, str(operator)])

        rc = drain_once(
            actor_id="browser_agent_session",
            mailbox_base=base,
            lease_dir=lease_dir,
        )
        assert rc == 0
        results = mailbox.read_results("task-gemini")
        assert len(results) == 1
        assert results[0]["status"] == "completed"
        assert results[0]["result_file"].endswith("gemini-deep-research-result.json")
        assert Path(results[0]["result_file"]).exists()


def test_supervise_loop_writes_state_and_prewarms_slots(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "actors"
        lease_dir = Path(td) / "run" / "actor-leases"
        monkeypatch.setenv("HARNESS_DIR", str(Path(td)))
        rc = supervise_loop(
            actor_id="browser_agent_session",
            mailbox_base=base,
            lease_dir=lease_dir,
            poll_interval_seconds=0.01,
            max_loops=1,
        )
        assert rc == 0
        state_path = Path(td) / "run" / "browser-agent-session-supervisor" / "browser_agent_session.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["status"] == "stopped"
        assert state["loop_count"] == 1
        pool_dir = Path(td) / "run" / "browser-agent-session-pool" / "chatgpt"
        assert (pool_dir / "slot-01.json").exists()
        assert (pool_dir / "slot-02.json").exists()


def test_ensure_supervisor_running_reuses_alive_pid(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "actors"
        lease_dir = Path(td) / "run" / "actor-leases"
        pid_path = Path(td) / "run" / "browser-agent-session-supervisor" / "browser_agent_session.pid"
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text("43210", encoding="utf-8")
        monkeypatch.setenv("HARNESS_DIR", str(Path(td)))
        monkeypatch.setattr("browser_agent_session_actor._pid_alive", lambda pid: pid == 43210)
        result = ensure_supervisor_running(
            actor_id="browser_agent_session",
            mailbox_base=base,
            lease_dir=lease_dir,
        )
        assert result["ok"] is True
        assert result["reused"] is True
        assert result["pid"] == 43210
