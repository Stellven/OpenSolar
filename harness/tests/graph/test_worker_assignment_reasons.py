"""Regression tests for graph worker assignment queue reasons."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from graph_scheduler import assign_workers, enqueue_ready  # noqa: E402


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
    assert result["queued"][0]["node"] == "N2"
    assert result["queued"][0]["reason"] == "worker_capacity_exhausted"
    assert "details" in result["queued"][0]


def test_queue_reason_remains_no_matching_worker_when_skills_are_missing() -> None:
    worker = _worker("pane-a")
    worker["skills"] = ["python"]
    result = assign_workers([_node("N1")], [worker])
    assert result["assigned"] == []
    assert result["queued"][0]["node"] == "N1"
    assert result["queued"][0]["reason"] == "no_matching_worker"
    assert "pytest" in result["queued"][0]["details"]["missing_skills"]


def test_busy_matching_worker_is_assigned_instead_of_queued() -> None:
    result = assign_workers([_node("N1")], [_worker("pane-a", busy=True)])
    assert result["assigned"][0]["node"] == "N1"
    assert result["assigned"][0]["pane"] == "pane-a"
    assert result["queued"] == []


def test_queue_reason_runtime_not_running_when_matching_worker_is_shell_residue() -> None:
    worker = _worker("pane-a")
    worker["busy"] = True
    worker["unavailable_reason"] = "worker_runtime_not_running"
    result = assign_workers([_node("N1")], [worker])
    assert result["assigned"] == []
    assert result["queued"][0]["node"] == "N1"
    assert result["queued"][0]["reason"] == "worker_runtime_not_running"


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


def test_control_plane_aliases_can_bind_specialized_builder_nodes() -> None:
    worker = _worker("pane-a")
    worker["skills"] = ["python", "workflow.planning", "technical-writing", "algorithm"]
    worker["capabilities"] = ["documentation", "governance"]
    node = {
        "id": "N1",
        "preferred_model": "sonnet",
        "required_skills": ["python", "solar-harness-control-plane", "architecture-writing"],
        "required_capabilities": ["algorithm_design", "documentation"],
    }
    result = assign_workers([node], [worker])
    assert result["queued"] == []
    assert result["assigned"][0]["node"] == "N1"


def test_product_analytics_nodes_bind_general_builder_workers() -> None:
    worker = _worker("pane-a")
    worker["skills"] = ["python", "product.requirements", "planning", "analytics"]
    worker["capabilities"] = ["product.requirements", "analytics"]
    node = {
        "id": "N1",
        "preferred_model": "glm-5.1",
        "required_skills": ["analytics", "product.requirements"],
        "required_capabilities": ["analytics", "product.requirements"],
    }
    result = assign_workers([node], [worker])
    assert result["queued"] == []
    assert result["assigned"][0]["node"] == "N1"


def test_code_impl_and_test_generation_aliases_bind_general_builder_workers() -> None:
    worker = _worker("pane-a")
    worker["skills"] = ["python", "pytest", "refactor", "ImplementationWorker"]
    worker["capabilities"] = ["testing"]
    node = {
        "id": "N1",
        "preferred_model": "glm-5.1",
        "required_skills": [],
        "required_capabilities": ["code_impl", "test_generation"],
    }
    result = assign_workers([node], [worker])
    assert result["queued"] == []
    assert result["assigned"][0]["node"] == "N1"


def test_enqueue_ready_marks_no_matching_worker_nodes_as_worker_blocked(tmp_path: Path, monkeypatch) -> None:
    graph = {
        "sprint_id": "sid",
        "nodes": [
            {
                "id": "N1",
                "depends_on": [],
                "required_skills": ["python", "solar-harness-control-plane"],
                "required_capabilities": ["algorithm_design"],
            }
        ],
    }
    graph_path = tmp_path / "sid.task_graph.json"
    graph_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("task_queue.enqueue", lambda *a, **kw: {"ok": True, "id": "q-1"})
    result = enqueue_ready(
        graph,
        str(graph_path),
        [{"pane": "pane-a", "models": ["sonnet"], "skills": ["python"], "capabilities": ["python"]}],
        lease=False,
        dry_run=False,
    )
    assert result["queued"][0]["reason"] == "no_matching_worker"
    assert result["worker_blocked"][0]["node"] == "N1"
    assert graph["nodes"][0]["status"] == "worker_blocked"
    assert graph["node_results"]["N1"]["blocking_reason"] == "no_matching_worker"


def test_worker_blocked_nodes_are_retryable_after_capability_fix(tmp_path: Path, monkeypatch) -> None:
    graph = {
        "sprint_id": "sid",
        "nodes": [
            {
                "id": "N1",
                "depends_on": [],
                "status": "worker_blocked",
                "required_skills": [],
                "required_capabilities": ["code_impl", "test_generation"],
                "preferred_model": "glm-5.1",
            }
        ],
    }
    graph_path = tmp_path / "sid.task_graph.json"
    graph_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("task_queue.enqueue", lambda *a, **kw: {"ok": True, "id": "q-2"})
    result = enqueue_ready(
        graph,
        str(graph_path),
        [{
            "pane": "pane-a",
            "models": ["glm-5.1"],
            "skills": ["python", "pytest", "ImplementationWorker"],
            "capabilities": ["testing"],
            "busy": False,
        }],
        lease=False,
        dry_run=False,
    )
    assert result["enqueued"][0]["node"] == "N1"
    assert result["queued"] == []
    assert graph["nodes"][0]["status"] == "assigned"
