#!/usr/bin/env python3
"""Small event bridge for remote solar-harness sprint monitoring.

The bridge is intentionally file based: it runs on the remote executor host,
scans a task graph on a short interval, and appends compact JSON events when
state changes. A local Codex session can pull only the latest JSON/event tail
over SSH without keeping a long blocking monitor in the foreground.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def graph_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = graph.get("nodes") or []
    if isinstance(nodes, dict):
        return [node for node in nodes.values() if isinstance(node, dict)]
    if isinstance(nodes, list):
        return [node for node in nodes if isinstance(node, dict)]
    return []


def node_status(node: dict[str, Any]) -> str:
    raw = node.get("status")
    if raw:
        return str(raw)
    meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
    return str(meta.get("status") or "pending")


def safe_tail(path: Path, limit: int = 1200) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-limit:]
    except Exception:
        return ""


def latest_task_for_node(run_dir: Path, sprint_id: str, node_id: str) -> dict[str, Any] | None:
    best: tuple[float, dict[str, Any]] | None = None
    for status_path in run_dir.glob("*/status.json"):
        data = load_json(status_path)
        if data.get("sprint_id") != sprint_id or data.get("node_id") != node_id:
            continue
        try:
            mtime = status_path.stat().st_mtime
        except Exception:
            mtime = 0
        data["_task_dir"] = str(status_path.parent)
        data["_output_tail"] = safe_tail(status_path.parent / "output.log", 1200)
        if best is None or mtime > best[0]:
            best = (mtime, data)
    return best[1] if best else None


def tmux_window_exists(session: str, window: str) -> bool:
    if not window:
        return False
    try:
        return subprocess.run(
            ["tmux", "has-session", "-t", f"{session}:{window}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).returncode == 0
    except Exception:
        return False


def summarize(graph_path: Path, run_dir: Path, stale_sec: int) -> dict[str, Any]:
    graph = load_json(graph_path)
    sprint_id = str(graph.get("sprint_id") or graph_path.name.replace(".task_graph.json", ""))
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    warnings: list[str] = []
    now_ts = time.time()

    for node in graph_nodes(graph):
        node_id = str(node.get("id") or "N/A")
        status = node_status(node)
        counts[status] = counts.get(status, 0) + 1
        task = latest_task_for_node(run_dir, sprint_id, node_id)
        active_task = str((task or {}).get("id") or "N/A")
        updated_at = str((task or {}).get("updated_at") or node.get("updated_at") or "N/A")
        blocker = "N/A"
        next_action = "wait"
        task_status = str((task or {}).get("status") or "N/A")
        output_tail = str((task or {}).get("_output_tail") or "")
        window = str((task or {}).get("window") or "")
        tmux_live = tmux_window_exists(str((task or {}).get("session") or "solar-harness-multi-task"), window)
        age_s = None
        try:
            age_s = int(now_ts - dt.datetime.fromisoformat(updated_at.replace("Z", "+00:00")).timestamp())
        except Exception:
            pass

        if status in {"dispatched", "running"} and age_s is not None and age_s > stale_sec:
            blocker = f"stale>{stale_sec}s"
            next_action = "diagnose"
        elif status in {"dispatched", "running"} and task and not tmux_live:
            blocker = "tmux_window_missing"
            next_action = "safe-align-or-restart"
        elif status == "reviewing":
            handoff = Path(str((task or {}).get("handoff") or graph_path.with_name(f"{sprint_id}.{node_id}-handoff.md")))
            if handoff.exists() and handoff.stat().st_size > 200:
                next_action = "can-mark-passed"
            else:
                blocker = "handoff_missing_or_small"
                next_action = "inspect"
        elif status == "passed":
            next_action = "done"

        if blocker != "N/A":
            warnings.append(f"{node_id}:{blocker}")

        rows.append({
            "node": node_id,
            "status": status,
            "task_status": task_status,
            "active_task": active_task,
            "updated_at": updated_at,
            "blocker": blocker,
            "next_action": next_action,
            "tmux_live": tmux_live,
            "output_tail_hash": hashlib.sha256(output_tail.encode("utf-8")).hexdigest()[:12] if output_tail else "N/A",
        })

    return {
        "schema": "solar.monitor_bridge.v1",
        "sprint_id": sprint_id,
        "graph": str(graph_path),
        "observed_at": now_iso(),
        "counts": counts,
        "warnings": warnings,
        "nodes": rows,
        "all_passed": bool(rows) and all(r["status"] == "passed" for r in rows),
    }


def digest(snapshot: dict[str, Any]) -> str:
    compact = {
        "counts": snapshot.get("counts"),
        "warnings": snapshot.get("warnings"),
        "nodes": [
            {
                "node": n.get("node"),
                "status": n.get("status"),
                "task_status": n.get("task_status"),
                "active_task": n.get("active_task"),
                "blocker": n.get("blocker"),
                "next_action": n.get("next_action"),
                "tail": n.get("output_tail_hash"),
            }
            for n in snapshot.get("nodes", [])
        ],
    }
    return hashlib.sha256(json.dumps(compact, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def append_event(events_path: Path, event: dict[str, Any]) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def write_latest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(args: argparse.Namespace) -> int:
    graph = Path(args.graph).expanduser()
    run_dir = Path(args.run_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    latest_path = out_dir / f"{args.name}.latest.json"
    events_path = out_dir / f"{args.name}.events.jsonl"
    state_path = out_dir / f"{args.name}.state.json"
    previous = load_json(state_path).get("digest")

    while True:
        snapshot = summarize(graph, run_dir, int(args.stale_sec))
        current = digest(snapshot)
        snapshot["digest"] = current
        snapshot["events_path"] = str(events_path)
        write_latest(latest_path, snapshot)
        if current != previous:
            append_event(events_path, {"ts": now_iso(), "type": "snapshot_changed", "digest": current, "snapshot": snapshot})
            write_latest(state_path, {"digest": current, "updated_at": now_iso()})
            previous = current
        if args.once or snapshot.get("all_passed"):
            return 0
        time.sleep(float(args.interval))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--run-dir", default=str(Path.home() / ".solar" / "harness" / "run" / "multi-task"))
    parser.add_argument("--out-dir", default=str(Path.home() / ".solar" / "harness" / "run" / "monitor-bridge"))
    parser.add_argument("--interval", type=float, default=15)
    parser.add_argument("--stale-sec", type=int, default=300)
    parser.add_argument("--once", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
