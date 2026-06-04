from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _do_eval_verdict_body() -> str:
    script = (REPO_ROOT / "solar-harness.sh").read_text(encoding="utf-8")
    start = script.index("do_eval_verdict() {")
    end = script.index("\ndo_verify_events() {", start)
    return script[start:end]


def test_eval_verdict_pass_path_calls_evidence_gate_before_status_write() -> None:
    body = _do_eval_verdict_body()

    gate_index = body.index("gate_status_transition(sid, \"reviewing\", \"passed\")")
    transition_index = body.index("rs_transition \"$sid\" \"$new_status\"")

    assert gate_index < transition_index
    assert "if decision.action == \"abort\":" in body
    assert "eval-verdict evidence gate blocked" in body
