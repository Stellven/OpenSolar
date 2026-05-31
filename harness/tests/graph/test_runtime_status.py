"""Regression tests for runtime-backed status cache transitions."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import runtime_status  # noqa: E402


class _NoopRuntime:
    def __init__(self, sid: str, harness_dir: str) -> None:
        self.sid = sid
        self.harness_dir = harness_dir

    def state_transition(self, **kwargs) -> None:
        return None


def test_terminal_passed_transition_clears_stale_graph_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_status, "ActivityRuntime", _NoopRuntime)
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    status_path = sprints / "sprint-test.status.json"
    status_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-test",
                "status": "active",
                "phase": "graph_in_progress",
                "round": 1,
                "active_node": "N6",
                "open_nodes": ["N4", "N5", "N6"],
                "failed_nodes": ["N5"],
                "history": [],
            }
        ),
        encoding="utf-8",
    )

    updated, _ = runtime_status.transition_status(
        status_path,
        "passed",
        "patrol_terminal_cleanup",
        "test",
    )

    assert updated["status"] == "passed"
    assert updated["phase"] == "eval_passed"
    assert updated["active_node"] is None
    assert "open_nodes" not in updated
    assert "failed_nodes" not in updated


def test_planner_ready_epic_child_transition_is_canonicalized_to_active(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_status, "ActivityRuntime", _NoopRuntime)
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    status_path = sprints / "sprint-epic-child.status.json"
    status_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-epic-child",
                "status": "drafting",
                "phase": "spec",
                "handoff_to": "pm",
                "target_role": "pm",
                "epic_id": "epic-demo",
                "dependency_policy": "activated_by_epic_dag",
                "round": 1,
                "history": [],
            }
        ),
        encoding="utf-8",
    )

    updated, _ = runtime_status.transition_status(
        status_path,
        "drafting",
        "planner_gate_ready",
        "test",
        extra={
            "status_fields": {
                "phase": "prd_ready",
                "handoff_to": "planner",
                "target_role": "planner",
            }
        },
    )

    assert updated["status"] == "active"
    assert updated["phase"] == "prd_ready"
    assert updated["handoff_to"] == "planner"
    assert updated["target_role"] == "planner"


def test_terminal_status_is_sticky_without_explicit_reopen(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_status, "ActivityRuntime", _NoopRuntime)
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    status_path = sprints / "sprint-sticky.status.json"
    status_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-sticky",
                "status": "passed",
                "phase": "eval_passed",
                "round": 1,
                "history": [],
            }
        ),
        encoding="utf-8",
    )

    updated, message = runtime_status.transition_status(
        status_path,
        "drafting",
        "bad_reopen_attempt",
        "test",
    )

    assert updated["status"] == "passed"
    assert updated["phase"] == "eval_passed"
    assert "ignored attempted downgrade" in message
    assert updated["history"][-1]["note"] == "terminal_status_sticky: attempted downgrade ignored"
    assert updated["history"][-1]["attempted_status"] == "drafting"
