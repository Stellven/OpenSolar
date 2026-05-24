#!/usr/bin/env bash
set -euo pipefail

HARNESS_DIR_SRC="${HARNESS_DIR_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

HARNESS_DIR="$HARNESS_DIR_SRC" SOLAR_HARNESS_SESSION="solar-harness-test" python3 - <<'PY'
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.environ["HARNESS_DIR"], "lib"))
import graph_node_dispatcher as g


def fake_check_output(*args, **kwargs):
    return (
        b"solar-harness-test:0.0\tBuilder wrong-main-slot\n"
        b"solar-harness-test:0.2\tPM \xe4\xba\xa7\xe5\x93\x81\xe7\xbb\x8f\xe7\x90\x86\n"
        b"solar-harness-lab:0.0\tPlanner \xe8\xa7\x84\xe5\x88\x92\xe8\x80\x85\n"
        b"solar-harness-lab:0.1\tBuilder 2 | \xe6\xa8\xa1\xe5\x9e\x8b:GLM\n"
    )


subprocess.check_output = fake_check_output
g._clear_stale_prompt_residue = lambda pane: False
g._pane_runtime_unavailable_reason = lambda pane, title="": ""
g._pane_unavailable_reason = lambda pane: ""
g._pane_has_active_lease = lambda pane: False
g._pane_tui_busy = lambda pane: False
g._pane_current_command = lambda pane: "claude"
g._pane_health = lambda pane: {}
workers = [item["pane"] for item in g._discover_workers(False)]
assert workers == ["solar-harness-lab:0.1"], workers

subprocess.check_output = lambda *args, **kwargs: (
    b"solar-harness-test:0.3\tEvaluator \xe5\xae\xa1\xe5\x88\xa4\xe5\xae\x98\n"
    b"solar-harness-lab:0.3\tBuilder 4 | \xe6\xa8\xa1\xe5\x9e\x8b:Sonnet\n"
)
g._pane_exists = lambda pane: True
g._pane_title = lambda pane: "PM 产品经理" if pane == "solar-harness-test:0.3" else "Builder 4 | 模型:Sonnet"
assert g._discover_evaluators(False) == []
g._pane_title = lambda pane: "Evaluator 审判官 | 模型:Opus" if pane == "solar-harness-test:0.3" else "Builder 4 | 模型:Sonnet"
evaluators = [item["pane"] for item in g._discover_evaluators(False)]
assert evaluators == ["solar-harness-test:0.3"], evaluators
PY

echo "PASS graph dispatch filters pane targets by role title"
