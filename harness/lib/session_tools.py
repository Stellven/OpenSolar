#!/usr/bin/env python3
"""Session log tools for Solar-Harness runtime.

These commands make the append-only log operationally useful:

  replay    materialize a session into status/context-friendly facts
  diff      compare two sessions or the same session across harness dirs
  evaluate  run a log-native evaluator without relying on final artifacts

The tools intentionally consume `sessions/<session_id>/events.jsonl` as the
source of truth.  Files such as status.json are projection caches only.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))

from projection_engine import ProjectionEngine  # type: ignore
from session_log import SessionLog  # type: ignore


HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", str(Path.home() / ".solar" / "harness")))
REPORTS_DIR = HARNESS_DIR / "reports"


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_events(session_id: str, harness_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    path = harness_dir / "sessions" / session_id / "events.jsonl"
    events: List[Dict[str, Any]] = []
    bad_lines = 0
    seq_gaps: List[int] = []
    last_seq = 0
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    bad_lines += 1
                    continue
                seq = int(ev.get("seq") or 0)
                if events and seq != last_seq + 1:
                    seq_gaps.append(seq)
                last_seq = seq
                events.append(ev)
    meta = {
        "path": str(path),
        "exists": path.exists(),
        "event_count": len(events),
        "bad_lines": bad_lines,
        "seq_gaps": seq_gaps,
    }
    return events, meta


def project_session(session_id: str, harness_dir: Path) -> Dict[str, Any]:
    try:
        state = ProjectionEngine(session_id, harness_dir=str(harness_dir)).project()
        return {
            "ok": True,
            "sprint_id": state.sprint_id,
            "status": state.status,
            "round": state.round,
            "event_count": state.event_count,
            "last_event_ts": state.last_event_ts,
            "drift_detected": state.drift_detected,
            "drift_reason": state.drift_reason,
            "duplicate_commands": state.duplicate_commands,
            "stale_activities": state.stale_activities,
            "activities": [
                {
                    "activity_id": a.activity_id,
                    "status": a.status,
                    "last_event_type": a.last_event_type,
                    "last_event_ts": a.last_event_ts,
                    "error_count": a.error_count,
                    "retry_count": a.retry_count,
                }
                for a in state.activities
            ],
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def event_type_counts(events: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counter: Dict[str, int] = collections.Counter(str(ev.get("type") or "") for ev in events)
    return dict(sorted(counter.items()))


def stable_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Return event content suitable for semantic diff.

    event_id and ts are intentionally excluded so two harnesses can be compared
    without false divergence from append-time metadata.
    """
    return {
        "seq": ev.get("seq"),
        "session_id": ev.get("session_id"),
        "type": ev.get("type"),
        "actor": ev.get("actor"),
        "source": ev.get("source"),
        "sprint_id": ev.get("sprint_id"),
        "activity_id": ev.get("activity_id"),
        "correlation_id": ev.get("correlation_id"),
        "causation_id": ev.get("causation_id"),
        "idempotency_key": ev.get("idempotency_key"),
        "payload": ev.get("payload") or {},
    }


def event_fingerprint(ev: Dict[str, Any]) -> str:
    text = json.dumps(stable_event(ev), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def first_divergence(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> Dict[str, Any]:
    max_len = max(len(a), len(b))
    for idx in range(max_len):
        if idx >= len(a):
            return {"index": idx, "reason": "missing_in_a", "a": None, "b": summarize_event(b[idx])}
        if idx >= len(b):
            return {"index": idx, "reason": "missing_in_b", "a": summarize_event(a[idx]), "b": None}
        if stable_event(a[idx]) != stable_event(b[idx]):
            return {
                "index": idx,
                "reason": "event_content_differs",
                "a": summarize_event(a[idx]),
                "b": summarize_event(b[idx]),
            }
    return {"index": None, "reason": "none", "a": None, "b": None}


def summarize_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
    return {
        "seq": ev.get("seq"),
        "type": ev.get("type"),
        "actor": ev.get("actor"),
        "activity_id": ev.get("activity_id"),
        "status": payload.get("status") or payload.get("to") or "",
        "error": payload.get("error") or "",
    }


def pending_model_calls(events: Iterable[Dict[str, Any]]) -> List[str]:
    requested: Dict[str, Dict[str, Any]] = {}
    terminal = set()
    for ev in events:
        etype = ev.get("type")
        payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        dispatch_id = str(payload.get("dispatch_id") or ev.get("activity_id") or "")
        if not dispatch_id:
            continue
        if etype == "model_call_requested":
            requested[dispatch_id] = ev
        elif etype in {"model_call_succeeded", "model_call_failed"}:
            terminal.add(dispatch_id)
    return sorted(k for k in requested if k not in terminal)


def replay_payload(session_id: str, harness_dir: Path, include_events: bool = False) -> Dict[str, Any]:
    events, meta = load_events(session_id, harness_dir)
    payload = {
        "ok": meta["exists"] and meta["bad_lines"] == 0,
        "generated_at": now_ts(),
        "session_id": session_id,
        "harness_dir": str(harness_dir),
        "log": meta,
        "event_type_counts": event_type_counts(events),
        "projection": project_session(session_id, harness_dir),
        "pending_model_calls": pending_model_calls(events),
        "event_summaries": [summarize_event(ev) for ev in events[-30:]],
        "source_of_truth": "sessions/<session_id>/events.jsonl",
        "projection_note": "status.json/UI/context are projections, not the source of truth",
    }
    if include_events:
        payload["events"] = events
    return payload


def diff_payload(session_a: str, session_b: str, harness_a: Path, harness_b: Path) -> Dict[str, Any]:
    events_a, meta_a = load_events(session_a, harness_a)
    events_b, meta_b = load_events(session_b, harness_b)
    fp_a = {event_fingerprint(ev) for ev in events_a}
    fp_b = {event_fingerprint(ev) for ev in events_b}
    proj_a = project_session(session_a, harness_a)
    proj_b = project_session(session_b, harness_b)
    diff = {
        "ok": meta_a["bad_lines"] == 0 and meta_b["bad_lines"] == 0,
        "generated_at": now_ts(),
        "source_of_truth": "append-only session event logs",
        "same_session_cross_harness": session_a == session_b and harness_a.resolve() != harness_b.resolve(),
        "a": {
            "session_id": session_a,
            "harness_dir": str(harness_a),
            "log": meta_a,
            "event_type_counts": event_type_counts(events_a),
            "projection": proj_a,
        },
        "b": {
            "session_id": session_b,
            "harness_dir": str(harness_b),
            "log": meta_b,
            "event_type_counts": event_type_counts(events_b),
            "projection": proj_b,
        },
        "summary": {
            "event_count_delta": len(events_a) - len(events_b),
            "only_in_a": len(fp_a - fp_b),
            "only_in_b": len(fp_b - fp_a),
            "projection_status_equal": proj_a.get("status") == proj_b.get("status"),
            "first_divergence": first_divergence(events_a, events_b),
        },
    }
    diff["ok"] = bool(diff["ok"] and diff["summary"]["only_in_a"] == 0 and diff["summary"]["only_in_b"] == 0)
    return diff


def evaluate_payload(session_id: str, harness_dir: Path) -> Dict[str, Any]:
    events, meta = load_events(session_id, harness_dir)
    projection = project_session(session_id, harness_dir)
    event_counts = event_type_counts(events)
    model_pending = pending_model_calls(events)
    errors: List[str] = []
    warnings: List[str] = []

    if not meta["exists"]:
        errors.append("session_log_missing")
    if meta["bad_lines"]:
        errors.append("session_log_corrupt")
    if meta["seq_gaps"]:
        errors.append("session_seq_gap")
    if not events:
        warnings.append("session_has_no_events")
    if not projection.get("ok"):
        errors.append("projection_failed")
    if projection.get("drift_detected"):
        warnings.append("projection_drift")
    if projection.get("duplicate_commands"):
        errors.append("duplicate_commands")
    if projection.get("stale_activities"):
        warnings.append("stale_activities")
    if model_pending:
        warnings.append("pending_model_calls")

    status = str(projection.get("status") or "unknown")
    if status in {"error", "failed", "failed_review", "cancelled"}:
        errors.append("terminal_failure_status")
    elif status not in {"passed", "reviewing"}:
        warnings.append("non_terminal_status")

    verdict = "fail" if errors else ("warn" if warnings else "pass")
    return {
        "ok": verdict != "fail",
        "generated_at": now_ts(),
        "session_id": session_id,
        "harness_dir": str(harness_dir),
        "verdict": verdict,
        "log_native": True,
        "artifact_native": False,
        "private_reasoning_visible": False,
        "source_of_truth": str(Path(meta["path"])),
        "status": status,
        "event_count": meta["event_count"],
        "event_type_counts": event_counts,
        "projection": projection,
        "pending_model_calls": model_pending,
        "errors": errors,
        "warnings": warnings,
        "note": "Evaluator consumed session events/projection only; final files are not required for this verdict.",
    }


def render_markdown(payload: Dict[str, Any], title: str) -> str:
    rows = []
    if "summary" in payload:
        summary = payload["summary"]
        rows = [
            ("event_count_delta", summary.get("event_count_delta")),
            ("only_in_a", summary.get("only_in_a")),
            ("only_in_b", summary.get("only_in_b")),
            ("projection_status_equal", summary.get("projection_status_equal")),
            ("first_divergence", (summary.get("first_divergence") or {}).get("reason")),
        ]
    elif "verdict" in payload:
        rows = [
            ("verdict", payload.get("verdict")),
            ("status", payload.get("status")),
            ("event_count", payload.get("event_count")),
            ("errors", ", ".join(payload.get("errors") or []) or "none"),
            ("warnings", ", ".join(payload.get("warnings") or []) or "none"),
        ]
    else:
        rows = [
            ("session_id", payload.get("session_id")),
            ("event_count", (payload.get("log") or {}).get("event_count")),
            ("projection_status", (payload.get("projection") or {}).get("status")),
            ("pending_model_calls", len(payload.get("pending_model_calls") or [])),
        ]
    table = ["| Key | Value |", "| --- | --- |"]
    table.extend(f"| {k} | `{v}` |" for k, v in rows)
    return "\n".join([
        f"# {title}",
        "",
        f"- Generated: `{payload.get('generated_at')}`",
        f"- Source of truth: `{payload.get('source_of_truth')}`",
        "",
        *table,
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2)[:20000],
        "```",
        "",
    ])


def print_payload(payload: Dict[str, Any], as_json: bool, markdown_title: str = "") -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(render_markdown(payload, markdown_title or "Solar Session Report"))


def cmd_replay(args: argparse.Namespace) -> int:
    payload = replay_payload(args.session_id, Path(args.harness_dir), include_events=args.include_events)
    if args.out:
        write_json(Path(args.out), payload)
    print_payload(payload, args.json, f"Solar Session Replay: {args.session_id}")
    return 0 if payload["ok"] else 1


def cmd_diff(args: argparse.Namespace) -> int:
    payload = diff_payload(args.session_a, args.session_b, Path(args.harness_a), Path(args.harness_b))
    if args.out:
        write_json(Path(args.out), payload)
    print_payload(payload, args.json, "Solar Session Diff")
    return 0 if payload["ok"] else 1


def cmd_evaluate(args: argparse.Namespace) -> int:
    payload = evaluate_payload(args.session_id, Path(args.harness_dir))
    if args.out:
        write_json(Path(args.out), payload)
    print_payload(payload, args.json, f"Solar Log-Native Evaluation: {args.session_id}")
    return 0 if payload["ok"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="solar-harness session", description="Session log replay/diff/evaluation tools")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("replay", help="Replay one append-only session log")
    p.add_argument("session_id")
    p.add_argument("--harness-dir", default=str(HARNESS_DIR))
    p.add_argument("--include-events", action="store_true")
    p.add_argument("--out", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("diff", help="Diff two sessions or one session across harness dirs")
    p.add_argument("session_a")
    p.add_argument("session_b")
    p.add_argument("--harness-a", default=str(HARNESS_DIR))
    p.add_argument("--harness-b", default=str(HARNESS_DIR))
    p.add_argument("--out", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("evaluate", aliases=["eval"], help="Evaluate directly from session log")
    p.add_argument("session_id")
    p.add_argument("--harness-dir", default=str(HARNESS_DIR))
    p.add_argument("--out", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_evaluate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
