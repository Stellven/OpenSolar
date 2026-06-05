"""Regression tests for evaluation planning before evaluator dispatch."""

from __future__ import annotations

import json
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
                "eval_retry_reason": "eval_dispatch_send_failed",
                "eval_retry_detail": {"reason": "operator_pool_eval_submit_failed"},
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
    assert "eval_retry_reason" not in graph["nodes"][0]
    assert "eval_retry_detail" not in graph["nodes"][0]


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


def test_dispatch_node_evals_operator_pool_send_failed_records_submit_detail(monkeypatch) -> None:
    graph = {
        "sprint_id": "sid-eval-pool-send-failed",
        "nodes": [
            {
                "id": "N2",
                "goal": "needs operator-pool eval",
                "status": "reviewing",
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
    monkeypatch.setattr(gnd, "_eval_dispatch_member_file", lambda sid, node_id, idx: Path(f"/tmp/eval-dispatch-{idx}.md"))
    monkeypatch.setattr(gnd, "_inject_dispatch_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "release_lease", lambda *args, **kwargs: {"released": True})
    monkeypatch.setattr(
        gnd,
        "_submit_eval_to_operator_pool",
        lambda **kwargs: {
            "ok": False,
            "reason": "operator_pool_eval_submit_failed",
            "returncode": 1,
            "stderr": "ERROR: 没有可用算子 (no_dispatchable_operator_for_role: evaluator)",
            "stdout": "",
        },
    )
    monkeypatch.setattr(
        gnd,
        "_discover_evaluators",
        lambda dry_run=False: [
            {"pane": "operator-pool:evaluator.0", "busy": False, "models": ["operator-pool"], "skills": ["review"]},
        ],
    )

    result = gnd.dispatch_node_evals("/tmp/sid-eval-pool-send-failed.task_graph.json", dry_run=False)

    node = graph["nodes"][0]
    assert result["ok"] is False
    assert result["skipped"][0]["reason"] == "send_failed"
    assert result["skipped"][0]["operator_pool"]["reason"] == "operator_pool_eval_submit_failed"
    assert "no_dispatchable_operator_for_role" in result["skipped"][0]["operator_pool"]["stderr"]
    assert node["status"] == "reviewing"
    assert node["eval_retry_detail"]["reason"] == "operator_pool_eval_submit_failed"
    assert "no_dispatchable_operator_for_role" in node["eval_retry_detail"]["stderr"]
    assert saved["graph"] is graph


def test_dispatch_node_evals_operator_pool_uses_pm_task_id_as_durable_eval_dispatch(monkeypatch) -> None:
    graph = {
        "sprint_id": "sid-eval-pool-success",
        "nodes": [
            {
                "id": "N2",
                "goal": "needs operator-pool eval",
                "status": "reviewing",
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
    monkeypatch.setattr(gnd, "_eval_dispatch_member_file", lambda sid, node_id, idx: Path(f"/tmp/eval-dispatch-{idx}.md"))
    monkeypatch.setattr(gnd, "_inject_dispatch_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_write_submit_ack", lambda *args, **kwargs: None)
    monkeypatch.setattr(gnd, "_sync_state_node", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(
        gnd,
        "_submit_eval_to_operator_pool",
        lambda **kwargs: {
            "ok": True,
            "pane": "operator:mini-codex-gpt55-medium-builder-1",
            "operator_id": "mini-codex-gpt55-medium-builder-1",
            "pm_dispatch": {
                "pm_task_id": "pm-sid-eval-pool-success-N2-test",
                "pm_dispatch_file": "/tmp/pm-dispatch.md",
            },
        },
    )
    monkeypatch.setattr(
        gnd,
        "_discover_evaluators",
        lambda dry_run=False: [
            {"pane": "operator-pool:evaluator.0", "busy": False, "models": ["operator-pool"], "skills": ["review"]},
        ],
    )

    result = gnd.dispatch_node_evals("/tmp/sid-eval-pool-success.task_graph.json", dry_run=False)

    node = graph["nodes"][0]
    assignment = node["eval_assignments"][0]
    assert result["ok"] is True
    assert result["skipped"] == []
    assert result["dispatched"][0]["dispatch_id"] == "pm-sid-eval-pool-success-N2-test"
    assert result["dispatched"][0]["pm_task_id"] == "pm-sid-eval-pool-success-N2-test"
    assert result["dispatched"][0]["graph_dispatch_id"].startswith("graph-eval-sid-eval-pool-success-N2-")
    assert node["eval_dispatch_id"] == "pm-sid-eval-pool-success-N2-test"
    assert node["eval_task_id"] == "pm-sid-eval-pool-success-N2-test"
    assert node["eval_graph_dispatch_id"].startswith("graph-eval-sid-eval-pool-success-N2-")
    assert assignment["task_id"] == "pm-sid-eval-pool-success-N2-test"
    assert assignment["dispatch_id"].startswith("graph-eval-sid-eval-pool-success-N2-")
    assert assignment["graph_dispatch_id"] == assignment["dispatch_id"]
    assert assignment["operator_id"] == "mini-codex-gpt55-medium-builder-1"
    assert saved["graph"] is graph


def test_node_eval_needed_recovers_active_pm_evaluator_task(monkeypatch, tmp_path) -> None:
    sid = "sid-eval-pm-recover"
    node_id = "N2"
    task_id = "pm-sid-eval-pm-recover-N2-active"
    operator_id = "mini-codex-gpt55-medium-builder-2"
    graph_dispatch_id = "graph-eval-sid-eval-pm-recover-N2-20260605T211102Z-q1"
    graph = {
        "sprint_id": sid,
        "nodes": [
            {
                "id": node_id,
                "goal": "recover active PM evaluator task",
                "status": "reviewing",
            }
        ],
    }
    node = graph["nodes"][0]
    inbox_path = tmp_path / "run" / "operator-inbox" / operator_id / f"{task_id}.json"
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text("{}", encoding="utf-8")
    pm_inbox = tmp_path / "run" / "pm-inbox"
    pm_inbox.mkdir(parents=True, exist_ok=True)
    (pm_inbox / f"{task_id}.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "sprint_id": sid,
                "node_id": node_id,
                "operator_id": operator_id,
                "requested_role": "evaluator",
                "status": "submitted",
                "graph_eval_dispatch": True,
                "graph_eval_dispatch_id": graph_dispatch_id,
                "inbox_path": str(inbox_path),
                "submitted_at": "2026-06-05T21:11:21Z",
            }
        ),
        encoding="utf-8",
    )
    operator_lease = tmp_path / "run" / "operator-leases" / f"{operator_id}.json"
    operator_lease.parent.mkdir(parents=True, exist_ok=True)
    operator_lease.write_text(
        json.dumps(
            {
                "operator_id": operator_id,
                "task_id": task_id,
                "sprint_id": sid,
                "node_id": node_id,
                "state": "running",
                "expires_at": "2999-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(gnd, "HARNESS_DIR", tmp_path)
    monkeypatch.setattr(gnd, "_eval_md_file", lambda sid, node_id: tmp_path / f"{sid}.{node_id}-eval.md")
    monkeypatch.setattr(gnd, "_eval_json_file", lambda sid, node_id: tmp_path / f"{sid}.{node_id}-eval.json")
    monkeypatch.setattr(gnd, "_sync_state_node", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(gnd, "list_leases", lambda: [])

    needed = gnd._node_eval_needed(graph, sid, node, force=False)

    assignment = node["eval_assignments"][0]
    assert needed is False
    assert node["eval_dispatch_id"] == task_id
    assert node["eval_task_id"] == task_id
    assert node["eval_graph_dispatch_id"] == graph_dispatch_id
    assert node["eval_operator_id"] == operator_id
    assert node["eval_recovered_from_pm_task"] is True
    assert assignment["pane"] == f"operator:{operator_id}"
    assert assignment["dispatch_id"] == task_id
    assert assignment["task_id"] == task_id
    assert assignment["graph_dispatch_id"] == graph_dispatch_id


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
