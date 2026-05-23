#!/usr/bin/env python3
"""Tests for operatord daemon mode (N3 acceptance criteria).

Covers:
- Unit tests for operator_runtime utility functions added in N3
- Integration test: submit a task → daemon --once processes it end-to-end
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

HARNESS_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = HARNESS_ROOT / "lib"
TOOLS_DIR = HARNESS_ROOT / "tools"
REAL_PERSONAS_DIR = HARNESS_ROOT / "personas"

sys.path.insert(0, str(LIB_DIR))

import operator_runtime as _rt  # noqa: E402 — after path setup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_REGISTRY = {
    "version": 1,
    "operators": {
        "test-local-builder": {
            "display_name": "Test Local Builder (N3 test operator)",
            "role": "builder",
            "persona": "builder",
            "backend": "local",
            "model": "local",
            "enabled": True,
        }
    },
}

_TASK_ENVELOPE = {
    "task_id": "T-n3-test-001",
    "sprint_id": "sprint-test-n3",
    "node_id": "N3",
    "operator_id": "test-local-builder",
    "task_type": "dummy",
    "objective": "Verify operatord daemon end-to-end lifecycle.",
}


def _setup_harness(tmp_path: Path) -> dict:
    """Create a minimal harness directory and return the env dict."""
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "personas").mkdir(parents=True)

    # Registry
    (tmp_path / "config" / "physical-operators.json").write_text(
        json.dumps(_MINIMAL_REGISTRY, indent=2)
    )

    # Persona file — copy real one if available, else write minimal content
    real_persona = REAL_PERSONAS_DIR / "builder.md"
    dest_persona = tmp_path / "personas" / "builder.md"
    if real_persona.exists():
        shutil.copy(real_persona, dest_persona)
    else:
        dest_persona.write_text("# Builder\nYou are a builder.")

    env = {**os.environ, "HARNESS_DIR": str(tmp_path)}
    return env


# ---------------------------------------------------------------------------
# Unit tests: scrub_secrets
# ---------------------------------------------------------------------------

class TestScrubSecrets:
    def test_scrubs_openai_key(self):
        text = "Using key sk-abcdefghijklmnopqrstuvwxyzABCDEFGH in request"
        out = _rt.scrub_secrets(text)
        assert "sk-" not in out
        assert "[SCRUBBED]" in out

    def test_scrubs_github_pat(self):
        text = "export TOKEN=ghp_" + "a" * 36
        out = _rt.scrub_secrets(text)
        assert "ghp_" not in out
        assert "[SCRUBBED]" in out

    def test_scrubs_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
        out = _rt.scrub_secrets(text)
        assert "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" not in out

    def test_passthrough_plain_text(self):
        text = "No secrets here, just a normal log line."
        assert _rt.scrub_secrets(text) == text


# ---------------------------------------------------------------------------
# Unit tests: list_inbox_tasks
# ---------------------------------------------------------------------------

class TestListInboxTasks:
    def test_empty_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_rt, "OPERATOR_INBOX_DIR", tmp_path / "inbox")
        result = _rt.list_inbox_tasks("no-such-operator")
        assert result == []

    def test_returns_tasks(self, tmp_path, monkeypatch):
        inbox = tmp_path / "inbox" / "my-op"
        inbox.mkdir(parents=True)
        env = {"task_id": "T-001", "sprint_id": "s1", "node_id": "N1",
               "operator_id": "my-op", "task_type": "dummy", "objective": "test"}
        (inbox / "T-001.json").write_text(json.dumps(env))

        monkeypatch.setattr(_rt, "OPERATOR_INBOX_DIR", tmp_path / "inbox")
        tasks = _rt.list_inbox_tasks("my-op")
        assert len(tasks) == 1
        tid, envelope, path = tasks[0]
        assert tid == "T-001"
        assert envelope["task_id"] == "T-001"
        assert path.name == "T-001.json"


# ---------------------------------------------------------------------------
# Unit tests: write_heartbeat
# ---------------------------------------------------------------------------

class TestWriteHeartbeat:
    def _patch_dirs(self, monkeypatch, tmp_path):
        status_dir = tmp_path / "run" / "operator-status"
        monkeypatch.setattr(_rt, "OPERATOR_STATUS_DIR", status_dir)
        monkeypatch.setattr(_rt, "OPERATOR_LEASE_DIR", tmp_path / "run" / "operator-leases")
        return status_dir

    def test_writes_heartbeat_file(self, tmp_path, monkeypatch):
        status_dir = self._patch_dirs(monkeypatch, tmp_path)
        _rt.write_heartbeat("op1", "idle", resolved_persona="builder")

        hb = json.loads((status_dir / "op1.json").read_text())
        assert hb["runtime_state"] == "idle"
        assert hb["state"] == "idle"
        assert "heartbeat_at" in hb
        assert hb["resolved_persona"] == "builder"

    def test_includes_current_task(self, tmp_path, monkeypatch):
        self._patch_dirs(monkeypatch, tmp_path)
        _rt.write_heartbeat("op1", "running", current_task_id="T-abc")

        hb_path = tmp_path / "run" / "operator-status" / "op1.json"
        hb = json.loads(hb_path.read_text())
        assert hb["current_task_id"] == "T-abc"


# ---------------------------------------------------------------------------
# Unit tests: write_result
# ---------------------------------------------------------------------------

class TestWriteResult:
    def _patch_dirs(self, monkeypatch, tmp_path):
        results_dir = tmp_path / "run" / "operator-results"
        monkeypatch.setattr(_rt, "OPERATOR_RESULTS_DIR", results_dir)
        return results_dir

    def test_writes_result_json(self, tmp_path, monkeypatch):
        results_dir = self._patch_dirs(monkeypatch, tmp_path)
        path = _rt.write_result(
            operator_id="op1",
            task_id="T-001",
            sprint_id="sprint-1",
            node_id="N1",
            status="completed",
            exit_code=0,
            started_at="2026-05-22T00:00:00Z",
            finished_at="2026-05-22T00:00:05Z",
            log_tail="task=T-001\ncompleted",
        )
        assert path.exists()
        result = json.loads(path.read_text())
        assert result["task_id"] == "T-001"
        assert result["operator_id"] == "op1"
        assert result["status"] == "completed"
        assert result["exit_code"] == 0
        assert result["started_at"] == "2026-05-22T00:00:00Z"
        assert result["finished_at"] == "2026-05-22T00:00:05Z"
        assert "log_tail" in result

    def test_scrubs_secrets_in_log_tail(self, tmp_path, monkeypatch):
        self._patch_dirs(monkeypatch, tmp_path)
        _rt.write_result(
            operator_id="op1",
            task_id="T-002",
            sprint_id="s1",
            node_id="N1",
            status="completed",
            exit_code=0,
            started_at="2026-05-22T00:00:00Z",
            finished_at="2026-05-22T00:00:01Z",
            log_tail="sk-secretkeyABCDEFGHIJKLMNOPQRSTUVWXYZ logged",
        )
        result_path = tmp_path / "run" / "operator-results" / "op1" / "T-002" / "result.json"
        result = json.loads(result_path.read_text())
        assert "sk-secret" not in result["log_tail"]
        assert "[SCRUBBED]" in result["log_tail"]


# ---------------------------------------------------------------------------
# Integration test: full daemon --once end-to-end
# ---------------------------------------------------------------------------

class TestDaemonOnce:
    """Run the full operatord daemon --once via subprocess with a temp HARNESS_DIR."""

    OPERATOR_ID = "test-local-builder"
    TASK_ID = "T-n3-test-001"

    def _run_submit(self, env: dict, envelope_path: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(TOOLS_DIR / "..") + "/lib/operator_runtime.py",
                "submit",
                "--envelope",
                str(envelope_path),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"submit failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        return json.loads(result.stdout)

    def _run_daemon_once(self, env: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(TOOLS_DIR / "operatord.py"),
                "daemon",
                "--operator",
                self.OPERATOR_ID,
                "--once",
                "--poll-interval",
                "0.2",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_end_to_end(self, tmp_path):
        env = _setup_harness(tmp_path)

        # Write task envelope file
        envelope_path = tmp_path / "envelope.json"
        envelope = dict(_TASK_ENVELOPE)
        envelope_path.write_text(json.dumps(envelope))

        # Submit task via operator_runtime CLI
        submit_out = self._run_submit(env, envelope_path)
        assert submit_out["status"] == "submitted"
        assert submit_out["task_id"] == self.TASK_ID

        # Verify inbox was populated
        inbox_file = (
            tmp_path
            / "run"
            / "operator-inbox"
            / self.OPERATOR_ID
            / f"{self.TASK_ID}.json"
        )
        assert inbox_file.exists(), "Inbox file should be created by submit()"

        # Run daemon --once
        daemon_proc = self._run_daemon_once(env)
        assert daemon_proc.returncode == 0, (
            f"daemon --once failed:\nstdout={daemon_proc.stdout}\nstderr={daemon_proc.stderr}"
        )

        # ── Verify result artifact ────────────────────────────────────────────
        result_json = (
            tmp_path
            / "run"
            / "operator-results"
            / self.OPERATOR_ID
            / self.TASK_ID
            / "result.json"
        )
        assert result_json.exists(), (
            f"result.json not found at {result_json}\n"
            f"daemon stdout:\n{daemon_proc.stdout}\n"
            f"daemon stderr:\n{daemon_proc.stderr}"
        )
        result = json.loads(result_json.read_text())

        # Acceptance: result artifact must contain these fields
        assert result["task_id"] == self.TASK_ID
        assert result["operator_id"] == self.OPERATOR_ID
        assert result["status"] == "completed"
        assert "started_at" in result
        assert "finished_at" in result
        assert "log_tail" in result
        assert result["exit_code"] == 0

        # ── Verify status transitions via heartbeat file ───────────────────────
        hb_file = (
            tmp_path
            / "run"
            / "operator-status"
            / f"{self.OPERATOR_ID}.json"
        )
        assert hb_file.exists(), "Heartbeat status file should be written"
        hb = json.loads(hb_file.read_text())
        # After --once completes, daemon resets to idle
        assert hb["runtime_state"] == "idle"
        assert "heartbeat_at" in hb

        # ── Verify inbox is cleaned up ────────────────────────────────────────
        assert not inbox_file.exists(), (
            "Task envelope should be removed from inbox after processing"
        )

        # ── Verify lease is released ──────────────────────────────────────────
        lease_file = (
            tmp_path
            / "run"
            / "operator-leases"
            / f"{self.OPERATOR_ID}.json"
        )
        assert not lease_file.exists(), (
            "Lease file should be removed after task completion"
        )

    def test_output_log_written(self, tmp_path):
        env = _setup_harness(tmp_path)
        envelope_path = tmp_path / "envelope2.json"
        envelope = dict(_TASK_ENVELOPE)
        envelope["task_id"] = "T-n3-test-002"
        envelope_path.write_text(json.dumps(envelope))

        self._run_submit(env, envelope_path)

        daemon_proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS_DIR / "operatord.py"),
                "daemon",
                "--operator",
                self.OPERATOR_ID,
                "--once",
                "--poll-interval",
                "0.2",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert daemon_proc.returncode == 0

        output_log = (
            tmp_path
            / "run"
            / "operator-results"
            / self.OPERATOR_ID
            / "T-n3-test-002"
            / "output.log"
        )
        assert output_log.exists(), "output.log should be written alongside result.json"
        log_content = output_log.read_text()
        assert "T-n3-test-002" in log_content or "operatord" in log_content

    def test_signal_leaves_final_status(self, tmp_path):
        """SIGTERM while idle should leave a final idle status file."""
        import signal as _signal

        env = _setup_harness(tmp_path)

        # Start daemon with no task submitted (will poll and wait)
        proc = subprocess.Popen(
            [
                sys.executable,
                str(TOOLS_DIR / "operatord.py"),
                "daemon",
                "--operator",
                self.OPERATOR_ID,
                "--poll-interval",
                "0.1",
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Wait until at least one heartbeat is written
        hb_file = (
            tmp_path
            / "run"
            / "operator-status"
            / f"{self.OPERATOR_ID}.json"
        )
        deadline = time.time() + 5.0
        while not hb_file.exists() and time.time() < deadline:
            time.sleep(0.1)

        assert hb_file.exists(), "Heartbeat should be written within 5s of daemon start"

        # Send SIGTERM
        proc.send_signal(_signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        # Final status should be idle
        hb = json.loads(hb_file.read_text())
        assert hb["runtime_state"] == "idle", (
            f"Final heartbeat after SIGTERM should be idle, got {hb['runtime_state']}"
        )
