#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "lib" / "operator_health_watchdog_graph_adapters.py"


def _load_adapter(sprints_dir: Path):
    os.environ["SOLAR_HARNESS_SPRINTS_DIR"] = str(sprints_dir)
    if "operator_health_watchdog_graph_adapters" in sys.modules:
        del sys.modules["operator_health_watchdog_graph_adapters"]
    if "pm_dispatch" in sys.modules:
        del sys.modules["pm_dispatch"]

    spec = importlib.util.spec_from_file_location(
        "operator_health_watchdog_graph_adapters",
        ADAPTER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    importlib.invalidate_caches()
    return module


def _load_graph(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_release_builder_assignment_exact_identity_from_node_results(tmp_path):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    graph_path = sprints / "sprint-requeue.task_graph.json"
    task_id = "pm-sprint-requeue-B1-test"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-requeue",
                "nodes": [
                    {
                        "id": "B1",
                        "status": "dispatched",
                        "assigned_to": "mini-claude-gpt55",
                    }
                ],
                "node_results": {
                    "B1": {
                        "status": "dispatched",
                        "pm_task_id": task_id,
                        "operator_id": "mini-claude-gpt55",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    adapter = _load_adapter(sprints)
    result = adapter.release_builder_assignment_on_transient_provider_failure(
        {
            "sprint_id": "sprint-requeue",
            "node_id": "B1",
            "task_id": task_id,
            "status": "failed",
            "failure_reason": "runtime_state=quota_exhausted",
        }
    )

    assert result["released"] is True
    graph = _load_graph(graph_path)
    node = graph["nodes"][0]
    assert node["status"] == "pending"
    assert node["requeue_reason"] == "transient_provider_failure"
    assert "dispatch_id" not in node
    assert graph["node_results"]["B1"]["status"] == "pending"


def test_public_watchdog_helper_aliases_exist(tmp_path):
    adapter = _load_adapter(tmp_path / "sprints")

    assert hasattr(adapter, "release_builder_assignment_on_transient_failure")
    assert hasattr(adapter, "release_evaluator_assignment_on_transient_failure")
    assert adapter.release_builder_assignment_on_transient_failure(
        {
            "sprint_id": "",
            "node_id": "",
            "task_id": "",
            "failure_reason": "runtime_state=cooldown",
        }
    )["reason"] == "missing_graph_identity"
    assert adapter.release_evaluator_assignment_on_transient_failure(
        {
            "requested_role": "builder",
            "sprint_id": "s",
            "node_id": "n",
            "task_id": "t",
            "failure_reason": "runtime_state=cooldown",
        }
    )["reason"] == "not_evaluator_task"


def test_release_builder_assignment_not_released_when_dispatch_mismatch(tmp_path):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    graph_path = sprints / "sprint-mismatch.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-mismatch",
                "nodes": [
                    {
                        "id": "B1",
                        "status": "dispatched",
                        "dispatch_id": "pm-other-task",
                    }
                ],
                "node_results": {
                    "B1": {
                        "status": "dispatched",
                        "dispatch_id": "pm-other-task",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    adapter = _load_adapter(sprints)
    result = adapter.release_builder_assignment_on_transient_provider_failure(
        {
            "sprint_id": "sprint-mismatch",
            "node_id": "B1",
            "task_id": "pm-different-task",
            "status": "failed",
            "failure_reason": "runtime_state=cooldown",
        }
    )

    assert result["released"] is False
    assert result["reason"] == "dispatch_mismatch"
    graph = _load_graph(graph_path)
    assert graph["nodes"][0]["status"] == "dispatched"


def test_release_builder_assignment_blocks_business_failure_signal(tmp_path):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    graph_path = sprints / "sprint-business.task_graph.json"
    task_id = "pm-task-business"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-business",
                "nodes": [
                    {
                        "id": "B1",
                        "status": "dispatched",
                        "dispatch_id": task_id,
                    }
                ],
                "node_results": {
                    "B1": {
                        "status": "dispatched",
                        "dispatch_id": task_id,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    adapter = _load_adapter(sprints)
    result = adapter.release_builder_assignment_on_transient_provider_failure(
        {
            "sprint_id": "sprint-business",
            "node_id": "B1",
            "task_id": task_id,
            "status": "failed",
            "failure_reason": "business validation failed: schema mismatch",
        }
    )

    assert result["released"] is False
    assert result["reason"] == "not_transient_provider_failure"
    graph = _load_graph(graph_path)
    assert graph["nodes"][0]["status"] == "dispatched"


def test_release_evaluator_assignment_exact_task_and_cleanup(tmp_path):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    graph_path = sprints / "sprint-eval.task_graph.json"
    task_id = "pm-sprint-eval-E1-test"
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
                        "eval_assignments": [
                            {"task_id": task_id, "operator_id": "mini-claude-opus-evaluator"},
                            {"task_id": "other-task", "operator_id": "mini-other"},
                        ],
                    }
                ],
                "node_results": {
                    "E1": {
                        "status": "reviewing",
                        "eval_dispatch_id": task_id,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    adapter = _load_adapter(sprints)
    result = adapter.release_evaluator_assignment_on_transient_provider_failure(
        {
            "requested_role": "evaluator",
            "sprint_id": "sprint-eval",
            "node_id": "E1",
            "task_id": task_id,
            "status": "failed",
            "failure_reason": "You’ve hit your quota limit",
        }
    )

    assert result["released"] is True
    graph = _load_graph(graph_path)
    node = graph["nodes"][0]
    assert node["status"] == "reviewing"
    assert "eval_dispatch_id" not in node
    assert len(node.get("eval_assignments", [])) == 1
    assert node["eval_assignments"][0]["task_id"] == "other-task"


def test_release_evaluator_assignment_ignores_non_evaluator_role(tmp_path):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    graph_path = sprints / "sprint-eval-role.task_graph.json"
    graph_path.write_text(
        json.dumps({"sprint_id": "sprint-eval-role", "nodes": [{"id": "E1", "status": "reviewing"}]}),
        encoding="utf-8",
    )

    adapter = _load_adapter(sprints)
    result = adapter.release_evaluator_assignment_on_transient_provider_failure(
        {
            "requested_role": "builder",
            "sprint_id": "sprint-eval-role",
            "node_id": "E1",
            "task_id": "pm-not-used",
            "status": "failed",
            "failure_reason": "runtime_state=cooldown",
        }
    )

    assert result["released"] is False
    assert result["reason"] == "not_evaluator_task"
    graph = _load_graph(graph_path)
    assert graph["nodes"][0]["status"] == "reviewing"
