#!/usr/bin/env python3
"""
solar-autopilot-monitor.py

Detects Solar Harness coordination dead-ends and applies safe default repairs.
It is intentionally conservative: it does not delete data, call external APIs,
or spend model tokens. It updates local sprint status/events and can dispatch
clear instructions to tmux panes when requested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


HOME = Path.home()
HARNESS = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
SPRINTS = HARNESS / "sprints"
EVENTS = HARNESS / "events" / "all.jsonl"
SESSION = os.environ.get("SOLAR_HARNESS_SESSION", "solar-harness")
STATE = HARNESS / "state" / "autopilot-state.json"
LOCK = HARNESS / "run" / "autopilot.lock"
QUEUE = HARNESS / "run" / "autopilot-queue.jsonl"
NO_DISPATCH_FLAG = HARNESS / "run" / "no-dispatch.flag"
PANE_ASSIGNMENTS = HARNESS / ".pane-assignments"
PANE_LEASE_DIR = HARNESS / "run" / "pane-leases"
QUEUE_TTL_SEC = 3600
KB_PROBE_SCRIPT = HARNESS / "tests" / "test-knowledge-probe-coverage.sh"
KB_PROBE_HEALTH = HARNESS / "state" / "knowledge-probe-health.json"
KB_PROBE_INTERVAL_SEC = int(os.environ.get("SOLAR_KB_PROBE_INTERVAL_SEC", "1800"))
KB_PROBE_TRIGGER_COOLDOWN_SEC = int(os.environ.get("SOLAR_KB_PROBE_TRIGGER_COOLDOWN_SEC", "300"))
KB_PROBE_TIMEOUT_SEC = int(os.environ.get("SOLAR_KB_PROBE_TIMEOUT_SEC", "120"))
MODEL_DOCTOR_HEALTH = HARNESS / "state" / "model-registry-doctor-health.json"
MODEL_DOCTOR_INTERVAL_SEC = int(os.environ.get("SOLAR_MODEL_DOCTOR_INTERVAL_SEC", "1800"))
MODEL_DOCTOR_TIMEOUT_SEC = int(os.environ.get("SOLAR_MODEL_DOCTOR_TIMEOUT_SEC", "120"))

sys.path.insert(0, str(HARNESS / "lib"))
try:
    from runtime_bridge import record_legacy_event
except Exception:  # pragma: no cover - monitor must fail open
    record_legacy_event = None  # type: ignore
try:
    from workflow_guard import route as workflow_route
except Exception:  # pragma: no cover - older harness installs may not have it
    workflow_route = None  # type: ignore
QMD_PROXY_HEALTH = HARNESS / "state" / "qmd-mcp-ipv4-health.json"
TELEMETRY_ONLY_FINDINGS = {
    "knowledge_context_sqlite_only",
    "knowledge_context_timeout",
    "knowledge_probe_failed",
    "model_registry_doctor_failed",
    "runtime_soak_failed",
}


ASK_BOSS_RE = re.compile(r"拍板|要走哪条|你决定|老板.*决定|昊哥拍板|等.*确认|是否.*继续")
COMPACTING_RE = re.compile(r"Compacting conversation|压缩上下文|Compacting", re.I)
PROMPT_IDLE_RE = re.compile(r"Press up to edit queued messages|❯\s*$|Try \"", re.M)
PANE_BUSY_RE = re.compile(
    r"✳|✶|⏺ Bash|Running|Effecting|Swooping|thinking|Cogitating|Churning|Ruminating|Working",
    re.I,
)
SQLITE_ONLY_RE = re.compile(r"sqlite3\s+~?/?.*\.solar/solar\.db", re.I)
CONTEXT_INJECT_RE = re.compile(r"solar-harness\s+context\s+inject|Solar Unified Context", re.I)
CONTEXT_TIMEOUT_RE = re.compile(r"context inject[\s\S]{0,240}timeout\s+\d+s|timeout\s+\d+s[\s\S]{0,240}context inject", re.I)
ACTIVE_STATUSES = {"drafting", "queued", "active", "planning", "approved", "reviewing", "ready_for_review", "needs_human_review", "failed_review"}
GRAPH_READY_HANDOFFS = {"builder", "builder_main", "builder_parallel", "builder-lab"}
GRAPH_EVAL_HANDOFFS = {"evaluator", "reviewer"}

import sys
sys.path.insert(0, str(HARNESS / "lib"))
try:
    from graph_scheduler import load_graph, enqueue_ready, parent_ready_check, validate_graph, blocked_external_prerequisites
except Exception:  # pragma: no cover - fallback for partially installed harnesses
    load_graph = enqueue_ready = parent_ready_check = validate_graph = blocked_external_prerequisites = None
try:
    from graph_node_dispatcher import dispatch_ready as graph_dispatch_ready
    from graph_node_dispatcher import dispatch_node_evals as graph_dispatch_node_evals
except Exception:  # pragma: no cover - graph dispatcher may be absent in scheduler-only tests
    graph_dispatch_ready = graph_dispatch_node_evals = None


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def load_state() -> dict:
    state = load_json(STATE)
    state.setdefault("pane", {})
    state.setdefault("actions", {})
    state.setdefault("target_actions", {})
    state.setdefault("started_at", utc_now())
    # State is cache/projection, not the source of truth. If a sprint was
    # quarantined or deleted, stale action cache entries must not keep nudging
    # panes with dead dispatch text.
    for key in list(state.get("actions", {})):
        sid = key.split(":", 1)[0]
        if sid.startswith("sprint-") and not (SPRINTS / f"{sid}.status.json").exists():
            state["actions"].pop(key, None)
    for key in list(state.get("target_actions", {})):
        result = (state["target_actions"].get(key) or {}).get("result") or {}
        sid = str(result.get("sid") or "")
        if sid.startswith("sprint-") and not (SPRINTS / f"{sid}.status.json").exists():
            state["target_actions"].pop(key, None)
    return state


def save_state(state: dict) -> None:
    state["updated_at"] = utc_now()
    save_json(STATE, state)


def append_event(sid: str, event: str, severity: str = "info", data: dict | None = None) -> None:
    obj = {
        "ts": utc_now(),
        "sprint_id": sid,
        "actor": "solar-autopilot",
        "event": event,
        "severity": severity,
        "data": data or {},
    }
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    if sid:
        with (SPRINTS / f"{sid}.events.jsonl").open("a") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        if record_legacy_event is not None:
            try:
                record_legacy_event(sid, event, "solar-autopilot", data or {}, harness_dir=HARNESS)
            except Exception:
                pass


def ensure_qmd_mcp_ipv4(reason: str) -> dict:
    """Keep the QMD MCP reachable from strict IPv4 clients before KB probes.

    QMD itself may listen only on ::1. Some Solar-Harness context paths probe
    127.0.0.1:8181, so a healthy QMD can look unavailable unless the local
    IPv4 proxy is running. This helper is best-effort and token-free.
    """
    harness_sh = HARNESS / "solar-harness.sh"
    checked_at_epoch = time.time()
    if os.environ.get("SOLAR_SKIP_QMD_MCP_HEAL") == "1":
        result = {
            "ok": True,
            "status": "skipped",
            "reason": reason,
            "skipped": "env_SOLAR_SKIP_QMD_MCP_HEAL",
            "checked_at": utc_now(),
            "checked_at_epoch": checked_at_epoch,
        }
        save_json(QMD_PROXY_HEALTH, result)
        return result
    if not harness_sh.exists():
        result = {
            "ok": False,
            "status": "error",
            "reason": reason,
            "error": "solar_harness_sh_missing",
            "path": str(harness_sh),
            "checked_at": utc_now(),
            "checked_at_epoch": checked_at_epoch,
        }
        save_json(QMD_PROXY_HEALTH, result)
        append_event("", "autopilot_qmd_mcp_ipv4_unavailable", "warn", result)
        return result
    try:
        proc = subprocess.run(
            [str(harness_sh), "wiki", "qmd-mcp", "start"],
            cwd=str(HARNESS),
            text=True,
            capture_output=True,
            timeout=15,
        )
        ok = proc.returncode == 0 and "127.0.0.1:8181" in ((proc.stdout or "") + (proc.stderr or ""))
        result = {
            "ok": ok,
            "status": "ok" if ok else "warn",
            "reason": reason,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-2000:],
            "checked_at": utc_now(),
            "checked_at_epoch": checked_at_epoch,
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "status": "warn",
            "reason": reason,
            "error": "qmd_mcp_start_timeout",
            "timeout_sec": 15,
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
            "checked_at": utc_now(),
            "checked_at_epoch": checked_at_epoch,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "status": "warn",
            "reason": reason,
            "error": f"{type(exc).__name__}: {exc}",
            "checked_at": utc_now(),
            "checked_at_epoch": checked_at_epoch,
        }
    save_json(QMD_PROXY_HEALTH, result)
    append_event(
        "",
        "autopilot_qmd_mcp_ipv4_ready" if result.get("ok") else "autopilot_qmd_mcp_ipv4_unavailable",
        "info" if result.get("ok") else "warn",
        result,
    )
    return result


def run_kb_probe(reason: str, force: bool = False) -> dict:
    """Run the default knowledge retrieval regression probe.

    This is intentionally local and token-free. It proves the default
    Mirage/QMD/Obsidian context path still answers the common probe set instead
    of silently degrading to sqlite-only lookups.
    """
    last = load_json(KB_PROBE_HEALTH)
    now_epoch = time.time()
    if force and last and last.get("reason") == reason and now_epoch - float(last.get("checked_at_epoch", 0)) < KB_PROBE_TRIGGER_COOLDOWN_SEC:
        last["skipped"] = "trigger_cooldown"
        last["reason"] = reason
        return last
    if not force and last and now_epoch - float(last.get("checked_at_epoch", 0)) < KB_PROBE_INTERVAL_SEC:
        last["skipped"] = "cooldown"
        last["reason"] = reason
        return last
    if not KB_PROBE_SCRIPT.exists():
        result = {
            "ok": False,
            "status": "error",
            "reason": reason,
            "error": "kb_probe_script_missing",
            "script": str(KB_PROBE_SCRIPT),
            "checked_at": utc_now(),
            "checked_at_epoch": now_epoch,
        }
        save_json(KB_PROBE_HEALTH, result)
        append_event("", "autopilot_kb_probe_missing", "error", result)
        return result
    qmd_proxy = ensure_qmd_mcp_ipv4(reason)
    try:
        proc = subprocess.run(
            [str(KB_PROBE_SCRIPT)],
            cwd=str(HARNESS),
            text=True,
            capture_output=True,
            timeout=KB_PROBE_TIMEOUT_SEC,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        passed = re.search(r"PROBES_PASSED=(\d+)\s+PROBES_FAILED=(\d+)", output)
        passed_count = int(passed.group(1)) if passed else None
        failed_count = int(passed.group(2)) if passed else None
        ok = proc.returncode == 0 and failed_count == 0
        result = {
            "ok": ok,
            "status": "ok" if ok else "error",
            "reason": reason,
            "returncode": proc.returncode,
            "probes_passed": passed_count,
            "probes_failed": failed_count,
            "stdout_tail": (proc.stdout or "")[-4000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
            "script": str(KB_PROBE_SCRIPT),
            "checked_at": utc_now(),
            "checked_at_epoch": now_epoch,
            "qmd_mcp_ipv4": qmd_proxy,
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "status": "error",
            "reason": reason,
            "error": "kb_probe_timeout",
            "timeout_sec": KB_PROBE_TIMEOUT_SEC,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "script": str(KB_PROBE_SCRIPT),
            "checked_at": utc_now(),
            "checked_at_epoch": now_epoch,
            "qmd_mcp_ipv4": qmd_proxy,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "status": "error",
            "reason": reason,
            "error": f"{type(exc).__name__}: {exc}",
            "script": str(KB_PROBE_SCRIPT),
            "checked_at": utc_now(),
            "checked_at_epoch": now_epoch,
            "qmd_mcp_ipv4": qmd_proxy,
        }
    save_json(KB_PROBE_HEALTH, result)
    append_event(
        "",
        "autopilot_kb_probe_passed" if result.get("ok") else "autopilot_kb_probe_failed",
        "info" if result.get("ok") else "error",
        result,
    )
    return result


def run_model_registry_doctor(reason: str = "periodic", force: bool = False) -> dict:
    """Run model routing single-source guard without touching panes."""
    last = load_json(MODEL_DOCTOR_HEALTH)
    now_epoch = time.time()
    if not force and last and now_epoch - float(last.get("checked_at_epoch", 0)) < MODEL_DOCTOR_INTERVAL_SEC:
        last["skipped"] = "cooldown"
        last["reason"] = reason
        return last

    harness_cmd = HARNESS / "solar-harness.sh"
    if not harness_cmd.exists():
        harness_cmd = HOME / ".solar" / "bin" / "solar-harness"
    if not harness_cmd.exists():
        result = {
            "ok": False,
            "status": "error",
            "reason": reason,
            "error": "solar_harness_command_missing",
            "checked_at": utc_now(),
            "checked_at_epoch": now_epoch,
        }
        save_json(MODEL_DOCTOR_HEALTH, result)
        append_event("", "autopilot_model_registry_doctor_failed", "error", result)
        return result

    try:
        proc = subprocess.run(
            [str(harness_cmd), "models", "doctor"],
            cwd=str(HARNESS),
            text=True,
            capture_output=True,
            timeout=MODEL_DOCTOR_TIMEOUT_SEC,
        )
        ok = proc.returncode == 0
        result = {
            "ok": ok,
            "status": "ok" if ok else "error",
            "reason": reason,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-4000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
            "command": str(harness_cmd),
            "checked_at": utc_now(),
            "checked_at_epoch": now_epoch,
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "status": "error",
            "reason": reason,
            "error": "model_doctor_timeout",
            "timeout_sec": MODEL_DOCTOR_TIMEOUT_SEC,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "command": str(harness_cmd),
            "checked_at": utc_now(),
            "checked_at_epoch": now_epoch,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "status": "error",
            "reason": reason,
            "error": f"{type(exc).__name__}: {exc}",
            "command": str(harness_cmd),
            "checked_at": utc_now(),
            "checked_at_epoch": now_epoch,
        }

    save_json(MODEL_DOCTOR_HEALTH, result)
    append_event(
        "",
        "autopilot_model_registry_doctor_passed" if result.get("ok") else "autopilot_model_registry_doctor_failed",
        "info" if result.get("ok") else "error",
        result,
    )
    return result


def tmux_capture(target: str) -> str:
    try:
        r = subprocess.run(
            ["tmux", "capture-pane", "-t", target, "-p", "-S", "-80"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def tmux_send(target: str, text: str) -> bool:
    if no_dispatch_enabled():
        return False
    try:
        r = subprocess.run(["tmux", "send-keys", "-t", target, text, "Enter"], timeout=2)
        return r.returncode == 0
    except Exception:
        return False


def no_dispatch_enabled() -> bool:
    return os.environ.get("SOLAR_NO_DISPATCH") == "1" or NO_DISPATCH_FLAG.exists()


def pane_safe(target: str) -> str:
    return target.replace(":", "_").replace(".", "_")


def parse_utc(ts: str) -> float:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return 0.0


def pane_lease(target: str) -> dict:
    path = PANE_LEASE_DIR / f"{pane_safe(target)}.json"
    d = load_json(path)
    if not d:
        return {}
    now = time.time()
    exp = parse_utc(d.get("expires_at", ""))
    if exp and exp > now:
        d["active"] = True
        d["seconds_left"] = int(exp - now)
        return d
    return {}


def pane_assignments() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not PANE_ASSIGNMENTS.exists():
        return out
    now = time.time()
    for raw in PANE_ASSIGNMENTS.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        pane, rest = line.split("=", 1)
        parts = rest.rsplit(":", 1)
        sid = parts[0]
        ts = float(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0.0
        out[pane] = {"sid": sid, "assigned_at": ts, "age_sec": int(now - ts) if ts else None}
    return out


def pane_assignment(target: str) -> dict:
    return pane_assignments().get(target, {})


def enqueue_action(finding: dict, reason: str, detail: dict | None = None) -> None:
    if is_telemetry_only_finding(finding):
        append_event(
            finding.get("sid", ""),
            "autopilot_queue_skip_telemetry_only",
            "info",
            {"target": finding.get("target", ""), "type": finding.get("type"), "reason": reason},
        )
        return
    existing_key = f"{finding.get('sid','')}:{finding.get('type','')}:{finding.get('target','')}"
    for old in load_queue():
        old_key = f"{old.get('sid','')}:{old.get('type','')}:{old.get('target','')}"
        if old_key == existing_key:
            return
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    item = {
        "ts": utc_now(),
        "created_at_epoch": time.time(),
        "sid": finding.get("sid", ""),
        "type": finding.get("type", ""),
        "target": finding.get("target", ""),
        "message": finding.get("message", ""),
        "reason": reason,
        "detail": detail or {},
        "attempts": int(finding.get("attempts", 0)),
    }
    with QUEUE.open("a") as q:
        q.write(json.dumps(item, ensure_ascii=False) + "\n")


def is_telemetry_only_finding(finding: dict) -> bool:
    """Signals that must never become pane work items.

    PM pane 0 is the user's intake surface. Autopilot can record PM residue and
    health failures, but must not push remediation prompts into that pane.
    """
    ftype = finding.get("type")
    target = finding.get("target", "")
    role = finding.get("role", "")
    if ftype in TELEMETRY_ONLY_FINDINGS:
        return True
    return ftype == "pane_asks_boss" and (role == "pm" or target == f"{SESSION}:0.0")


def load_queue() -> list[dict]:
    if not QUEUE.exists():
        return []
    items: list[dict] = []
    for raw in QUEUE.read_text(errors="ignore").splitlines():
        try:
            item = json.loads(raw)
        except Exception:
            continue
        if item.get("done") or item.get("expired"):
            continue
        items.append(item)
    return items


def save_queue(items: list[dict]) -> None:
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE.with_suffix(".jsonl.tmp")
    with tmp.open("w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    tmp.replace(QUEUE)


def retry_queue(state: dict, dispatch: bool, cooldown: int) -> list[dict]:
    now_epoch = time.time()
    retained: list[dict] = []
    actions: list[dict] = []
    for item in load_queue():
        sid = item.get("sid", "")
        target = item.get("target", "")
        if is_telemetry_only_finding(item):
            append_event(sid, "autopilot_queue_drop_telemetry_only", "info", {"target": target, "type": item.get("type")})
            actions.append({"sid": sid, "action": item.get("type"), "dropped": "telemetry_only", "target": target})
            continue
        age = now_epoch - float(item.get("created_at_epoch", now_epoch))
        if age > QUEUE_TTL_SEC:
            append_event(sid, "autopilot_queue_expired", "warn", {"target": target, "type": item.get("type"), "age_sec": int(age)})
            actions.append({"sid": sid, "action": item.get("type"), "expired": True, "target": target})
            continue
        if target_recently_dispatched(state, target, cooldown):
            retained.append(item)
            actions.append({"sid": sid, "action": item.get("type"), "queued": True, "reason": "target_cooldown", "target": target})
            continue
        allowed, gate_reason, gate_detail = pane_gate(target, sid)
        if not allowed:
            item["reason"] = gate_reason
            item["detail"] = gate_detail
            retained.append(item)
            actions.append({"sid": sid, "action": item.get("type"), "queued": True, "reason": gate_reason, "target": target})
            continue
        if pane_is_busy(target):
            item["reason"] = "pane_busy"
            retained.append(item)
            actions.append({"sid": sid, "action": item.get("type"), "queued": True, "reason": "pane_busy", "target": target})
            continue
        sent = False
        if dispatch and sid:
            sent = wake_sid(sid)
        elif dispatch and target and item.get("message"):
            sent = tmux_send(target, item["message"])
        item["attempts"] = int(item.get("attempts", 0)) + 1
        if sent:
            append_event(sid, "autopilot_queue_dispatched", "info", {"target": target, "type": item.get("type"), "attempts": item["attempts"]})
            result = {"sid": sid, "action": item.get("type"), "dispatched_from_queue": True, "target": target}
            mark_action(state, {"sid": sid, "type": item.get("type", ""), "target": target}, result)
            actions.append(result)
        else:
            item["reason"] = "dispatch_failed"
            retained.append(item)
            append_event(sid, "autopilot_queue_dispatch_failed", "warn", {"target": target, "type": item.get("type"), "attempts": item["attempts"]})
            actions.append({"sid": sid, "action": item.get("type"), "queued": True, "reason": "dispatch_failed", "target": target})
    save_queue(retained)
    return actions


def pane_gate(target: str, sid: str) -> tuple[bool, str, dict]:
    lease = pane_lease(target)
    if lease and lease.get("sid") != sid:
        return False, "pane_leased", lease
    assignment = pane_assignment(target)
    if assignment and assignment.get("sid") != sid:
        age = assignment.get("age_sec")
        if age is None or age < 1800:
            return False, "pane_assigned", assignment
    return True, "ok", {"lease": lease, "assignment": assignment}


def wake_sid(sid: str) -> bool:
    try:
        r = subprocess.run(
            [str(HOME / ".solar" / "bin" / "solar-harness"), "wake", sid],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return r.returncode == 0
    except Exception:
        return False


def pane_is_busy(target: str) -> bool:
    tail = tmux_capture(target)
    return bool(PANE_BUSY_RE.search(tail)) and not bool(PROMPT_IDLE_RE.search(tail))


def sprint_files(sid: str) -> dict[str, bool]:
    return {
        "status": (SPRINTS / f"{sid}.status.json").exists(),
        "prd": (SPRINTS / f"{sid}.prd.md").exists(),
        "contract": (SPRINTS / f"{sid}.contract.md").exists(),
        "design": (SPRINTS / f"{sid}.design.md").exists(),
        "plan": (SPRINTS / f"{sid}.plan.md").exists(),
        "task_graph": (SPRINTS / f"{sid}.task_graph.json").exists(),
        "handoff": (SPRINTS / f"{sid}.handoff.md").exists(),
        "eval": (SPRINTS / f"{sid}.eval.md").exists() or (SPRINTS / f"{sid}.eval.json").exists(),
    }


def artifact_signature(sid: str) -> dict:
    names = ["status.json", "prd.md", "contract.md", "design.md", "plan.md", "handoff.md", "eval.md", "eval.json", "events.jsonl"]
    items = {}
    max_mtime = 0.0
    for suffix in names:
        path = SPRINTS / f"{sid}.{suffix}"
        if not path.exists():
            continue
        st = path.stat()
        max_mtime = max(max_mtime, st.st_mtime)
        items[suffix] = {"mtime": int(st.st_mtime), "size": st.st_size}
    return {"items": items, "max_mtime": int(max_mtime)}


def tail_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def active_statuses() -> list[dict]:
    rows = []
    for path in sorted(SPRINTS.glob("sprint-*.status.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        d = load_json(path)
        sid = d.get("sprint_id") or d.get("id") or path.name.removesuffix(".status.json")
        if d.get("status") in ACTIVE_STATUSES:
            d["_sid"] = sid
            d["_mtime"] = path.stat().st_mtime
            rows.append(d)
    return rows


def candidate_sid_for_role(role: str) -> str:
    for st in active_statuses():
        handoff = st.get("handoff_to", "")
        phase = st.get("phase", "")
        sid = st.get("_sid", "")
        if role == "planner" and (handoff == "planner" or phase == "prd_ready"):
            return sid
        if role == "builder" and handoff in ("builder", "builder_main", "builder_parallel", "builder-lab"):
            return sid
        if role == "evaluator" and handoff in ("evaluator", "reviewer"):
            return sid
        if role == "pm" and handoff in ("pm", "") and st.get("status") in ("drafting", "queued"):
            return sid
    return ""


def pane_target_for_handoff(handoff: str) -> str:
    if handoff in ("planner", "architect"):
        return f"{SESSION}:0.1"
    if handoff in ("builder", "builder_main", "builder_parallel", "builder-lab"):
        return f"{SESSION}:0.2"
    if handoff in ("evaluator", "reviewer"):
        return f"{SESSION}:0.3"
    return f"{SESSION}:0.0"


def discover_worker_panes() -> list[str]:
    try:
        r = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{session_name}:#{window_index}.#{pane_index}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0:
            panes = [p.strip() for p in r.stdout.splitlines() if p.strip()]
            builders = [p for p in panes if p.startswith(f"{SESSION}:") or p.startswith("solar-harness-lab:")]
            return builders or panes
    except Exception:
        pass
    return [f"{SESSION}:0.2"]


def infer_worker_models(pane: str) -> list[str]:
    if pane.startswith("solar-harness-lab:"):
        if pane.endswith(".3"):
            return ["sonnet", "anthropic-sonnet", "claude-sonnet"]
        return ["glm", "glm-5.1", "zhipu"]
    if pane.endswith(".2"):
        return ["opus", "anthropic-opus", "claude-opus"]
    if pane.endswith(".3"):
        return ["opus", "anthropic-opus", "claude-opus"]
    return ["sonnet"]


def graph_workers() -> list[dict]:
    workers = []
    skills = [
        "bash", "python", "typescript", "docs", "testing",
        "frontend",
        "product", "planning",
        "architecture", "schema", "state-machine", "distributed-systems",
        "routing", "diagnostics", "evaluation", "debug.systematic",
    ]
    capabilities = [
        "bash", "python", "typescript", "docs", "testing",
        "frontend", "observability",
        "documentation", "schema", "state-machine", "storage", "sources",
        "code.review", "debug.systematic", "skill.methodology",
        "workflow.planning", "product.requirements", "test.tdd", "browser.browse", "browser.qa",
        "architecture", "distributed-systems", "evaluation",
        "research.scope_rewrite", "research.source_matrix", "research.evidence.extract",
        "research.claim.mine", "research.citation.verify", "research.report.compile",
        "document.convert", "document.markdown_extract",
        "ruflo.swarm", "ruflo.plugins", "ruflo.agent_catalog",
        "ruflo.memory", "ruflo.mcp", "ruflo.workflow_templates",
    ]
    for pane in discover_worker_panes():
        lease = pane_lease(pane)
        busy = bool(lease) or pane_is_busy(pane)
        workers.append(
            {
                "pane": pane,
                "models": infer_worker_models(pane),
                "skills": skills,
                "capabilities": capabilities,
                "busy": busy,
                "lease": lease,
            }
        )
    return workers


def graph_path_for(sid: str) -> Path:
    return SPRINTS / f"{sid}.task_graph.json"


def sprint_status_payload(sid: str) -> dict:
    path = SPRINTS / f"{sid}.status.json"
    if not path.exists():
        return {}
    return load_json(path)


def sprint_passed(sid: str) -> bool:
    return str(sprint_status_payload(sid).get("status", "")).lower() in {"passed", "completed", "eval_passed"}


def epic_dep_passed(dep_node: dict) -> bool:
    dep_sid = str(dep_node.get("child_sprint_id") or "")
    dep_node_state = str(dep_node.get("status") or "").lower()
    return dep_node_state in {"passed", "completed", "eval_passed"} or (dep_sid and sprint_passed(dep_sid))


def epic_child_dependency_ready(sid: str) -> tuple[bool, list[str]]:
    status = sprint_status_payload(sid)
    epic_id = str(status.get("epic_id") or "")
    if not epic_id:
        return True, []
    graph_path = SPRINTS / f"{epic_id}.task_graph.json"
    if not graph_path.exists():
        return True, []
    graph = load_json(graph_path)
    nodes = [n for n in graph.get("nodes", []) if isinstance(n, dict)]
    by_id = {str(n.get("id")): n for n in nodes if n.get("id")}
    child_node = None
    for node in nodes:
        if str(node.get("child_sprint_id") or "") == sid:
            child_node = node
            break
    if not child_node:
        return True, []
    blocked_by: list[str] = []
    for dep in child_node.get("depends_on", []) or []:
        dep_node = by_id.get(str(dep), {})
        dep_sid = str(dep_node.get("child_sprint_id") or "")
        if dep_sid and not epic_dep_passed(dep_node):
            blocked_by.append(dep_sid)
    return not blocked_by, blocked_by


def child_graph_external_prerequisite_blocks(sid: str) -> list[dict]:
    graph_path = SPRINTS / f"{sid}.task_graph.json"
    if not graph_path.exists():
        return []
    graph = load_json(graph_path)
    entries: list[str] = []
    for raw in graph.get("prerequisites") or []:
        if str(raw).strip():
            entries.append(str(raw).strip())
    policy = graph.get("dependency_policy") or {}
    if isinstance(policy, dict):
        for raw in policy.get("blocks_until") or []:
            if str(raw).strip():
                entries.append(str(raw).strip())
    blocked: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        if entry in seen:
            continue
        seen.add(entry)
        if ":" in entry:
            upstream_sid, required = entry.rsplit(":", 1)
        else:
            upstream_sid, required = entry, "passed"
        upstream_sid = upstream_sid.strip()
        required = (required.strip().lower() or "passed")
        status = sprint_status_payload(upstream_sid)
        current_status = str(status.get("status") or "").lower()
        current_phase = str(status.get("phase") or "").lower()
        ok = current_status == "passed" if required == "passed" else (
            current_status == required or current_phase == required
        )
        if not ok:
            blocked.append({
                "requirement": entry,
                "sprint_id": upstream_sid,
                "required": required,
                "current_status": current_status,
                "current_phase": current_phase,
                "reason": "status_not_satisfied" if status else "missing_status",
            })
    return blocked


def set_epic_child_node_status(sid: str, node_status: str) -> bool:
    status = sprint_status_payload(sid)
    epic_id = str(status.get("epic_id") or "")
    if not epic_id:
        return False
    graph_path = SPRINTS / f"{epic_id}.task_graph.json"
    if not graph_path.exists():
        return False
    graph = load_json(graph_path)
    changed = False
    for node in graph.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        if str(node.get("child_sprint_id") or "") != sid:
            continue
        if str(node.get("status") or "") != node_status:
            node["status"] = node_status
            node["updated_at"] = utc_now()
            changed = True
    if changed:
        save_json(graph_path, graph)
    return changed


def inspect_epics() -> list[dict]:
    findings = []
    for meta_path in sorted(SPRINTS.glob("epic-*.epic.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = load_json(meta_path)
        epic_id = meta.get("epic_id") or meta_path.name.removesuffix(".epic.json")
        graph_path = SPRINTS / f"{epic_id}.task_graph.json"
        if not graph_path.exists():
            continue
        graph = load_json(graph_path)
        nodes = [n for n in graph.get("nodes", []) if isinstance(n, dict)]
        by_id = {str(n.get("id")): n for n in nodes if n.get("id")}
        ready = []
        blocked = []
        for node in nodes:
            child_sid = str(node.get("child_sprint_id") or "")
            if not child_sid:
                continue
            st = sprint_status_payload(child_sid)
            if str(st.get("status", "")).lower() not in {"queued", "drafting"}:
                continue
            missing = []
            for dep in node.get("depends_on", []) or []:
                dep_node = by_id.get(str(dep), {})
                dep_sid = str(dep_node.get("child_sprint_id") or "")
                if dep_sid and not epic_dep_passed(dep_node):
                    missing.append(dep_sid)
            if missing:
                blocked.append({"sid": child_sid, "blocked_by": missing})
            else:
                child_graph_blocked = child_graph_external_prerequisite_blocks(child_sid)
                route = workflow_guard_route(child_sid)
                if child_graph_blocked or route.get("reason") == "external_prerequisite_blocked":
                    blocked.append({
                        "sid": child_sid,
                        "blocked_by": child_graph_blocked or route.get("blocked_prerequisites", []),
                    })
                    continue
                ready.append({"sid": child_sid, "node_id": node.get("id")})
        if ready:
            findings.append(
                {
                    "sid": str(epic_id),
                    "type": "epic_ready_children",
                    "severity": "info",
                    "target": "",
                    "message": f"{epic_id} has dependency-ready child sprints.",
                    "ready_children": ready,
                    "blocked_children": blocked,
                }
            )
    return findings


def inspect_epic_child_state_drift() -> list[dict]:
    """Find child sprints whose live state violates parent DAG dependencies."""
    findings: list[dict] = []
    for meta_path in sorted(SPRINTS.glob("epic-*.epic.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = load_json(meta_path)
        epic_id = str(meta.get("epic_id") or meta_path.name.removesuffix(".epic.json"))
        graph_path = SPRINTS / f"{epic_id}.task_graph.json"
        if not graph_path.exists():
            continue
        graph = load_json(graph_path)
        nodes = [n for n in graph.get("nodes", []) if isinstance(n, dict)]
        by_id = {str(n.get("id")): n for n in nodes if n.get("id")}
        for node in nodes:
            sid = str(node.get("child_sprint_id") or "")
            if not sid:
                continue
            status = sprint_status_payload(sid)
            child_state = str(status.get("status", "")).lower()
            if child_state not in {"active", "approved", "reviewing", "ready_for_review"}:
                continue
            blocked_by: list[str] = []
            for dep in node.get("depends_on", []) or []:
                dep_node = by_id.get(str(dep), {})
                dep_sid = str(dep_node.get("child_sprint_id") or "")
                if dep_sid and not epic_dep_passed(dep_node):
                    blocked_by.append(dep_sid)
            if blocked_by:
                findings.append(
                    {
                        "sid": sid,
                        "type": "epic_child_dependency_blocked",
                        "severity": "warn",
                        "target": "",
                        "message": f"{sid} is active before dependencies passed; autopilot will downgrade to queued.",
                        "blocked_by": blocked_by,
                        "epic_id": epic_id,
                    }
                )
    return findings


def graph_status(sid: str) -> dict:
    path = graph_path_for(sid)
    if not path.exists() or load_graph is None:
        return {"exists": path.exists(), "ready": False, "path": str(path)}
    try:
        graph = load_graph(path)
        validation = validate_graph(graph) if validate_graph else {"ok": False, "errors": ["graph_scheduler_unavailable"]}
        parent = parent_ready_check(graph) if parent_ready_check else {"ready": False}
        return {
            "exists": True,
            "path": str(path),
            "valid": bool(validation.get("ok")),
            "validation": validation,
            "parent_ready": bool(parent.get("ready")),
            "parent": parent,
        }
    except Exception as exc:
        return {"exists": True, "ready": False, "path": str(path), "valid": False, "error": str(exc)}


def assigned_graph_node_for_pane(target: str) -> dict:
    if load_graph is None:
        return {}
    active_node_statuses = {"assigned", "dispatched", "in_progress", "running"}
    for status in active_statuses():
        sid = status.get("_sid") or status.get("sprint_id") or status.get("id")
        if not sid:
            continue
        path = graph_path_for(str(sid))
        if not path.exists():
            continue
        try:
            graph = load_graph(path)
        except Exception:
            continue
        for node in graph.get("nodes", []):
            node_status = str(node.get("status") or "").lower()
            if node.get("assigned_to") != target or node_status not in active_node_statuses:
                continue
            node_id = str(node.get("id") or "")
            handoff = SPRINTS / f"{sid}.{node_id}-handoff.md"
            if handoff.exists():
                continue
            return {
                "sid": str(sid),
                "node_id": node_id,
                "status": node_status,
                "graph": str(path),
                "dispatch_file": str(SPRINTS / f"{sid}.{node_id}-dispatch.md"),
                "dispatch_id": node.get("dispatch_id", ""),
            }
    return {}


def dispatch_ready_graph_nodes(sid: str, lease: bool = True) -> dict:
    if no_dispatch_enabled():
        return {"ok": False, "reason": "no_dispatch_flag", "sprint_id": sid, "dispatched": [], "skipped": []}
    path = graph_path_for(sid)
    if not path.exists():
        return {"ok": False, "reason": "task_graph_missing", "path": str(path)}
    if load_graph is None or validate_graph is None:
        return {"ok": False, "reason": "graph_scheduler_unavailable"}
    graph = load_graph(path)
    validation = validate_graph(graph) if validate_graph else {"ok": False, "errors": ["graph_scheduler_unavailable"]}
    if not validation.get("ok"):
        return {"ok": False, "reason": "task_graph_invalid", "validation": validation}
    if graph_dispatch_ready is not None and graph_dispatch_node_evals is not None:
        evals = graph_dispatch_node_evals(str(path), dry_run=not lease, ttl=900)
        ready = graph_dispatch_ready(str(path), dry_run=not lease, ttl=900)
        return {
            "ok": bool(evals.get("ok")) and bool(ready.get("ok")),
            "evals": evals,
            "ready": ready,
        }
    if enqueue_ready is None:
        return {"ok": False, "reason": "graph_dispatcher_unavailable"}
    result = enqueue_ready(graph, str(path), graph_workers(), max_parallel=8, lease=lease, ttl=900)
    from graph_scheduler import save_graph  # imported late so older installs can still inspect
    save_graph(path, graph)
    return {"ok": result.get("ok"), "ready": result}


def instruction_for(status: dict, files: dict[str, bool]) -> str:
    sid = status.get("sprint_id") or status.get("id") or ""
    handoff = status.get("handoff_to", "")
    if handoff == "planner" and files["prd"] and not files["plan"]:
        return (
            f"请接手 {sid}：读取 .prd.md 和 .contract.md，产出 {sid}.plan.md 和 {sid}.task_graph.json。"
            "task_graph 必须通过 solar-harness graph-scheduler validate。不要问用户拍板；这是 P0 reliability 默认推进。"
        )
    if handoff in ("builder", "builder_main", "builder_parallel", "builder-lab") and files["plan"] and not files["handoff"]:
        return (
            f"请接手 {sid}：按 plan/contract 实现并写 {sid}.handoff.md。"
            "先跑验收命令，缺口写清楚。"
        )
    if handoff in ("evaluator", "reviewer") and files["handoff"] and not files["eval"]:
        return f"请评审 {sid}：读取 handoff/contract，产出 eval.md/eval.json。"
    return ""


def workflow_guard_route(sid: str) -> dict:
    if workflow_route is None:
        return {}
    try:
        return workflow_route(sid)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def normalize_status_to_workflow_route(sid: str, status: dict, route: dict) -> bool:
    role = str(route.get("route_role") or "")
    stage = str(route.get("stage") or "")
    if role == "none" and stage == "done":
        fields = ("passed", "completed", "done", "done")
    elif not role or role == "pm":
        return False
    else:
        fields = {
            "planner": ("drafting", "prd_ready", "planner", "planner"),
            "builder_main": ("active", "planning_complete", "builder_main", "builder_main"),
            "builder": ("active", "planning_complete", "builder", "builder"),
            "evaluator": ("reviewing", "handoff_ready", "evaluator", "evaluator"),
        }.get(role)
        if not fields:
            return False
    new_status, new_phase, handoff, target_role = fields
    changed = any(
        str(status.get(k, "")) != v
        for k, v in {
            "status": new_status,
            "phase": new_phase,
            "handoff_to": handoff,
            "target_role": target_role,
        }.items()
    )
    if not changed:
        return False
    status.update(
        {
            "status": new_status,
            "phase": new_phase,
            "handoff_to": handoff,
            "target_role": target_role,
            "updated_at": utc_now(),
        }
    )
    hist = status.setdefault("history", [])
    if isinstance(hist, list):
        hist.append(
            {
                "ts": utc_now(),
                "event": "autopilot_workflow_route_normalized",
                "by": "solar-autopilot",
                "route_role": role,
                "stage": stage,
                "reason": route.get("reason", ""),
            }
        )
    save_json(SPRINTS / f"{sid}.status.json", status)
    append_event(
        sid,
        "autopilot_workflow_route_normalized",
        "info",
        {"route_role": role, "stage": stage, "reason": route.get("reason", "")},
    )
    return True


def inspect_sprints() -> list[dict]:
    raw_findings = []
    for path in sorted(SPRINTS.glob("sprint-*.status.json")):
        status = load_json(path)
        sid = status.get("sprint_id") or status.get("id") or path.name.removesuffix(".status.json")
        files = sprint_files(sid)
        st = status.get("status", "")
        phase = status.get("phase", "")
        handoff = status.get("handoff_to", "")
        priority = status.get("priority", "")
        if st not in ACTIVE_STATUSES:
            continue
        dep_ready, blocked_by = epic_child_dependency_ready(str(sid))
        if not dep_ready:
            raw_findings.append(
                {
                    "sid": sid,
                    "type": "epic_child_dependency_blocked",
                    "severity": "warn",
                    "target": "",
                    "blocked_by": blocked_by,
                    "message": "Epic child sprint dependency is not satisfied; keep queued and do not dispatch.",
                }
            )
            continue

        route = workflow_guard_route(str(sid))
        if route.get("reason") == "external_prerequisite_blocked":
            raw_findings.append(
                {
                    "sid": sid,
                    "type": "epic_child_dependency_blocked",
                    "severity": "warn",
                    "target": "",
                    "blocked_by": route.get("blocked_prerequisites", []),
                    "message": "Child task_graph prerequisite is not satisfied; keep queued and do not dispatch.",
                }
            )
            continue
        if route.get("ok") and not route.get("violations"):
            if normalize_status_to_workflow_route(str(sid), status, route):
                status = load_json(path)
                st = status.get("status", "")
                phase = status.get("phase", "")
                handoff = status.get("handoff_to", "")

        if priority == "P0" and files["contract"] and not files["prd"]:
            raw_findings.append(
                {
                    "sid": sid,
                    "type": "missing_prd",
                    "severity": "warn",
                    "safe_default": "write_prd_or_escalate_to_codex_pm",
                    "message": "P0 has contract/evidence but no PRD.",
                }
            )
        if files["prd"] and handoff == "planner" and not files["plan"]:
            raw_findings.append(
                {
                    "sid": sid,
                    "type": "ready_for_planner",
                    "severity": "info",
                    "target": pane_target_for_handoff(handoff),
                    "message": instruction_for(status, files),
                }
            )
        if files["plan"] and not files["task_graph"] and handoff in GRAPH_READY_HANDOFFS:
            raw_findings.append(
                {
                    "sid": sid,
                    "type": "missing_task_graph",
                    "severity": "warn",
                    "target": pane_target_for_handoff("planner"),
                    "message": (
                        f"{sid} 已有 plan.md 但缺 task_graph.json。请补机器可执行 DAG，"
                        "并运行 graph-scheduler validate；未补前禁止粗派发给 builder。"
                    ),
                }
            )
        if files["plan"] and files["task_graph"] and handoff in (GRAPH_READY_HANDOFFS | GRAPH_EVAL_HANDOFFS):
            gs = graph_status(sid)
            if gs.get("parent_ready"):
                raw_findings.append(
                    {
                        "sid": sid,
                        "type": "graph_parent_ready",
                        "severity": "info",
                        "target": pane_target_for_handoff("evaluator"),
                        "message": f"{sid} DAG 全部 gate 已通过，请做 parent eval/closeout。",
                        "graph": gs,
                    }
                )
            elif gs.get("valid"):
                raw_findings.append(
                    {
                        "sid": sid,
                        "type": "graph_ready_nodes",
                        "severity": "info",
                        "target": "",
                        "message": (
                            f"{sid} task_graph valid；autopilot 将派发 ready DAG nodes "
                            "并处理 reviewing node evaluator。"
                        ),
                        "graph": gs,
                    }
                )
            else:
                raw_findings.append(
                    {
                        "sid": sid,
                        "type": "invalid_task_graph",
                        "severity": "warn",
                        "target": pane_target_for_handoff("planner"),
                        "message": f"{sid} task_graph.json 无效，请修复后再派发 builder。",
                        "graph": gs,
                    }
                )
        if files["plan"] and not files["task_graph"] and handoff in ("builder", "builder_main", "builder_parallel", "builder-lab") and not files["handoff"]:
            raw_findings.append(
                {
                    "sid": sid,
                    "type": "ready_for_builder",
                    "severity": "info",
                    "target": pane_target_for_handoff(handoff),
                    "message": instruction_for(status, files),
                }
            )
        if st in ("active", "approved", "reviewing") and phase and not files["plan"] and not files["handoff"] and handoff in ("builder", "builder_main", "builder_parallel", "builder-lab"):
            raw_findings.append(
                {
                    "sid": sid,
                    "type": "active_without_handoff",
                    "severity": "warn",
                    "target": pane_target_for_handoff(handoff),
                    "message": instruction_for(status, files),
                }
            )
        if files["handoff"] and not files["task_graph"] and handoff in ("evaluator", "reviewer") and not files["eval"]:
            raw_findings.append(
                {
                    "sid": sid,
                    "type": "ready_for_evaluator",
                    "severity": "info",
                    "target": pane_target_for_handoff(handoff),
                    "message": instruction_for(status, files),
                }
            )
    p0 = [f for f in raw_findings if load_json(SPRINTS / f"{f.get('sid')}.status.json").get("priority") == "P0"]
    return p0 or raw_findings


def inspect_panes(state: dict, stall_seconds: int) -> list[dict]:
    findings = []
    now_epoch = time.time()
    for idx, role in enumerate(("pm", "planner", "builder", "evaluator")):
        target = f"{SESSION}:0.{idx}"
        tail = tmux_capture(target)
        h = tail_hash(tail)
        prev = state["pane"].get(target, {})
        changed = h != prev.get("hash")
        unchanged_for = 0 if changed else int(now_epoch - float(prev.get("seen_at", now_epoch)))
        if changed:
            state["pane"][target] = {"hash": h, "seen_at": now_epoch, "role": role}
        if ASK_BOSS_RE.search(tail):
            # PM pane is the user's intake surface. If it is stuck in Claude
            # Rewind/interrupt UI or contains old prompt residue, do not send
            # another auto-reply into the same pane. Record the signal only.
            if role == "pm" and ("Rewind" in tail or "Interrupted · What should Claude do instead?" in tail):
                findings.append(
                    {
                        "sid": "",
                        "type": "pm_pane_interrupt_residue",
                        "severity": "warn",
                        "target": target,
                        "role": role,
                        "message": "PM pane contains interrupt/Rewind residue; do not auto-dispatch into user intake pane.",
                    }
                )
                continue
            sid = candidate_sid_for_role(role)
            if sid:
                findings.append(
                    {
                        "sid": sid,
                        "type": "pane_asks_boss",
                        "severity": "warn",
                        "target": target,
                        "role": role,
                        "message": "不要等待用户拍板；按当前 sprint 合约和 safe default 继续推进。若需要交接，请写明 artifact 并更新 status.json。",
                    }
                )
        if COMPACTING_RE.search(tail) and unchanged_for >= stall_seconds:
            sid = candidate_sid_for_role(role)
            if sid:
                findings.append(
                    {
                        "sid": sid,
                        "type": "pane_compacting_stall",
                        "severity": "warn",
                        "target": target,
                        "role": role,
                        "unchanged_for_sec": unchanged_for,
                        "message": f"{role} pane compacting/stalled; re-wake sprint {sid} to continue missing artifact work.",
                    }
                )
        if PROMPT_IDLE_RE.search(tail) and not PANE_BUSY_RE.search(tail):
            graph_node = assigned_graph_node_for_pane(target)
            if graph_node:
                findings.append(
                    {
                        "sid": graph_node["sid"],
                        "type": "graph_node_idle_assigned",
                        "severity": "warn",
                        "target": target,
                        "role": role,
                        "graph_node": graph_node,
                        "message": (
                            f"继续执行 DAG node {graph_node['node_id']}，不要等待用户输入继续。"
                            f"读取并完成 {graph_node['dispatch_file']}；完成后写 handoff 并标记 reviewing。"
                        ),
                    }
                )
                continue
            sid = candidate_sid_for_role(role)
            if sid:
                status = load_json(SPRINTS / f"{sid}.status.json")
                files = sprint_files(sid)
                if files.get("task_graph"):
                    continue
                msg = instruction_for(status, files)
                if msg:
                    findings.append(
                        {
                            "sid": sid,
                            "type": "pane_idle_with_pending_artifact",
                            "severity": "info",
                            "target": target,
                            "role": role,
                            "message": msg,
                        }
                    )
    # Lab builders also receive DAG nodes. They are not covered by the fixed
    # main-screen role loop above, so resume assigned lab nodes explicitly when
    # the pane returns to prompt without a node handoff.
    for target in discover_worker_panes():
        if not target.startswith("solar-harness-lab:"):
            continue
        tail = tmux_capture(target)
        if not PROMPT_IDLE_RE.search(tail) or PANE_BUSY_RE.search(tail):
            continue
        graph_node = assigned_graph_node_for_pane(target)
        if not graph_node:
            continue
        findings.append(
            {
                "sid": graph_node["sid"],
                "type": "graph_node_idle_assigned",
                "severity": "warn",
                "target": target,
                "role": "lab-builder",
                "graph_node": graph_node,
                "message": (
                    f"继续执行 DAG node {graph_node['node_id']}，不要等待用户输入继续。"
                    f"读取并完成 {graph_node['dispatch_file']}；完成后写 handoff 并标记 reviewing。"
                ),
            }
        )
    return findings


def inspect_knowledge_context(state: dict) -> list[dict]:
    """Detect default-context regressions and run the KB probe automatically.

    The user-facing failure mode is a pane answering with sqlite-only lookup or
    timing out on `solar-harness context inject`. Both mean the default
    knowledge path may be broken even if the underlying pages exist.
    """
    findings: list[dict] = []
    force_probe = False
    reasons: list[str] = []
    for idx, role in enumerate(("pm", "planner", "builder", "evaluator")):
        target = f"{SESSION}:0.{idx}"
        tail = tmux_capture(target)
        has_sqlite = bool(SQLITE_ONLY_RE.search(tail))
        has_context = bool(CONTEXT_INJECT_RE.search(tail))
        if has_sqlite and not has_context:
            force_probe = True
            reasons.append(f"{target}:sqlite_only")
            findings.append(
                {
                    "sid": "",
                    "type": "knowledge_context_sqlite_only",
                    "severity": "warn",
                    "target": target,
                    "role": role,
                    "message": "检测到 pane 使用 sqlite3 ~/.solar/solar.db 且未看到 solar-harness context inject；自动运行 KB probe。",
                }
            )
        if CONTEXT_TIMEOUT_RE.search(tail):
            force_probe = True
            reasons.append(f"{target}:context_timeout")
            findings.append(
                {
                    "sid": "",
                    "type": "knowledge_context_timeout",
                    "severity": "warn",
                    "target": target,
                    "role": role,
                    "message": "检测到 context inject timeout；自动运行 KB probe 并记录健康状态。",
                }
            )
    reason = ",".join(reasons) if reasons else "periodic"
    probe = run_kb_probe(reason, force=force_probe)
    if probe.get("ok"):
        state["knowledge_probe"] = {
            "status": "ok",
            "checked_at": probe.get("checked_at"),
            "probes_passed": probe.get("probes_passed"),
            "probes_failed": probe.get("probes_failed"),
            "reason": probe.get("reason"),
        }
    else:
        findings.append(
            {
                "sid": "",
                "type": "knowledge_probe_failed",
                "severity": "error",
                "target": f"{SESSION}:0.0",
                "role": "pm",
                "message": (
                    "KB probe failed；默认知识路径可能不可用。先不要只查 sqlite，"
                    "请检查 state/knowledge-probe-health.json 和 tests/test-knowledge-probe-coverage.sh 输出。"
                ),
                "probe": probe,
            }
        )
        state["knowledge_probe"] = {
            "status": "error",
            "checked_at": probe.get("checked_at"),
            "probes_passed": probe.get("probes_passed"),
            "probes_failed": probe.get("probes_failed"),
            "reason": probe.get("reason"),
        }
    return findings


def inspect_model_registry(state: dict) -> list[dict]:
    """Periodically verify model routing has not drifted back to hardcoding."""
    probe = run_model_registry_doctor("periodic", force=False)
    state["model_registry_doctor"] = {
        "status": "ok" if probe.get("ok") else "error",
        "checked_at": probe.get("checked_at"),
        "reason": probe.get("reason"),
        "skipped": probe.get("skipped", ""),
    }
    if probe.get("ok"):
        return []
    return [
        {
            "sid": "",
            "type": "model_registry_doctor_failed",
            "severity": "error",
            "target": "",
            "role": "autopilot",
            "message": "models doctor failed；模型路由单一事实源可能漂移。检查 state/model-registry-doctor-health.json。",
            "probe": probe,
        }
    ]


def should_act(state: dict, finding: dict, cooldown: int) -> bool:
    key = f"{finding.get('sid','')}:{finding.get('type','')}:{finding.get('target','')}"
    last = float(state["actions"].get(key, {}).get("at", 0))
    return (time.time() - last) >= cooldown


def mark_action(state: dict, finding: dict, result: dict) -> None:
    key = f"{finding.get('sid','')}:{finding.get('type','')}:{finding.get('target','')}"
    state["actions"][key] = {"at": time.time(), "ts": utc_now(), "result": result}
    target = finding.get("target", "")
    if target and result.get("dispatched"):
        state["target_actions"][target] = {"at": time.time(), "ts": utc_now(), "result": result}


def target_recently_dispatched(state: dict, target: str, cooldown: int) -> bool:
    if not target:
        return False
    last = float(state.get("target_actions", {}).get(target, {}).get("at", 0))
    return (time.time() - last) < cooldown


def apply_findings(findings: list[dict], dispatch: bool, state: dict, cooldown: int) -> list[dict]:
    actions = []
    used_targets = set()
    for f in findings:
        sid = f.get("sid", "")
        ftype = f.get("type", "")
        target = f.get("target", "")
        if is_telemetry_only_finding(f):
            append_event(sid, f"autopilot_{ftype}", f.get("severity", "warn"), f)
            result = {
                "sid": sid,
                "action": ftype,
                "target": target,
                "dispatched": False,
                "recorded_only": True,
            }
            mark_action(state, f, result)
            actions.append(result)
            continue
        if target and target in used_targets:
            actions.append({"sid": sid, "action": ftype, "skipped": "target_already_used_this_scan", "target": target})
            continue
        if not should_act(state, f, cooldown):
            actions.append({"sid": sid, "action": ftype, "skipped": "cooldown", "target": target})
            continue
        if target_recently_dispatched(state, target, cooldown):
            actions.append({"sid": sid, "action": ftype, "skipped": "target_cooldown", "target": target})
            continue
        if dispatch and target:
            allowed, gate_reason, gate_detail = pane_gate(target, sid)
            if not allowed:
                enqueue_action(f, gate_reason, gate_detail)
                append_event(sid, "autopilot_dispatch_queued_pane_occupied", "warn", {"target": target, "type": ftype, "reason": gate_reason, "detail": gate_detail})
                result = {"sid": sid, "action": ftype, "queued": True, "reason": gate_reason, "target": target}
                mark_action(state, f, result)
                actions.append(result)
                continue
        if dispatch and target and pane_is_busy(target):
            append_event(sid, "autopilot_dispatch_deferred_pane_busy", "warn", {"target": target, "type": ftype})
            enqueue_action(f, "pane_busy", {})
            result = {"sid": sid, "action": ftype, "skipped": "pane_busy", "target": target}
            mark_action(state, f, result)
            actions.append(result)
            continue
        if ftype in ("graph_ready_nodes",):
            result = dispatch_ready_graph_nodes(sid, lease=dispatch)
            append_event(sid, "autopilot_graph_enqueue_ready", "info" if result.get("ok") else "warn", result)
            mark_action(state, f, {"sid": sid, "action": ftype, **result})
            actions.append({"sid": sid, "action": ftype, **result})
        elif ftype == "epic_ready_children":
            # This is a local metadata transition, not a pane dispatch. Use the
            # library entrypoint so tests and alternate HARNESS_DIR installs do
            # not accidentally activate the user's real sprint directory.
            cmd = [sys.executable, str(HARNESS / "lib" / "epic_decomposer.py"), "activate-ready", sid, "--max", "2", "--json"]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                payload = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {"stdout": proc.stdout[-2000:]}
                result = {"sid": sid, "action": ftype, "ok": proc.returncode == 0, "returncode": proc.returncode, **payload}
            except Exception as exc:
                result = {"sid": sid, "action": ftype, "ok": False, "error": str(exc)}
            append_event(sid, "autopilot_epic_activate_ready", "info" if result.get("ok") else "warn", result)
            mark_action(state, f, result)
            actions.append(result)
        elif ftype == "graph_node_idle_assigned":
            append_event(sid, "autopilot_graph_node_idle_resume", "warn", f.get("graph_node", {}))
            sent = False
            if dispatch and target and f.get("message"):
                sent = tmux_send(target, f["message"])
            result = {"sid": sid, "action": ftype, "target": target, "dispatched": sent, "graph_node": f.get("graph_node", {})}
            if sent and target:
                used_targets.add(target)
            mark_action(state, f, result)
            actions.append(result)
        elif ftype == "epic_child_dependency_blocked":
            status_path = SPRINTS / f"{sid}.status.json"
            status = load_json(status_path)
            status.update({
                "status": "queued",
                "phase": "epic_waiting_dependency",
                "handoff_to": "",
                "target_role": "",
                "updated_at": utc_now(),
            })
            hist = status.setdefault("history", [])
            if isinstance(hist, list):
                hist.append({
                    "ts": utc_now(),
                    "event": "autopilot_epic_child_dependency_blocked",
                    "by": "solar-autopilot",
                    "note": "Dependency not satisfied; dispatch suppressed.",
                    "blocked_by": f.get("blocked_by", []),
                })
            save_json(status_path, status)
            graph_updated = set_epic_child_node_status(sid, "pending")
            append_event(sid, "autopilot_epic_child_dependency_blocked", "warn", {"blocked_by": f.get("blocked_by", [])})
            result = {
                "sid": sid,
                "action": ftype,
                "queued": True,
                "blocked_by": f.get("blocked_by", []),
                "parent_graph_updated": graph_updated,
            }
            mark_action(state, f, result)
            actions.append(result)
        elif ftype in ("graph_parent_ready",):
            append_event(sid, "autopilot_graph_parent_ready", "info", f.get("graph", {}))
            sent = False
            if dispatch and sid:
                sent = wake_sid(sid)
            result = {"sid": sid, "action": ftype, "target": f.get("target", ""), "dispatched": sent}
            if sent and target:
                used_targets.add(target)
            mark_action(state, f, result)
            actions.append(result)
        elif ftype in ("missing_task_graph", "invalid_task_graph"):
            append_event(sid, f"autopilot_{ftype}", "warn", f.get("graph", {}))
            sent = False
            if dispatch and sid:
                sent = wake_sid(sid)
            elif dispatch and f.get("message") and f.get("target"):
                sent = tmux_send(f["target"], f["message"])
            result = {"sid": sid, "action": ftype, "target": f.get("target", ""), "dispatched": sent}
            if sent and target:
                used_targets.add(target)
            mark_action(state, f, result)
            actions.append(result)
        elif ftype in ("ready_for_planner", "ready_for_builder", "ready_for_evaluator", "active_without_handoff", "pane_compacting_stall", "pane_idle_with_pending_artifact"):
            status_path = SPRINTS / f"{sid}.status.json"
            status = load_json(status_path)
            hist = status.setdefault("history", [])
            hist.append(
                {
                    "ts": utc_now(),
                    "event": f"autopilot_{ftype}",
                    "by": "solar-autopilot",
                    "note": f.get("message", ""),
                }
            )
            status["updated_at"] = utc_now()
            if ftype == "ready_for_planner":
                status["phase"] = "spec"
            save_json(status_path, status)
            append_event(sid, f"autopilot_{ftype}", f.get("severity", "info"), {"target": f.get("target", "")})
            sent = False
            if dispatch and sid:
                sent = wake_sid(sid)
            elif dispatch and f.get("message") and f.get("target"):
                sent = tmux_send(f["target"], f["message"])
            result = {"sid": sid, "action": ftype, "dispatched": sent, "target": f.get("target", "")}
            if sent and target:
                used_targets.add(target)
            mark_action(state, f, result)
            actions.append(result)
        elif ftype == "pane_asks_boss":
            append_event("", "autopilot_detected_boss_question", "warn", f)
            sent = False
            if f.get("role") == "pm" or f.get("target") == f"{SESSION}:0.0":
                sent = False
            elif dispatch and sid:
                sent = wake_sid(sid)
            elif dispatch and f.get("target"):
                sent = tmux_send(f["target"], f.get("message", "不要等待用户拍板；按 safe default 继续。"))
            result = {"sid": sid, "action": ftype, "target": f.get("target", ""), "dispatched": sent}
            if sent and target:
                used_targets.add(target)
            mark_action(state, f, result)
            actions.append(result)
        elif ftype == "pm_pane_interrupt_residue":
            append_event("", "autopilot_pm_pane_interrupt_residue", "warn", f)
            result = {"sid": sid, "action": ftype, "target": f.get("target", ""), "dispatched": False, "recorded_only": True}
            mark_action(state, f, result)
            actions.append(result)
        elif ftype == "missing_prd":
            append_event(sid, "autopilot_missing_prd", "warn", f)
            result = {"sid": sid, "action": ftype, "requires_codex_pm": True}
            mark_action(state, f, result)
            actions.append(result)
        elif ftype in TELEMETRY_ONLY_FINDINGS:
            append_event("", f"autopilot_{ftype}", f.get("severity", "warn"), f)
            # Probe failures are telemetry, not worker assignments. Sending a
            # remediation prompt to a live pane can leave stale text in the TUI
            # and block the next real dispatch. Keep the signal in events/state.
            result = {"sid": sid, "action": ftype, "target": f.get("target", ""), "dispatched": False, "recorded_only": True}
            mark_action(state, f, result)
            actions.append(result)
    return actions


def acquire_lock() -> bool:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            old = int(LOCK.read_text().strip() or "0")
            subprocess.run(["kill", "-0", str(old)], capture_output=True, timeout=1, check=True)
            return False
        except Exception:
            pass
    LOCK.write_text(str(os.getpid()))
    return True


def release_lock() -> None:
    try:
        if LOCK.exists() and LOCK.read_text().strip() == str(os.getpid()):
            LOCK.unlink()
    except Exception:
        pass


def scan_once(args: argparse.Namespace, state: dict) -> dict:
    queue_actions = retry_queue(state, args.dispatch, args.cooldown) if args.apply else []
    findings = (
        inspect_epics()
        + inspect_epic_child_state_drift()
        + inspect_sprints()
        + inspect_panes(state, args.stall_seconds)
        + inspect_knowledge_context(state)
        + inspect_model_registry(state)
    )
    actions = apply_findings(findings, args.dispatch, state, args.cooldown) if args.apply else []
    payload = {
        "ok": True,
        "apply": args.apply,
        "dispatch": args.dispatch,
        "loop": args.loop,
        "findings": findings,
        "actions": queue_actions + actions,
        "queue_actions": queue_actions,
        "queue_depth": len(load_queue()),
        "state_path": str(STATE),
    }
    save_state(state)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dispatch", action="store_true")
    parser.add_argument("--loop", action="store_true", help="run continuously")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--max-iterations", type=int, default=0, help="0 means forever")
    parser.add_argument("--cooldown", type=int, default=300, help="seconds between repeated actions for same finding")
    parser.add_argument("--stall-seconds", type=int, default=180, help="pane unchanged seconds before compact/stall recovery")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.loop and not acquire_lock():
        payload = {"ok": False, "error": "autopilot already running", "lock": str(LOCK)}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["error"])
        return 1

    state = load_state()
    iterations = 0
    try:
        while True:
            payload = scan_once(args, state)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
            else:
                print(f"findings={len(payload['findings'])} actions={len(payload['actions'])}", flush=True)
                for f in payload["findings"]:
                    print(f"- {f.get('severity')} {f.get('type')} {f.get('sid')} {f.get('target','')}", flush=True)
            iterations += 1
            if not args.loop or (args.max_iterations and iterations >= args.max_iterations):
                break
            time.sleep(max(5, args.interval))
    finally:
        if args.loop:
            release_lock()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
