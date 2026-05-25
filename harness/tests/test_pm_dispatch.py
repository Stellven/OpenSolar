#!/usr/bin/env python3
"""Tests for PM dispatch capability capsule integration."""

from __future__ import annotations

import argparse
import importlib.util
import json
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
