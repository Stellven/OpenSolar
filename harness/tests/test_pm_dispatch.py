#!/usr/bin/env python3
"""Tests for PM dispatch capability capsule integration."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM_DISPATCH_PATH = ROOT / "tools" / "pm_dispatch.py"


def _load_pm_dispatch():
    spec = importlib.util.spec_from_file_location("pm_dispatch", PM_DISPATCH_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_operator_by_role_prefers_capsule_operator_constraints(monkeypatch):
    pm_dispatch = _load_pm_dispatch()
    monkeypatch.setattr(
        pm_dispatch,
        "load_registry",
        lambda: {
            "version": 1,
            "operators": {
                "builder-a": {
                    "enabled": True,
                    "available": True,
                    "roles": ["builder"],
                    "launch_cmd_kind": "command",
                    "task_classes": ["implementation"],
                    "profile": "generic",
                    "preferred_for": [],
                },
                "builder-b": {
                    "enabled": True,
                    "available": True,
                    "roles": ["builder"],
                    "launch_cmd_kind": "command",
                    "task_classes": ["implementation"],
                    "profile": "generic",
                    "preferred_for": [],
                },
            },
        },
    )
    monkeypatch.setattr(pm_dispatch, "is_dispatchable", lambda op: (True, ""))
    operator_id, _, reason = pm_dispatch.select_operator_by_role(
        role="builder",
        task_type="implementation",
        resolved_capsule={"operator_constraints": {"preferred": ["builder-b"], "forbidden": [], "default_operator_profile": ""}},
    )
    assert reason == ""
    assert operator_id == "builder-b"


def test_cmd_submit_reads_task_graph_capsule_metadata(monkeypatch):
    pm_dispatch = _load_pm_dispatch()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        monkeypatch.setattr(pm_dispatch, "HARNESS_DIR", root)
        monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", root / "sprints")
        monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", root / "run" / "pm-inbox")
        monkeypatch.setattr(pm_dispatch, "OPERATOR_INBOX_DIR", root / "run" / "operator-inbox")
        monkeypatch.setattr(pm_dispatch, "OPERATOR_STATUS_DIR", root / "run" / "operator-status")
        monkeypatch.setattr(pm_dispatch, "PERSONAS_DIR", root / "personas")
        (root / "personas").mkdir(parents=True, exist_ok=True)
        (root / "personas" / "builder.md").write_text("# Builder\n", encoding="utf-8")
        sprint_graph = {
            "nodes": [
                {
                    "id": "S2",
                    "goal": "Implement the approved scope.",
                    "logical_operator": "ImplementationWorker",
                    "acceptance": ["Patch is produced within declared write scope."],
                    "requirement_ids": ["REQ-001"],
                    "capability_native": True,
                    "capability_capsule_id": "cap.requirement-compiler-implementation",
                    "dispatch_task_type": "implementation",
                    "capsule_plan": {
                        "capability_native": True,
                        "capability_capsule_id": "cap.requirement-compiler-implementation",
                        "dispatch_task_type": "implementation",
                    },
                }
            ]
        }
        (root / "sprints").mkdir(parents=True, exist_ok=True)
        (root / "sprints" / "sprint-cap.task_graph.json").write_text(json.dumps(sprint_graph), encoding="utf-8")

        monkeypatch.setattr(
            pm_dispatch,
            "load_registry",
            lambda: {
                "version": 1,
                "operators": {
                    "mini-claude-sonnet-builder": {
                        "enabled": True,
                        "available": True,
                        "roles": ["builder"],
                        "launch_cmd_kind": "command",
                        "task_classes": ["implementation"],
                        "profile": "builder",
                        "preferred_for": ["builder", "implementation"],
                        "model": "test-model",
                        "persona": "builder",
                    }
                },
            },
        )
        monkeypatch.setattr(pm_dispatch, "is_dispatchable", lambda op: (True, ""))

        sys.path.insert(0, str(ROOT / "lib"))
        import capability_capsules as caps

        monkeypatch.setattr(
            caps,
            "resolve_capability_capsule_for_task",
            lambda task, operator_id=None, registry_path=None: {
                "capability_capsule_id": "cap.requirement-compiler-implementation",
                "operator_constraints": {
                    "preferred": ["mini-claude-sonnet-builder"],
                    "forbidden": [],
                    "default_operator_profile": "mini-claude-sonnet-builder",
                },
            },
        )

        captured: dict[str, object] = {}
        fake_operator_runtime = types.ModuleType("operator_runtime")

        def _submit(envelope):
            captured["envelope"] = dict(envelope)
            return {
                "lease_id": "lease-1",
                "inbox_path": str(root / "run" / "operator-inbox" / "mini-claude-sonnet-builder" / "pm.json"),
            }

        fake_operator_runtime.submit = _submit  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "operator_runtime", fake_operator_runtime)
        monkeypatch.setenv("SOLAR_PM_DISPATCH_ALLOW_DIRECT", "1")

        args = argparse.Namespace(
            role="builder",
            objective="Implement the approved scope.",
            operator="",
            sprint="sprint-cap",
            node="S2",
            task_type="",
            context="",
            dry_run=False,
        )
        rc = pm_dispatch.cmd_submit(args)
        assert rc == 0
        envelope = captured["envelope"]
        assert envelope["capability_native"] is True
        assert envelope["capability_capsule_id"] == "cap.requirement-compiler-implementation"
        assert envelope["logical_operator"] == "ImplementationWorker"
        assert envelope["task_type"] == "implementation"


def test_cmd_compile_request_rejects_invalid_compiled_package(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    monkeypatch.setenv("SOLAR_PM_DISPATCH_ALLOW_DIRECT", "1")
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", tmp_path / "sprints")
    monkeypatch.setattr(pm_dispatch, "HARNESS_DIR", tmp_path / "harness")

    router = types.SimpleNamespace(
        build_pm_intake=lambda *args, **kwargs: {"compiled_artifacts": {"product_brief": {"title": "bad", "problem": "bad"}}},
        validate_compiled_package=lambda payload: {"ok": False, "errors": ["raw_metadata_pollution_detected"]},
        emit_requirement_package=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("emit should not run")),
    )

    class _Loader:
        def exec_module(self, module):
            return None

    fake_spec = types.SimpleNamespace(loader=_Loader())
    monkeypatch.setattr(pm_dispatch.importlib.util, "spec_from_file_location", lambda *args, **kwargs: fake_spec)
    monkeypatch.setattr(pm_dispatch.importlib.util, "module_from_spec", lambda spec: router)

    touched: dict[str, object] = {"status": False}

    def _unexpected_status(*args, **kwargs):
        touched["status"] = True
        raise AssertionError("status should not be created when validation fails")

    monkeypatch.setattr(pm_dispatch, "ensure_compiled_sprint_status", _unexpected_status)

    args = argparse.Namespace(
        text="坏包不能继续落 status",
        input_file="",
        sprint="sprint-test",
        workspace_root=str(tmp_path / "workspace"),
        paper=[],
        log=[],
        repo_context=[],
        target_system="solar-harness",
        dispatch_planner=False,
        dry_run=False,
    )
    rc = pm_dispatch.cmd_compile_request(args)
    assert rc == 2
    assert touched["status"] is False


def test_cmd_submit_persists_failed_record_when_no_operator_available(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    monkeypatch.setenv("SOLAR_PM_DISPATCH_ALLOW_DIRECT", "1")
    monkeypatch.setattr(pm_dispatch, "HARNESS_DIR", tmp_path)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", tmp_path / "sprints")
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", tmp_path / "run" / "pm-inbox")
    monkeypatch.setattr(pm_dispatch, "OPERATOR_INBOX_DIR", tmp_path / "run" / "operator-inbox")
    monkeypatch.setattr(pm_dispatch, "OPERATOR_STATUS_DIR", tmp_path / "run" / "operator-status")
    monkeypatch.setattr(
        pm_dispatch,
        "select_operator_by_role",
        lambda **kwargs: ("", {}, "no_dispatchable_operator_for_role: planner"),
    )

    args = argparse.Namespace(
        role="planner",
        objective="Need planner handoff",
        operator="",
        sprint="sprint-no-operator",
        node="N0",
        task_type="planning",
        context="",
        dry_run=False,
    )
    rc = pm_dispatch.cmd_submit(args)
    assert rc == 1
    records = list((tmp_path / "run" / "pm-inbox").glob("pm-*.json"))
    assert len(records) == 1
    payload = json.loads(records[0].read_text(encoding="utf-8"))
    assert payload["status"] == "failed_no_dispatchable_operator"
    assert payload["failure_reason"] == "no_dispatchable_operator_for_role: planner"


def test_pending_pm_backlog_count_ignores_failed_variants(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    inbox = tmp_path / "run" / "pm-inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)
    samples = {
        "pm-a.json": {"status": "submitted"},
        "pm-b.json": {"status": "failed_contract_closeout"},
        "pm-c.json": {"status": "failed_missing_pm_result"},
        "pm-d.json": {"status": "completed"},
    }
    for name, payload in samples.items():
        (inbox / name).write_text(json.dumps(payload), encoding="utf-8")
    assert pm_dispatch._pending_pm_backlog_count() == 1


def _write_builder_ready_graph(sprints: Path, sprint_id: str) -> None:
    (sprints / f"{sprint_id}.status.json").write_text(
        json.dumps({"status": "active", "phase": "planning_complete"}),
        encoding="utf-8",
    )
    (sprints / f"{sprint_id}.task_graph.json").write_text(
        json.dumps(
            {
                "sprint_id": sprint_id,
                "nodes": [
                    {
                        "id": "B1",
                        "goal": "Implement approved change.",
                        "logical_operator": "ImplementationWorker",
                        "dispatch_task_type": "implementation",
                        "acceptance": ["handoff exists"],
                        "requirement_ids": ["REQ-1"],
                        "status": "pending",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_eval_ready_graph(sprints: Path, sprint_id: str, node_id: str = "E1") -> None:
    (sprints / f"{sprint_id}.status.json").write_text(
        json.dumps({"sprint_id": sprint_id, "status": "reviewing", "phase": "handoff_ready", "handoff_to": "evaluator"}),
        encoding="utf-8",
    )
    (sprints / f"{sprint_id}.task_graph.json").write_text(
        json.dumps(
            {
                "sprint_id": sprint_id,
                "nodes": [
                    {
                        "id": node_id,
                        "goal": "Review builder handoff.",
                        "logical_operator": "Verifier",
                        "acceptance": ["eval exists"],
                        "requirement_ids": ["REQ-1"],
                        "status": "reviewing",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (sprints / f"{sprint_id}.{node_id}-handoff.md").write_text("handoff\n", encoding="utf-8")


def test_builder_pool_backlog_includes_latent_planning_complete(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    inbox = tmp_path / "run" / "pm-inbox"
    sprints.mkdir(parents=True)
    inbox.mkdir(parents=True)
    _write_builder_ready_graph(sprints, "sprint-latent")
    (sprints / "sprint-planner.status.json").write_text(
        json.dumps({"status": "drafting", "phase": "prd_ready", "handoff_to": "planner"}),
        encoding="utf-8",
    )
    (sprints / "sprint-builder.status.json").write_text(
        json.dumps({"status": "active", "phase": "planning_complete", "handoff_to": "builder_main"}),
        encoding="utf-8",
    )
    _write_eval_ready_graph(sprints, "sprint-eval")
    (sprints / "stale-node-sidecar.status.json").write_text(
        json.dumps({"status": "reviewing", "phase": "handoff_ready", "handoff_to": "evaluator"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)

    assert pm_dispatch._builder_pool_backlog_breakdown() == {
        "pending_pm": 0,
        "latent_builder_ready": 1,
        "planner_prd_ready": 1,
        "builder_planning_complete": 1,
        "evaluator_handoff_ready": 1,
        "total": 4,
    }

    (inbox / "pm-existing.json").write_text(
        json.dumps({"status": "submitted", "sprint_id": "sprint-latent", "node_id": "B1"}),
        encoding="utf-8",
    )
    assert pm_dispatch._builder_pool_backlog_breakdown() == {
        "pending_pm": 1,
        "latent_builder_ready": 0,
        "planner_prd_ready": 1,
        "builder_planning_complete": 1,
        "evaluator_handoff_ready": 1,
        "total": 4,
    }

    (inbox / "pm-planner.json").write_text(
        json.dumps({"status": "submitted", "sprint_id": "sprint-planner", "node_id": "PLAN"}),
        encoding="utf-8",
    )
    assert pm_dispatch._builder_pool_backlog_breakdown() == {
        "pending_pm": 2,
        "latent_builder_ready": 0,
        "planner_prd_ready": 0,
        "builder_planning_complete": 1,
        "evaluator_handoff_ready": 1,
        "total": 4,
    }

    eval_graph = sprints / "sprint-eval.task_graph.json"
    eval_payload = json.loads(eval_graph.read_text(encoding="utf-8"))
    eval_payload["nodes"][0]["eval_dispatched_at"] = "2026-06-04T00:00:00Z"
    eval_payload["nodes"][0]["eval_assignments"] = [{"pane": "solar-harness-lab:0.3", "dispatch_id": "graph-eval-1"}]
    eval_graph.write_text(json.dumps(eval_payload), encoding="utf-8")
    assert pm_dispatch._builder_pool_backlog_breakdown() == {
        "pending_pm": 2,
        "latent_builder_ready": 0,
        "planner_prd_ready": 0,
        "builder_planning_complete": 1,
        "evaluator_handoff_ready": 0,
        "total": 3,
    }

    eval_payload["nodes"][0].pop("eval_dispatched_at")
    eval_payload["nodes"][0].pop("eval_assignments")
    eval_graph.write_text(json.dumps(eval_payload), encoding="utf-8")
    (inbox / "pm-eval.json").write_text(
        json.dumps({"status": "submitted", "sprint_id": "sprint-eval", "node_id": "E1", "requested_role": "evaluator"}),
        encoding="utf-8",
    )
    assert pm_dispatch._builder_pool_backlog_breakdown() == {
        "pending_pm": 3,
        "latent_builder_ready": 0,
        "planner_prd_ready": 0,
        "builder_planning_complete": 1,
        "evaluator_handoff_ready": 0,
        "total": 4,
    }


def test_drain_builder_ready_submits_and_marks_graph(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    inbox = tmp_path / "run" / "pm-inbox"
    sprints.mkdir(parents=True)
    inbox.mkdir(parents=True)
    _write_builder_ready_graph(sprints, "sprint-drain")

    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)
    monkeypatch.setattr(pm_dispatch, "HARNESS_DIR", tmp_path)

    def fake_cmd_submit(args):
        pm_dispatch.write_pm_task_record(
            "pm-sprint-drain-B1-test",
            {
                "task_id": "pm-sprint-drain-B1-test",
                "status": "submitted",
                "sprint_id": args.sprint,
                "node_id": args.node,
                "operator_id": "mini-codex-gpt53-spark-builder-1",
            },
        )
        return 0

    monkeypatch.setattr(pm_dispatch, "cmd_submit", fake_cmd_submit)
    rc = pm_dispatch.cmd_drain_builder_ready(
        argparse.Namespace(sprint="", max_items=0, dry_run=False, json=True)
    )

    assert rc == 0
    graph = json.loads((sprints / "sprint-drain.task_graph.json").read_text(encoding="utf-8"))
    assert graph["nodes"][0]["status"] == "dispatched"
    assert graph["nodes"][0]["dispatched_via"] == "pm_dispatch"
    assert graph["nodes"][0]["pm_task_id"] == "pm-sprint-drain-B1-test"


def test_cmd_fail_requeues_transient_operator_failure_graph_node(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    inbox = tmp_path / "run" / "pm-inbox"
    sprints.mkdir(parents=True)
    inbox.mkdir(parents=True)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)

    task_id = "pm-sprint-requeue-B1-test"
    graph_path = sprints / "sprint-requeue.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-requeue",
                "nodes": [
                    {
                        "id": "B1",
                        "status": "dispatched",
                        "assigned_to": "mini-codex-gpt53-spark-builder-1",
                        "dispatch_id": task_id,
                        "pm_task_id": task_id,
                        "operator_id": "mini-codex-gpt53-spark-builder-1",
                    }
                ],
                "node_results": {
                    "B1": {
                        "status": "dispatched",
                        "dispatch_id": task_id,
                        "pm_task_id": task_id,
                        "operator_id": "mini-codex-gpt53-spark-builder-1",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    pm_dispatch.write_pm_task_record(
        task_id,
        {
            "task_id": task_id,
            "status": "submitted",
            "sprint_id": "sprint-requeue",
            "node_id": "B1",
            "operator_id": "mini-codex-gpt53-spark-builder-1",
        },
    )

    rc = pm_dispatch.cmd_fail(
        argparse.Namespace(
            task_id=task_id,
            status="failed",
            reason="ERROR: You've hit your usage limit. [flow-control] runtime_state=cooldown",
        )
    )

    assert rc == 0
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    node = graph["nodes"][0]
    assert node["status"] == "pending"
    assert node["requeue_reason"] == "transient_operator_failure"
    assert "dispatch_id" not in node
    assert node["dispatch_requeue_history"][0]["previous_dispatch"]["dispatch_id"] == task_id
    record = json.loads((inbox / f"{task_id}.json").read_text(encoding="utf-8"))
    assert record["graph_requeue"]["released"] is True


def test_cmd_complete_marks_builder_graph_node_reviewing(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    inbox = tmp_path / "run" / "pm-inbox"
    sprints.mkdir(parents=True)
    inbox.mkdir(parents=True)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)

    task_id = "pm-sprint-review-B1-test"
    graph_path = sprints / "sprint-review.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-review",
                "nodes": [
                    {
                        "id": "B1",
                        "status": "dispatched",
                        "assigned_to": "mini-glm51-builder-1",
                        "dispatch_id": task_id,
                        "pm_task_id": task_id,
                        "operator_id": "mini-glm51-builder-1",
                    }
                ],
                "node_results": {
                    "B1": {
                        "status": "dispatched",
                        "dispatch_id": task_id,
                        "pm_task_id": task_id,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (sprints / "sprint-review.status.json").write_text(
        json.dumps({"sprint_id": "sprint-review", "status": "active", "phase": "planning_complete"}),
        encoding="utf-8",
    )
    (sprints / "sprint-review.B1-handoff.md").write_text("# Handoff\n", encoding="utf-8")
    pm_dispatch.write_pm_task_record(
        task_id,
        {
            "task_id": task_id,
            "status": "submitted",
            "sprint_id": "sprint-review",
            "node_id": "B1",
            "operator_id": "mini-glm51-builder-1",
            "requested_role": "builder",
        },
    )

    rc = pm_dispatch.cmd_complete(argparse.Namespace(task_id=task_id))

    assert rc == 0
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    node = graph["nodes"][0]
    assert node["status"] == "reviewing"
    assert "dispatch_id" not in node
    assert node["handoff_path"].endswith("sprint-review.B1-handoff.md")
    status = json.loads((sprints / "sprint-review.status.json").read_text(encoding="utf-8"))
    assert status["status"] == "reviewing"
    assert status["phase"] == "handoff_ready"
    assert status["handoff_to"] == "evaluator"
    record = json.loads((inbox / f"{task_id}.json").read_text(encoding="utf-8"))
    assert record["graph_reviewing"]["marked"] is True


def test_evaluator_dispatch_marks_graph_assignment(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    inbox = tmp_path / "run" / "pm-inbox"
    sprints.mkdir(parents=True)
    inbox.mkdir(parents=True)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)

    graph_path = sprints / "sprint-eval.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-eval",
                "nodes": [{"id": "E1", "status": "reviewing"}],
                "node_results": {"E1": {"status": "reviewing"}},
            }
        ),
        encoding="utf-8",
    )

    result = pm_dispatch._mark_graph_node_evaluation_dispatched(
        {
            "task_id": "pm-sprint-eval-E1-test",
            "sprint_id": "sprint-eval",
            "node_id": "E1",
            "operator_id": "mini-claude-opus-evaluator",
            "requested_role": "evaluator",
        }
    )

    assert result["marked"] is True
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    node = graph["nodes"][0]
    assert node["eval_dispatch_id"] == "pm-sprint-eval-E1-test"
    assert node["eval_assignments"][0]["operator_id"] == "mini-claude-opus-evaluator"
    assert graph["node_results"]["E1"]["eval_dispatch_id"] == "pm-sprint-eval-E1-test"


def test_transient_evaluator_failure_releases_graph_assignment(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    inbox = tmp_path / "run" / "pm-inbox"
    sprints.mkdir(parents=True)
    inbox.mkdir(parents=True)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)

    task_id = "pm-sprint-eval-E1-test"
    graph_path = sprints / "sprint-eval.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-eval",
                "nodes": [
                    {
                        "id": "E1",
                        "status": "reviewing",
                        "eval_dispatch_id": task_id,
                        "eval_dispatched_at": "2026-06-05T00:00:00Z",
                        "eval_operator_id": "mini-claude-opus-evaluator",
                        "eval_assignments": [{"task_id": task_id, "operator_id": "mini-claude-opus-evaluator"}],
                    }
                ],
                "node_results": {
                    "E1": {
                        "status": "reviewing",
                        "eval_dispatch_id": task_id,
                        "eval_dispatched_at": "2026-06-05T00:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = pm_dispatch._release_graph_eval_on_transient_operator_failure(
        {
            "task_id": task_id,
            "sprint_id": "sprint-eval",
            "node_id": "E1",
            "operator_id": "mini-claude-opus-evaluator",
            "requested_role": "evaluator",
            "status": "failed",
            "failure_reason": "quota_guard_state=cooldown",
        }
    )

    assert result["released"] is True
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    node = graph["nodes"][0]
    assert "eval_dispatch_id" not in node
    assert "eval_assignments" not in node
    assert node["eval_requeue_history"][0]["task_id"] == task_id
    assert "eval_dispatch_id" not in graph["node_results"]["E1"]
