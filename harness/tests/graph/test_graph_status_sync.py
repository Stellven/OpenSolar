#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

HARNESS_LIB = Path(__file__).resolve().parent.parent.parent / "lib"
sys.path.insert(0, str(HARNESS_LIB))


def test_sync_status_cache_creates_missing_inflight_status(tmp_path, monkeypatch):
    import graph_scheduler as gs

    sprints = tmp_path / "sprints"
    sprints.mkdir()
    monkeypatch.setattr(gs, "SPRINTS_DIR", sprints)

    sid = "sprint-test-orphan-graph"
    graph_path = sprints / f"{sid}.task_graph.json"
    graph = {
        "sprint_id": sid,
        "title": "Orphan graph",
        "created_at": "2026-05-25T21:16:39Z",
        "required_gates": ["G1"],
        "nodes": [
            {"id": "N1", "status": "passed", "depends_on": [], "gate": "G1"},
            {"id": "N2", "status": "pending", "depends_on": ["N1"], "gate": "G1"},
        ],
        "node_results": {"N1": {"status": "passed"}},
        "gate_results": {},
    }
    graph_path.write_text(json.dumps(graph), encoding="utf-8")

    result = gs.sync_status_cache_from_graph(graph, graph_path, actor="test", event="graph_mark_N1_passed")

    status_path = sprints / f"{sid}.status.json"
    assert result["ok"] is True
    assert result["created"] is True
    assert result["updated"] is False
    assert result["reason"] == "parent_not_ready"
    assert status_path.exists()

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["status"] == "active"
    assert status["phase"] == "graph_in_progress"
    assert status["task_graph"] == str(graph_path)
    assert status["active_node"] == "N2"
    assert status["open_nodes"] == ["N2"]

