#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


LIB_DIR = Path(__file__).resolve().parents[1] / "lib"


def _load_controller():
    spec = importlib.util.spec_from_file_location("graph_drain_controller_test", LIB_DIR / "graph_drain_controller.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_graph(sprints: Path, sid: str) -> Path:
    graph = {
        "schema_version": "solar.task_graph.v1",
        "sprint_id": sid,
        "nodes": [
            {"id": "B1", "status": "reviewing"},
            {"id": "B2", "status": "pending"},
        ],
        "node_results": {},
    }
    path = sprints / f"{sid}.task_graph.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    (sprints / f"{sid}.B1-handoff.md").write_text("# handoff\n", encoding="utf-8")
    return path


def _write_graph_with_nodes(sprints: Path, sid: str, nodes: list[dict]) -> Path:
    graph = {
        "schema_version": "solar.task_graph.v1",
        "sprint_id": sid,
        "nodes": nodes,
        "node_results": {},
    }
    path = sprints / f"{sid}.task_graph.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    return path


def test_graph_drain_dry_run_discovers_without_counting_submitted(monkeypatch, tmp_path):
    controller = _load_controller()
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sid = "sprint-test"
    _write_graph(sprints, sid)
    calls: list[tuple[str, bool, int | None]] = []

    class FakeDispatcher:
        @staticmethod
        def load_graph(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))

        @staticmethod
        def _existing_node_handoff(sprint_id, node, graph):
            path = sprints / f"{sprint_id}.{node['id']}-handoff.md"
            return path if path.exists() else None

        @staticmethod
        def _node_eval_needed(graph, sprint_id, node, force=False):
            return node["id"] == "B1"

        @staticmethod
        def ready_nodes(graph):
            return [node for node in graph["nodes"] if node["id"] == "B2"]

        @staticmethod
        def dispatch_node_evals(path, dry_run=False, ttl=900, max_items=0):
            calls.append(("eval", dry_run, max_items))
            return {"ok": True, "dispatched": [{"node": "B1"}], "reconciled": [], "skipped": []}

        @staticmethod
        def dispatch_ready(path, dry_run=False, ttl=900, max_parallel=None):
            calls.append(("builder", dry_run, max_parallel))
            return {"ok": True, "enqueue": {"enqueued": [{"node": "B2"}]}, "drain": {"ok": True, "processed": 1, "results": [{"ok": True, "instruction_file": "/tmp/B2-dispatch.md"}]}}

    monkeypatch.setattr(controller, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(controller, "_load_graph_dispatcher", lambda: FakeDispatcher)

    payload = controller.run_graph_drain(apply=False, max_graphs=5, max_evals=2, max_builders=1)

    assert payload["dry_run"] is True
    assert payload["counters"]["eval_candidates"] == 1
    assert payload["counters"]["builder_candidates"] == 1
    assert payload["counters"]["drain_submitted"] == 0
    assert ("eval", True, 1) in calls
    assert ("builder", True, 1) in calls
    assert payload["actions"][0]["would_submit"] == 1


def test_graph_drain_apply_counts_real_eval_and_builder_submissions(monkeypatch, tmp_path):
    controller = _load_controller()
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sid = "sprint-test"
    _write_graph(sprints, sid)

    class FakeDispatcher:
        @staticmethod
        def load_graph(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))

        @staticmethod
        def _existing_node_handoff(sprint_id, node, graph):
            path = sprints / f"{sprint_id}.{node['id']}-handoff.md"
            return path if path.exists() else None

        @staticmethod
        def _node_eval_needed(graph, sprint_id, node, force=False):
            return node["id"] == "B1"

        @staticmethod
        def ready_nodes(graph):
            return [node for node in graph["nodes"] if node["id"] == "B2"]

        @staticmethod
        def dispatch_node_evals(path, dry_run=False, ttl=900, max_items=0):
            return {"ok": True, "dispatched": [{"node": "B1"}], "reconciled": [{"node": "old"}], "skipped": []}

        @staticmethod
        def dispatch_ready(path, dry_run=False, ttl=900, max_parallel=None):
            return {"ok": True, "enqueue": {"enqueued": [{"node": "B2"}]}, "drain": {"ok": True, "processed": 1, "results": [{"ok": True, "instruction_file": "/tmp/B2-dispatch.md"}]}}

    monkeypatch.setattr(controller, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(controller, "_load_graph_dispatcher", lambda: FakeDispatcher)

    payload = controller.run_graph_drain(apply=True, max_graphs=5, max_evals=2, max_builders=1)

    assert payload["dry_run"] is False
    assert payload["counters"]["evals_dispatched"] == 1
    assert payload["counters"]["builders_dispatched"] == 1
    assert payload["counters"]["reconciled"] == 1
    assert payload["counters"]["drain_submitted"] == 2


def test_graph_drain_apply_does_not_count_unavailable_builder_retry(monkeypatch, tmp_path):
    controller = _load_controller()
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sid = "sprint-test"
    _write_graph(sprints, sid)

    class FakeDispatcher:
        @staticmethod
        def load_graph(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))

        @staticmethod
        def _existing_node_handoff(sprint_id, node, graph):
            return None

        @staticmethod
        def ready_nodes(graph):
            return [node for node in graph["nodes"] if node["id"] == "B2"]

        @staticmethod
        def dispatch_ready(path, dry_run=False, ttl=900, max_parallel=None):
            return {
                "ok": True,
                "enqueue": {"enqueued": [{"node": "B2"}]},
                "drain": {
                    "ok": True,
                    "processed": 1,
                    "results": [
                        {
                            "ok": True,
                            "reason": "assigned_pane_unavailable_retry_later",
                            "unavailable_reason": "pane_hygiene_needs_respawn",
                        }
                    ],
                },
            }

    monkeypatch.setattr(controller, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(controller, "_load_graph_dispatcher", lambda: FakeDispatcher)

    payload = controller.run_graph_drain(apply=True, max_graphs=5, max_evals=0, max_builders=1)

    assert payload["counters"]["builder_candidates"] == 1
    assert payload["counters"]["builders_dispatched"] == 0
    assert payload["counters"]["drain_submitted"] == 0
    assert payload["counters"]["skipped"] == 1
    assert payload["skipped"][0]["reason"] == "builder_drain_no_dispatch"
    assert payload["skipped"][0]["drain_reasons"] == ["assigned_pane_unavailable_retry_later"]


def test_graph_drain_uses_autopilot_ready_decision_for_builder_candidates(monkeypatch, tmp_path):
    controller = _load_controller()
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sid = "sprint-test"
    _write_graph(sprints, sid)

    class FakeDispatcher:
        @staticmethod
        def load_graph(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))

        @staticmethod
        def _existing_node_handoff(sprint_id, node, graph):
            return None

        @staticmethod
        def ready_nodes(graph):
            return [node for node in graph["nodes"] if node["id"] == "B2"]

        @staticmethod
        def autopilot_ready_decision(graph, emit_shadow=False):
            return {"ready_nodes": []}

        @staticmethod
        def dispatch_ready(path, dry_run=False, ttl=900, max_parallel=None):
            raise AssertionError("autopilot-empty graph should not dispatch builders")

    monkeypatch.setattr(controller, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(controller, "_load_graph_dispatcher", lambda: FakeDispatcher)

    payload = controller.run_graph_drain(apply=True, max_graphs=5, max_evals=0, max_builders=1)

    assert payload["counters"]["builder_candidates"] == 0
    assert payload["counters"]["builder_attempts"] == 0
    assert payload["skipped"] == []


def test_graph_drain_uses_scheduler_autopilot_when_dispatcher_lacks_it(monkeypatch, tmp_path):
    controller = _load_controller()
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    sid = "sprint-test"
    _write_graph(sprints, sid)

    class FakeDispatcher:
        @staticmethod
        def load_graph(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))

        @staticmethod
        def _existing_node_handoff(sprint_id, node, graph):
            return None

        @staticmethod
        def ready_nodes(graph):
            return [node for node in graph["nodes"] if node["id"] == "B2"]

        @staticmethod
        def dispatch_ready(path, dry_run=False, ttl=900, max_parallel=None):
            raise AssertionError("scheduler autopilot-empty graph should not dispatch builders")

    class FakeScheduler:
        @staticmethod
        def autopilot_ready_decision(graph, emit_shadow=False):
            return {"ready_nodes": []}

    monkeypatch.setattr(controller, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(controller, "_load_graph_dispatcher", lambda: FakeDispatcher)
    monkeypatch.setattr(controller, "_load_graph_scheduler", lambda: FakeScheduler)

    payload = controller.run_graph_drain(apply=True, max_graphs=5, max_evals=0, max_builders=1)

    assert payload["counters"]["builder_candidates"] == 0
    assert payload["counters"]["builder_attempts"] == 0
    assert payload["skipped"] == []


def test_graph_drain_prioritizes_handoff_ready_eval_graphs_inside_scan_window(monkeypatch, tmp_path):
    controller = _load_controller()
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    hot_sid = "sprint-hot-eval"
    cold_sid = "sprint-cold-newer"
    _write_graph_with_nodes(
        sprints,
        hot_sid,
        [{"id": "B1", "status": "reviewing", "artifacts": {"handoff_md": f"{hot_sid}.B1-handoff.md"}}],
    )
    (sprints / f"{hot_sid}.B1-handoff.md").write_text("# hot handoff\n", encoding="utf-8")
    _write_graph_with_nodes(
        sprints,
        cold_sid,
        [{"id": "B1", "status": "pending"}],
    )
    cold_path = sprints / f"{cold_sid}.task_graph.json"
    hot_path = sprints / f"{hot_sid}.task_graph.json"
    cold_path.touch()

    class FakeDispatcher:
        @staticmethod
        def load_graph(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))

        @staticmethod
        def _existing_node_handoff(sprint_id, node, graph):
            path = sprints / f"{sprint_id}.{node['id']}-handoff.md"
            return path if path.exists() else None

        @staticmethod
        def _node_eval_needed(graph, sprint_id, node, force=False):
            return sprint_id == hot_sid and node["id"] == "B1"

        @staticmethod
        def ready_nodes(graph):
            return []

        @staticmethod
        def dispatch_node_evals(path, dry_run=False, ttl=900, max_items=0):
            assert Path(path) == hot_path
            return {"ok": True, "dispatched": [{"node": "B1"}], "reconciled": [], "skipped": []}

    monkeypatch.setattr(controller, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(controller, "_load_graph_dispatcher", lambda: FakeDispatcher)

    payload = controller.run_graph_drain(apply=False, max_graphs=1, max_evals=1, max_builders=0)

    assert payload["counters"]["graphs_scanned"] == 1
    assert payload["counters"]["eval_candidates"] == 1
    assert payload["candidates"][0]["sprint_id"] == hot_sid
