"""Regression tests for graph worker assignment queue reasons."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from graph_scheduler import assign_workers  # noqa: E402


def _worker(pane: str, *, busy: bool = False) -> dict:
    return {
        "pane": pane,
        "models": ["glm"],
        "skills": ["python", "pytest", "stub-llm"],
        "capabilities": ["harness.context_preflight", "harness.dag"],
        "busy": busy,
    }


def _node(node_id: str) -> dict:
    return {
        "id": node_id,
        "preferred_model": "sonnet",
        "required_skills": ["python", "pytest", "stub-llm"],
        "required_capabilities": ["harness.context_preflight", "harness.dag"],
    }


def test_queue_reason_distinguishes_capacity_from_no_matching_worker() -> None:
    result = assign_workers([_node("N1"), _node("N2")], [_worker("pane-a")])
    assert [item["node"] for item in result["assigned"]] == ["N1"]
    assert result["queued"] == [{"node": "N2", "reason": "worker_capacity_exhausted"}]


def test_queue_reason_remains_no_matching_worker_when_skills_are_missing() -> None:
    worker = _worker("pane-a")
    worker["skills"] = ["python"]
    result = assign_workers([_node("N1")], [worker])
    assert result["assigned"] == []
    assert result["queued"] == [{"node": "N1", "reason": "no_matching_worker"}]


def test_queue_reason_capacity_when_matching_worker_is_busy() -> None:
    result = assign_workers([_node("N1")], [_worker("pane-a", busy=True)])
    assert result["assigned"] == []
    assert result["queued"] == [{"node": "N1", "reason": "worker_capacity_exhausted"}]


def test_queue_reason_runtime_not_running_when_matching_worker_is_shell_residue() -> None:
    worker = _worker("pane-a")
    worker["busy"] = True
    worker["unavailable_reason"] = "worker_runtime_not_running"
    result = assign_workers([_node("N1")], [worker])
    assert result["assigned"] == []
    assert result["queued"] == [{"node": "N1", "reason": "worker_runtime_not_running"}]


def test_enriched_dag_capabilities_are_assignable() -> None:
    worker = _worker("pane-a")
    worker["capabilities"] = [
        "harness.context_preflight",
        "harness.dag",
        "dag.validate",
        "dag.ready_nodes",
        "dag.join_gate",
    ]
    node = _node("N1")
    node["required_capabilities"] = [
        "harness.context_preflight",
        "harness.dag",
        "dag.validate",
        "dag.ready_nodes",
        "dag.join_gate",
    ]
    result = assign_workers([node], [worker])
    assert result["queued"] == []
    assert result["assigned"][0]["node"] == "N1"


def test_skill_labels_can_satisfy_required_capabilities() -> None:
    worker = _worker("pane-a")
    worker["skills"] = ["python", "pytest", "stub-llm", "cli"]
    worker["capabilities"] = ["harness.context_preflight", "harness.dag"]
    node = _node("N1")
    node["required_capabilities"] = ["harness.context_preflight", "cli"]
    result = assign_workers([node], [worker])
    assert result["queued"] == []
    assert result["assigned"][0]["node"] == "N1"
