from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.append(str(ROOT / "tools"))

from actor_mailbox import ActorMailbox
from browser_agent_session_control import main as control_main


def _run_cli(args: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = control_main(args)
    text = buf.getvalue().strip()
    return rc, json.loads(text) if text else {}


def test_supervisor_status_drain_stop(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        monkeypatch.setenv("HARNESS_DIR", str(td_path))
        state_dir = td_path / "run" / "browser-agent-session-supervisor"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "browser_agent_session.pid").write_text("43210", encoding="utf-8")
        (state_dir / "browser_agent_session.json").write_text(
            json.dumps({"status": "running", "loop_count": 3}),
            encoding="utf-8",
        )
        monkeypatch.setattr("browser_agent_session_actor._pid_alive", lambda pid: pid == 43210)

        rc, status = _run_cli(["supervisor", "status"])
        assert rc == 0
        assert status["pid"] == 43210
        assert status["pid_alive"] is True

        rc, drain = _run_cli(["supervisor", "drain"])
        assert rc == 0
        assert Path(drain["drain_flag"]).exists()

        killpg_calls: list[tuple[int, int]] = []
        kill_calls: list[tuple[int, int]] = []
        monkeypatch.setattr("os.killpg", lambda pid, sig: killpg_calls.append((pid, sig)))
        monkeypatch.setattr("os.kill", lambda pid, sig: kill_calls.append((pid, sig)))
        rc, stop = _run_cli(["supervisor", "stop"])
        assert rc == 0
        assert Path(stop["stop_flag"]).exists()
        assert killpg_calls == [(43210, 15)]
        assert kill_calls == []


def test_submit_poll_collect_cli(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        monkeypatch.setenv("HARNESS_DIR", str(td_path))
        mailbox = ActorMailbox("browser_agent_session", td_path / "actors")

        class FakeSubmitResult:
            success = True
            error = None
            lease = None
            inbox_path = str(td_path / "actors" / "browser_agent_session" / "inbox" / "task-demo.json")
            outbox_path = str(td_path / "actors" / "browser_agent_session" / "outbox")
            evidence_ledger_path = ""
            scheduler_decision = {}

            def to_dict(self):
                return {
                    "success": True,
                    "lease": None,
                    "inbox_path": self.inbox_path,
                    "outbox_path": self.outbox_path,
                    "evidence_ledger_path": "",
                    "scheduler_decision": {},
                    "error": None,
                }

        class FakeRuntime:
            def submit(self, task_envelope, logical_operator=None):
                mailbox.submit_task(task_envelope)
                return FakeSubmitResult()

        monkeypatch.setattr("browser_agent_session_control._runtime", lambda: FakeRuntime())
        rc, submit = _run_cli(["submit", "--task-id", "task-demo", "--prompt", "研究实现 一个测试"])
        assert rc == 0
        assert submit["task_id"] == "task-demo"
        assert submit["actor_id"] == "browser_agent_session"
        assert submit["inbox_task_file"]

        rc, poll_queued = _run_cli(["poll", "--task-id", "task-demo"])
        assert rc == 0
        assert poll_queued["status"] == "queued"

        request_dir = td_path / "req"
        request_dir.mkdir(parents=True, exist_ok=True)
        mailbox.write_result(
            "task-demo",
            {
                "task_id": "task-demo",
                "status": "completed",
                "request_dir": str(request_dir),
                "text": "final answer",
            },
        )
        rc, poll_done = _run_cli(["poll", "--task-id", "task-demo"])
        assert rc == 0
        assert poll_done["status"] == "completed"

        rc, collected = _run_cli(["collect", "--task-id", "task-demo", "--timeout-seconds", "1", "--poll-interval-seconds", "0.2"])
        assert rc == 0
        assert collected["status"] == "completed"
