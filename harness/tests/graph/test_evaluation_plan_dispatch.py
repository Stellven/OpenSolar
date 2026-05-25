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
        "proof_obligations": [
            {"kind": "self_check", "requirement": "check.coverage_reviewed"},
            {"kind": "postcondition", "requirement": "output_present", "field": "eval_json"},
        ],
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
    assert "## Proof Obligations" in text
    assert "Review Mode: `single`" in text
    assert '"evaluation_plan": {' in text
    assert '"proof_obligations": [' in text
    assert '"proof_checks": {' in text
    assert '"verification_results": {' in text
