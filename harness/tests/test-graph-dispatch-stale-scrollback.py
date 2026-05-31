#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "lib" / "graph_node_dispatcher.py"
spec = importlib.util.spec_from_file_location("graph_node_dispatcher", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["graph_node_dispatcher"] = mod
spec.loader.exec_module(mod)


def main() -> int:
    tail = """
S03 sprint 全部 10 个节点收官

✻ Churned for 2m 45s

────────────────────────────────────────────────────────────────
❯ finalize sprint
────────────────────────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle)
"""
    mod._pane_tail = lambda pane, lines=80: tail
    mod._pane_current_command = lambda pane: "bash"
    mod._pane_health = lambda pane: {}

    assert mod._pane_current_prompt_has_residue(tail)
    assert mod._pane_prompt_residue_is_stale_scrollback("solar-harness:0.3", tail)
    assert mod._pane_unavailable_reason("solar-harness:0.3") == ""
    assert mod._pane_tui_busy("solar-harness:0.3") is False

    distant_marker_tail = """
Evaluator finished prior node review.

✻ Sautéed for 4m 1s

old lines 01
old lines 02
old lines 03
old lines 04
old lines 05
old lines 06
old lines 07
old lines 08
old lines 09
old lines 10
old lines 11
old lines 12
old lines 13
────────────────────────────────────────────────────────────────
❯ 看下 N2 N3 N4 跑完没
────────────────────────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle)
"""
    mod._pane_tail = lambda pane, lines=80: distant_marker_tail
    assert mod._pane_current_prompt_has_residue("\n".join(distant_marker_tail.splitlines()[-12:]))
    assert mod._pane_prompt_residue_is_stale_scrollback("solar-harness:0.3", distant_marker_tail)
    assert mod._pane_unavailable_reason("solar-harness:0.3") == ""
    assert mod._pane_tui_busy("solar-harness:0.3") is False

    worked_marker_tail = distant_marker_tail.replace("✻ Sautéed for 4m 1s", "✻ Worked for 4m 27s")
    mod._pane_tail = lambda pane, lines=80: worked_marker_tail
    assert mod._pane_prompt_residue_is_stale_scrollback("solar-harness:0.3", worked_marker_tail)
    assert mod._pane_unavailable_reason("solar-harness:0.3") == ""
    assert mod._pane_tui_busy("solar-harness:0.3") is False

    cooked_marker_tail = distant_marker_tail.replace("✻ Sautéed for 4m 1s", "✻ Cooked for 4m 1s")
    mod._pane_tail = lambda pane, lines=80: cooked_marker_tail
    assert mod._pane_prompt_residue_is_stale_scrollback("solar-harness:0.3", cooked_marker_tail)
    assert mod._pane_unavailable_reason("solar-harness:0.3") == ""
    assert mod._pane_tui_busy("solar-harness:0.3") is False

    live_prompt = """
────────────────────────────────────────────────────────────────
❯ finalize sprint
────────────────────────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle)
"""
    mod._pane_tail = lambda pane, lines=80: live_prompt
    assert not mod._pane_prompt_residue_is_stale_scrollback("solar-harness:0.3", live_prompt)
    assert mod._pane_unavailable_reason("solar-harness:0.3") == "unsubmitted_prompt_residue"
    assert mod._pane_tui_busy("solar-harness:0.3") is True

    confirmation_prompt = """
────────────────────────────────────────────────────────────────
 Bash command

   for file in *.json; do jq -r 'paths | join(".")' "$file"; done

 Unhandled node type: string

 Do you want to proceed?
 ❯ 1. Yes
   2. No

 Esc to cancel · Tab to amend · ctrl+e to explain
"""
    mod._pane_tail = lambda pane, lines=80: confirmation_prompt
    assert mod._pane_tui_busy("solar-harness-lab:0.1") is True

    stale_confirmation_prompt = """
 Bash command

   python3 scripts/check.py

 Do you want to proceed?
 ❯ 1. Yes
   2. No

 Esc to cancel · Tab to amend

────────────────────────────────────────────────────────────────
❯
────────────────────────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle) · esc to interrupt
"""
    mod._pane_tail = lambda pane, lines=80: stale_confirmation_prompt
    assert mod._pane_unavailable_reason("solar-harness-lab:0.1") == ""
    assert mod._pane_tui_busy("solar-harness-lab:0.1") is False

    stale_busy_marker_with_empty_prompt = """
  ⎿  ~/.solar/harness/lib/benchmark/schemas.py

· Pondering… (29s · ↓ 430 tokens · thought for 4s)

● How is Claude doing this session? (optional)
  1: Bad    2: Fine   3: Good   0: Dismiss

────────────────────────────────────────────────────────────────
❯
────────────────────────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle) · esc to interrupt
"""
    mod._pane_tail = lambda pane, lines=80: stale_busy_marker_with_empty_prompt
    assert mod._pane_tui_busy("solar-harness:0.3") is False

    with tempfile.TemporaryDirectory() as tmp:
        original_harness = mod.HARNESS_DIR
        original_sprints = mod.SPRINTS_DIR
        tmp_path = Path(tmp)
        mod.HARNESS_DIR = tmp_path
        mod.SPRINTS_DIR = tmp_path / "sprints"
        (mod.SPRINTS_DIR / "graph-acks").mkdir(parents=True)
        released: list[tuple[str, str, str]] = []
        mod.read_lease = lambda pane: {
            "dispatch_id": "dispatch-live-no-ack",
            "expires_at": "2099-01-01T00:00:00Z",
            "acquired_at": "2026-01-01T00:00:00Z",
        }
        mod.release_lease = lambda pane, dispatch_id, reason: released.append((pane, dispatch_id, reason)) or {"released": True}
        mod._pane_title = lambda pane: "Builder | 状态:working/graph_node_idle_assigned"
        mod._pane_tail = lambda pane, lines=80: live_prompt.replace("finalize sprint", "")
        mod._pane_cooldown_reason = lambda pane: ""
        mod._pane_runtime_unavailable_reason = lambda pane, title="": ""
        mod._pane_unavailable_reason = lambda pane: ""
        mod._pane_tui_busy = lambda pane: False
        graph = {
            "sprint_id": "sprint-live-lease-no-ack",
            "nodes": [
                {
                    "id": "N1",
                    "status": "assigned",
                    "assigned_to": "solar-harness-lab:0.2",
                    "dispatch_id": "dispatch-live-no-ack",
                }
            ],
        }
        repaired = mod._reconcile_existing_dispatches(graph, tmp_path / "sprint-live-lease-no-ack.task_graph.json")
        assert repaired and repaired[0]["reason"] == "live_lease_idle_without_submit_ack"
        assert graph["nodes"][0]["status"] == "pending"
        assert "assigned_to" not in graph["nodes"][0]
        assert released[0] == (
            "solar-harness-lab:0.2",
            "dispatch-live-no-ack",
            "graph_dispatch_reconcile_live_lease_idle_without_submit_ack",
        )
        mod.HARNESS_DIR = original_harness
        mod.SPRINTS_DIR = original_sprints

    with tempfile.TemporaryDirectory() as tmp:
        original_harness = mod.HARNESS_DIR
        original_sprints = mod.SPRINTS_DIR
        tmp_path = Path(tmp)
        sid = "sprint-canonical-eval-cleanup"
        mod.HARNESS_DIR = tmp_path
        mod.SPRINTS_DIR = tmp_path / "sprints"
        mod.SPRINTS_DIR.mkdir(parents=True)
        (mod.SPRINTS_DIR / f"{sid}.N1-handoff.md").write_text("# handoff\n", encoding="utf-8")
        (mod.SPRINTS_DIR / f"{sid}.N1-eval.json").write_text(
            json.dumps({"verdict": "PASS", "status": "passed"}),
            encoding="utf-8",
        )
        graph = {
            "sprint_id": sid,
            "nodes": [
                {
                    "id": "N1",
                    "status": "passed",
                    "eval_retry_reason": "eval_failed_contract_closeout",
                    "last_eval_closeout_failure": {"reason": "eval_failed_contract_closeout"},
                    "last_eval_operator_cooldown_after_closeout": {"ok": True},
                    "eval_assigned_to": "operator:bad-evaluator",
                    "eval_dispatch_id": "eval-dispatch-stale",
                }
            ],
        }

        repaired = mod._reconcile_existing_dispatches(graph, tmp_path / f"{sid}.task_graph.json")
        node = graph["nodes"][0]
        assert repaired and repaired[0]["reason"] == "canonical_eval_verdict_cleared_stale_eval_state"
        assert node["status"] == "passed"
        assert node["eval_json"].endswith(f"{sid}.N1-eval.json")
        assert "eval_retry_reason" not in node
        assert "last_eval_closeout_failure" not in node
        assert "eval_assigned_to" not in node
        assert "eval_dispatch_id" not in node
        mod.HARNESS_DIR = original_harness
        mod.SPRINTS_DIR = original_sprints

    with tempfile.TemporaryDirectory() as tmp:
        original_harness = mod.HARNESS_DIR
        tmp_path = Path(tmp)
        mod.HARNESS_DIR = tmp_path
        stale = tmp_path / "sprints" / "s01-req-N5-handoff.md"
        stale.parent.mkdir(parents=True)
        stale.write_text(
            "sprint: `sprint-old-runtime`\n# old handoff\n",
            encoding="utf-8",
        )
        block = mod._write_scope_preflight_block(
            "sprint-current-runtime",
            {"write_scope": ["sprints/s01-req-N5-handoff.md"]},
        )
        assert "Write Scope Preflight" in block
        assert "Treat them as stale inputs" in block
        assert "sprint-old-runtime" in block
        assert "contains_current_sprint=false" in block
        mod.HARNESS_DIR = original_harness

    print("PASS graph dispatcher ignores stale completed prompt scrollback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
