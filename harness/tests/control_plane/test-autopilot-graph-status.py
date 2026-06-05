#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "solar-autopilot-monitor.py"
spec = importlib.util.spec_from_file_location("solar_autopilot_monitor", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["solar_autopilot_monitor"] = mod
spec.loader.exec_module(mod)


def _write_graph(path: Path, sid: str) -> None:
    path.write_text(
        json.dumps(
            {
                "sprint_id": sid,
                "nodes": [
                    {
                        "id": "S1",
                        "depends_on": ["external:sprint-parent"],
                        "status": "pending",
                        "write_scope": ["/tmp/s1"],
                        "required_capabilities": ["planning"],
                    },
                ],
                "node_results": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_graph_status_includes_blocked_prerequisites(tmp_path: Path, monkeypatch: Any) -> None:
    sid = "sprint-autopilot-graph-status-blocked"
    graph_path = tmp_path / "sprints" / f"{sid}.task_graph.json"
    graph_path.parent.mkdir(parents=True)
    _write_graph(graph_path, sid)

    def fake_summarize(blocked: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "sprint_id": item.get("sprint_id") or item.get("dependency_sprint"),
                "reason": item.get("reason", "external_dependency_blocked"),
                "guidance": item.get("guidance", "wait for dependency to pass"),
                "blocked_by": ["sprint:" + str(item.get("sprint_id") or item.get("dependency_sprint") or "")],
                "blocked_prerequisites": [item],
            }
            for item in blocked
        ]

    monkeypatch.setattr(
        mod,
        "blocked_external_prerequisites",
        lambda graph: [
            {
                "sprint_id": "sprint-parent",
                "required_status": "passed",
                "reason": "external_dependency_blocked",
                "guidance": "wait for dependency sprint to pass",
            }
        ],
    )
    monkeypatch.setattr(mod, "summarize_blocked_prerequisites", fake_summarize)
    monkeypatch.setattr(mod, "SPRINTS", graph_path.parent)
    monkeypatch.setattr(
        mod,
        "graph_dispatch_ready",
        lambda *a, **kw: {
            "enqueue": {
                "assigned": [],
                "enqueued": [],
                "blocked_prerequisites": [
                    {
                        "sprint_id": "sprint-parent",
                        "reason": "external_dependency_blocked",
                    }
                ],
            },
            "drain": {"ok": True, "processed": 0, "results": []},
        },
    )

    status = mod.graph_status(sid)

    assert status["scheduler_state"] == "blocked"
    assert isinstance(status["blocked"], list) and status["blocked"]
    assert status["blocked"][0]["blocked_by"] == ["sprint:sprint-parent"]
    assert status["blocked"][0]["reason"] == "external_dependency_blocked"
    assert status["blocked"][0]["guidance"] == "wait for dependency sprint to pass"
    assert status["graph_dispatch_ready"] == {}


def test_graph_status_returns_ready_nodes_when_dispatchable(tmp_path: Path, monkeypatch: Any) -> None:
    sid = "sprint-autopilot-graph-status-ready"
    graph_path = tmp_path / "sprints" / f"{sid}.task_graph.json"
    graph_path.parent.mkdir(parents=True)
    _write_graph(graph_path, sid)

    monkeypatch.setattr(mod, "blocked_external_prerequisites", lambda graph: [])
    monkeypatch.setattr(mod, "summarize_blocked_prerequisites", lambda blocked: blocked)
    monkeypatch.setattr(mod, "SPRINTS", graph_path.parent)
    monkeypatch.setattr(
        mod,
        "graph_dispatch_ready",
        lambda *a, **kw: {
            "enqueue": {
                "assigned": [{"node": "S1"}],
                "enqueued": [{"node": "S1"}],
            },
            "drain": {"ok": True, "processed": 1, "results": []},
        },
    )

    status = mod.graph_status(sid)

    assert status["scheduler_state"] == "ready"
    assert status["ready_nodes"] == ["S1"]
    assert status["dispatchable_nodes"] == ["S1"]
    assert status["blocked"] == []
