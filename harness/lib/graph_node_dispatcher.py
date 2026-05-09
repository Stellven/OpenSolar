#!/usr/bin/env python3
"""graph_node_dispatcher.py — dispatch queued DAG nodes to builder panes.

The graph scheduler decides which nodes are ready. This dispatcher consumes
`task_queue.py` items with intent `graph_node|node_id=...`, creates explicit
per-node dispatch files, binds/verifies pane leases, and sends the node task to
the assigned pane.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
SPRINTS_DIR = HARNESS_DIR / "sprints"
SESSION = os.environ.get("SOLAR_HARNESS_SESSION", "solar-harness")

sys.path.insert(0, str(HARNESS_DIR / "lib"))
from graph_scheduler import (  # noqa: E402
    load_graph,
    save_graph,
    enqueue_ready,
    set_node_status,
)
from pane_lease import acquire as acquire_lease, release as release_lease, read_lease  # noqa: E402
from task_queue import pop, enqueue  # noqa: E402


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _node_id_from_intent(intent: str) -> str:
    match = re.search(r"(?:^|\|)node_id=([^|]+)", intent or "")
    return match.group(1) if match else ""


def _scope_lines(values: Any) -> str:
    if not values:
        return "- N/A"
    if isinstance(values, str):
        values = [values]
    return "\n".join(f"- `{v}`" for v in values)


def _acceptance_lines(values: Any) -> str:
    if not values:
        return "- N/A"
    return "\n".join(f"- [ ] {v}" for v in values)


def _dispatch_file(sid: str, node_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", node_id).strip("-") or "node"
    return SPRINTS_DIR / f"{sid}.{safe}-dispatch.md"


def _mark_graph_node(graph_path: str, node_id: str, status: str,
                     pane: str | None = None, dispatch_id: str | None = None,
                     clear_assignment: bool = False) -> bool:
    try:
        graph = load_graph(graph_path)
        for node in graph.get("nodes", []):
            if node.get("id") != node_id:
                continue
            node["status"] = status
            node["updated_at"] = _utc_now()
            if clear_assignment:
                node.pop("assigned_to", None)
                node.pop("dispatch_id", None)
            else:
                if pane:
                    node["assigned_to"] = pane
                if dispatch_id:
                    node["dispatch_id"] = dispatch_id
            save_graph(graph_path, graph)
            return True
    except Exception:
        return False
    return False


def build_dispatch_text(payload: dict[str, Any], pane: str) -> str:
    node = payload.get("node") or {}
    sid = payload.get("sprint_id") or payload.get("sid") or ""
    node_id = node.get("id") or payload.get("node_id") or _node_id_from_intent(payload.get("intent", ""))
    graph_path = payload.get("graph") or str(SPRINTS_DIR / f"{sid}.task_graph.json")
    dispatch_id = payload.get("dispatch_id", "")

    return f"""# DAG Node Dispatch — {sid} / {node_id}

Sprint: `{sid}`
Node: `{node_id}`
Pane: `{pane}`
Dispatch ID: `{dispatch_id or "N/A"}`
Graph: `{graph_path}`

## Goal

{node.get("goal", "N/A")}

## Required Skills

{_scope_lines(node.get("required_skills"))}

## Read Scope

{_scope_lines(node.get("read_scope"))}

## Write Scope

{_scope_lines(node.get("write_scope"))}

## Acceptance

{_acceptance_lines(node.get("acceptance"))}

## Rules

- 只做本节点，不接手其他 DAG node。
- 只允许修改 `Write Scope` 里的文件/目录；需要扩大范围时写入 handoff 的 `Scope Change Request`，不要直接扩大。
- 不要把 parent sprint 标成 passed。
- 不要等待用户确认；遇到阻塞先写清楚证据和最小修复建议。

## Work Steps

1. 读取 graph 和合约：
   ```bash
   cat "{graph_path}"
   cat "{SPRINTS_DIR / f'{sid}.contract.md'}"
   ```

2. 按本节点 goal/acceptance 实现。

3. 运行本节点相关验证；把命令和结果写入 handoff。

4. 写节点 handoff：
   ```bash
   cat > "{SPRINTS_DIR / f'{sid}.{node_id}-handoff.md'}" <<'EOF'
   # Handoff — {sid} / {node_id}

   ## Summary

   ## Changed Files

   ## Verification Evidence

   ## Scope Compliance

   ## Known Risks

   ## Not Done
   EOF
   ```

5. 将节点状态置为 reviewing，等待 evaluator：
   ```bash
   /Users/sihaoli/.solar/harness/solar-harness.sh graph-scheduler mark --graph "{graph_path}" --node "{node_id}" --status reviewing --in-place
   ```
"""


def _pane_exists(pane: str) -> bool:
    try:
        return subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane, "#{pane_id}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).returncode == 0
    except Exception:
        return False


def _send_to_pane(pane: str, instruction_file: Path, dry_run: bool) -> bool:
    if dry_run:
        return True
    short_cmd = f"读取并执行 {instruction_file}"
    try:
        subprocess.run(["tmux", "send-keys", "-t", pane, "C-u"], timeout=2)
        subprocess.run(["tmux", "send-keys", "-t", pane, short_cmd], timeout=2)
        subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], timeout=2)
        subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], timeout=2)
        return True
    except Exception:
        return False


def _lease_active_for(pane: str, sid: str, dispatch_id: str) -> bool:
    lease = read_lease(pane)
    if not lease:
        return False
    return (
        lease.get("sprint_id", lease.get("sid")) == sid
        and lease.get("dispatch_id") == dispatch_id
        and lease.get("expires_at", "") > _utc_now()
    )


def _utc_now() -> str:
    import datetime

    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_lease(pane: str, sid: str, dispatch_id: str, ttl: int, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"acquired": True, "dry_run": True}
    if _lease_active_for(pane, sid, dispatch_id):
        return {"acquired": True, "existing": True}
    return acquire_lease(pane, sid, dispatch_id, ttl)


def dispatch_queue_item(item: dict[str, Any], dry_run: bool = False, ttl: int = 900) -> dict[str, Any]:
    payload = item.get("payload") or {}
    sid = payload.get("sprint_id") or item.get("sprint_id") or item.get("sid") or ""
    node = payload.get("node") or {}
    node_id = node.get("id") or _node_id_from_intent(item.get("intent", ""))
    assignment = payload.get("assignment") or {}
    pane = assignment.get("pane") or payload.get("pane") or ""
    graph_path = payload.get("graph") or str(SPRINTS_DIR / f"{sid}.task_graph.json")
    dispatch_id = payload.get("dispatch_id") or f"graph-{sid}-{node_id}"

    if not sid or not node_id:
        return {"ok": False, "reason": "invalid_graph_queue_item", "item": item}
    if not pane:
        return {"ok": False, "reason": "missing_assigned_pane", "node": node_id}
    if not dry_run and not _pane_exists(pane):
        enqueue(sid, item.get("intent", f"graph_node|node_id={node_id}"), item.get("priority", 80), payload)
        _mark_graph_node(graph_path, node_id, "pending", clear_assignment=True)
        return {"ok": False, "reason": "pane_missing", "node": node_id, "pane": pane, "requeued": True}

    lease_result = _ensure_lease(pane, sid, dispatch_id, ttl, dry_run)
    if not lease_result.get("acquired"):
        enqueue(sid, item.get("intent", f"graph_node|node_id={node_id}"), item.get("priority", 80), payload)
        _mark_graph_node(graph_path, node_id, "pending", clear_assignment=True)
        return {
            "ok": False,
            "reason": lease_result.get("reason", "lease_failed"),
            "node": node_id,
            "pane": pane,
            "lease": lease_result,
            "requeued": True,
        }

    instruction_file = _dispatch_file(sid, node_id)
    text_payload = dict(payload, dispatch_id=dispatch_id, sprint_id=sid)
    instruction_file.parent.mkdir(parents=True, exist_ok=True)
    instruction_file.write_text(build_dispatch_text(text_payload, pane), encoding="utf-8")

    sent = _send_to_pane(pane, instruction_file, dry_run)
    graph_updated = False
    if sent:
        try:
            graph = load_graph(graph_path)
            set_node_status(graph, node_id, "dispatched", pane=pane, dispatch_id=dispatch_id)
            save_graph(graph_path, graph)
            graph_updated = True
        except Exception:
            graph_updated = False
        return {
            "ok": True,
            "node": node_id,
            "pane": pane,
            "dispatch_id": dispatch_id,
            "instruction_file": str(instruction_file),
            "dry_run": dry_run,
            "graph_updated": graph_updated,
        }

    if not dry_run:
        release_lease(pane, dispatch_id, "graph_dispatch_send_failed")
    enqueue(sid, item.get("intent", f"graph_node|node_id={node_id}"), item.get("priority", 80), payload)
    _mark_graph_node(graph_path, node_id, "pending", clear_assignment=True)
    return {
        "ok": False,
        "reason": "send_failed",
        "node": node_id,
        "pane": pane,
        "instruction_file": str(instruction_file),
        "requeued": True,
    }


def drain_queue(sprint_id: str, dry_run: bool = False, max_items: int = 0, ttl: int = 900) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    processed = 0
    while True:
        if max_items and processed >= max_items:
            break
        item = pop(sprint_id)
        if item is None:
            break
        intent = item.get("intent", "")
        if "graph_node|" not in intent and not (item.get("payload") or {}).get("node"):
            # Preserve non-graph queue semantics by putting old items back.
            enqueue(sprint_id, intent, item.get("priority", 50), item.get("payload"))
            results.append({"ok": False, "reason": "non_graph_item_requeued", "intent": intent})
            break
        results.append(dispatch_queue_item(item, dry_run=dry_run, ttl=ttl))
        processed += 1
    return {
        "ok": all(r.get("ok") for r in results) if results else True,
        "sprint_id": sprint_id,
        "processed": processed,
        "results": results,
    }


def _discover_workers(dry_run: bool = False) -> list[dict[str, Any]]:
    if dry_run:
        return [
            {"pane": f"{SESSION}:0.2", "models": ["sonnet", "glm-5.1"], "skills": ["bash", "python", "typescript", "docs", "testing"]},
            {"pane": "solar-harness-lab:0.0", "models": ["sonnet", "glm-5.1"], "skills": ["bash", "python", "typescript", "docs", "testing"]},
            {"pane": "solar-harness-lab:0.1", "models": ["sonnet", "glm-5.1"], "skills": ["bash", "python", "typescript", "docs", "testing"]},
            {"pane": "solar-harness-lab:0.2", "models": ["sonnet", "glm-5.1"], "skills": ["bash", "python", "typescript", "docs", "testing"]},
        ]
    try:
        out = subprocess.check_output(
            ["tmux", "list-panes", "-a", "-F", "#{session_name}:#{window_index}.#{pane_index}"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode()
        panes = [p.strip() for p in out.splitlines() if p.strip()]
    except Exception:
        panes = []
    workers = []
    for pane in panes:
        if not (pane.startswith(f"{SESSION}:") or pane.startswith("solar-harness-lab:")):
            continue
        workers.append({
            "pane": pane,
            "models": ["sonnet", "glm-5.1", "deepseek"],
            "skills": ["bash", "python", "typescript", "docs", "testing"],
            "busy": bool(read_lease(pane)),
        })
    return workers


def dispatch_ready(graph_path: str, dry_run: bool = False, ttl: int = 900) -> dict[str, Any]:
    graph = load_graph(graph_path)
    sid = graph.get("sprint_id") or Path(graph_path).stem.replace(".task_graph", "")
    enqueue_result = enqueue_ready(graph, graph_path, _discover_workers(dry_run), max_parallel=8, lease=not dry_run, ttl=ttl)
    save_graph(graph_path, graph)
    drain_result = drain_queue(str(sid), dry_run=dry_run, max_items=len(enqueue_result.get("enqueued", [])), ttl=ttl)
    return {"ok": enqueue_result.get("ok") and drain_result.get("ok"), "enqueue": enqueue_result, "drain": drain_result}


def main() -> int:
    ap = argparse.ArgumentParser(prog="graph_node_dispatcher.py")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("drain-queue")
    p.add_argument("--sprint", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-items", type=int, default=0)
    p.add_argument("--ttl", type=int, default=900)

    p = sub.add_parser("dispatch-ready")
    p.add_argument("--graph", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ttl", type=int, default=900)

    args = ap.parse_args()
    if args.cmd == "drain-queue":
        result = drain_queue(args.sprint, args.dry_run, args.max_items, args.ttl)
    elif args.cmd == "dispatch-ready":
        result = dispatch_ready(args.graph, args.dry_run, args.ttl)
    else:
        ap.print_help()
        return 1

    print(_json(result))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
