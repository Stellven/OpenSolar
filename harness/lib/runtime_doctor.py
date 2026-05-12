"""Solar Harness — Runtime Doctor.

Diagnoses event log health, projection drift, duplicate commands,
stale activities, and pane/session ownership.

Usage::

    solar-harness runtime doctor --json
    python3 lib/runtime_doctor.py --json
"""
from __future__ import annotations

import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HARNESS_DIR = os.path.expanduser("~/.solar/harness")
SPRINTS_DIR = os.path.join(HARNESS_DIR, "sprints")
SESSIONS_DIR = os.path.join(HARNESS_DIR, "sessions")


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _age_minutes(ts_str: str) -> Optional[float]:
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        return (datetime.now(timezone.utc) - dt).total_seconds() / 60
    except ValueError:
        return None


# ------------------------------------------------------------------
# Individual checks
# ------------------------------------------------------------------

def _check_event_log_health(sprint_id: str) -> Dict[str, Any]:
    log_path = os.path.join(SESSIONS_DIR, sprint_id, "events.jsonl")
    if not os.path.exists(log_path):
        return {"ok": True, "warn": False, "message": "no event log (no events yet)", "event_count": 0}

    event_count = 0
    bad_lines = 0
    last_seq = 0
    seq_gaps: List[int] = []
    last_ts: Optional[str] = None

    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                event_count += 1
                seq = ev.get("seq", 0)
                if seq != last_seq + 1 and event_count > 1:
                    seq_gaps.append(seq)
                last_seq = seq
                ts = ev.get("ts")
                if ts:
                    last_ts = ts
            except json.JSONDecodeError:
                bad_lines += 1

    warn = bad_lines > 0 or bool(seq_gaps)
    message = "ok"
    if bad_lines:
        message = f"{bad_lines} corrupt line(s)"
    elif seq_gaps:
        message = f"seq gaps at {seq_gaps[:5]}"

    return {
        "ok": bad_lines == 0,
        "warn": warn,
        "message": message,
        "event_count": event_count,
        "bad_lines": bad_lines,
        "seq_gaps": seq_gaps[:10],
        "last_ts": last_ts,
    }


def _check_projection_drift(sprint_id: str) -> Dict[str, Any]:
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from projection_engine import ProjectionEngine
        engine = ProjectionEngine(sprint_id, harness_dir=HARNESS_DIR)
        state = engine.project()
        return {
            "ok": not state.drift_detected,
            "warn": state.drift_detected,
            "message": state.drift_reason if state.drift_detected else "no drift",
            "projected_status": state.status,
            "event_count": state.event_count,
        }
    except Exception as exc:
        return {"ok": False, "warn": True, "message": f"projection error: {exc}"}


def _check_duplicate_commands(sprint_id: str) -> Dict[str, Any]:
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from projection_engine import ProjectionEngine
        engine = ProjectionEngine(sprint_id, harness_dir=HARNESS_DIR)
        state = engine.project()
        dups = state.duplicate_commands
        return {
            "ok": len(dups) == 0,
            "warn": len(dups) > 0,
            "message": f"{len(dups)} duplicate(s): {dups[:5]}" if dups else "none",
            "duplicate_commands": dups,
        }
    except Exception as exc:
        return {"ok": False, "warn": True, "message": f"error: {exc}"}


def _check_stale_activities(sprint_id: str) -> Dict[str, Any]:
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from projection_engine import ProjectionEngine
        engine = ProjectionEngine(sprint_id, harness_dir=HARNESS_DIR)
        state = engine.project()
        stale = state.stale_activities
        return {
            "ok": len(stale) == 0,
            "warn": len(stale) > 0,
            "message": f"{len(stale)} stale: {stale[:5]}" if stale else "none",
            "stale_activities": stale,
        }
    except Exception as exc:
        return {"ok": False, "warn": True, "message": f"error: {exc}"}


def _check_status_json(sprint_id: str) -> Dict[str, Any]:
    path = os.path.join(SPRINTS_DIR, f"{sprint_id}.status.json")
    if not os.path.exists(path):
        return {"ok": False, "warn": True, "message": "status.json missing"}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        age = None
        ts = data.get("updated_at") or data.get("projected_at")
        if ts:
            age = _age_minutes(ts)
        return {
            "ok": True,
            "warn": False,
            "message": "ok",
            "status": data.get("status"),
            "age_minutes": round(age, 1) if age is not None else None,
        }
    except Exception as exc:
        return {"ok": False, "warn": True, "message": f"corrupt: {exc}"}


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def doctor_sprint(
    sprint_id: str,
    *,
    stale_threshold_minutes: int = 60,
) -> Dict[str, Any]:
    """Run all checks for one sprint and return a report dict."""
    # Default adoption path: every doctor pass first mirrors legacy sprint
    # artifacts into session-log v2. This makes doctor a runtime gate, not a
    # passive linter that can silently ignore old-only state.
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from runtime_bridge import adopt_sprint
        adopt_sprint(sprint_id, harness_dir=Path(HARNESS_DIR))
    except Exception:
        # Individual checks below will surface event/projection issues. Doctor
        # must remain fail-open enough to report corrupt legacy state.
        pass

    checks = {
        "event_log_health": _check_event_log_health(sprint_id),
        "projection_drift":  _check_projection_drift(sprint_id),
        "duplicate_commands": _check_duplicate_commands(sprint_id),
        "stale_activities":  _check_stale_activities(sprint_id),
        "status_json":       _check_status_json(sprint_id),
    }

    all_ok  = all(c.get("ok",   True) for c in checks.values())
    any_warn = any(c.get("warn", False) for c in checks.values())

    return {
        "sprint_id": sprint_id,
        "ok": all_ok,
        "warn": any_warn and all_ok,
        "ts": _now_ts(),
        "checks": checks,
    }


def doctor_all(*, active_only: bool = True) -> Dict[str, Any]:
    """Scan all sprints in SPRINTS_DIR and run checks."""
    pattern = os.path.join(SPRINTS_DIR, "*.status.json")
    sprint_ids: List[str] = []
    for p in sorted(glob.glob(pattern)):
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
            sid = data.get("sprint_id") or data.get("id") or data.get("sid")
            if not sid:
                continue
            if active_only:
                status = data.get("status", "")
                if status in ("passed", "cancelled", "finalized"):
                    continue
            sprint_ids.append(sid)
        except Exception:
            continue

    reports = [doctor_sprint(sid) for sid in sprint_ids]
    overall_ok = all(r["ok"] for r in reports)
    any_warn = any(r.get("warn") for r in reports)

    return {
        "ok": overall_ok,
        "warn": any_warn and overall_ok,
        "ts": _now_ts(),
        "sprint_count": len(reports),
        "sprints": reports,
    }


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="solar-harness runtime doctor — event log health report"
    )
    parser.add_argument("sprint_id", nargs="?", default=None,
                        help="Sprint ID (default: all active sprints)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--all", action="store_true", help="Include terminal sprints")
    args = parser.parse_args()

    if args.sprint_id:
        report = doctor_sprint(args.sprint_id)
    else:
        report = doctor_all(active_only=not args.all)

    if args.json:
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["ok"] else 1)

    # Human-readable output
    ok_sym = "✅" if report["ok"] else "❌"
    warn_sym = "⚠" if report.get("warn") else ""
    print(f"{ok_sym} {warn_sym} runtime doctor  {report['ts']}")

    if "sprints" in report:
        for r in report["sprints"]:
            _print_sprint_report(r)
    else:
        _print_sprint_report(report)

    sys.exit(0 if report["ok"] else 1)


def _print_sprint_report(r: Dict[str, Any]) -> None:
    sym = "✅" if r["ok"] else "❌"
    print(f"\n{sym} {r['sprint_id']}")
    for name, check in r.get("checks", {}).items():
        c_sym = "✅" if check.get("ok") else ("⚠" if check.get("warn") else "❌")
        print(f"  {c_sym} {name}: {check.get('message', '')}")


if __name__ == "__main__":
    main()
