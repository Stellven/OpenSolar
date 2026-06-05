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


def test_select_operator_by_role_rejects_write_denied_planner(monkeypatch):
    pm_dispatch = _load_pm_dispatch()
    monkeypatch.setattr(
        pm_dispatch,
        "load_registry",
        lambda: {
            "version": 1,
            "operators": {
                "deepseek-advisory": {
                    "enabled": True,
                    "available": True,
                    "role": "evaluator",
                    "roles": ["planner", "evaluator"],
                    "launch_cmd_kind": "print_once",
                    "task_classes": ["analysis", "review", "advisory"],
                    "profile": "deepseek-advisory",
                    "preferred_for": ["architecture-review"],
                    "policy": {"write_files": "denied"},
                },
                "gpt-planner": {
                    "enabled": True,
                    "available": True,
                    "role": "planner",
                    "roles": ["planner"],
                    "launch_cmd_kind": "command",
                    "task_classes": ["planning"],
                    "profile": "gpt-planner",
                    "preferred_for": [],
                    "policy": {"write_files": "allowed"},
                },
            },
        },
    )
    monkeypatch.setattr(pm_dispatch, "is_dispatchable", lambda op: (True, ""))

    operator_id, _, reason = pm_dispatch.select_operator_by_role(role="planner", task_type="planning")

    assert reason == ""
    assert operator_id == "gpt-planner"


def test_multi_role_operator_uses_requested_role_persona(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    monkeypatch.setattr(pm_dispatch, "PERSONAS_DIR", tmp_path)
    (tmp_path / "builder.md").write_text("# Builder\n", encoding="utf-8")
    (tmp_path / "evaluator.md").write_text("# Evaluator\n", encoding="utf-8")
    monkeypatch.setattr(
        pm_dispatch,
        "load_registry",
        lambda: {
            "version": 1,
            "operators": {
                "gpt55-multi": {
                    "enabled": True,
                    "available": True,
                    "role": "builder",
                    "roles": ["builder", "evaluator"],
                    "persona": "builder",
                    "launch_cmd_kind": "command",
                    "task_classes": ["implementation", "review", "verification"],
                    "profile": "codex-builder",
                    "preferred_for": ["evaluator"],
                    "model": "gpt-5.5",
                }
            },
        },
    )
    monkeypatch.setattr(pm_dispatch, "is_dispatchable", lambda op: (True, ""))

    operator_id, operator, reason = pm_dispatch.select_operator_by_role(role="evaluator", task_type="review")

    assert reason == ""
    assert operator_id == "gpt55-multi"
    assert operator["selected_for_role"] == "evaluator"
    dispatch_text = pm_dispatch.build_pm_dispatch_text(
        "task-1",
        operator_id,
        operator,
        "review the handoff",
        "sprint-1",
        "N1",
        "/tmp/result.md",
    )
    assert "Persona file: `" + str(tmp_path / "evaluator.md") + "`" in dispatch_text
    assert "# Evaluator" in dispatch_text
    assert "# Builder" not in dispatch_text


def test_is_dispatchable_inherits_shared_billing_pool_cooldown(monkeypatch):
    pm_dispatch = _load_pm_dispatch()
    monkeypatch.setattr(
        pm_dispatch,
        "load_registry",
        lambda: {
            "version": 1,
            "operators": {
                "primary-opus-evaluator": {
                    "enabled": True,
                    "available": True,
                    "operator_id": "primary-opus-evaluator",
                    "billing_pool": "anthropic_subscription_interactive",
                    "key_ref": "claude_subscription",
                },
                "reserve-opus-print": {
                    "enabled": True,
                    "available": True,
                    "operator_id": "reserve-opus-print",
                    "billing_pool": "anthropic_subscription_interactive",
                    "key_ref": "claude_subscription",
                },
            },
        },
    )
    monkeypatch.setattr(
        pm_dispatch,
        "get_operator_status_data",
        lambda operator_id: {
            "runtime_state": "cooldown",
            "expires_at": "2099-01-01T00:00:00Z",
        }
        if operator_id == "primary-opus-evaluator"
        else {},
    )

    ok, reason = pm_dispatch.is_dispatchable(
        {
            "enabled": True,
            "available": True,
            "operator_id": "reserve-opus-print",
            "billing_pool": "anthropic_subscription_interactive",
            "key_ref": "claude_subscription",
        }
    )

    assert ok is False
    assert "shared_quota_guard_state=cooldown" in reason
    assert "primary-opus-evaluator" in reason


def test_is_dispatchable_does_not_share_key_ref_across_distinct_models(monkeypatch):
    pm_dispatch = _load_pm_dispatch()
    monkeypatch.setattr(
        pm_dispatch,
        "load_registry",
        lambda: {
            "version": 1,
            "operators": {
                "spark-builder": {
                    "enabled": True,
                    "available": True,
                    "operator_id": "spark-builder",
                    "provider": "openai",
                    "model": "gpt-5.3-codex-spark",
                    "key_ref": "codex_auth",
                },
                "gpt55-builder": {
                    "enabled": True,
                    "available": True,
                    "operator_id": "gpt55-builder",
                    "provider": "openai",
                    "model": "gpt-5.5",
                    "key_ref": "codex_auth",
                },
            },
        },
    )
    monkeypatch.setattr(
        pm_dispatch,
        "get_operator_status_data",
        lambda operator_id: {
            "runtime_state": "cooldown",
            "expires_at": "2099-01-01T00:00:00Z",
        }
        if operator_id == "spark-builder"
        else {},
    )
    monkeypatch.setattr(pm_dispatch, "get_operator_runtime_state", lambda operator_id: "idle")
    monkeypatch.setattr(pm_dispatch, "_operator_external_health", lambda op: (True, ""))

    ok, reason = pm_dispatch.is_dispatchable(
        {
            "enabled": True,
            "available": True,
            "operator_id": "gpt55-builder",
            "provider": "openai",
            "model": "gpt-5.5",
            "key_ref": "codex_auth",
        }
    )

    assert ok is True
    assert reason == ""


def test_transient_operator_failure_text_reads_operator_result_logs(tmp_path):
    pm_dispatch = _load_pm_dispatch()
    pm_dispatch.HARNESS_DIR = tmp_path
    result_dir = tmp_path / "operator-result"
    result_dir.mkdir()
    (result_dir / "codex-cli-output.log").write_text(
        "ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark. "
        "Switch to another model now, or try again at Jun 10th, 2026 10:25 PM.",
        encoding="utf-8",
    )

    text = pm_dispatch._transient_operator_failure_text(
        {
            "failure_reason": "failed",
            "artifact_paths": {"operator_result_dir": str(result_dir)},
        }
    )

    assert "usage limit" in text
    assert pm_dispatch.TRANSIENT_OPERATOR_FAILURE_RE.search(text)


def test_transient_operator_failure_text_infers_operator_result_dir(tmp_path):
    pm_dispatch = _load_pm_dispatch()
    pm_dispatch.HARNESS_DIR = tmp_path
    result_dir = tmp_path / "run" / "operator-results" / "spark-builder" / "task-1"
    result_dir.mkdir(parents=True)
    (result_dir / "output.log").write_text("ERROR: rate limit reached", encoding="utf-8")

    text = pm_dispatch._transient_operator_failure_text(
        {
            "task_id": "task-1",
            "operator_id": "spark-builder",
            "failure_reason": "failed",
        }
    )

    assert "rate limit reached" in text
    assert pm_dispatch.TRANSIENT_OPERATOR_FAILURE_RE.search(text)


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


def test_cmd_submit_graph_eval_uses_verification_capsule(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    monkeypatch.setenv("SOLAR_PM_DISPATCH_ALLOW_DIRECT", "1")
    monkeypatch.setattr(pm_dispatch, "HARNESS_DIR", tmp_path)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", tmp_path / "sprints")
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", tmp_path / "run" / "pm-inbox")
    monkeypatch.setattr(pm_dispatch, "OPERATOR_INBOX_DIR", tmp_path / "run" / "operator-inbox")
    monkeypatch.setattr(pm_dispatch, "OPERATOR_STATUS_DIR", tmp_path / "run" / "operator-status")
    monkeypatch.setattr(pm_dispatch, "PERSONAS_DIR", tmp_path / "personas")
    (tmp_path / "personas").mkdir(parents=True, exist_ok=True)
    (tmp_path / "personas" / "evaluator.md").write_text("# Evaluator\n", encoding="utf-8")
    (tmp_path / "sprints").mkdir(parents=True, exist_ok=True)
    (tmp_path / "sprints" / "sprint-graph-eval.task_graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "S1",
                        "goal": "Implementation node now needs graph eval.",
                        "logical_operator": "ImplementationWorker",
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
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        pm_dispatch,
        "load_registry",
        lambda: {
            "version": 1,
            "operators": {
                "gpt55-evaluator": {
                    "enabled": True,
                    "available": True,
                    "roles": ["evaluator"],
                    "launch_cmd_kind": "command",
                    "task_classes": ["review", "verification", "graph_eval"],
                    "profile": "evaluator",
                    "preferred_for": ["evaluator"],
                    "model": "gpt-5.5",
                    "persona": "evaluator",
                }
            },
        },
    )
    monkeypatch.setattr(pm_dispatch, "is_dispatchable", lambda op: (True, ""))

    sys.path.insert(0, str(ROOT / "lib"))
    import capability_capsules as caps

    resolved_requests: list[dict[str, object]] = []

    def _resolve(task, operator_id=None, registry_path=None):
        resolved_requests.append(dict(task))
        return {
            "capability_capsule_id": task["capability_capsule_id"],
            "operator_constraints": {
                "preferred": ["gpt55-evaluator"],
                "forbidden": [],
                "default_operator_profile": "gpt55-evaluator",
            },
        }

    monkeypatch.setattr(caps, "resolve_capability_capsule_for_task", _resolve)
    captured: dict[str, object] = {}
    fake_operator_runtime = types.ModuleType("operator_runtime")

    def _submit(envelope):
        captured["envelope"] = dict(envelope)
        return {
            "lease_id": "lease-graph-eval",
            "inbox_path": str(tmp_path / "run" / "operator-inbox" / "gpt55-evaluator" / "pm.json"),
        }

    fake_operator_runtime.submit = _submit  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "operator_runtime", fake_operator_runtime)

    args = argparse.Namespace(
        role="evaluator",
        objective="Evaluate S1 handoff.",
        operator="",
        sprint="sprint-graph-eval",
        node="S1",
        task_type="graph_eval",
        context="",
        dry_run=False,
    )
    rc = pm_dispatch.cmd_submit(args)

    assert rc == 0
    assert resolved_requests[0]["capability_capsule_id"] == "cap.requirement-compiler-verification"
    assert resolved_requests[0]["task_type"] == "graph_eval"
    envelope = captured["envelope"]
    assert envelope["capability_capsule_id"] == "cap.requirement-compiler-verification"
    assert envelope["capsule_plan"]["capability_capsule_id"] == "cap.requirement-compiler-verification"
    assert envelope["capsule_plan"]["dispatch_task_type"] == "graph_eval"
    assert envelope["logical_operator"] == "Verifier"
    assert envelope["task_type"] == "graph_eval"


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


def test_eval_backlog_ignores_failed_graphs_and_failed_sprint_eval(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    inbox = tmp_path / "run" / "pm-inbox"
    sprints.mkdir(parents=True)
    inbox.mkdir(parents=True)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)

    _write_eval_ready_graph(sprints, "sprint-failed-node")
    (sprints / "sprint-failed-node.status.json").write_text(
        json.dumps({"status": "reviewing", "phase": "handoff_ready", "handoff_to": "evaluator"}),
        encoding="utf-8",
    )
    failed_node_graph = json.loads((sprints / "sprint-failed-node.task_graph.json").read_text(encoding="utf-8"))
    failed_node_graph["nodes"].append({"id": "E2", "status": "failed"})
    (sprints / "sprint-failed-node.task_graph.json").write_text(json.dumps(failed_node_graph), encoding="utf-8")

    _write_eval_ready_graph(sprints, "sprint-failed-eval")
    (sprints / "sprint-failed-eval.status.json").write_text(
        json.dumps({"status": "reviewing", "phase": "handoff_ready", "handoff_to": "evaluator"}),
        encoding="utf-8",
    )
    (sprints / "sprint-failed-eval.eval.json").write_text(json.dumps({"verdict": "FAIL"}), encoding="utf-8")

    assert pm_dispatch._builder_pool_backlog_breakdown() == {
        "pending_pm": 0,
        "latent_builder_ready": 0,
        "planner_prd_ready": 0,
        "builder_planning_complete": 0,
        "evaluator_handoff_ready": 0,
        "total": 0,
    }


def test_operator_health_watchdog_status_projects_latest_and_legacy_pruner(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    root = tmp_path / "harness"
    latest = root / "run" / "operator-health-watchdog" / "latest.json"
    latest.parent.mkdir(parents=True)
    (latest.parent / "com.solar.harness.operator-health-watchdog.plist").write_text("<plist/>", encoding="utf-8")
    latest.write_text(
        json.dumps(
            {
                "ok": True,
                "finished_at": "2026-06-05T02:00:00Z",
                "last_exit_code": 0,
                "counters": {
                    "expired_blocks_pruned": 1,
                    "pm_failures_reconciled": 2,
                    "graph_nodes_released": 3,
                    "stale_leases_released": 4,
                    "drain_submitted": 5,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pm_dispatch, "HARNESS_DIR", root)
    monkeypatch.setattr(pm_dispatch, "HOME", tmp_path)
    monkeypatch.setattr(pm_dispatch.shutil, "which", lambda name: None)

    status = pm_dispatch._operator_health_watchdog_status()

    assert status["last_run_at"] == "2026-06-05T02:00:00Z"
    assert status["last_exit_code"] == 0
    assert status["installed"] is True
    assert status["plist_path"].endswith("/run/operator-health-watchdog/com.solar.harness.operator-health-watchdog.plist")
    assert status["last_actions"]["graph_nodes_released"] == 3
    assert status["legacy_pruner"]["label"] == "com.solar.harness-rate-limit-pruner"
    assert status["legacy_pruner"]["launchd_loaded"] is False


def test_pm_reconcile_excludes_capacity_probe_records(monkeypatch, tmp_path, capsys):
    pm_dispatch = _load_pm_dispatch()
    inbox = tmp_path / "pm-inbox"
    inbox.mkdir()
    stale_ts = "2026-01-01T00:00:00Z"
    probe_id = "pm-graph-dispatch-capacity-probe-CAPACITY-deadbeef"
    normal_id = "pm-real-task-N1-deadbeef"
    (inbox / f"{probe_id}.json").write_text(
        json.dumps(
            {
                "task_id": probe_id,
                "sprint_id": "graph-dispatch-capacity-probe",
                "node_id": "CAPACITY",
                "result_path": str(tmp_path / "missing-probe-result.md"),
                "status": "submitted",
                "submitted_at": stale_ts,
            }
        ),
        encoding="utf-8",
    )
    (inbox / f"{normal_id}.json").write_text(
        json.dumps(
            {
                "task_id": normal_id,
                "sprint_id": "sprint-real",
                "node_id": "N1",
                "result_path": str(tmp_path / "missing-real-result.md"),
                "status": "submitted",
                "submitted_at": stale_ts,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)
    monkeypatch.setattr(pm_dispatch, "_active_pm_task_ids", lambda: set())

    files = [path.name for path in pm_dispatch._pm_record_files(include_probe_records=False)]
    assert f"{probe_id}.json" not in files
    assert f"{normal_id}.json" in files

    rc = pm_dispatch.cmd_reconcile(argparse.Namespace(apply=True, max_age_minutes=1, json=True, limit=40))
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["summary"] == {"fail_missing_pm_result": 1}
    assert json.loads((inbox / f"{probe_id}.json").read_text(encoding="utf-8"))["status"] == "submitted"
    assert json.loads((inbox / f"{normal_id}.json").read_text(encoding="utf-8"))["status"] == "failed_missing_pm_result"


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
    (sprints / "sprint-requeue.task_dag.state.json").write_text(
        json.dumps(
            {
                "schema_version": "solar.task_graph_state.v1",
                "sprint_id": "sprint-requeue",
                "node_results": {"B1": {"status": "dispatched", "dispatch_id": task_id}},
                "gate_results": {},
                "dispatch_ids": {"B1": task_id},
                "events": [],
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
    state = json.loads((sprints / "sprint-requeue.task_dag.state.json").read_text(encoding="utf-8"))
    assert state["node_results"]["B1"]["status"] == "pending"
    assert "B1" not in state["dispatch_ids"]
    record = json.loads((inbox / f"{task_id}.json").read_text(encoding="utf-8"))
    assert record["graph_requeue"]["released"] is True


def test_transient_builder_release_reads_operator_log_tail(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    sprints.mkdir(parents=True)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)

    task_id = "pm-sprint-logtail-B1-test"
    graph_path = sprints / "sprint-logtail.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-logtail",
                "nodes": [
                    {
                        "id": "B1",
                        "status": "dispatched",
                        "dispatch_id": task_id,
                        "pm_task_id": task_id,
                        "operator_id": "mini-codex-gpt53-spark-builder-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = pm_dispatch.release_builder_assignment_on_transient_failure(
        {
            "task_id": task_id,
            "sprint_id": "sprint-logtail",
            "node_id": "B1",
            "operator_id": "mini-codex-gpt53-spark-builder-1",
            "status": "failed",
            "log_tail": "[flow-control] runtime_state=cooldown",
        }
    )

    assert result["released"] is True
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    node = graph["nodes"][0]
    assert node["status"] == "pending"
    assert node["requeue_reason"] == "transient_operator_failure"


def test_transient_builder_release_allows_pm_graph_dispatch_id_skew(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    sprints.mkdir(parents=True)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)

    pm_task_id = "pm-sprint-skew-B1-test"
    graph_dispatch_id = "graph-sprint-skew-B1-20260605T081430Z"
    graph_path = sprints / "sprint-skew.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-skew",
                "nodes": [
                    {
                        "id": "B1",
                        "status": "dispatched",
                        "assigned_to": "operator:mini-codex-gpt53-spark-builder-4",
                        "dispatch_id": graph_dispatch_id,
                    }
                ],
                "node_results": {
                    "B1": {
                        "status": "dispatched",
                        "dispatch_id": graph_dispatch_id,
                        "operator_id": "mini-codex-gpt53-spark-builder-4",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = pm_dispatch.release_builder_assignment_on_transient_failure(
        {
            "task_id": pm_task_id,
            "sprint_id": "sprint-skew",
            "node_id": "B1",
            "operator_id": "mini-codex-gpt53-spark-builder-4",
            "status": "failed_quota_cooldown",
            "failure_reason": "GPT-5.3-Codex-Spark usage limit; runtime_state=cooldown",
        }
    )

    assert result["released"] is True
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    node = graph["nodes"][0]
    assert node["status"] == "pending"
    assert node["requeue_reason"] == "transient_operator_failure"
    assert node["dispatch_requeue_history"][0]["previous_dispatch"]["dispatch_id"] == graph_dispatch_id
    assert "dispatch_id" not in node


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


def test_cmd_complete_reopens_failed_node_for_fresh_repair_handoff(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    inbox = tmp_path / "run" / "pm-inbox"
    sprints.mkdir(parents=True)
    inbox.mkdir(parents=True)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(pm_dispatch, "PM_INBOX_DIR", inbox)

    task_id = "pm-sprint-repair-B1-test"
    graph_path = sprints / "sprint-repair.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-repair",
                "nodes": [{"id": "B1", "status": "failed", "updated_at": "2026-06-05T01:00:00Z"}],
                "node_results": {"B1": {"status": "failed", "pm_task_id": "old-task"}},
            }
        ),
        encoding="utf-8",
    )
    (sprints / "sprint-repair.status.json").write_text(
        json.dumps({"sprint_id": "sprint-repair", "status": "active", "phase": "planning_complete"}),
        encoding="utf-8",
    )
    (sprints / "sprint-repair.B1-eval.md").write_text("old fail", encoding="utf-8")
    (sprints / "sprint-repair.B1-eval.json").write_text('{"verdict":"FAIL"}', encoding="utf-8")
    (sprints / "sprint-repair.B1-eval-dispatch-q1.md").write_text("old dispatch", encoding="utf-8")
    ack_dir = sprints / "graph-acks"
    ack_dir.mkdir()
    (ack_dir / "sprint-repair.B1-submit-ack.json").write_text('{"submitted_at":"2026-06-05T00:59:00Z"}', encoding="utf-8")
    (sprints / "sprint-repair.B1-handoff.md").write_text("# Repaired handoff\n", encoding="utf-8")
    pm_dispatch.write_pm_task_record(
        task_id,
        {
            "task_id": task_id,
            "status": "submitted",
            "sprint_id": "sprint-repair",
            "node_id": "B1",
            "operator_id": "mini-glm51-builder-1",
            "requested_role": "builder",
            "objective": "Repair failed DAG node B1 and produce a fresh handoff.",
            "submitted_at": "2026-06-05T01:00:00Z",
        },
    )

    rc = pm_dispatch.cmd_complete(argparse.Namespace(task_id=task_id))

    assert rc == 0
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    node = graph["nodes"][0]
    assert node["status"] == "reviewing"
    assert node["completion_history"][0]["reason"] == "pm_builder_repair_complete"
    assert node["eval_retry_reason"] == "pm_repair_archived_stale_eval_sidecars"
    assert not (sprints / "sprint-repair.B1-eval.md").exists()
    assert not (sprints / "sprint-repair.B1-eval.json").exists()
    assert not (sprints / "sprint-repair.B1-eval-dispatch-q1.md").exists()
    assert not (ack_dir / "sprint-repair.B1-submit-ack.json").exists()
    assert len(node["last_eval_sidecar_archive"]) == 4
    result_entry = graph["node_results"]["B1"]
    assert result_entry["status"] == "reviewing"
    assert result_entry["eval_retry_reason"] == "pm_repair_archived_stale_eval_sidecars"
    state = json.loads((sprints / "sprint-repair.task_dag.state.json").read_text(encoding="utf-8"))
    state_result = state["node_results"]["B1"]
    assert state_result["status"] == "reviewing"
    assert state_result["completion_history"][0]["reason"] == "pm_builder_repair_complete"
    assert state_result["eval_retry_reason"] == "pm_repair_archived_stale_eval_sidecars"
    record = json.loads((inbox / f"{task_id}.json").read_text(encoding="utf-8"))
    assert record["graph_reviewing"]["repair_completion"] is True
    assert record["graph_reviewing"]["state_sync"]["ok"] is True
    assert len(record["graph_reviewing"]["archived_eval_sidecars"]) == 4


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
    (sprints / "sprint-eval.task_dag.state.json").write_text(
        json.dumps(
            {
                "schema_version": "solar.task_graph_state.v1",
                "sprint_id": "sprint-eval",
                "node_results": {"E1": {"status": "failed"}},
                "gate_results": {},
                "dispatch_ids": {},
                "events": [],
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
    state = json.loads((sprints / "sprint-eval.task_dag.state.json").read_text(encoding="utf-8"))
    assert state["node_results"]["E1"]["status"] == "reviewing"
    assert state["node_results"]["E1"]["dispatch_id"] == "pm-sprint-eval-E1-test"


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


def test_transient_evaluator_release_reads_operator_stderr(monkeypatch, tmp_path):
    pm_dispatch = _load_pm_dispatch()
    sprints = tmp_path / "sprints"
    sprints.mkdir(parents=True)
    monkeypatch.setattr(pm_dispatch, "SPRINTS_DIR", sprints)

    task_id = "pm-sprint-eval-stderr-E1-test"
    graph_path = sprints / "sprint-eval-stderr.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-eval-stderr",
                "nodes": [
                    {
                        "id": "E1",
                        "status": "reviewing",
                        "eval_dispatch_id": task_id,
                        "eval_assignments": [{"task_id": task_id, "operator_id": "mini-claude-opus-evaluator"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = pm_dispatch.release_evaluator_assignment_on_transient_failure(
        {
            "task_id": task_id,
            "sprint_id": "sprint-eval-stderr",
            "node_id": "E1",
            "operator_id": "mini-claude-opus-evaluator",
            "requested_role": "evaluator",
            "status": "failed",
            "stderr": "quota exhausted by provider",
        }
    )

    assert result["released"] is True
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    node = graph["nodes"][0]
    assert "eval_dispatch_id" not in node
    assert "eval_assignments" not in node
