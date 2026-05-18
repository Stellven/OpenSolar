#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
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

    print("PASS graph dispatcher ignores stale completed prompt scrollback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
