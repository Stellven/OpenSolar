"""test_browser_agent_operator.py — Unit tests for async Browser Agent job runtime and mock adapter.

Verifies submit, poll, collect, and cancel flows under the mock job runner.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Path setup
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import browser_job_runtime as bjrt


@pytest.fixture(autouse=True)
def setup_teardown_env(monkeypatch):
    """Fixture to isolate run directories for test execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        monkeypatch.setattr(bjrt, "BROWSER_JOBS_DIR", tmp_path / "run" / "browser-jobs")
        monkeypatch.setattr(bjrt, "OPERATOR_RESULTS_DIR", tmp_path / "run" / "operator-results")
        yield


def test_submit_browser_job():
    """Verify submit_browser_job initializes state on disk and returns a valid ID."""
    envelope = {
        "task_id": "T001",
        "sprint_id": "sprint-test",
        "node_id": "N3",
        "operator_id": "mini-browser-deepresearch",
        "task_type": "RESEARCH",
        "objective": "Test async submission"
    }

    job_id = bjrt.submit_browser_job("mini-browser-deepresearch", envelope)
    assert job_id.startswith("job-")

    # Check state on disk
    job_dir = bjrt.BROWSER_JOBS_DIR / job_id
    assert job_dir.exists()
    state_file = job_dir / "state.json"
    assert state_file.exists()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["job_id"] == job_id
    assert state["actor_id"] == "mini-browser-deepresearch"
    assert state["state"] == "submitted"
    assert state["envelope"] == envelope


def test_poll_mock_sequence():
    """Verify poll transitions the job state according to the mock sequence."""
    envelope = {"task_id": "T001"}
    sequence = ["running", "waiting_human", "reauth_required", "done"]

    job_id = bjrt.submit_browser_job("mini-browser-deepresearch", envelope, mock_sequence=sequence)

    # Initial poll should be at the start of mock sequence
    r1 = bjrt.poll_browser_job(job_id)
    assert r1["state"] == "running"

    # Subsequent polls transition state
    r2 = bjrt.poll_browser_job(job_id)
    assert r2["state"] == "waiting_human"

    r3 = bjrt.poll_browser_job(job_id)
    assert r3["state"] == "reauth_required"

    r4 = bjrt.poll_browser_job(job_id)
    assert r4["state"] == "done"
    assert len(r4["artifacts"]) == 2
    assert any(a["name"] == "screenshot.png" for a in r4["artifacts"])

    # Polling after done should remain done
    r5 = bjrt.poll_browser_job(job_id)
    assert r5["state"] == "done"


def test_collect_browser_job_success():
    """Verify collect writes a structured result.json and copies artifacts on success."""
    envelope = {
        "task_id": "T001",
        "sprint_id": "sprint-test",
        "node_id": "N3",
        "operator_id": "mini-browser-deepresearch"
    }
    sequence = ["running", "done"]

    job_id = bjrt.submit_browser_job("mini-browser-deepresearch", envelope, mock_sequence=sequence)

    # Poll twice to reach done state
    bjrt.poll_browser_job(job_id)
    bjrt.poll_browser_job(job_id)

    # Collect the job results
    with tempfile.TemporaryDirectory() as outdir:
        out_path = Path(outdir)
        result = bjrt.collect_browser_job(job_id, output_dir=out_path)

        assert result["task_id"] == "T001"
        assert result["operator_id"] == "mini-browser-deepresearch"
        assert result["status"] == "completed"
        assert result["exit_code"] == 0
        assert "screenshot.png" in [Path(a).name for a in result["artifacts"]]

        # Verify output directory contains result.json and artifacts
        assert (out_path / "result.json").exists()
        assert (out_path / "screenshot.png").exists()
        assert (out_path / "logs.txt").exists()


def test_collect_browser_job_not_terminal():
    """Verify collect raises RuntimeError if the job is not in a terminal state."""
    envelope = {"task_id": "T001"}
    sequence = ["running", "done"]
    job_id = bjrt.submit_browser_job("mini-browser-deepresearch", envelope, mock_sequence=sequence)

    bjrt.poll_browser_job(job_id)  # State is running (non-terminal)

    with pytest.raises(RuntimeError, match="Cannot collect job"):
        bjrt.collect_browser_job(job_id)


def test_collect_browser_job_failed():
    """Verify collect processes failed and timeout states correctly."""
    envelope = {
        "task_id": "T001",
        "sprint_id": "sprint-test",
        "node_id": "N3",
        "operator_id": "mini-browser-deepresearch"
    }
    sequence = ["running", "failed"]

    job_id = bjrt.submit_browser_job("mini-browser-deepresearch", envelope, mock_sequence=sequence)
    bjrt.poll_browser_job(job_id)
    bjrt.poll_browser_job(job_id)

    with tempfile.TemporaryDirectory() as outdir:
        out_path = Path(outdir)
        result = bjrt.collect_browser_job(job_id, output_dir=out_path)

        assert result["status"] == "failed"
        assert result["exit_code"] == 1
        assert (out_path / "result.json").exists()


def test_cancel_browser_job():
    """Verify cancel_browser_job terminates the job and marks it as failed."""
    envelope = {"task_id": "T001"}
    job_id = bjrt.submit_browser_job("mini-browser-deepresearch", envelope)

    cancelled = bjrt.cancel_browser_job(job_id)
    assert cancelled is True

    # Polling should reflect cancelled/failed state
    state = bjrt.poll_browser_job(job_id)
    assert state["state"] == "failed"
    assert "cancelled" in state["logs"].lower()
