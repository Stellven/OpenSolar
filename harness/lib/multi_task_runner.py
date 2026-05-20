#!/usr/bin/env python3
"""tmux-backed DAG worker pool for Solar Harness multi-task execution."""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

try:
    import readline  # type: ignore
except Exception:  # pragma: no cover - readline may be unavailable in minimal Python builds
    readline = None  # type: ignore

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
SPRINTS_DIR = Path(os.environ.get("HARNESS_SPRINTS_DIR", HARNESS_DIR / "sprints"))
RUN_DIR = HARNESS_DIR / "run" / "multi-task"
SESSION = os.environ.get("SOLAR_HARNESS_MULTI_TASK_SESSION", "solar-harness-multi-task")
PROFILE_PATH = Path(os.environ.get("SOLAR_MULTI_TASK_PROFILES", HARNESS_DIR / "config" / "multi-task-profiles.json"))
SCREEN_HISTORY_PATH = Path(os.environ.get("SOLAR_MULTI_TASK_SCREEN_HISTORY", RUN_DIR / "screen-history.txt"))
DEFAULT_MAX_WORKERS = int(os.environ.get("SOLAR_MULTI_TASK_MAX_WORKERS", "2") or "2")
DEFAULT_INTERVAL = int(os.environ.get("SOLAR_MULTI_TASK_INTERVAL_SEC", "15") or "15")
DEFAULT_COOLDOWN = int(os.environ.get("SOLAR_MULTI_TASK_LAUNCH_COOLDOWN_SEC", "30") or "30")
DEFAULT_MEMORY_RESERVE_GB = float(os.environ.get("SOLAR_MULTI_TASK_MEMORY_RESERVE_GB", "4") or "4")
DEFAULT_QUOTA_BACKOFF = int(os.environ.get("SOLAR_MULTI_TASK_QUOTA_BACKOFF_SEC", "900") or "900")

DEFAULT_PROFILE_CONFIG: dict[str, Any] = {
    "defaults": {"profile": "builder", "backend": "claude-cli", "max_workers": 2},
    "profiles": {
        "builder": {
            "role": "builder",
            "label": "构建者",
            "persona": "builder",
            "backend": "claude-cli",
            "model": "sonnet",
            "approval_mode": "yolo",
            "best_for": ["implementation", "debugging", "tests"],
            "max_parallel": 2,
        },
        "planner": {
            "role": "planner",
            "label": "规划者",
            "persona": "planner",
            "backend": "claude-cli",
            "model": "sonnet",
            "approval_mode": "auto_edit",
            "best_for": ["planning", "architecture"],
            "max_parallel": 1,
        },
        "evaluator": {
            "role": "evaluator",
            "label": "审判者",
            "persona": "evaluator",
            "backend": "claude-cli",
            "model": "opus",
            "approval_mode": "auto_edit",
            "best_for": ["verification", "review"],
            "max_parallel": 1,
        },
        "pm": {
            "role": "pm",
            "label": "PM",
            "persona": "pm",
            "backend": "claude-cli",
            "model": "sonnet",
            "approval_mode": "auto_edit",
            "best_for": ["requirements", "acceptance"],
            "max_parallel": 1,
        },
        "gemini-builder": {
            "role": "builder",
            "label": "Gemini 构建者",
            "persona": "builder",
            "backend": "gemini-cli",
            "model": "gemini",
            "approval_mode": "yolo",
            "best_for": ["large-context", "implementation"],
            "max_parallel": 1,
        },
    },
}

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


def load_profiles() -> dict[str, Any]:
    if PROFILE_PATH.exists():
        try:
            data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            if isinstance(data.get("profiles"), dict):
                return data
        except Exception:
            pass
    return DEFAULT_PROFILE_CONFIG


def profile_names() -> list[str]:
    return sorted((load_profiles().get("profiles") or {}).keys())


def role_from_node(node: dict[str, Any]) -> str:
    raw = (
        node.get("target_role")
        or node.get("role")
        or node.get("persona")
        or node.get("worker_role")
        or node.get("handoff_to")
        or ""
    )
    value = str(raw).strip().lower().replace("_", "-")
    aliases = {
        "builder-main": "builder",
        "build": "builder",
        "implementation": "builder",
        "implementer": "builder",
        "judge": "evaluator",
        "reviewer": "evaluator",
        "verifier": "evaluator",
        "product": "pm",
        "product-manager": "pm",
        "planning": "planner",
        "architect": "planner",
    }
    return aliases.get(value, value or "builder")


def select_profile(node: dict[str, Any], profile_override: str = "", model_override: str = "", backend_override: str = "") -> dict[str, Any]:
    config = load_profiles()
    profiles = config.get("profiles") or {}
    profile_name = profile_override or ""
    if not profile_name:
        role = role_from_node(node)
        for name, spec in profiles.items():
            if str(spec.get("role", "")).lower() == role and not str(name).startswith(("gemini-", "deepseek-", "glm-", "thunder")):
                profile_name = str(name)
                break
    profile_name = profile_name or str((config.get("defaults") or {}).get("profile") or "builder")
    if profile_name not in profiles:
        raise ValueError(f"unknown multi-task profile: {profile_name}")
    selected = dict(profiles[profile_name])
    selected["name"] = profile_name
    selected["role"] = str(selected.get("role") or role_from_node(node))
    selected["persona"] = str(selected.get("persona") or selected["role"])
    selected["model"] = str(model_override or node.get("preferred_model") or selected.get("model") or "sonnet")
    selected["backend"] = str(backend_override or selected.get("backend") or (config.get("defaults") or {}).get("backend") or "claude-cli")
    selected["approval_mode"] = str(selected.get("approval_mode") or "auto_edit")
    return selected


def persona_text(persona: str) -> tuple[str, str]:
    path = HARNESS_DIR / "personas" / f"{persona}.md"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return str(path), text[:12000]
    except Exception:
        return str(path), "N/A"


def claude_model_arg(model: str) -> str:
    value = str(model or "sonnet").lower()
    if "opus" in value:
        return "opus"
    if "sonnet" in value or value in {"claude", "anthropic"}:
        return "sonnet"
    return value


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


def build_dispatch_text(graph_path: Path, graph: dict[str, Any], node: dict[str, Any], dispatch_id: str, window: str,
                        profile: dict[str, Any]) -> str:
    sid = sprint_id_for(graph, graph_path)
    node_id = str(node.get("id") or "")
    handoff = SPRINTS_DIR / f"{sid}.{node_id}-handoff.md"
    harness = HARNESS_DIR / "solar-harness.sh"
    persona_path, persona_body = persona_text(str(profile.get("persona") or "builder"))

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
Role/Profile: `{profile.get("role")}` / `{profile.get("name")}`
Backend/Model: `{profile.get("backend")}` / `{profile.get("model")}`
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

## Worker Persona

Persona file: `{persona_path}`

```markdown
{persona_body}
```

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
    backend = str(payload.get("backend") or "claude-cli")
    model = str(payload.get("model") or "sonnet")
    approval_mode = str(payload.get("approval_mode") or "auto_edit")
    agent_cmd = os.environ.get("SOLAR_MULTI_TASK_AGENT_CMD", "").strip()
    adapter = HARNESS_DIR / "lib" / "gemini_adapter.py"
    if backend == "gemini-cli":
        agent_line = f"python3 {shlex.quote(str(adapter))} run --backend cli --model {shlex.quote(model)} --approval-mode {shlex.quote(approval_mode)} --prompt-file \"$DISPATCH_FILE\""
    elif backend == "gemini-sdk":
        agent_line = f"python3 {shlex.quote(str(adapter))} run --backend sdk --model {shlex.quote(model)} --prompt-file \"$DISPATCH_FILE\""
    elif backend == "command":
        agent_line = f"SOLAR_MULTI_TASK_DISPATCH_FILE=\"$DISPATCH_FILE\" bash -lc {shlex.quote(agent_cmd)}"
    else:
        agent_line = f"claude --permission-mode bypassPermissions --model {shlex.quote(claude_model_arg(model))} -p \"$(cat \"$DISPATCH_FILE\")\""
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
BACKEND={shlex.quote(backend)}
MODEL={shlex.quote(model)}
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
  echo "[solar-harness multi-task] sid=$SID node=$NODE_ID backend=$BACKEND model=$MODEL start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [[ "$BACKEND" == "command" && -z {shlex.quote(agent_cmd)} ]]; then
    echo "ERROR: backend=command requires SOLAR_MULTI_TASK_AGENT_CMD"
    exit 127
  elif [[ -n {shlex.quote(agent_cmd)} && "$BACKEND" != "command" ]]; then
    SOLAR_MULTI_TASK_DISPATCH_FILE="$DISPATCH_FILE" bash -lc {shlex.quote(agent_cmd)}
  else
    if [[ "$BACKEND" == "claude-cli" ]] && ! command -v claude >/dev/null 2>&1; then
      echo "ERROR: claude command not found; set SOLAR_MULTI_TASK_AGENT_CMD"
      exit 127
    fi
    {agent_line}
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


def launch_node(graph_path: Path, graph: dict[str, Any], node: dict[str, Any], args: argparse.Namespace,
                dry_run: bool = False) -> dict[str, Any]:
    sid = sprint_id_for(graph, graph_path)
    node_id = str(node.get("id") or "")
    profile = select_profile(node, getattr(args, "profile", "") or "", getattr(args, "model", "") or "", getattr(args, "backend", "") or "")
    dispatch_id = task_id(sid, node_id)
    window = short_window(f"{dispatch_id}-{profile.get('role')}-{node_id}")
    task_dir = RUN_DIR / dispatch_id
    handoff = SPRINTS_DIR / f"{sid}.{node_id}-handoff.md"
    task_dir.mkdir(parents=True, exist_ok=True)

    dispatch = build_dispatch_text(graph_path, graph, node, dispatch_id, window, profile)
    (task_dir / "dispatch.md").write_text(dispatch, encoding="utf-8")
    payload = {
        "id": dispatch_id,
        "status": "dry_run" if dry_run else "dispatched",
        "session": SESSION,
        "window": window,
        "profile": profile.get("name"),
        "role": profile.get("role"),
        "persona": profile.get("persona"),
        "backend": profile.get("backend"),
        "model": profile.get("model"),
        "approval_mode": profile.get("approval_mode"),
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
            launched.append(launch_node(graph_path, graph, node, args, dry_run=args.dry_run))
            if not args.dry_run:
                slots -= 1

    if not summaries:
        summaries = [status_summary_for_graph(p) for p in graph_files(args.graph)]
    return {"guard": guard, "launched": launched, "skipped": skipped, "graphs": summaries}


def status_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    """Read current worker and DAG state without dispatching new work."""
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    max_workers = max(1, int(getattr(args, "max_workers", DEFAULT_MAX_WORKERS)))
    memory_reserve_gb = float(getattr(args, "memory_reserve_gb", DEFAULT_MEMORY_RESERVE_GB))
    cooldown_sec = int(getattr(args, "cooldown_sec", DEFAULT_COOLDOWN))
    quota_backoff_sec = int(getattr(args, "quota_backoff_sec", DEFAULT_QUOTA_BACKOFF))
    graph_arg = getattr(args, "graph", [])
    return {
        "guard": launch_guard(max_workers, memory_reserve_gb, cooldown_sec, quota_backoff_sec),
        "launched": [],
        "skipped": [],
        "graphs": [status_summary_for_graph(p) for p in graph_files(graph_arg)],
    }


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
        str(t.get("role", "N/A"))[:10],
        str(t.get("model", "N/A"))[:16],
        str(t.get("backend", "N/A"))[:12],
        str(t.get("sprint_id", "N/A"))[:20],
        str(t.get("node_id", "N/A"))[:24],
        str(t.get("updated_at", "N/A"))[:20],
    ] for t in tasks]
    print()
    print_table(
        ["task", "status", "role", "model", "backend", "sprint", "node", "updated"],
        task_rows or [["N/A", "pending", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"]],
    )

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


def render_to_lines(result: dict[str, Any]) -> list[str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        render(result, no_clear=True)
    return buf.getvalue().splitlines()


def command_log_path() -> Path:
    return RUN_DIR / "screen-commands.jsonl"


def load_screen_history() -> None:
    if readline is None:
        return
    try:
        SCREEN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if SCREEN_HISTORY_PATH.exists():
            readline.read_history_file(str(SCREEN_HISTORY_PATH))
        readline.set_history_length(1000)
    except Exception:
        return


def save_screen_history() -> None:
    if readline is None:
        return
    try:
        SCREEN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        readline.set_history_length(1000)
        readline.write_history_file(str(SCREEN_HISTORY_PATH))
    except Exception:
        return


def remember_screen_input(text: str) -> None:
    raw = text.strip()
    if not raw:
        return
    if readline is not None:
        try:
            last = readline.get_history_item(readline.get_current_history_length()) or ""
            if last != raw:
                readline.add_history(raw)
            save_screen_history()
            return
        except Exception:
            pass
    try:
        SCREEN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        old = SCREEN_HISTORY_PATH.read_text(encoding="utf-8").splitlines() if SCREEN_HISTORY_PATH.exists() else []
        if not old or old[-1] != raw:
            old.append(raw)
        SCREEN_HISTORY_PATH.write_text("\n".join(old[-1000:]) + "\n", encoding="utf-8")
    except Exception:
        return


def append_screen_command(text: str, intent: dict[str, Any], action: str, status: str, detail: str = "") -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": now_iso(),
        "input": text,
        "intent": intent,
        "action": action,
        "status": status,
        "detail": detail,
    }
    with command_log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def match_intent(text: str) -> dict[str, Any]:
    try:
        from intent_engine_adapter import match as intent_match  # noqa: WPS433

        return intent_match(text, record=True)
    except Exception as exc:
        return {
            "ok": False,
            "input": text,
            "matched": False,
            "matches": [],
            "error": f"{type(exc).__name__}: {exc}",
            "generated_at": now_iso(),
        }


def _intent_label(intent: dict[str, Any]) -> str:
    labels: list[str] = []
    for item in intent.get("matches") or []:
        label = item.get("skill") or item.get("target") or item.get("type") or item.get("source")
        if label:
            labels.append(str(label))
    return ",".join(labels[:3]) if labels else "N/A"


def _set_screen_model_preference(text: str, args: argparse.Namespace) -> str:
    lower = text.lower()
    if "gemini" in lower:
        args.profile = "gemini-builder"
        args.backend = "gemini-cli"
        args.model = "gemini"
        return "profile=gemini-builder backend=gemini-cli model=gemini"
    if "deepseek" in lower or "deepseek" in text:
        args.profile = "deepseek-builder"
        args.backend = ""
        args.model = "deepseek"
        return "profile=deepseek-builder model=deepseek"
    if "glm" in lower or "智谱" in text or "gml" in lower:
        args.profile = "glm-planner"
        args.backend = ""
        args.model = "glm-5.1"
        return "profile=glm-planner model=glm-5.1"
    if "opus" in lower:
        args.profile = "evaluator"
        args.backend = "claude-cli"
        args.model = "opus"
        return "profile=evaluator backend=claude-cli model=opus"
    if "sonnet" in lower:
        args.profile = "builder"
        args.backend = "claude-cli"
        args.model = "sonnet"
        return "profile=builder backend=claude-cli model=sonnet"
    if "thunderomlx" in lower or "thunder" in lower or "omlx" in lower:
        args.profile = "thunderomlx-local"
        args.backend = "command"
        args.model = "thunderomlx"
        return "profile=thunderomlx-local backend=command model=thunderomlx"
    return ""


def _selector_from_text(text: str) -> str:
    lower = text.lower()
    for selector in ("planner", "builder", "evaluator", "pm", "gemini-builder", "latest"):
        if selector in lower:
            return selector
    for cn, selector in (("规划", "planner"), ("构建", "builder"), ("建设", "builder"), ("审判", "evaluator"), ("评审", "evaluator")):
        if cn in text:
            return selector
    return "latest"


def _looks_like_task_status_query(text: str) -> bool:
    lower = text.lower()
    query_markers = ("哪些", "哪个", "什么", "多少", "有没有", "是否", "吗", "?", "？", "list", "show", "what", "which", "running")
    task_markers = ("任务", "worker", "pane", "后台", "dag", "task")
    status_markers = ("执行", "运行", "正在", "状态", "进展", "active", "running", "status")
    has_query = any(marker in text or marker in lower for marker in query_markers)
    has_task = any(marker in text or marker in lower for marker in task_markers)
    has_status = any(marker in text or marker in lower for marker in status_markers)
    return has_task and (has_query or has_status)


def _task_status_message() -> str:
    tasks = list_task_rows()
    active = [t for t in tasks if str(t.get("status", "")).lower() in ACTIVE_TASK_STATUSES]
    graph_summaries = [status_summary_for_graph(path) for path in graph_files([])[:12]]
    dag_counts: dict[str, int] = {}
    ready_sprints: list[str] = []
    for summary in graph_summaries:
        for status, count in (summary.get("counts") or {}).items():
            dag_counts[str(status)] = dag_counts.get(str(status), 0) + int(count)
        ready = summary.get("ready") or []
        if ready:
            ready_sprints.append(f"{summary.get('sid', 'N/A')}:{','.join(ready[:5])}")
    dag_active = sum(dag_counts.get(status, 0) for status in ("active", "assigned", "dispatched", "in_progress", "running", "reviewing"))
    dag_ready = sum(len(summary.get("ready") or []) for summary in graph_summaries)
    bg_summary = f"BG active={len(active)}/{len(tasks)}"
    dag_summary = f"DAG active={dag_active} ready={dag_ready}"
    if not tasks and not dag_active and not dag_ready:
        return f"当前任务: {bg_summary}; {dag_summary}"
    if not active:
        latest = f" latest={tasks[0].get('id', 'N/A')} status={tasks[0].get('status', 'N/A')}" if tasks else ""
        ready_text = f" ready_sprints={' | '.join(ready_sprints[:2])}" if ready_sprints else ""
        return f"当前任务: {bg_summary}; {dag_summary}{ready_text}{latest}"
    parts = []
    for task in active[:5]:
        parts.append(
            f"{task.get('id', 'N/A')}[{task.get('role', 'N/A')}/{task.get('model', 'N/A')}/{task.get('status', 'N/A')}]"
        )
    ready_text = f" ready_sprints={' | '.join(ready_sprints[:2])}" if ready_sprints else ""
    return f"当前任务: {bg_summary}; {dag_summary}{ready_text}; workers=" + "; ".join(parts)


def handle_screen_input(text: str, args: argparse.Namespace) -> tuple[str, str]:
    raw = text.strip()
    if not raw:
        return "noop", "空输入"
    intent = match_intent(raw)
    matched = _intent_label(intent)
    lower = raw.lower()

    if lower in {"q", "quit", "exit", "退出", "关闭"}:
        append_screen_command(raw, intent, "exit", "ok", matched)
        return "exit", f"intent={matched} action=exit"
    if lower in {"help", "?", "/help", "帮助"}:
        msg = "命令: status/profiles/doctor/start/foreground latest/logs latest/cancel latest；自然语言会先 intent match，再 intake。"
        append_screen_command(raw, intent, "help", "ok", matched)
        return "message", msg
    if lower in {"status", "状态", "显示状态", "看状态"} or _looks_like_task_status_query(raw):
        label = "task_status_query" if _looks_like_task_status_query(raw) else matched
        append_screen_command(raw, intent, "status", "ok", label)
        return "message", f"intent={label} action=status {_task_status_message()}"
    if lower in {"profiles", "profile", "角色", "模型", "选项"}:
        append_screen_command(raw, intent, "profiles", "ok", matched)
        return "profiles", "显示 profiles"
    if lower in {"doctor", "检查", "自检"}:
        append_screen_command(raw, intent, "doctor", "ok", matched)
        return "doctor", "显示 doctor"
    if lower.startswith(("foreground", "focus", "fg", "前台", "看输出", "查看输出")):
        selector = raw.split(maxsplit=1)[1] if " " in raw and not raw.startswith(("前台", "看输出", "查看输出")) else _selector_from_text(raw)
        append_screen_command(raw, intent, "foreground", "ok", selector)
        return "foreground", selector
    if lower.startswith(("logs", "log", "日志")):
        selector = raw.split(maxsplit=1)[1] if " " in raw else _selector_from_text(raw)
        append_screen_command(raw, intent, "logs", "ok", selector)
        return "logs", selector
    if lower.startswith(("cancel", "取消")):
        selector = raw.split(maxsplit=1)[1] if " " in raw else _selector_from_text(raw)
        append_screen_command(raw, intent, "cancel", "ok", selector)
        return "cancel", selector
    if lower.startswith(("start", "启动调度", "开始调度")) or any((m.get("type") == "execute") for m in intent.get("matches") or []):
        pref = _set_screen_model_preference(raw, args)
        result = schedule_once(args)
        append_screen_command(raw, intent, "schedule_once", "ok", pref)
        return "message", f"intent={matched} action=schedule_once launched={len(result.get('launched') or [])} {pref}".strip()

    pref = _set_screen_model_preference(raw, args)
    harness = HARNESS_DIR / "solar-harness.sh"
    proc = subprocess.run(
        [str(harness), "intake", "--request", raw],
        text=True,
        capture_output=True,
        timeout=120,
    )
    detail = (proc.stdout or proc.stderr or "").strip().splitlines()
    summary = detail[-1] if detail else f"exit={proc.returncode}"
    append_screen_command(raw, intent, "intake", "ok" if proc.returncode == 0 else "error", f"{pref} {summary}".strip())
    return "message", f"intent={matched} action=intake rc={proc.returncode} {pref}".strip()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def _display_width(text: str) -> int:
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1
    return width


def _clip_display(text: str, max_width: int) -> str:
    if max_width <= 0:
        return ""
    out: list[str] = []
    width = 0
    for ch in text:
        ch_width = 0 if unicodedata.combining(ch) else (2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1)
        if width + ch_width > max_width:
            break
        out.append(ch)
        width += ch_width
    return "".join(out)


def _pad_display(text: str, width: int, fill: str = " ") -> str:
    clipped = _clip_display(text, width)
    pad = max(0, width - _display_width(clipped))
    return clipped + fill * pad


def _box_lines(title: str, lines: list[str], width: int, height: int) -> list[str]:
    total_width = max(40, width)
    hline_width = max(10, total_width - 2)
    content_width = max(8, total_width - 4)
    title_text = f" {title} "
    top = "┌" + _pad_display(title_text, hline_width, "─") + "┐"
    bottom = "└" + "─" * hline_width + "┘"
    body_height = max(0, height - 2)
    out = [top]
    for line in lines[:body_height]:
        clean = _strip_ansi(line)
        out.append("│ " + _pad_display(clean, content_width) + " │")
    while len(out) < height - 1:
        out.append("│ " + " " * content_width + " │")
    out.append(bottom)
    return out[:height]


def draw_screen(result: dict[str, Any], messages: list[str], args: argparse.Namespace) -> None:
    size = shutil.get_terminal_size((120, 40))
    rows = max(12, size.lines)
    cols = max(60, size.columns)
    available = max(10, rows - 1)
    top_h = max(6, int(available * 0.68))
    bottom_h = max(4, available - top_h)
    if top_h + bottom_h > available:
        top_h = max(6, available - bottom_h)
    if top_h + bottom_h > available:
        bottom_h = max(3, available - top_h)
    if not args.no_clear and sys.stdout.isatty():
        print("\033[H\033[2J", end="")
    status_lines = render_to_lines(result)
    fixed_input_lines = [
        f"profile={args.profile or 'auto'} backend={args.backend or 'auto'} model={args.model or 'auto'}",
        "输入: 自然语言需求 / status / profiles / doctor / foreground latest / logs latest / q",
        f"history: ↑/↓ 回滚历史输入; {SCREEN_HISTORY_PATH.name}",
        "intent: 每条输入都会写入 run/multi-task/screen-commands.jsonl",
        "",
    ]
    input_body_height = max(0, bottom_h - 2)
    message_slots = max(1, input_body_height - len(fixed_input_lines))
    input_lines = fixed_input_lines + messages[-message_slots:]
    print("\n".join(_box_lines("后台 pane 状态 / DAG worker 池", status_lines, cols, top_h)))
    print("\n".join(_box_lines("自然语言指令 / Intent Engine 输入区", input_lines, cols, bottom_h)))
    print("solar> ", end="", flush=True)


def screen_loop(args: argparse.Namespace) -> int:
    messages: list[str] = ["screen started"]
    load_screen_history()
    if args.command or not sys.stdin.isatty():
        commands = [args.command] if args.command else [line.strip() for line in sys.stdin if line.strip()]
        if not commands:
            draw_screen(status_snapshot(args), messages, args)
            return 0
        for raw in commands:
            remember_screen_input(raw)
            action, detail = handle_screen_input(raw, args)
            messages.append(f"{now_iso()} {raw} -> {detail}")
            if action == "foreground":
                print()
                return attach_or_log(detail, attach=True)
            if action == "logs":
                print()
                return attach_or_log(detail, attach=False)
            if action == "cancel":
                rc = cancel(detail)
                messages.append(f"cancel rc={rc}")
            if action == "profiles":
                config = load_profiles()
                for name, spec in sorted((config.get("profiles") or {}).items()):
                    messages.append(f"{name}: role={spec.get('role')} backend={spec.get('backend')} model={spec.get('model')}")
            if action == "doctor":
                adapter = HARNESS_DIR / "lib" / "gemini_adapter.py"
                gemini = subprocess.run([sys.executable, str(adapter), "doctor"], text=True, capture_output=True)
                messages.append("doctor gemini: " + " ".join((gemini.stdout or gemini.stderr).split())[:160])
            if action == "exit":
                break
        draw_screen(status_snapshot(args), messages, args)
        return 0
    while True:
        result = status_snapshot(args)
        draw_screen(result, messages, args)
        if args.once and not args.command:
            return 0
        try:
            raw = input()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        commands = [raw]
        for raw in commands:
            remember_screen_input(raw)
            action, detail = handle_screen_input(raw, args)
            messages.append(f"{now_iso()} {raw} -> {detail}")
            if action == "exit":
                draw_screen(status_snapshot(args), messages, args)
                return 0
            if action == "foreground":
                print()
                return attach_or_log(detail, attach=True)
            if action == "logs":
                print()
                return attach_or_log(detail, attach=False)
            if action == "cancel":
                rc = cancel(detail)
                messages.append(f"cancel rc={rc}")
            if action == "profiles":
                config = load_profiles()
                for name, spec in sorted((config.get("profiles") or {}).items()):
                    messages.append(f"{name}: role={spec.get('role')} backend={spec.get('backend')} model={spec.get('model')}")
            if action == "doctor":
                adapter = HARNESS_DIR / "lib" / "gemini_adapter.py"
                gemini = subprocess.run([sys.executable, str(adapter), "doctor"], text=True, capture_output=True)
                messages.append("doctor gemini: " + " ".join((gemini.stdout or gemini.stderr).split())[:160])
        if args.command or not sys.stdin.isatty():
            draw_screen(status_snapshot(args), messages, args)
            return 0


def resolve_task(selector: str) -> dict[str, Any] | None:
    rows = list_task_rows()
    if not rows:
        return None
    value = str(selector or "latest").strip()
    if value in {"latest", "last", ""}:
        return rows[0]
    for row in rows:
        task = str(row.get("id") or "")
        if task == value or task.startswith(value):
            return row
    for row in rows:
        if value.lower() in {
            str(row.get("role") or "").lower(),
            str(row.get("profile") or "").lower(),
            str(row.get("node_id") or "").lower(),
        }:
            return row
    return None


def attach_or_log(task_id_value: str, attach: bool) -> int:
    status = resolve_task(task_id_value)
    if not status:
        print(f"status not found: {task_id_value}", file=sys.stderr)
        return 1
    task_id_value = str(status.get("id") or task_id_value)
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
    status = resolve_task(task_id_value)
    if not status:
        print(f"status not found: {task_id_value}", file=sys.stderr)
        return 1
    task_id_value = str(status.get("id") or task_id_value)
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
    screen = sub.add_parser("screen", help="interactive split terminal screen with status and natural-language input")
    screen.add_argument("--graph", action="append", default=[], help="task_graph.json path; can repeat")
    screen.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    screen.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    screen.add_argument("--cooldown-sec", type=int, default=DEFAULT_COOLDOWN)
    screen.add_argument("--memory-reserve-gb", type=float, default=DEFAULT_MEMORY_RESERVE_GB)
    screen.add_argument("--quota-backoff-sec", type=int, default=DEFAULT_QUOTA_BACKOFF)
    screen.add_argument("--profile", default="", help=f"worker profile: {','.join(profile_names())}")
    screen.add_argument("--model", default="", help="override selected profile model")
    screen.add_argument("--backend", default="", choices=["", "claude-cli", "gemini-cli", "gemini-sdk", "command"], help="override selected profile backend")
    screen.add_argument("--command", default="", help="process one input command, useful for tests/scripts")
    screen.add_argument("--dry-run", action="store_true")
    screen.add_argument("--once", action="store_true", help="render once and exit")
    screen.add_argument("--no-clear", action="store_true")
    start = sub.add_parser("start", help="start tmux-backed DAG worker scheduler")
    start.add_argument("--graph", action="append", default=[], help="task_graph.json path; can repeat")
    start.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    start.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    start.add_argument("--cooldown-sec", type=int, default=DEFAULT_COOLDOWN)
    start.add_argument("--memory-reserve-gb", type=float, default=DEFAULT_MEMORY_RESERVE_GB)
    start.add_argument("--quota-backoff-sec", type=int, default=DEFAULT_QUOTA_BACKOFF)
    start.add_argument("--profile", default="", help=f"worker profile: {','.join(profile_names())}")
    start.add_argument("--model", default="", help="override selected profile model")
    start.add_argument("--backend", default="", choices=["", "claude-cli", "gemini-cli", "gemini-sdk", "command"], help="override selected profile backend")
    start.add_argument("--once", action="store_true")
    start.add_argument("--dry-run", action="store_true")
    start.add_argument("--no-clear", action="store_true")

    status = sub.add_parser("status", help="show current scheduler summary")
    status.add_argument("--graph", action="append", default=[])
    status.add_argument("--no-clear", action="store_true")

    logs = sub.add_parser("logs", help="show task log")
    logs.add_argument("task_id", help="task id/prefix, latest, role, profile, or node id")
    attach = sub.add_parser("attach", help="attach tmux task window")
    attach.add_argument("task_id", help="task id/prefix, latest, role, profile, or node id")
    for alias in ("foreground", "focus", "fg"):
        fg = sub.add_parser(alias, help="bring a background tmux task to foreground")
        fg.add_argument("task_id", nargs="?", default="latest", help="task id/prefix, latest, role, profile, or node id")
    cancel_p = sub.add_parser("cancel", help="cancel task and mark graph node failed")
    cancel_p.add_argument("task_id")
    sub.add_parser("profiles", help="list worker profiles and model/task affinity")
    sub.add_parser("doctor", help="check multi-task external backends")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["screen"]
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "logs":
        return attach_or_log(args.task_id, attach=False)
    if args.cmd == "attach":
        return attach_or_log(args.task_id, attach=True)
    if args.cmd in {"foreground", "focus", "fg"}:
        return attach_or_log(args.task_id, attach=True)
    if args.cmd == "cancel":
        return cancel(args.task_id)
    if args.cmd == "profiles":
        config = load_profiles()
        rows = []
        for name, spec in sorted((config.get("profiles") or {}).items()):
            rows.append([
                name,
                str(spec.get("role", "N/A")),
                str(spec.get("backend", "N/A")),
                str(spec.get("model", "N/A")),
                ",".join(spec.get("best_for") or [])[:44] or "N/A",
            ])
        print_table(["profile", "role", "backend", "model", "best_for"], rows)
        return 0
    if args.cmd == "doctor":
        adapter = HARNESS_DIR / "lib" / "gemini_adapter.py"
        gemini = subprocess.run([sys.executable, str(adapter), "doctor"], text=True, capture_output=True)
        gemini_evidence = " ".join((gemini.stdout or gemini.stderr).strip().split())
        print_table(
            ["backend", "状态", "证据"],
            [
                ["claude-cli", "ok" if shutil.which("claude") else "warn", shutil.which("claude") or "missing"],
                ["gemini", "ok" if gemini.returncode == 0 else "warn", gemini_evidence[:96] or "N/A"],
                ["command", "ok" if os.environ.get("SOLAR_MULTI_TASK_AGENT_CMD") else "warn", "SOLAR_MULTI_TASK_AGENT_CMD set" if os.environ.get("SOLAR_MULTI_TASK_AGENT_CMD") else "env missing"],
            ],
        )
        return 0
    if args.cmd == "status":
        render(status_snapshot(args), no_clear=args.no_clear)
        return 0
    if args.cmd == "screen":
        return screen_loop(args)

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
