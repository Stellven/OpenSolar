from __future__ import annotations

import json
import sys
from pathlib import Path

HARNESS_LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(HARNESS_LIB))

import graph_scheduler  # noqa: E402


def test_external_depends_on_blocks_ready_nodes(monkeypatch, tmp_path):
    graph = {
        "sprint_id": "epic-external",
        "nodes": [
            {
                "id": "S01_requirements",
                "status": "blocked",
                "depends_on": ["external:sprint-browser-agent-cutover"],
                "write_scope": ["sprints/*prd.md"],
                "acceptance": ["requirements ready"],
                "required_capabilities": ["planning"],
            }
        ],
    }
    monkeypatch.setattr(graph_scheduler, "SPRINTS_DIR", tmp_path)

    validation = graph_scheduler.validate_graph(graph)
    blocked = graph_scheduler.blocked_external_prerequisites(graph)

    assert validation["ok"] is True
    assert blocked
    assert blocked[0]["sprint_id"] == "sprint-browser-agent-cutover"
    assert graph_scheduler.ready_nodes(graph) == []


def test_external_depends_on_allows_ready_after_upstream_passed(monkeypatch, tmp_path):
    graph = {
        "sprint_id": "epic-external",
        "nodes": [
            {
                "id": "S01_requirements",
                "status": "pending",
                "depends_on": ["external:sprint-browser-agent-cutover"],
                "write_scope": ["sprints/*prd.md"],
                "acceptance": ["requirements ready"],
                "required_capabilities": ["planning"],
            }
        ],
    }
    (tmp_path / "sprint-browser-agent-cutover.status.json").write_text(
        json.dumps({"status": "passed", "phase": "completed"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(graph_scheduler, "SPRINTS_DIR", tmp_path)

    assert graph_scheduler.blocked_external_prerequisites(graph) == []
    assert [node["id"] for node in graph_scheduler.ready_nodes(graph)] == ["S01_requirements"]
