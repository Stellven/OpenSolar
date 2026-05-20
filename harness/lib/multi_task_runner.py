#!/usr/bin/env python3
"""tmux-backed DAG worker pool for Solar Harness multi-task execution."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
SPRINTS_DIR = Path(os.environ.get("HARNESS_SPRINTS_DIR", HARNESS_DIR / "sprints"))
RUN_DIR = HARNESS_DIR / "run" / "multi-task"
SESSION = os.environ.get("SOLAR_HARNESS_MULTI_TASK_SESSION", "solar-harness-multi-task")
DEFAULT_MAX_WORKERS = int(os.environ.get("SOLAR_MULTI_TASK_MAX_WORKERS", "2") or "2")
DEFAULT_INTERVAL = int(os.environ.get("SOLAR_MULTI_TASK_INTERVAL_SEC", "15") or "15")
DEFAULT_COOLDOWN = int(os.environ.get("SOLAR_MULTI_TASK_LAUNCH_COOLDOWN_SEC", "30") or "30")
DEFAULT_MEMORY_RESERVE_GB = float(os.environ.get("SOLAR_MULTI_TASK_MEMORY_RESERVE_GB", "4") or "4")
DEFAULT_QUOTA_BACKOFF = int(os.environ.get("SOLAR_MULTI_TASK_QUOTA_BACKOFF_SEC", "900") or "900")

sys.path.insert(0, str(HARNESS_DIR / "lib"))
from graph_scheduler import (  # noqa: E402
    load_graph,
    node_status,
    ready_nodes,
    save_graph,
    set_node_status,
    write_scope_conflict,
)

ACTIVE_TASK_STATUSES = {"queued", "dispatched", "running"}
TERMINAL_TASK_STATUSES = {"completed", "failed", "failed_missing_handoff", "cancelled"}
QUOTA_RE = re.compile(
    r"rate[- ]?limit|quota|you(?:'|’)ve hit your limit|resets\s+\d|"
    r"api usage billing|429|upgrade your plan",
    re.I,
)


def now_iso() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def task_id(sid: str, node_id: str) -> str:
    stamp = _dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    safe_sid = re.sub(r"[^A-Za-z0-9_.-]+", "-", sid)[:36] or "sprint"
    safe_node = re.sub(r"[^A-Za-z0-9_.-]+", "-", node_id)[:24] or "node"
    return f"mt-{stamp}-{safe_sid}-{safe_node}"


def short_window(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-")
    return (value or "multi-task")[:48]


def status_path(task_dir: Path) -> Path:
    return task_dir / "status.json"


def read_task_status(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_task_rows() -> list[dict[str, Any]]:
    if not RUN_DIR.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(RUN_DIR.glob("*/status.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        row = read_task_status(path)
        if row:
            rows.append(row)
    return rows


def active_tasks() -> list[dict[str, Any]]:
    return [row for row in list_task_rows() if str(row.get("status", "")).lower() in ACTIVE_TASK_STATUSES]


def last_launch_at() -> float | None:
    path = RUN_DIR / ".last-launch"
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def set_last_launch() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / ".last-launch").write_text(str(time.time()), encoding="utf-8")


def free_memory_gb() -> float | None:
    if sys.platform == "darwin" and shutil.which("vm_stat"):
        try:
            out = subprocess.check_output(["vm_stat"], text=True, stderr=subprocess.DEVNULL)
            page_size = 4096
            free_pages = 0
            for line in out.splitlines():
                if "page size of" in line:
                    m = re.search(r"page size of (\d+) bytes", line)
                    if m:
                        page_size = int(m.group(1))
                if line.startswith(("Pages free:", "Pages inactive:", "Pages speculative:")):
                    free_pages += int(re.sub(r"[^0-9]", "", line.split(":", 1)[1]) or "0")
            if free_pages:
                return free_pages * page_size / 1024 / 1024 / 1024
        except Exception:
            return None
    return None


def quota_guard(backoff_seconds: int) -> dict[str, Any]:
    cutoff = time.time() - backoff_seconds
    hits: list[dict[str, Any]] = []
    if RUN_DIR.exists():
        for log in RUN_DIR.glob("*/output.log"):
            try:
                if log.stat().st_mtime < cutoff:
                    continue
                tail = log.read_text(encoding="utf-8", errors="replace")[-8000:]
            except Exception:
                continue
            if QUOTA_RE.search(tail):
                hits.append({"task": log.parent.name, "log": str(log)})
    if hits:
        return {"ok": False, "reason": "recent_quota_or_rate_limit", "hits": hits[:5]}
    return {"ok": True, "reason": "no_recent_quota_hit"}


def launch_guard(max_workers: int, reserve_gb: float, cooldown: int, quota_backoff: int) -> dict[str, Any]:
    active = active_tasks()
    if len(active) >= max_workers:
        return {"ok": False, "reason": "worker_pool_full", "active": len(active), "max_workers": max_workers}

    mem = free_memory_gb()
    if mem is not None and mem < reserve_gb:
        return {"ok": False, "reason": "low_memory", "free_gb": round(mem, 2), "reserve_gb": reserve_gb}

    last = last_launch_at()
    if last is not None:
        elapsed = time.time() - last
        if elapsed < cooldown:
            return {"ok": False, "reason": "launch_cooldown", "wait_s": int(cooldown - elapsed)}

    quota = quota_guard(quota_backoff)
    if not quota.get("ok"):
        return quota

    return {
        "ok": True,
        "reason": "ready",
        "active": len(active),
        "max_workers": max_workers,
        "free_gb": None if mem is None else round(mem, 2),
    }


def graph_files(explicit: list[str]) -> list[Path]:
    if explicit:
        return [Path(item).expanduser() for item in explicit]
    return sorted(SPRINTS_DIR.glob("*.task_graph.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def sprint_id_for(graph: dict[str, Any], graph_path: Path) -> str:
    return str(graph.get("sprint_id") or graph_path.name.replace(".task_graph.json", ""))


def status_summary_for_graph(graph_path: Path) -> dict[str, Any]:
    try:
        graph = load_graph(graph_path)
        nodes = graph.get("nodes") or []
        counts: dict[str, int] = {}
        for node in nodes:
            nid = str(node.get("id") or "")
            st = node_status(graph, nid) if nid else "invalid"
            counts[st] = counts.get(st, 0) + 1
        ready = [str(n.get("id") or "") for n in ready_nodes(graph)]
        return {"graph": str(graph_path), "sid": sprint_id_for(graph, graph_path), "ok": True, "counts": counts, "ready": ready}
    except Exception as exc:
        return {"graph": str(graph_path), "sid": graph_path.stem, "ok": False, "error": str(exc), "counts": {}, "ready": []}


def scope_conflicts_with_active(node: dict[str, Any]) -> bool:
    for task in active_tasks():
        scopes = task.get("write_scope")
        if not scopes:
            continue
        other = {"id": task.get("node_id"), "write_scope": scopes}
        try:
            if write_scope_conflict(node, other):
                return True
        except Exception:
            return True
    return False


def build_dispatch_text(graph_path: Path, graph: dict[str, Any], node: dict[str, Any], dispatch_id: str, window: str) -> str:
    sid = sprint_id_for(graph, graph_path)
    node_id = str(node.get("id") or "")
    handoff = SPRINTS_DIR / f"{sid}.{node_id}-handoff.md"
    harness = HARNESS_DIR / "solar-harness.sh"

    def lines(value: Any) -> str:
        if value is None or value == "":
            return "- N/A"
        if isinstance(value, str):
            return f"- {value}"
        if isinstance(value, list):
            return "\n".join(f"- {item}" for item in value) if value else "- N/A"
        if isinstance(value, dict):
            return "\n".join(f"- {k}: {v}" for k, v in value.items()) if value else "- N/A"
        return f"- {value}"

    return f"""<!-- SOLAR_MULTI_TASK_DISPATCH -->
# Solar Harness Multi-Task DAG Dispatch

Sprint: `{sid}`
Node: `{node_id}`
Dispatch ID: `{dispatch_id}`
Execution plane: `tmux:{SESSION}:{window}`
Graph: `{graph_path}`
Handoff: `{handoff}`

## Definition of Done

任务没有完成，除非同时满足：

1. 真实调用链接入：新增/修改功能必须接入真实调用链。
2. 禁止硬编码：不得硬编码业务数据、路径、token、测试数据、feature flag。
3. 测试必须运行：不能运行时写清原因和风险。
4. 执行证据齐全：列出实际命令和结果摘要。
5. Diff 自审：列出每个改动文件的目的。
6. 禁用乐观词：存在未完成项时禁止报喜。
7. 结构化收尾：已完成 / 已验证 / 未验证 / 风险 / 后续待办。

## Goal

{node.get("goal") or node.get("title") or "N/A"}

## Read Scope

{lines(node.get("read_scope"))}

## Write Scope

{lines(node.get("write_scope"))}

## Required Skills

{lines(node.get("required_skills"))}

## Required Capabilities

{lines(node.get("required_capabilities"))}

## Acceptance

{lines(node.get("acceptance"))}

## Rules

- 只执行本节点，不抢其他 DAG node。
- 只修改 Write Scope；需要扩大范围时在 handoff 里写 Scope Change Request。
- 不要把 parent sprint 标成 passed。
- 交付必须写 handoff。没有 handoff，后台 runner 会把本节点判为失败。

## Required Closeout

1. 写入 handoff：

```bash
cat > "{handoff}" <<'EOF'
# Handoff — {sid} / {node_id}

## 已完成

## 已验证

## 未验证

## 风险

## 后续待办
EOF
```

2. 将节点标记为 reviewing：

```bash
"{harness}" graph-scheduler mark --graph "{graph_path}" --node "{node_id}" --status reviewing --in-place
```
"""


def runner_script(task_dir: Path, payload: dict[str, Any]) -> Path:
    runner = task_dir / "runner.sh"
    dispatch_file = task_dir / "dispatch.md"
    status_file = task_dir / "status.json"
    harness = HARNESS_DIR / "solar-harness.sh"
    graph = Path(str(payload["graph"]))
    handoff = Path(str(payload["handoff"]))
    node_id = str(payload["node_id"])
    sid = str(payload["sprint_id"])
    agent_cmd = os.environ.get("SOLAR_MULTI_TASK_AGENT_CMD", "").strip()
    script = f"""#!/usr/bin/env bash
set -u
TASK_DIR={shlex.quote(str(task_dir))}
STATUS_FILE={shlex.quote(str(status_file))}
DISPATCH_FILE={shlex.quote(str(dispatch_file))}
OUTPUT_LOG="$TASK_DIR/output.log"
HARNESS_DIR={shlex.quote(str(HARNESS_DIR))}
SPRINTS_DIR={shlex.quote(str(SPRINTS_DIR))}
GRAPH={shlex.quote(str(graph))}
NODE_ID={shlex.quote(node_id)}
SID={shlex.quote(sid)}
HANDOFF={shlex.quote(str(handoff))}
HARNESS={shlex.quote(str(harness))}

write_status() {{
  local status="$1" exit_code="${{2:-}}"
  python3 - "$STATUS_FILE" "$status" "$exit_code" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
data = {{}}
if p.exists():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {{}}
data["status"] = sys.argv[2]
data["exit_code"] = None if sys.argv[3] == "" else int(sys.argv[3])
data["updated_at"] = sys.argv[4]
data.setdefault("created_at", sys.argv[4])
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
PY
}}

mkdir -p "$TASK_DIR"
write_status running

if [[ "${{SOLAR_MULTI_TASK_SANITIZE_ENV:-1}}" != "0" ]]; then
  unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_EXECPATH
  unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY
fi

{{
  echo "[solar-harness multi-task] sid=$SID node=$NODE_ID start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [[ -n {shlex.quote(agent_cmd)} ]]; then
    SOLAR_MULTI_TASK_DISPATCH_FILE="$DISPATCH_FILE" bash -lc {shlex.quote(agent_cmd)}
  else
    if ! command -v claude >/dev/null 2>&1; then
      echo "ERROR: claude command not found; set SOLAR_MULTI_TASK_AGENT_CMD"
      exit 127
    fi
    claude --permission-mode bypassPermissions -p "$(cat "$DISPATCH_FILE")"
  fi
}} > >(tee -a "$OUTPUT_LOG") 2>&1
rc=$?

if [[ "$rc" -eq 0 && -s "$HANDOFF" ]]; then
  "$HARNESS" graph-scheduler mark --graph "$GRAPH" --node "$NODE_ID" --status reviewing --in-place >> "$OUTPUT_LOG" 2>&1 || true
  write_status completed "$rc"
elif [[ "$rc" -eq 0 ]]; then
  echo "ERROR: missing handoff: $HANDOFF" | tee -a "$OUTPUT_LOG"
  "$HARNESS" graph-scheduler mark --graph "$GRAPH" --node "$NODE_ID" --status failed --in-place >> "$OUTPUT_LOG" 2>&1 || true
  write_status failed_missing_handoff 65
  rc=65
else
  "$HARNESS" graph-scheduler mark --graph "$GRAPH" --node "$NODE_ID" --status failed --in-place >> "$OUTPUT_LOG" 2>&1 || true
  write_status failed "$rc"
fi
echo "[solar-harness multi-task] sid=$SID node=$NODE_ID exit=$rc end=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$OUTPUT_LOG"
exit "$rc"
"""
    runner.write_text(script, encoding="utf-8")
    runner.chmod(0o755)
    return runner


def tmux_start(window: str, runner: Path, cwd: Path, dry_run: bool = False) -> None:
    if dry_run:
        return
    cmd = f"bash {shlex.quote(str(runner))}; exec ${{SHELL:-/bin/zsh}}"
    if subprocess.run(["tmux", "has-session", "-t", SESSION], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        subprocess.check_call(["tmux", "new-window", "-d", "-t", SESSION, "-n", window, "-c", str(cwd), cmd])
    else:
        subprocess.check_call(["tmux", "new-session", "-d", "-s", SESSION, "-n", window, "-c", str(cwd), cmd])


def launch_node(graph_path: Path, graph: dict[str, Any], node: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    sid = sprint_id_for(graph, graph_path)
    node_id = str(node.get("id") or "")
    dispatch_id = task_id(sid, node_id)
    window = short_window(f"{dispatch_id}-{node_id}")
    task_dir = RUN_DIR / dispatch_id
    handoff = SPRINTS_DIR / f"{sid}.{node_id}-handoff.md"
    task_dir.mkdir(parents=True, exist_ok=True)

    dispatch = build_dispatch_text(graph_path, graph, node, dispatch_id, window)
    (task_dir / "dispatch.md").write_text(dispatch, encoding="utf-8")
    payload = {
        "id": dispatch_id,
        "status": "dry_run" if dry_run else "dispatched",
        "session": SESSION,
        "window": window,
        "graph": str(graph_path),
        "sprint_id": sid,
        "node_id": node_id,
        "title": str(node.get("goal") or node.get("title") or node_id)[:120],
        "write_scope": node.get("write_scope") or [],
        "handoff": str(handoff),
        "dispatch_file": str(task_dir / "dispatch.md"),
        "work_dir": str(Path.cwd()),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "exit_code": None,
    }
    json_write(status_path(task_dir), payload)
    runner = runner_script(task_dir, payload)

    if not dry_run:
        try:
            tmux_start(window, runner, Path.cwd())
        except Exception as exc:
            payload["status"] = "failed_launch"
            payload["updated_at"] = now_iso()
            payload["error"] = str(exc)
            json_write(status_path(task_dir), payload)
            (task_dir / "output.log").write_text(f"ERROR: tmux launch failed: {exc}\n", encoding="utf-8")
            return payload
        set_node_status(graph, node_id, "dispatched", pane=f"multi-task:{window}", dispatch_id=dispatch_id)
        save_graph(graph_path, graph)
        set_last_launch()

    return payload


def schedule_once(args: argparse.Namespace) -> dict[str, Any]:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    max_workers = max(1, int(args.max_workers))
    guard = launch_guard(max_workers, args.memory_reserve_gb, args.cooldown_sec, args.quota_backoff_sec)
    slots = max(0, max_workers - len(active_tasks()))
    launched: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    if not guard.get("ok") and not args.dry_run:
        return {"guard": guard, "launched": launched, "skipped": skipped, "graphs": [status_summary_for_graph(p) for p in graph_files(args.graph)]}

    for graph_path in graph_files(args.graph):
        if slots <= 0 and not args.dry_run:
            break
        try:
            graph = load_graph(graph_path)
            summaries.append(status_summary_for_graph(graph_path))
            candidates = ready_nodes(graph)
        except Exception as exc:
            skipped.append({"graph": str(graph_path), "reason": "graph_error", "error": str(exc)})
            continue
        for node in candidates:
            if slots <= 0 and not args.dry_run:
                break
            if scope_conflicts_with_active(node):
                skipped.append({"graph": str(graph_path), "node": node.get("id"), "reason": "write_scope_conflict_with_active"})
                continue
            launched.append(launch_node(graph_path, graph, node, dry_run=args.dry_run))
            if not args.dry_run:
                slots -= 1

    if not summaries:
        summaries = [status_summary_for_graph(p) for p in graph_files(args.graph)]
    return {"guard": guard, "launched": launched, "skipped": skipped, "graphs": summaries}


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    top = "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"
    mid = "├" + "┼".join("─" * (w + 2) for w in widths) + "┤"
    bot = "└" + "┴".join("─" * (w + 2) for w in widths) + "┘"
    print(top)
    print("│ " + " │ ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)) + " │")
    print(mid)
    for row in rows:
        print("│ " + " │ ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)) + " │")
    print(bot)


def render(result: dict[str, Any], no_clear: bool = False) -> None:
    if not no_clear and sys.stdout.isatty():
        print("\033[H\033[2J", end="")
    guard = result.get("guard") or {}
    mem = free_memory_gb()
    print("Solar Harness Multi-Task · tmux DAG worker pool")
    print_table(
        ["项目", "状态", "值"],
        [
            ["session", "ok", SESSION],
            ["active_workers", "ok", str(len(active_tasks()))],
            ["launch_guard", "ok" if guard.get("ok") else "warn", str(guard.get("reason", "N/A"))],
            ["free_memory_gb", "ok" if mem is None or mem >= DEFAULT_MEMORY_RESERVE_GB else "warn", "N/A" if mem is None else f"{mem:.2f}"],
            ["updated_at", "ok", now_iso()],
        ],
    )

    tasks = list_task_rows()[:20]
    task_rows = [[
        str(t.get("id", "N/A"))[:34],
        str(t.get("status", "N/A"))[:22],
        str(t.get("sprint_id", "N/A"))[:20],
        str(t.get("node_id", "N/A"))[:24],
        str(t.get("updated_at", "N/A"))[:20],
    ] for t in tasks]
    print()
    print_table(["task", "status", "sprint", "node", "updated"], task_rows or [["N/A", "pending", "N/A", "N/A", "N/A"]])

    graph_rows = []
    for graph in result.get("graphs", [])[:12]:
        counts = graph.get("counts") or {}
        graph_rows.append([
            str(graph.get("sid", "N/A"))[:28],
            "ok" if graph.get("ok") else "error",
            ",".join(f"{k}:{v}" for k, v in sorted(counts.items()))[:40] or "N/A",
            ",".join(graph.get("ready") or [])[:38] or "N/A",
        ])
    print()
    print_table(["sprint", "状态", "node_counts", "ready"], graph_rows or [["N/A", "pending", "N/A", "N/A"]])

    launched = result.get("launched") or []
    if launched:
        print()
        print_table("launched status sprint node".split(), [[
            str(x.get("id", "N/A"))[:34],
            str(x.get("status", "N/A")),
            str(x.get("sprint_id", "N/A"))[:20],
            str(x.get("node_id", "N/A"))[:24],
        ] for x in launched])


def attach_or_log(task_id_value: str, attach: bool) -> int:
    status = read_task_status(RUN_DIR / task_id_value / "status.json")
    if not status:
        print(f"status not found: {task_id_value}", file=sys.stderr)
        return 1
    if attach:
        window = str(status.get("window") or "")
        if sys.stdout.isatty():
            return subprocess.call(["tmux", "attach", "-t", f"{SESSION}:{window}"])
        print(f"tmux attach -t {SESSION}:{window}")
        return 0
    log = RUN_DIR / task_id_value / "output.log"
    if not log.exists():
        print(f"log not found: {log}", file=sys.stderr)
        return 1
    print(log.read_text(encoding="utf-8", errors="replace")[-20000:])
    return 0


def cancel(task_id_value: str) -> int:
    status = read_task_status(RUN_DIR / task_id_value / "status.json")
    if not status:
        print(f"status not found: {task_id_value}", file=sys.stderr)
        return 1
    window = str(status.get("window") or "")
    subprocess.run(["tmux", "kill-window", "-t", f"{SESSION}:{window}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    status["status"] = "cancelled"
    status["updated_at"] = now_iso()
    json_write(RUN_DIR / task_id_value / "status.json", status)
    try:
        graph_path = Path(str(status.get("graph")))
        graph = load_graph(graph_path)
        set_node_status(graph, str(status.get("node_id")), "failed", pane=f"multi-task:{window}", dispatch_id=task_id_value)
        save_graph(graph_path, graph)
    except Exception:
        pass
    print(f"cancelled: {task_id_value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="solar-harness multi-task")
    sub = p.add_subparsers(dest="cmd")
    start = sub.add_parser("start", help="start tmux-backed DAG worker scheduler")
    start.add_argument("--graph", action="append", default=[], help="task_graph.json path; can repeat")
    start.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    start.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    start.add_argument("--cooldown-sec", type=int, default=DEFAULT_COOLDOWN)
    start.add_argument("--memory-reserve-gb", type=float, default=DEFAULT_MEMORY_RESERVE_GB)
    start.add_argument("--quota-backoff-sec", type=int, default=DEFAULT_QUOTA_BACKOFF)
    start.add_argument("--once", action="store_true")
    start.add_argument("--dry-run", action="store_true")
    start.add_argument("--no-clear", action="store_true")

    status = sub.add_parser("status", help="show current scheduler summary")
    status.add_argument("--graph", action="append", default=[])
    status.add_argument("--no-clear", action="store_true")

    logs = sub.add_parser("logs", help="show task log")
    logs.add_argument("task_id")
    attach = sub.add_parser("attach", help="attach tmux task window")
    attach.add_argument("task_id")
    cancel_p = sub.add_parser("cancel", help="cancel task and mark graph node failed")
    cancel_p.add_argument("task_id")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["start"]
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "logs":
        return attach_or_log(args.task_id, attach=False)
    if args.cmd == "attach":
        return attach_or_log(args.task_id, attach=True)
    if args.cmd == "cancel":
        return cancel(args.task_id)
    if args.cmd == "status":
        render({"guard": launch_guard(DEFAULT_MAX_WORKERS, DEFAULT_MEMORY_RESERVE_GB, DEFAULT_COOLDOWN, DEFAULT_QUOTA_BACKOFF), "graphs": [status_summary_for_graph(p) for p in graph_files(args.graph)]}, no_clear=args.no_clear)
        return 0

    if args.cmd in {None, "start"}:
        while True:
            result = schedule_once(args)
            render(result, no_clear=args.no_clear)
            if args.once:
                return 0
            time.sleep(max(1, int(args.interval)))

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
