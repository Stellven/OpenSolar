#!/usr/bin/env python3
"""test_parent_ready_closeout.py — N3 tests: parent_ready_check closeout.

Tests verify:
  - parent sprint status is passed ONLY when parent_ready_check returns ready
  - _mark_parent_sprint_passed_if_ready is the single closeout path
  - node_verdict correctly delegates to parent_ready_check
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add harness lib to path
HARNESS_LIB = Path(__file__).resolve().parent.parent.parent / "lib"
sys.path.insert(0, str(HARNESS_LIB))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_harness(tmp_path, monkeypatch):
    """Create a minimal harness directory structure."""
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    run_dir = tmp_path / "run" / "queue"
    run_dir.mkdir(parents=True)

    sid = "test-parent-ready"
    graph = {
        "sprint_id": sid,
        "required_gates": ["gate-1"],
        "nodes": [
            {
                "id": "N1",
                "goal": "Test",
                "depends_on": [],
                "write_scope": ["/tmp/test"],
                "acceptance": ["test"],
                "status": "reviewing",
                "gate": "gate-1",
            },
        ],
        "node_results": {},
        "gate_results": {},
    }
    graph_path = sprints / f"{sid}.task_graph.json"
    graph_path.write_text(json.dumps(graph) + "\n")

    # Create status file
    status = {
        "id": sid,
        "status": "active",
        "phase": "graph_dispatch_active",
    }
    (sprints / f"{sid}.status.json").write_text(json.dumps(status) + "\n")

    monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
    import graph_node_dispatcher as gnd
    monkeypatch.setattr(gnd, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(gnd, "HARNESS_DIR", tmp_path)

    return tmp_path, sprints, sid, graph


# ---------------------------------------------------------------------------
# Test: parent sprint passed only when parent_ready_check is ready
# ---------------------------------------------------------------------------

class TestParentReadyCloseout:
    """D7: parent sprint is passed only via parent_ready_check."""

    def test_parent_not_passed_when_nodes_still_open(self, tmp_harness):
        """_mark_parent_sprint_passed_if_ready does NOT pass when nodes are open."""
        import graph_node_dispatcher as gnd

        tmp_path, sprints, sid, graph = tmp_harness

        # N1 is still reviewing (open), so parent_ready_check returns ready=False
        parent = {"ready": False, "node_count": 1, "open_nodes": ["N1"]}
        result = gnd._mark_parent_sprint_passed_if_ready(sid, parent, dry_run=False)
        assert result is False

        # Verify status was NOT changed to passed
        status = json.loads((sprints / f"{sid}.status.json").read_text())
        assert status["status"] != "passed"

    def test_parent_passed_when_all_nodes_done(self, tmp_harness):
        """_mark_parent_sprint_passed_if_ready DOES pass when ready=True."""
        import graph_node_dispatcher as gnd

        tmp_path, sprints, sid, graph = tmp_harness

        # All nodes passed
        parent = {
            "ready": True,
            "node_count": 1,
            "open_nodes": [],
            "required_gates": ["gate-1"],
            "missing_gates": [],
        }
        result = gnd._mark_parent_sprint_passed_if_ready(sid, parent, dry_run=False)
        assert result is True

        # Verify status was changed to passed
        status = json.loads((sprints / f"{sid}.status.json").read_text())
        assert status["status"] == "passed"
        assert status["phase"] == "completed"
        assert "graph_parent_ready_passed" in str(status.get("history", []))

    def test_parent_not_passed_in_dry_run(self, tmp_harness):
        """Dry run never marks parent as passed."""
        import graph_node_dispatcher as gnd

        tmp_path, sprints, sid, graph = tmp_harness

        parent = {"ready": True, "node_count": 1, "open_nodes": []}
        result = gnd._mark_parent_sprint_passed_if_ready(sid, parent, dry_run=True)
        assert result is False

    def test_parent_not_passed_when_gates_missing(self, tmp_harness):
        """Parent not passed when required gates haven't all passed."""
        import graph_node_dispatcher as gnd

        tmp_path, sprints, sid, graph = tmp_harness

        parent = {
            "ready": False,
            "node_count": 1,
            "open_nodes": [],
            "required_gates": ["gate-1"],
            "missing_gates": ["gate-1"],
        }
        result = gnd._mark_parent_sprint_passed_if_ready(sid, parent, dry_run=False)
        assert result is False

    def test_node_verdict_delegates_to_parent_ready_check(self, tmp_harness, monkeypatch):
        """node_verdict calls _mark_parent_sprint_passed_if_ready."""
        import graph_node_dispatcher as gnd

        tmp_path, sprints, sid, graph = tmp_harness

        # Set N1 as passed in node_results
        graph["node_results"]["N1"] = {"status": "passed"}
        graph["gate_results"]["gate-1"] = {"status": "passed", "node": "N1"}
        graph["nodes"][0]["status"] = "reviewing"
        graph["nodes"][0]["eval_assigned_to"] = "eval:0.3"
        graph["nodes"][0]["eval_dispatch_id"] = "eval-dispatch-123"

        # Mock all the things
        monkeypatch.setattr(gnd, "load_graph", lambda p: graph)
        monkeypatch.setattr(gnd, "save_graph", lambda p, g: None)

        from graph_scheduler import mark_node_result
        monkeypatch.setattr(gnd, "mark_node_result", mark_node_result)

        monkeypatch.setattr(gnd, "release_lease", lambda *a, **kw: {"released": True})
        monkeypatch.setattr(gnd, "dispatch_ready", lambda *a, **kw: {"ok": True})

        parent_passed_calls = []
        def mock_mark_parent(sid, parent, dry_run):
            parent_passed_calls.append({"sid": sid, "parent": parent, "dry_run": dry_run})
            return False
        monkeypatch.setattr(gnd, "_mark_parent_sprint_passed_if_ready", mock_mark_parent)

        eval_json_path = str(sprints / f"{sid}.N1-eval.json")
        result = gnd.node_verdict(
            str(sprints / f"{sid}.task_graph.json"),
            "N1",
            "pass",
            eval_json=eval_json_path,
            dry_run=False,
            dispatch_downstream=False,
        )

        assert result["ok"] is True
        assert result["status"] == "passed"
        # Verify _mark_parent_sprint_passed_if_ready was called
        assert len(parent_passed_calls) == 1
        assert parent_passed_calls[0]["dry_run"] is False

    def test_events_appended_on_parent_pass(self, tmp_harness):
        """Events file records graph_parent_ready_passed event."""
        import graph_node_dispatcher as gnd

        tmp_path, sprints, sid, graph = tmp_harness

        parent = {
            "ready": True,
            "node_count": 1,
            "open_nodes": [],
            "required_gates": ["gate-1"],
        }
        result = gnd._mark_parent_sprint_passed_if_ready(sid, parent, dry_run=False)
        assert result is True

        events_file = sprints / f"{sid}.events.jsonl"
        if events_file.exists():
            lines = events_file.read_text().strip().splitlines()
            assert any("graph_parent_ready_passed" in line for line in lines)


class TestParentReadyCheckIntegration:
    """Integration test: graph_scheduler.parent_ready_check is the source of truth."""

    def test_all_passed_means_ready(self, tmp_harness):
        """When all nodes and gates pass, parent_ready_check returns ready."""
        from graph_scheduler import parent_ready_check

        _, sprints, sid, graph = tmp_harness

        # Mark all nodes as passed
        graph["nodes"][0]["status"] = "passed"
        graph["node_results"] = {"N1": {"status": "passed"}}
        graph["gate_results"] = {"gate-1": {"status": "passed", "node": "N1"}}

        result = parent_ready_check(graph)
        assert result["ready"] is True
        assert result["open_nodes"] == []

    def test_open_nodes_means_not_ready(self, tmp_harness):
        """When nodes are still open, parent_ready_check returns not ready."""
        from graph_scheduler import parent_ready_check

        _, sprints, sid, graph = tmp_harness

        result = parent_ready_check(graph)
        assert result["ready"] is False
        assert "N1" in result["open_nodes"]

    def test_failed_node_means_not_ready(self, tmp_harness):
        """When a node is failed, parent_ready_check returns not ready."""
        from graph_scheduler import parent_ready_check

        _, sprints, sid, graph = tmp_harness

        graph["nodes"][0]["status"] = "failed"
        graph["node_results"] = {"N1": {"status": "failed"}}

        result = parent_ready_check(graph)
        assert result["ready"] is False
        assert "N1" in result["failed_nodes"]

    def test_newer_inline_passed_overrides_stale_node_result_reviewing(self, tmp_harness):
        """A stale node_results row must not keep a passed node open forever."""
        from graph_scheduler import node_status, parent_ready_check

        _, sprints, sid, graph = tmp_harness

        graph["nodes"][0]["status"] = "passed"
        graph["nodes"][0]["updated_at"] = "2026-05-14T07:24:00Z"
        graph["node_results"] = {
            "N1": {"status": "reviewing", "updated_at": "2026-05-14T07:23:00Z"}
        }
        graph["gate_results"] = {"gate-1": {"status": "passed", "node": "N1"}}

        assert node_status(graph, "N1") == "passed"
        result = parent_ready_check(graph)
        assert result["ready"] is True
        assert result["open_nodes"] == []

    def test_doctor_repairs_stale_node_result_reviewing(self, tmp_harness):
        """graph doctor repairs the exact stale-reviewing dead-end."""
        from graph_scheduler import doctor_graph, node_status, parent_ready_check

        _, sprints, sid, graph = tmp_harness

        graph["nodes"][0]["status"] = "passed"
        graph["nodes"][0]["updated_at"] = "2026-05-14T07:24:00Z"
        graph["node_results"] = {
            "N1": {"status": "reviewing", "updated_at": "2026-05-14T07:23:00Z"}
        }
        graph["gate_results"] = {"gate-1": {"status": "passed", "node": "N1"}}

        result = doctor_graph(graph, repair=True)
        assert result["repaired"] is True
        assert graph["node_results"]["N1"]["status"] == "passed"
        assert node_status(graph, "N1") == "passed"
        assert parent_ready_check(graph)["ready"] is True


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
