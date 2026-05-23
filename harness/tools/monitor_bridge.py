#!/usr/bin/env python3
"""monitor_bridge.py — emit operator fleet status snapshot as JSON.

Reads the physical-operators registry, enriches each entry with
lifecycle state, resolved persona, heartbeat, and submit/daemon fields
from live runtime artifacts, then writes the snapshot to stdout or a
named output file.

Usage
-----
    python tools/monitor_bridge.py
    python tools/monitor_bridge.py --out /tmp/fleet.json
    python tools/monitor_bridge.py --operators path/to/physical-operators.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))

# Insert lib into sys.path so multi_task_status is importable regardless of cwd.
_LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from multi_task_status import (  # noqa: E402
    load_operator_fleet,
    PHYSICAL_OPERATORS_PATH,
    OPERATOR_PERSONAS_DIR,
    OPERATOR_STATUS_DIR,
    OPERATOR_LEASE_DIR,
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _count_claude_print_processes() -> int:
    """Return the number of observed ``claude --print`` / ``claude -p`` processes.

    Uses ``pgrep -af claude`` to enumerate live claude processes, then filters
    lines that contain a standalone ``--print`` or `` -p `` flag.  Returns -1
    when the OS command is unavailable (Windows/non-POSIX environments).
    """
    try:
        result = subprocess.run(
            ["pgrep", "-af", "claude"],
            capture_output=True, text=True, timeout=5,
        )
        count = 0
        for line in result.stdout.splitlines():
            tokens = line.split()
            if "--print" in tokens or "-p" in tokens:
                count += 1
        return count
    except (FileNotFoundError, OSError):
        return -1
    except Exception:
        return -1


def build_snapshot(
    operators_path: Path = PHYSICAL_OPERATORS_PATH,
    *,
    personas_dir: Path = OPERATOR_PERSONAS_DIR,
    status_dir: Path = OPERATOR_STATUS_DIR,
    lease_dir: Path = OPERATOR_LEASE_DIR,
) -> dict[str, Any]:
    """Build and return the operator fleet snapshot dict.

    Fields
    ------
    schema                   ``"solar.monitor_bridge.operator_fleet.v1"``
    observed_at              ISO-8601 UTC timestamp.
    operator_count           Total number of registered operators.
    submit_count             Operators with an active (non-expired) lease / submit_state.
    daemon_active_count      Operators whose daemon_state is not idle/N/A.
    lifecycle_counts         ``{state: count}`` breakdown.
    claude_print_process_count  Observed count of live ``claude --print`` OS processes
                             (from ``pgrep``).  -1 if pgrep is unavailable.
    operator_fleet           ``{operator_id: enriched_entry}`` for all operators.
                             Each entry includes operator_id, role, resolved_persona,
                             lifecycle_state, heartbeat_at, daemon_state,
                             current_task_id, submit_state, surface,
                             billing_surface, and billing_pool.
    """
    fleet = load_operator_fleet(
        operators_path,
        personas_dir=personas_dir,
        status_dir=status_dir,
        lease_dir=lease_dir,
    )

    submit_count = sum(
        1 for entry in fleet.values() if entry.get("submit_state") is not None
    )
    daemon_active_count = sum(
        1
        for entry in fleet.values()
        if entry.get("daemon_state") not in ("idle", "N/A", None, "")
    )

    lifecycle_counts: dict[str, int] = {}
    for entry in fleet.values():
        state = str(entry.get("lifecycle_state") or "N/A")
        lifecycle_counts[state] = lifecycle_counts.get(state, 0) + 1

    return {
        "schema": "solar.monitor_bridge.operator_fleet.v1",
        "observed_at": _now_iso(),
        "operator_count": len(fleet),
        "submit_count": submit_count,
        "daemon_active_count": daemon_active_count,
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "claude_print_process_count": _count_claude_print_processes(),
        "operator_fleet": dict(sorted(fleet.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="monitor_bridge",
        description=(
            "Emit operator fleet status with lifecycle state, resolved persona, "
            "heartbeat, and submit/daemon fields."
        ),
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help="Write JSON to this file instead of stdout.",
    )
    parser.add_argument(
        "--operators",
        metavar="PATH",
        default=str(PHYSICAL_OPERATORS_PATH),
        help="Path to physical-operators.json.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="One-shot mode (default behaviour; flag kept for scripting compatibility).",
    )
    args = parser.parse_args(argv)

    snapshot = build_snapshot(Path(args.operators))
    text = json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(out_path.suffix + f".{os.getpid()}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(out_path)
        print(f"[monitor_bridge] written: {out_path}", file=sys.stderr)
    else:
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
