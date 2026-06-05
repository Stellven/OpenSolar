from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
TOOLS = ROOT / "tools"
sys.path.insert(0, str(LIB))

import graph_scheduler  # noqa: E402


def _load_autopilot():
    spec = importlib.util.spec_from_file_location("autopilot_s04_test", TOOLS / "autopilot.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _child_graph(status: str = "pending") -> dict:
    return {
        "sprint_id": "sprint-s04",
        "nodes": [
            {
                "id": "N1_activation_graph_route",
                "goal": "Wire graph activation",
                "depends_on": [],
                "write_scope": ["tools/autopilot.py"],
                "acceptance": ["ready nodes route to builder"],
                "status": status,
            }
        ],
    }


def _epic_graph(upstream_status: str = "passed") -> dict:
    return {
        "schema_version": "solar.epic.task_graph.v1",
        "epic_id": "epic-s04",
        "nodes": [
            {"id": "S03", "child_sprint_id": "sprint-s03", "depends_on": [], "status": upstream_status},
            {
                "id": "S04",
                "child_sprint_id": "sprint-s04",
                "depends_on": ["S03"],
                "status": "active",
            },
        ],
    }


def test_activation_decision_routes_ready_child_graph_to_builder():
    decision = graph_scheduler.activation_route_decision(
        _child_graph(),
        graph_path="/tmp/sprint-s04.task_graph.json",
        child_status={"phase": "planning_complete", "target_role": "builder_main"},
        epic_graph=_epic_graph("passed"),
    )

    assert decision["can_dispatch"] is True
    assert decision["route_role"] == "builder_main"
    assert decision["target_role"] == "builder_main"
    assert decision["ready_nodes"] == ["N1_activation_graph_route"]
    assert decision["blocked_reason"] == ""


def test_activation_decision_blocks_when_parent_dependency_is_not_passed():
    decision = graph_scheduler.activation_route_decision(
        _child_graph(),
        child_status={"phase": "planning_complete", "target_role": "builder_main"},
        epic_graph=_epic_graph("active"),
    )

    assert decision["can_dispatch"] is False
    assert decision["ready_nodes"] == []
    assert decision["blocked_reason"] == "parent_dependency_blocked"
    assert decision["parent_blockers"][0]["node"] == "S03"


def test_activation_decision_blocks_invalid_task_graph():
    graph = _child_graph()
    graph["nodes"].append(dict(graph["nodes"][0]))

    decision = graph_scheduler.activation_route_decision(
        graph,
        child_status={"phase": "planning_complete", "target_role": "builder_main"},
        epic_graph=_epic_graph("passed"),
    )

    assert decision["can_dispatch"] is False
    assert decision["ready_nodes"] == []
    assert decision["blocked_reason"] == "task_graph_validation_failed"
    assert decision["validation"]["errors"]


def test_autopilot_records_activation_history_without_workers(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    sprints = harness / "sprints"
    sprints.mkdir(parents=True)
    sprint_id = "sprint-s04"
    (sprints / f"{sprint_id}.task_graph.json").write_text(json.dumps(_child_graph()) + "\n", encoding="utf-8")
    (sprints / "epic-s04.task_graph.json").write_text(json.dumps(_epic_graph("passed")) + "\n", encoding="utf-8")
    status_path = sprints / f"{sprint_id}.status.json"
    status_path.write_text(
        json.dumps(
            {
                "sprint_id": sprint_id,
                "epic_id": "epic-s04",
                "phase": "planning_complete",
                "target_role": "builder_main",
                "history": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(graph_scheduler, "HARNESS_DIR", harness)
    monkeypatch.setattr(graph_scheduler, "SPRINTS_DIR", sprints)
    autopilot = _load_autopilot()
    monkeypatch.setattr(autopilot, "HARNESS_DIR", harness)

    result = autopilot.activate_graph(sprint_id)

    assert result["decision"]["can_dispatch"] is True
    assert result["enqueue"]["skipped"] is True
    status = json.loads(status_path.read_text(encoding="utf-8"))
    event = status["history"][-1]
    assert event["event"] == "autopilot_graph_activation_decision"
    assert event["route_role"] == "builder_main"
    assert event["target_role"] == "builder_main"
    assert event["phase"] == "planning_complete"
    assert event["blocked_reason"] == ""
    assert event["ready_nodes"] == ["N1_activation_graph_route"]


def test_autopilot_does_not_dispatch_when_dependency_blocked(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    sprints = harness / "sprints"
    sprints.mkdir(parents=True)
    sprint_id = "sprint-s04"
    (sprints / f"{sprint_id}.task_graph.json").write_text(json.dumps(_child_graph()) + "\n", encoding="utf-8")
    (sprints / "epic-s04.task_graph.json").write_text(json.dumps(_epic_graph("active")) + "\n", encoding="utf-8")
    (sprints / f"{sprint_id}.status.json").write_text(
        json.dumps(
            {
                "sprint_id": sprint_id,
                "epic_id": "epic-s04",
                "phase": "planning_complete",
                "target_role": "builder_main",
                "history": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(graph_scheduler, "HARNESS_DIR", harness)
    monkeypatch.setattr(graph_scheduler, "SPRINTS_DIR", sprints)
    autopilot = _load_autopilot()
    monkeypatch.setattr(autopilot, "HARNESS_DIR", harness)

    result = autopilot.activate_graph(sprint_id, workers_path=tmp_path / "workers.json")

    assert result["decision"]["can_dispatch"] is False
    assert result["decision"]["blocked_reason"] == "parent_dependency_blocked"
    assert result["enqueue"]["skipped"] is True


def test_assign_ready_uses_state_plane_when_inline_status_is_stale(tmp_path, monkeypatch):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sprint_id = "sprint-s04-state"
    graph_path = sprints / f"{sprint_id}.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": sprint_id,
                "nodes": [
                    {"id": "N1", "goal": "done", "status": "passed", "depends_on": [], "write_scope": ["a"]},
                    {"id": "N2", "goal": "dispatch", "status": "in_progress", "depends_on": ["N1"], "write_scope": ["b"]},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (sprints / f"{sprint_id}.task_dag.state.json").write_text(
        json.dumps(
            {
                "sprint_id": sprint_id,
                "node_results": {"N1": {"status": "passed"}, "N2": {"status": "pending"}},
                "gate_results": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SOLAR_AUTOPILOT_DECISION", "state")
    monkeypatch.setattr(graph_scheduler, "SPRINTS_DIR", sprints)

    graph = graph_scheduler.load_graph(graph_path)
    result = graph_scheduler.assign_ready(
        graph,
        [{
            "pane": "pane-a",
            "models": ["sonnet"],
            "skills": ["python", "workflow.planning", "technical-writing", "algorithm"],
            "capabilities": ["harness.context_preflight", "harness.contracts", "harness.dag", "harness.status"],
        }],
        graph_path=graph_path,
    )

    assert result["queued"] == []
    assert [item["node"] for item in result["assigned"]] == ["N2"]


def test_autopilot_shadow_writes_per_sprint_event_with_state_decision(tmp_path, monkeypatch):
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sprint_id = "sprint-s04-shadow"
    graph_path = sprints / f"{sprint_id}.task_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": sprint_id,
                "nodes": [
                    {"id": "N1", "goal": "done", "status": "passed", "depends_on": [], "write_scope": ["a"]},
                    {"id": "N2", "goal": "dispatch", "status": "in_progress", "depends_on": ["N1"], "write_scope": ["b"]},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (sprints / f"{sprint_id}.task_dag.state.json").write_text(
        json.dumps(
            {
                "sprint_id": sprint_id,
                "node_results": {"N1": {"status": "passed"}, "N2": {"status": "pending"}},
                "gate_results": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SOLAR_AUTOPILOT_DECISION", "inline")
    monkeypatch.setenv("SOLAR_AUTOPILOT_SHADOW", "1")
    monkeypatch.setattr(graph_scheduler, "SPRINTS_DIR", sprints)

    graph = graph_scheduler.load_graph(graph_path)
    decision = graph_scheduler.autopilot_ready_decision(graph, graph_path=graph_path, emit_shadow=True)

    assert decision["source"] == "inline"
    assert decision["ready_node_ids"] == []
    assert decision["state_ready"] == ["N2"]
    assert decision["decision_taken"] == "state"
    event = json.loads((sprints / f"{sprint_id}.events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert event["event"] == "autopilot_cutover_diff"
    assert event["decision_taken"] == "state"
    trace = json.loads((sprints / f"{sprint_id}.traceability.json").read_text(encoding="utf-8"))
    assert trace["s04_orchestration_ui:autopilot_drift"][-1]["diff_added"] == ["N2"]
