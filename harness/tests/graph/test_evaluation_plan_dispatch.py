"""Regression tests for evaluation planning before evaluator dispatch."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import graph_node_dispatcher as gnd  # noqa: E402


def test_plan_node_evaluation_derives_staged_mode_for_code_impl() -> None:
    node = {
        "id": "N1",
        "task_type": "CODE_IMPL",
        "verifier_required": True,
        "write_scope": ["/tmp/example.py"],
    }

    plan = gnd._plan_node_evaluation({}, node)

    assert plan["planning_source"] == "derived"
    assert plan["review_mode"] == "staged"
    assert plan["required_evaluators"] == 1
    assert "Verifier" in plan["evaluator_classes"]
    assert "patch_diff" in plan["evidence_requirements"]
    assert "test_report" in plan["evidence_requirements"]


def test_dispatch_node_evals_falls_back_dual_plan_to_staged_with_single_evaluator(monkeypatch) -> None:
    graph = {
        "sprint_id": "sid-eval-plan",
        "nodes": [
            {
                "id": "N2",
                "goal": "needs dual review",
                "status": "reviewing",
                "evaluation_plan": {
                    "review_mode": "dual",
                    "required_evaluators": 2,
                    "evaluator_classes": ["Verifier"],
                },
            }
        ],
    }
    saved: dict[str, object] = {}

    monkeypatch.setattr(gnd, "load_graph", lambda path: graph)
    monkeypatch.setattr(gnd, "save_graph", lambda path, data: saved.setdefault("graph", data))
    monkeypatch.setattr(gnd, "_node_eval_needed", lambda *args, **kwargs: True)
    monkeypatch.setattr(gnd, "_existing_node_handoff", lambda sid, node, graph: Path("/tmp/handoff.md"))
    monkeypatch.setattr(gnd, "_node_handoff_candidates", lambda sid, node, graph: [Path("/tmp/handoff.md")])
    monkeypatch.setattr(gnd, "_eval_md_file", lambda sid, node_id: Path("/tmp/eval.md"))
    monkeypatch.setattr(gnd, "_eval_json_file", lambda sid, node_id: Path("/tmp/eval.json"))
    monkeypatch.setattr(gnd, "_dispatch_file", lambda sid, node_id: Path("/tmp/dispatch.md"))
    monkeypatch.setattr(gnd, "_eval_dispatch_file", lambda sid, node_id: Path("/tmp/eval-dispatch.md"))
    monkeypatch.setattr(gnd, "_eval_dispatch_member_file", lambda sid, node_id, idx: Path(f"/tmp/eval-dispatch-{idx}.md"))
    monkeypatch.setattr(gnd, "_inject_dispatch_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_write_submit_ack", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_send_to_pane", lambda *args, **kwargs: True)
    monkeypatch.setattr(gnd, "_ensure_lease", lambda *args, **kwargs: {"acquired": True, "reason": "ok"})
    monkeypatch.setattr(
        gnd,
        "_discover_evaluators",
        lambda dry_run=False: [
            {"pane": "solar-harness:0.3", "busy": False, "models": ["opus"], "skills": ["review"]},
        ],
    )

    result = gnd.dispatch_node_evals("/tmp/sid-eval-plan.task_graph.json", dry_run=False)

    assert result["skipped"] == []
    assert result["dispatched"][0]["node"] == "N2"
    plan = graph["nodes"][0]["evaluation_plan"]
    requested = graph["nodes"][0]["evaluation_plan_requested"]
    assert requested["review_mode"] == "dual"
    assert requested["required_evaluators"] == 2
    assert plan["review_mode"] == "staged"
    assert plan["required_evaluators"] == 1
    assert plan["fallback_applied"] is True
    assert plan["requested_review_mode"] == "dual"
    assert plan["capacity"]["available_evaluators"] == 1
    assert plan["capacity"]["dispatchable_now"] is True


def test_dispatch_node_evals_send_failed_restores_reviewing(monkeypatch) -> None:
    graph = {
        "sprint_id": "sid-eval-send-failed",
        "nodes": [
            {
                "id": "N2",
                "goal": "needs retryable eval",
                "status": "dispatched",
                "eval_assignments": [
                    {
                        "pane": "solar-harness:0.3",
                        "dispatch_id": "old-eval-dispatch",
                    }
                ],
                "eval_dispatched_at": "2026-06-05T00:00:00Z",
            }
        ],
    }
    released: list[tuple[str, str, str]] = []
    saved: dict[str, object] = {}

    monkeypatch.setattr(gnd, "load_graph", lambda path: graph)
    monkeypatch.setattr(gnd, "save_graph", lambda path, data: saved.setdefault("graph", data))
    monkeypatch.setattr(gnd, "_node_eval_needed", lambda *args, **kwargs: True)
    monkeypatch.setattr(gnd, "_existing_node_handoff", lambda sid, node, graph: Path("/tmp/handoff.md"))
    monkeypatch.setattr(gnd, "_node_handoff_candidates", lambda sid, node, graph: [Path("/tmp/handoff.md")])
    monkeypatch.setattr(gnd, "_eval_md_file", lambda sid, node_id: Path("/tmp/eval.md"))
    monkeypatch.setattr(gnd, "_eval_json_file", lambda sid, node_id: Path("/tmp/eval.json"))
    monkeypatch.setattr(gnd, "_dispatch_file", lambda sid, node_id: Path("/tmp/dispatch.md"))
    monkeypatch.setattr(gnd, "_eval_dispatch_file", lambda sid, node_id: Path("/tmp/eval-dispatch.md"))
    monkeypatch.setattr(gnd, "_eval_dispatch_member_file", lambda sid, node_id, idx: Path(f"/tmp/eval-dispatch-{idx}.md"))
    monkeypatch.setattr(gnd, "_inject_dispatch_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_write_submit_ack", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_send_to_pane", lambda *args, **kwargs: False)
    monkeypatch.setattr(gnd, "_pane_unavailable_reason", lambda pane: "test_send_failed")
    monkeypatch.setattr(gnd, "_mark_pane_recover_retryable", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_mark_pane_recover_cooldown", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_ensure_lease", lambda *args, **kwargs: {"acquired": True, "reason": "ok"})
    monkeypatch.setattr(gnd, "release_lease", lambda pane, dispatch_id, reason: released.append((pane, dispatch_id, reason)) or {"released": True})
    monkeypatch.setattr(
        gnd,
        "_discover_evaluators",
        lambda dry_run=False: [
            {"pane": "solar-harness:0.3", "busy": False, "models": ["opus"], "skills": ["review"]},
        ],
    )

    result = gnd.dispatch_node_evals("/tmp/sid-eval-send-failed.task_graph.json", dry_run=False)

    node = graph["nodes"][0]
    assert result["ok"] is False
    assert result["skipped"][0]["reason"] == "send_failed"
    assert node["status"] == "reviewing"
    assert node["eval_retry_reason"] == "eval_dispatch_send_failed"
    assert "eval_assignments" not in node
    assert "eval_dispatched_at" not in node
    assert released[0][2] == "graph_eval_dispatch_send_failed"
    assert saved["graph"] is graph


def test_force_dispatch_node_evals_archives_stale_eval_sidecars(monkeypatch, tmp_path) -> None:
    graph = {
        "sprint_id": "sid-force-archive",
        "nodes": [
            {
                "id": "N1",
                "goal": "retry after repaired artifact",
                "status": "failed",
            }
        ],
        "node_results": {"N1": {"status": "failed"}},
    }
    eval_md = tmp_path / "sid-force-archive.N1-eval.md"
    eval_json = tmp_path / "sid-force-archive.N1-eval.json"
    eval_md.write_text("old fail", encoding="utf-8")
    eval_json.write_text('{"verdict":"FAIL"}', encoding="utf-8")
    handoff = tmp_path / "sid-force-archive.N1-handoff.md"
    handoff.write_text("repaired", encoding="utf-8")

    monkeypatch.setattr(gnd, "load_graph", lambda path: graph)
    monkeypatch.setattr(gnd, "save_graph", lambda path, data: None)
    monkeypatch.setattr(gnd, "_existing_node_handoff", lambda sid, node, graph: handoff)
    monkeypatch.setattr(gnd, "_node_handoff_candidates", lambda sid, node, graph: [handoff])
    monkeypatch.setattr(gnd, "_eval_md_file", lambda sid, node_id: eval_md)
    monkeypatch.setattr(gnd, "_eval_json_file", lambda sid, node_id: eval_json)
    monkeypatch.setattr(gnd, "_dispatch_file", lambda sid, node_id: tmp_path / "dispatch.md")
    monkeypatch.setattr(gnd, "_eval_dispatch_file", lambda sid, node_id: tmp_path / "eval-dispatch.md")
    monkeypatch.setattr(gnd, "_inject_dispatch_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_write_submit_ack", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_send_to_pane", lambda *args, **kwargs: True)
    monkeypatch.setattr(gnd, "_ensure_lease", lambda *args, **kwargs: {"acquired": True, "reason": "ok"})
    monkeypatch.setattr(
        gnd,
        "_discover_evaluators",
        lambda dry_run=False: [
            {"pane": "solar-harness:0.3", "busy": False, "models": ["opus"], "skills": ["review"]},
        ],
    )

    result = gnd.dispatch_node_evals("/tmp/sid-force-archive.task_graph.json", dry_run=False, force=True)

    assert result["skipped"] == []
    assert result["dispatched"][0]["node"] == "N1"
    assert not eval_md.exists()
    assert not eval_json.exists()
    archived = graph["nodes"][0]["last_eval_sidecar_archive"]
    assert {Path(item["from"]).name for item in archived} == {
        "sid-force-archive.N1-eval.md",
        "sid-force-archive.N1-eval.json",
    }
    assert all(Path(item["to"]).exists() for item in archived)
    assert graph["nodes"][0]["eval_retry_reason"] == "force_retry_archived_stale_eval_sidecars"


def test_dispatch_node_evals_keeps_dual_plan_when_quorum_capacity_exists(monkeypatch) -> None:
    graph = {
        "sprint_id": "sid-eval-plan-quorum",
        "nodes": [
            {
                "id": "N4",
                "goal": "needs committee",
                "status": "reviewing",
                "evaluation_plan": {
                    "review_mode": "dual",
                    "required_evaluators": 2,
                    "evaluator_classes": ["Verifier"],
                },
            }
        ],
    }

    monkeypatch.setattr(gnd, "load_graph", lambda path: graph)
    monkeypatch.setattr(gnd, "save_graph", lambda path, data: None)
    monkeypatch.setattr(gnd, "_node_eval_needed", lambda *args, **kwargs: True)
    monkeypatch.setattr(gnd, "_existing_node_handoff", lambda sid, node, graph: Path("/tmp/handoff.md"))
    monkeypatch.setattr(gnd, "_node_handoff_candidates", lambda sid, node, graph: [Path("/tmp/handoff.md")])
    monkeypatch.setattr(gnd, "_eval_md_file", lambda sid, node_id: Path("/tmp/eval.md"))
    monkeypatch.setattr(gnd, "_eval_json_file", lambda sid, node_id: Path("/tmp/eval.json"))
    monkeypatch.setattr(gnd, "_dispatch_file", lambda sid, node_id: Path("/tmp/dispatch.md"))
    monkeypatch.setattr(gnd, "_eval_dispatch_file", lambda sid, node_id: Path("/tmp/eval-dispatch.md"))
    monkeypatch.setattr(gnd, "_eval_dispatch_member_file", lambda sid, node_id, idx: Path(f"/tmp/eval-dispatch-{idx}.md"))
    monkeypatch.setattr(gnd, "_inject_dispatch_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_write_submit_ack", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_send_to_pane", lambda *args, **kwargs: True)
    monkeypatch.setattr(gnd, "_ensure_lease", lambda *args, **kwargs: {"acquired": True, "reason": "ok"})
    monkeypatch.setattr(
        gnd,
        "_discover_evaluators",
        lambda dry_run=False: [
            {"pane": "solar-harness:0.3", "busy": False, "models": ["opus"], "skills": ["review"]},
            {"pane": "solar-harness-lab:0.3", "busy": False, "models": ["opus"], "skills": ["review"]},
        ],
    )

    result = gnd.dispatch_node_evals("/tmp/sid-eval-plan-quorum.task_graph.json", dry_run=False)

    assert result["skipped"] == []
    assert len(result["dispatched"]) == 2
    assert {item["pane"] for item in result["dispatched"]} == {"solar-harness:0.3", "solar-harness-lab:0.3"}
    plan = graph["nodes"][0]["evaluation_plan"]
    requested = graph["nodes"][0]["evaluation_plan_requested"]
    assert requested["review_mode"] == "dual"
    assert requested["capacity"]["quorum_dispatch_supported"] is True
    assert plan["review_mode"] == "dual"
    assert plan["required_evaluators"] == 2
    assert plan["capacity"]["dispatchable_now"] is True
    assert graph["nodes"][0]["eval_assignments"][0]["role"] == "primary"
    assert graph["nodes"][0]["eval_assignments"][1]["role"] == "secondary"


def test_build_eval_dispatch_text_includes_evaluation_plan(monkeypatch, tmp_path) -> None:
    graph = {"sprint_id": "sid-eval-text"}
    node = {
        "id": "N3",
        "goal": "review with explicit plan",
        "evaluation_plan": {
            "review_mode": "single",
            "required_evaluators": 1,
            "evaluator_classes": ["Verifier"],
            "evidence_requirements": ["handoff_md", "session_log"],
        },
    }
    handoff = tmp_path / "sid-eval-text.N3-handoff.md"
    dispatch = tmp_path / "sid-eval-text.N3-dispatch.md"
    monkeypatch.setattr(gnd, "_existing_node_handoff", lambda sid, node, graph: handoff)
    monkeypatch.setattr(gnd, "_node_handoff_candidates", lambda sid, node, graph: [handoff])
    monkeypatch.setattr(gnd, "_eval_md_file", lambda sid, node_id: tmp_path / "eval.md")
    monkeypatch.setattr(gnd, "_eval_json_file", lambda sid, node_id: tmp_path / "eval.json")
    monkeypatch.setattr(gnd, "_dispatch_file", lambda sid, node_id: dispatch)
    monkeypatch.setattr(gnd, "SPRINTS_DIR", tmp_path)
    (tmp_path / "sid-eval-text.contract.md").write_text("# contract\n", encoding="utf-8")

    text = gnd.build_eval_dispatch_text(graph, "/tmp/graph.json", node, "solar-harness:0.3", "did")

    assert "## Evaluation Plan" in text
    assert "Review Mode: `single`" in text
    assert '"evaluation_plan": {' in text
