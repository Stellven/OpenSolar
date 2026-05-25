"""Proof obligation gate tests for graph node verdict."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import graph_node_dispatcher as gnd  # noqa: E402


def _graph(sid: str, proof_obligations: list[dict]) -> dict:
    return {
        "sprint_id": sid,
        "nodes": [{
            "id": "N2",
            "goal": "Implement and verify patch",
            "depends_on": [],
            "write_scope": ["/tmp/repo"],
            "status": "reviewing",
            "proof_obligations": proof_obligations,
        }],
        "node_results": {},
        "gate_results": {},
    }


def test_node_verdict_blocks_missing_handoff_proof(tmp_path, monkeypatch):
    sid = "sprint-proof-handoff-missing"
    graph_path = tmp_path / f"{sid}.task_graph.json"
    graph_path.write_text(
        json.dumps(
            _graph(
                sid,
                [
                    {"kind": "postcondition", "source_capsule_id": "cap.impl", "requirement": "output_present", "field": "handoff_md"},
                    {"kind": "external_verifier", "source_capsule_id": "cap.impl", "requirement": "external_verifier.required"},
                ],
            )
        ),
        encoding="utf-8",
    )
    eval_json = tmp_path / f"{sid}.N2-eval.json"
    eval_json.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")

    monkeypatch.setattr(gnd, "SPRINTS_DIR", tmp_path)

    result = gnd.node_verdict(str(graph_path), "N2", "pass", eval_json=str(eval_json), dispatch_downstream=False)
    assert result["ok"] is False
    assert result["reason"] == "proof_obligations_failed"
    assert any(item["field"] == "handoff_md" for item in result["proof_gate"]["missing"])


def test_node_verdict_accepts_satisfied_proof_obligations(tmp_path, monkeypatch):
    sid = "sprint-proof-pass"
    graph_path = tmp_path / f"{sid}.task_graph.json"
    graph_path.write_text(
        json.dumps(
            _graph(
                sid,
                [
                    {"kind": "postcondition", "source_capsule_id": "cap.impl", "requirement": "output_present", "field": "handoff_md"},
                    {"kind": "external_verifier", "source_capsule_id": "cap.impl", "requirement": "external_verifier.required"},
                ],
            )
        ),
        encoding="utf-8",
    )
    eval_json = tmp_path / f"{sid}.N2-eval.json"
    eval_json.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
    handoff = tmp_path / f"{sid}.N2-handoff.md"
    handoff.write_text("# Handoff\n", encoding="utf-8")

    monkeypatch.setattr(gnd, "SPRINTS_DIR", tmp_path)
    monkeypatch.setattr(gnd, "release_lease", lambda *a, **kw: {"released": False})
    monkeypatch.setattr(gnd, "_mark_parent_sprint_passed_if_ready", lambda *a, **kw: False)

    result = gnd.node_verdict(str(graph_path), "N2", "pass", eval_json=str(eval_json), dispatch_downstream=False)
    assert result["ok"] is True
    assert result["status"] == "passed"
    assert result["proof_gate"]["ok"] is True
