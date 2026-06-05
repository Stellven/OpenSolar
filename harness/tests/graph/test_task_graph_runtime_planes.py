#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HARNESS_LIB = Path(__file__).resolve().parent.parent.parent / "lib"
sys.path.insert(0, str(HARNESS_LIB))
GRAPH_SCHEDULER_PATH = HARNESS_LIB / "graph_scheduler.py"


def _load_local_graph_scheduler():
    spec = importlib.util.spec_from_file_location("test_graph_scheduler_local", GRAPH_SCHEDULER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_load_graph_prefers_state_plane_and_save_graph_projects_closure(tmp_path, monkeypatch):
    gs = _load_local_graph_scheduler()

    sprints = tmp_path / "sprints"
    sprints.mkdir()
    monkeypatch.setattr(gs, "SPRINTS_DIR", sprints)

    sid = "sprint-runtime-planes"
    graph_path = sprints / f"{sid}.task_graph.json"
    state_path = sprints / f"{sid}.task_dag.state.json"
    closure_path = sprints / f"{sid}.closure.json"

    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": sid,
                "required_gates": ["G1"],
                "nodes": [
                    {"id": "N1", "goal": "Implement", "depends_on": [], "gate": "G1", "status": "pending"},
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "solar.task_graph_state.v1",
                "sprint_id": sid,
                "graph_ref": f"{sid}.task_graph.json",
                "node_results": {"N1": {"status": "passed", "updated_at": "2026-05-31T12:00:00Z"}},
                "gate_results": {"G1": {"status": "passed", "node": "N1"}},
                "leases": {},
                "dispatch_ids": {},
                "events": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    graph = gs.load_graph(graph_path)
    assert gs.node_status(graph, "N1") == "passed"
    assert graph["nodes"][0]["status"] == "passed"

    gs.set_node_status(graph, "N1", "reviewing")
    gs.save_graph(graph_path, graph)

    saved_graph = json.loads(graph_path.read_text(encoding="utf-8"))
    saved_state = json.loads(state_path.read_text(encoding="utf-8"))
    saved_closure = json.loads(closure_path.read_text(encoding="utf-8"))

    assert "node_results" not in saved_graph
    assert "gate_results" not in saved_graph
    assert saved_state["node_results"]["N1"]["status"] == "reviewing"
    assert saved_closure["status"] == "pending"


def test_save_graph_marks_closure_closed_when_parent_ready(tmp_path, monkeypatch):
    gs = _load_local_graph_scheduler()

    sprints = tmp_path / "sprints"
    sprints.mkdir()
    monkeypatch.setattr(gs, "SPRINTS_DIR", sprints)

    sid = "sprint-runtime-closure"
    graph_path = sprints / f"{sid}.task_graph.json"
    graph = {
        "sprint_id": sid,
        "required_gates": ["G1"],
        "nodes": [
            {"id": "N1", "goal": "Implement", "depends_on": [], "gate": "G1", "status": "passed"},
        ],
        "node_results": {"N1": {"status": "passed", "updated_at": "2026-05-31T12:00:00Z"}},
        "gate_results": {"G1": {"status": "passed", "node": "N1"}},
    }

    gs.save_graph(graph_path, graph)

    closure = json.loads((sprints / f"{sid}.closure.json").read_text(encoding="utf-8"))
    assert closure["status"] == "closed"
    assert closure["all_nodes_passed"] is True
    assert closure["all_required_gates_passed"] is True


def test_save_graph_rebuilds_state_projection_and_clears_terminal_leases(tmp_path, monkeypatch):
    gs = _load_local_graph_scheduler()

    sprints = tmp_path / "sprints"
    sprints.mkdir()
    monkeypatch.setattr(gs, "SPRINTS_DIR", sprints)

    sid = "sprint-runtime-state-projection"
    graph_path = sprints / f"{sid}.task_graph.json"
    state_path = sprints / f"{sid}.task_dag.state.json"
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": sid,
                "required_gates": ["G1"],
                "nodes": [
                    {
                        "id": "N1",
                        "goal": "Release",
                        "depends_on": [],
                        "gate": "G1",
                        "status": "dispatched",
                        "assigned_to": "operator:builder-1",
                        "dispatch_id": "d-001",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "solar.task_graph_state.v1",
                "sprint_id": sid,
                "graph_ref": f"{sid}.task_graph.json",
                "node_status": {"N1": {"status": "dispatched", "updated_at": "2026-05-31T12:00:00Z"}},
                "node_results": {
                    "N1": {
                        "status": "passed",
                        "updated_at": "2026-05-31T12:05:00Z",
                        "eval_json": "N1-eval.json",
                    },
                },
                "gate_results": {"G1": {"status": "passed", "node": "N1"}},
                "leases": {"N1": {"pane": "operator:builder-1", "dispatch_id": "d-001"}},
                "dispatch_ids": {"N1": "d-001"},
                "events": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    graph = gs.load_graph(graph_path)
    assert gs.node_status(graph, "N1") == "passed"

    gs.save_graph(graph_path, graph)
    saved_state = json.loads(state_path.read_text(encoding="utf-8"))

    assert saved_state["node_status"]["N1"]["status"] == "passed"
    assert saved_state["node_results"]["N1"]["status"] == "passed"
    assert saved_state["gate_results"]["G1"]["status"] == "passed"
    assert saved_state["leases"] == {}
    assert saved_state["dispatch_ids"] == {}
