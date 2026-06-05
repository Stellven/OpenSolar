#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_adapter(sprints_dir: Path):
    adapter_path = Path(__file__).resolve().parents[1] / "lib" / "operator_health_watchdog_lease_adapters.py"
    import os
    import sys

    os.environ["SOLAR_HARNESS_SPRINTS_DIR"] = str(sprints_dir)
    if "operator_health_watchdog_lease_adapters" in sys.modules:
        del sys.modules["operator_health_watchdog_lease_adapters"]

    spec = importlib.util.spec_from_file_location(
        "operator_health_watchdog_lease_adapters",
        adapter_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_reconcile_stale_leases_release_when_dead_pid(monkeypatch, tmp_path):
    lease_dir = tmp_path / "leases"
    status_dir = tmp_path / "status"
    lease_dir.mkdir()
    status_dir.mkdir()

    lease_file = lease_dir / "op-1.json"
    _write_json(lease_file, {"lease_id": "L1", "expires_at": "2099-01-01T00:00:00Z"})
    _write_json(status_dir / "op-1.json", {"worker_pid": 999999})

    adapter = _load_adapter(tmp_path / "sprints")

    monkeypatch.setattr(adapter, "_pid_exists", lambda pid: False)
    released = {"args": []}

    runtime = SimpleNamespace(
        release_operator_lease=lambda operator_id, reason: released["args"].append((operator_id, reason)) or True
    )

    result = adapter.reconcile_stale_leases(
        runtime_module=runtime,
        lease_dir=lease_dir,
        status_dir=status_dir,
        apply=True,
        now=dt.datetime(2026, 6, 5, 0, 0, 0, tzinfo=dt.timezone.utc),
    )

    assert result["ok"] is True
    assert result["summary"]["released"] == 1
    assert result["summary"]["checked"] == 1
    assert len(result["actions"]) == 1
    assert released["args"] == [("op-1", "watchdog_stale_recovery")]


def test_reconcile_stale_leases_skips_active_pid_or_future_ttl(tmp_path, monkeypatch):
    lease_dir = tmp_path / "leases"
    status_dir = tmp_path / "status"
    lease_dir.mkdir()
    status_dir.mkdir()

    lease_file = lease_dir / "op-2.json"
    _write_json(lease_file, {"lease_id": "L2", "expires_at": "2099-01-01T00:00:00Z"})
    _write_json(status_dir / "op-2.json", {"worker_pid": 222222})

    adapter = _load_adapter(tmp_path / "sprints")
    monkeypatch.setattr(adapter, "_pid_exists", lambda pid: True)
    release_calls = []
    runtime = SimpleNamespace(
        release_operator_lease=lambda operator_id, reason: release_calls.append((operator_id, reason)) or True
    )

    result = adapter.reconcile_stale_leases(
        runtime_module=runtime,
        lease_dir=lease_dir,
        status_dir=status_dir,
        apply=True,
        now=dt.datetime(2026, 6, 1, 0, 0, 0, tzinfo=dt.timezone.utc),
    )

    assert result["ok"] is True
    assert result["summary"]["released"] == 0
    assert result["summary"]["checked"] == 1
    assert result["skipped"][0]["reason"] == "active_pid_or_ttl"
    assert release_calls == []


def test_reconcile_stale_leases_releases_expired_ttl_without_pid(tmp_path, monkeypatch):
    lease_dir = tmp_path / "leases"
    status_dir = tmp_path / "status"
    lease_dir.mkdir()
    status_dir.mkdir()

    lease_file = lease_dir / "op-3.json"
    _write_json(lease_file, {"lease_id": "L3", "expires_at": "2026-06-01T00:00:00Z"})

    adapter = _load_adapter(tmp_path / "sprints")
    monkeypatch.setattr(adapter, "_pid_exists", lambda pid: True)
    released = []
    runtime = SimpleNamespace(
        release_operator_lease=lambda operator_id, reason: released.append((operator_id, reason)) or True
    )

    result = adapter.reconcile_stale_leases(
        runtime_module=runtime,
        lease_dir=lease_dir,
        status_dir=status_dir,
        apply=True,
        now=dt.datetime(2026, 6, 2, 0, 0, 0, tzinfo=dt.timezone.utc),
    )

    assert result["ok"] is True
    assert result["summary"]["released"] == 1
    assert released == [("op-3", "watchdog_stale_recovery")]


def test_repair_status_projection_marks_builder_reviewing_on_exact_dispatch_and_handoff(tmp_path):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sprint_id = "sprint-health"
    task_id = "pm-task-exact"
    graph_path = sprints / f"{sprint_id}.task_graph.json"
    _write_json(
        graph_path,
        {
            "sprint_id": sprint_id,
            "nodes": [
                {
                    "id": "B4",
                    "status": "dispatched",
                    "assigned_to": "mini-codex",
                    "dispatch_id": task_id,
                    "pm_task_id": "other",
                }
            ],
            "node_results": {
                "B4": {
                    "status": "dispatched",
                    "dispatch_id": task_id,
                }
            },
        },
    )
    handoff = sprints / f"{sprint_id}.B4-handoff.md"
    handoff.write_text("done", encoding="utf-8")
    (sprints / f"{sprint_id}.B4-eval.md").write_text("eval", encoding="utf-8")

    adapter = _load_adapter(sprints)
    record = {"sprint_id": sprint_id, "node_id": "B4", "task_id": task_id}
    result = adapter.repair_status_projection(record, graph_dir=sprints, apply=True)

    assert result["ok"] is True
    assert len(result["actions"]) == 1
    assert result["actions"][0]["action_type"] == "mark_builder_reviewing"

    repaired = json.loads(graph_path.read_text(encoding="utf-8"))
    assert repaired["nodes"][0]["status"] == "reviewing"
    assert repaired["nodes"][0]["handoff_path"] == str(handoff)
    assert "dispatch_id" not in repaired["nodes"][0]
    assert "eval_assignments" not in repaired["nodes"][0]


def test_repair_status_projection_clears_eval_assignment_exact_identity_and_sidecar_present(tmp_path):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sprint_id = "sprint-health-eval"
    task_id = "pm-task-eval"
    graph_path = sprints / f"{sprint_id}.task_graph.json"
    _write_json(
        graph_path,
        {
            "sprint_id": sprint_id,
            "nodes": [
                {
                    "id": "B4",
                    "status": "dispatched",
                    "eval_dispatch_id": task_id,
                    "eval_dispatched_at": "2026-06-01T00:00:00Z",
                    "eval_assignments": [
                        {"task_id": task_id, "operator_id": "mini-codex-eval"},
                        {"task_id": "other", "operator_id": "other-op"},
                    ],
                }
            ],
            "node_results": {
                "B4": {
                    "status": "dispatched",
                }
            },
        },
    )
    (sprints / f"{sprint_id}.B4-eval.md").write_text("eval", encoding="utf-8")

    adapter = _load_adapter(sprints)
    result = adapter.repair_status_projection(
        {
            "sprint_id": sprint_id,
            "node_id": "B4",
            "task_id": task_id,
        },
        graph_dir=sprints,
        apply=True,
    )

    assert result["summary"]["applied"] == 1
    assert result["actions"][0]["action_type"] == "clear_evaluator_assignment"
    repaired = json.loads(graph_path.read_text(encoding="utf-8"))
    assignments = repaired["nodes"][0]["eval_assignments"]
    assert len(assignments) == 1
    assert assignments[0]["task_id"] == "other"


def test_repair_status_projection_respects_dispatch_mismatch(tmp_path):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sprint_id = "sprint-health-mismatch"
    task_id = "pm-task-good"
    bad_task_id = "pm-task-bad"
    graph_path = sprints / f"{sprint_id}.task_graph.json"
    _write_json(
        graph_path,
        {
            "sprint_id": sprint_id,
            "nodes": [
                {
                    "id": "B4",
                    "status": "dispatched",
                    "dispatch_id": task_id,
                }
            ],
            "node_results": {
                "B4": {"status": "dispatched", "dispatch_id": task_id},
            },
        },
    )
    adapter = _load_adapter(sprints)
    result = adapter.repair_status_projection(
        {"sprint_id": sprint_id, "node_id": "B4", "task_id": bad_task_id},
        graph_dir=sprints,
        apply=True,
    )

    assert result["ok"] is False
    assert result["skipped"][0]["reason"] == "dispatch_mismatch"
    repaired = json.loads(graph_path.read_text(encoding="utf-8"))
    assert repaired["nodes"][0]["status"] == "dispatched"
