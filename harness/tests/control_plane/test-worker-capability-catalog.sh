#!/usr/bin/env bash
# Regression test: DAG worker discovery must advertise status UI/observability
# capabilities so frontend/status nodes are not stranded as no_matching_worker.
set -euo pipefail

HARNESS_DIR_REAL="${HARNESS_DIR:-$HOME/.solar/harness}"
TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

mkdir -p "$TMPDIR_TEST/lib" "$TMPDIR_TEST/config" "$TMPDIR_TEST/run/pane-leases"
cp "$HARNESS_DIR_REAL/lib/graph_node_dispatcher.py" "$TMPDIR_TEST/lib/graph_node_dispatcher.py"
cp "$HARNESS_DIR_REAL/lib/graph_scheduler.py" "$TMPDIR_TEST/lib/graph_scheduler.py"
cp "$HARNESS_DIR_REAL/lib/task_queue.py" "$TMPDIR_TEST/lib/task_queue.py"
cp "$HARNESS_DIR_REAL/lib/pane_lease.py" "$TMPDIR_TEST/lib/pane_lease.py"
cp "$HARNESS_DIR_REAL/lib/solar_skills.py" "$TMPDIR_TEST/lib/solar_skills.py"
cp "$HARNESS_DIR_REAL/tools/solar-autopilot-monitor.py" "$TMPDIR_TEST/solar-autopilot-monitor.py"
for optional in capability_effects.py resource_telemetry.py solar_db.py model_registry.py; do
  if [[ -f "$HARNESS_DIR_REAL/lib/$optional" ]]; then
    cp "$HARNESS_DIR_REAL/lib/$optional" "$TMPDIR_TEST/lib/$optional"
  fi
done
for optional_config in model-registry.json solar-user-config.json; do
  if [[ -f "$HARNESS_DIR_REAL/config/$optional_config" ]]; then
    cp "$HARNESS_DIR_REAL/config/$optional_config" "$TMPDIR_TEST/config/$optional_config"
  fi
done

HARNESS_DIR="$TMPDIR_TEST" SOLAR_HARNESS_SESSION="solar-harness-test" python3 - <<'PY'
import importlib.util
import os
import sys
from pathlib import Path

root = Path(os.environ["HARNESS_DIR"])
sys.path.insert(0, str(root / "lib"))

import graph_node_dispatcher as dispatcher

workers = dispatcher._discover_workers(dry_run=True)
assert workers, "dispatcher has no dry-run workers"
assert any("frontend" in w.get("skills", []) for w in workers), workers
assert any("observability" in w.get("capabilities", []) for w in workers), workers
assert any("documentation" in w.get("capabilities", []) for w in workers), workers

spec = importlib.util.spec_from_file_location("solar_autopilot_monitor", root / "solar-autopilot-monitor.py")
monitor = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(monitor)
monitor_workers = monitor.graph_workers()
assert monitor_workers, "autopilot has no workers"
assert any("frontend" in w.get("skills", []) for w in monitor_workers), monitor_workers
assert any("observability" in w.get("capabilities", []) for w in monitor_workers), monitor_workers
assert any("documentation" in w.get("capabilities", []) for w in monitor_workers), monitor_workers
PY

echo "PASS worker capability catalog covers frontend/observability"
