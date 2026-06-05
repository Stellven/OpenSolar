#!/usr/bin/env python3
"""Core operator health watchdog runtime.

The core exposes one run loop with a single file lock and writes both latest and
history reports with a stable schema.
"""
from __future__ import annotations

import argparse
import datetime
import fcntl
import io
import json
import os
import re
import shutil
import subprocess
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any, Iterable

from harness_paths import resolve_runtime_harness_dir

SCHEMA_VERSION = "operator_health_watchdog.v1"
LAUNCH_AGENT_LABEL = os.environ.get("SOLAR_OPERATOR_HEALTH_WATCHDOG_LABEL", "com.solar.harness.operator-health-watchdog")
SKIPPED_SAMPLE_LIMIT = int(os.environ.get("SOLAR_OHW_SKIPPED_SAMPLE_LIMIT", "25"))

HARNESS_DIR = resolve_runtime_harness_dir()
RUN_DIR = HARNESS_DIR / "run" / "operator-health-watchdog"
LOCK_PATH = RUN_DIR / "lock"
LATEST_REPORT_PATH = RUN_DIR / "latest.json"
HISTORY_PATH = RUN_DIR / "history.jsonl"
LIBRARY_LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
RUN_LAUNCH_AGENT_PATH = RUN_DIR / f"{LAUNCH_AGENT_LABEL}.plist"


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _coerce_int(value: object, default: int, min_value: int | None = None) -> int:
    try:
        int_value = int(value)
    except Exception:
        return default
    if min_value is not None and int_value < min_value:
        return default
    return int_value


def _atomic_write_text(path: Path, text: str) -> None:
    _ensure_parent(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _safe_json_load(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text.strip())
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _parse_time(value: Any) -> datetime.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(raw).astimezone(datetime.timezone.utc)
    except Exception:
        return None


def _load_tool(name: str):
    candidates: list[Path] = [
        HARNESS_DIR / "lib" / f"{name}.py",
        HARNESS_DIR / "tools" / f"{name}.py",
    ]
    for path in candidates:
        if not path.exists():
            continue
        import importlib.util

        spec = importlib.util.spec_from_file_location(f"operator_health_watchdog_{name}", path)
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    raise FileNotFoundError(f"tool not found: {name}")


def _capture_cmd_output(fn: Any, args: argparse.Namespace) -> dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        rc = int(fn(args) if fn is not None else 1)
    payload = _safe_json_load(stdout.getvalue())
    if not payload:
        payload = {}
    payload["returncode"] = rc
    if stderr.getvalue().strip():
        payload["stderr"] = stderr.getvalue().strip()
    return payload


def _acquire_lock(lock_path: Path, timeout_seconds: int = 1):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    deadline = datetime.datetime.now(datetime.timezone.utc).timestamp() + _coerce_int(timeout_seconds, 1, min_value=1)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if datetime.datetime.now(datetime.timezone.utc).timestamp() >= deadline:
                os.close(fd)
                return None
            import time
            time.sleep(0.05)

    def release() -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    return release


def _phase_entry(
    name: str,
    status: str,
    *,
    actions: list[dict[str, Any]] | None = None,
    skipped: list[dict[str, Any]] | None = None,
    blockers: list[str] | None = None,
    counters: dict[str, int] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "phase": name,
        "status": status,
        "actions": actions or [],
        "skipped": skipped or [],
        "blockers": blockers or [],
        "counters": counters or {},
        "details": details or {},
    }


def _indexed_skipped(skipped: list[dict[str, Any]], *, sample_limit: int = SKIPPED_SAMPLE_LIMIT) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not skipped:
        return [], None
    sample_limit = max(1, sample_limit)
    by_reason: dict[str, dict[str, Any]] = {}
    for item in skipped:
        reason = str(item.get("reason") or "unknown")
        entry = by_reason.setdefault(reason, {"reason": reason, "count": 0, "targets": []})
        entry["count"] += 1
        target = item.get("target")
        if target is not None and len(entry["targets"]) < 5:
            entry["targets"].append(str(target))
    index = {
        "total": len(skipped),
        "sample_limit": sample_limit,
        "truncated": len(skipped) > sample_limit,
        "by_reason": sorted(by_reason.values(), key=lambda entry: (-int(entry["count"]), str(entry["reason"]))),
    }
    return skipped[:sample_limit], index


def _attach_skipped_index(phase: dict[str, Any], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    sample, index = _indexed_skipped(skipped)
    phase["skipped"] = sample
    if index is not None:
        phase["skipped_index"] = index
        phase["counters"] = dict(phase.get("counters") or {})
        phase["counters"]["skipped_total"] = int(index["total"])
    return phase


def _action(
    action_type: str,
    target: str,
    status: str,
    idempotency_key: str,
    *,
    reason: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "action_type": action_type,
        "target": target,
        "status": status,
        "idempotency_key": idempotency_key,
    }
    if reason:
        item["reason"] = reason
    if meta:
        item.update(meta)
    return item


def _read_pm_backlog(pm_mod: Any) -> int:
    inbox_dir = getattr(pm_mod, "PM_INBOX_DIR", HARNESS_DIR / "run" / "pm-inbox")
    if not inbox_dir.exists():
        return 0
    terminal = {"completed", "cancelled"}
    count = 0
    for path in inbox_dir.glob("pm-*.json"):
        data = _load_json(path, {})
        status = str(data.get("status") or "").strip().lower()
        if status in terminal or status.startswith("failed"):
            continue
        count += 1
    return count


def _run_safe_drain_phase(pm_mod: Any, *, apply: bool, capacity: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not bool(capacity.get("ok", True)):
        return (
            _phase_entry(
                "drain_if_capacity_available",
                "skipped",
                skipped=[{"reason": "capacity_unavailable", "capacity": capacity}],
            ),
            0,
        )
    if int(capacity.get("operators_usable", 0) or 0) <= 0:
        return (
            _phase_entry(
                "drain_if_capacity_available",
                "skipped",
                skipped=[{"reason": "no_usable_operators", "capacity": capacity}],
            ),
            0,
        )
    if not hasattr(pm_mod, "cmd_drain_builder_ready"):
        return (
            _phase_entry(
                "drain_if_capacity_available",
                "skipped",
                skipped=[{"reason": "pm_drain_unavailable"}],
            ),
            0,
        )

    allow_apply = os.environ.get("SOLAR_OHW_ENABLE_DRAIN_APPLY", "").strip() == "1"
    dry_run = not (apply and allow_apply)
    args = argparse.Namespace(sprint="", max_items=3, dry_run=dry_run, json=True)
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        rc = pm_mod.cmd_drain_builder_ready(args)
    raw = stdout.getvalue().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {"raw_stdout": raw}
    if stderr.getvalue().strip():
        payload["stderr"] = stderr.getvalue().strip()
    submitted_count = len(payload.get("submitted") or []) if isinstance(payload.get("submitted"), list) else 0
    skipped_count = len(payload.get("skipped") or []) if isinstance(payload.get("skipped"), list) else 0
    phase_status = "ok" if rc == 0 or dry_run else "blocked"
    actions = []
    if submitted_count:
        actions.append(
            _action(
                "drain_builder_ready",
                "pm_dispatch",
                "applied",
                f"submitted={submitted_count}",
                reason="capacity_available",
                meta={"payload": payload},
            )
        )
    skipped = [
        {
            "reason": "dry_run" if dry_run else "drain_returned_nonzero",
            "returncode": rc,
            "payload": payload,
        }
    ]
    return (
        _phase_entry(
            "drain_if_capacity_available",
            phase_status,
            actions=actions,
            skipped=skipped,
            counters={"submitted": submitted_count, "skipped": skipped_count, "dry_run": int(dry_run)},
            details={"payload": payload, "allow_apply": allow_apply},
        ),
        submitted_count,
    )


def _run_graph_drain_phase(controller_mod: Any, *, apply: bool, capacity: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if controller_mod is None or not hasattr(controller_mod, "run_graph_drain"):
        return (
            _phase_entry(
                "graph_drain_controller",
                "skipped",
                skipped=[{"reason": "graph_drain_controller_unavailable"}],
            ),
            0,
        )
    if not bool(capacity.get("ok", True)):
        return (
            _phase_entry(
                "graph_drain_controller",
                "skipped",
                skipped=[{"reason": "capacity_unavailable", "capacity": capacity}],
            ),
            0,
        )

    max_graphs = _coerce_int(os.environ.get("SOLAR_OHW_GRAPH_DRAIN_MAX_GRAPHS", "30"), 30, min_value=0)
    max_evals = _coerce_int(os.environ.get("SOLAR_OHW_GRAPH_DRAIN_MAX_EVALS", "2"), 2, min_value=0)
    max_builders = _coerce_int(os.environ.get("SOLAR_OHW_GRAPH_DRAIN_MAX_BUILDERS", "1"), 1, min_value=0)
    ttl = _coerce_int(os.environ.get("SOLAR_OHW_GRAPH_DRAIN_TTL", "900"), 900, min_value=60)
    try:
        payload = controller_mod.run_graph_drain(
            apply=apply,
            max_graphs=max_graphs,
            max_evals=max_evals,
            max_builders=max_builders,
            ttl=ttl,
        )
    except Exception as exc:
        return (
            _phase_entry(
                "graph_drain_controller",
                "error",
                blockers=[str(exc)],
                details={"error_type": type(exc).__name__},
            ),
            0,
        )
    if not isinstance(payload, dict):
        payload = {"ok": False, "reason": "invalid_graph_drain_response"}
    drain_counters = payload.get("counters") if isinstance(payload.get("counters"), dict) else {}
    submitted_count = _coerce_int(drain_counters.get("drain_submitted"), 0, min_value=0)
    dry_run = bool(payload.get("dry_run", not apply))
    actions = [
        item
        for item in payload.get("actions", [])
        if isinstance(item, dict)
    ]
    skipped = [
        item
        for item in payload.get("skipped", [])
        if isinstance(item, dict)
    ]
    status = "ok" if bool(payload.get("ok", True)) else "warn"
    return (
        _phase_entry(
            "graph_drain_controller",
            status,
            actions=actions,
            skipped=skipped,
            counters={
                "submitted": submitted_count,
                "evals_dispatched": _coerce_int(drain_counters.get("evals_dispatched"), 0, min_value=0),
                "builders_dispatched": _coerce_int(drain_counters.get("builders_dispatched"), 0, min_value=0),
                "eval_attempts": _coerce_int(drain_counters.get("eval_attempts"), 0, min_value=0),
                "builder_attempts": _coerce_int(drain_counters.get("builder_attempts"), 0, min_value=0),
                "reconciled": _coerce_int(drain_counters.get("reconciled"), 0, min_value=0),
                "dry_run": int(dry_run),
            },
            details=payload,
        ),
        submitted_count,
    )


def _run_evaluator_closeout_control_plane_phase(
    graph_adapter_mod: Any,
    pm_mod: Any,
    *,
    apply: bool,
) -> tuple[dict[str, Any], set[str]]:
    enforcer = getattr(graph_adapter_mod, "enforce_evaluator_closeout_control_plane", None)
    if not callable(enforcer):
        return (
            _phase_entry(
                "evaluator_closeout_control_plane",
                "skipped",
                skipped=[{"reason": "evaluator_closeout_control_plane_unavailable"}],
            ),
            set(),
        )

    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    handled_task_ids: set[str] = set()
    counters = {
        "deterministic_eval_gate_checked": 0,
        "sidecar_closeout_enforced": 0,
        "evaluator_retry_routed": 0,
        "released": 0,
        "would_release": 0,
    }

    for path, record in _iter_pm_records(pm_mod, include_probe_records=False):
        if not isinstance(record, dict):
            continue
        task_id = str(record.get("task_id") or path.stem)
        role = str(record.get("requested_role") or "").strip().lower()
        if role != "evaluator":
            continue
        status = str(record.get("status") or "").strip().lower()
        if status not in {"completed", "failed_contract_closeout"} and not status.startswith("failed"):
            continue
        try:
            result = enforcer(record, apply=apply)
        except Exception as exc:
            skipped.append({"reason": f"control_plane_failed:{type(exc).__name__}", "target": task_id, "error": str(exc)})
            continue
        if not isinstance(result, dict):
            skipped.append({"reason": "invalid_control_plane_response", "target": task_id})
            continue

        control_plane = result.get("control_plane") if isinstance(result.get("control_plane"), dict) else {}
        if control_plane.get("deterministic_eval_gate"):
            counters["deterministic_eval_gate_checked"] += 1
        sidecar_enforcer = control_plane.get("sidecar_closeout_enforcer")
        if isinstance(sidecar_enforcer, dict) and sidecar_enforcer.get("status") == "required":
            counters["sidecar_closeout_enforced"] += 1
        retry_router = control_plane.get("evaluator_retry_router")
        routed = isinstance(retry_router, dict) and retry_router.get("status") in {"applied", "would_apply"}
        if routed:
            counters["evaluator_retry_routed"] += 1
            handled_task_ids.add(task_id)
        if result.get("released"):
            counters["released"] += 1
        if result.get("would_release"):
            counters["would_release"] += 1

        if routed:
            actions.append(
                _action(
                    "evaluator_retry_route",
                    task_id,
                    "applied" if result.get("released") else "skipped",
                    f"{task_id}|{result.get('graph','')}|{result.get('node_id','')}",
                    reason=str(result.get("requeue_reason") or result.get("reason") or "evaluator_retry_route"),
                    meta=result,
                )
            )
        else:
            skipped.append({"reason": str(result.get("reason") or "not_routed"), "target": task_id})

    if actions or skipped:
        phase = _phase_entry(
            "evaluator_closeout_control_plane",
            "ok",
            actions=actions,
            skipped=skipped,
            counters=counters,
        )
        return _attach_skipped_index(phase, skipped), handled_task_ids
    return (
        _phase_entry("evaluator_closeout_control_plane", "skipped", skipped=[{"reason": "nothing_to_enforce"}]),
        handled_task_ids,
    )


def _is_capacity_probe_record(pm_mod: Any, record: dict[str, Any], path: Path) -> bool:
    helper = getattr(pm_mod, "is_capacity_probe_record", None)
    if callable(helper):
        try:
            return bool(helper(record, path))
        except TypeError:
            try:
                return bool(helper(record=record, path=path))
            except Exception:
                pass
        except Exception:
            pass
    task_id = str(record.get("task_id") or path.stem)
    sprint_id = str(record.get("sprint_id") or "")
    return task_id.startswith("pm-graph-dispatch-capacity-probe-") or task_id.startswith("pm-eval-capacity-probe-") or sprint_id in {"graph-dispatch-capacity-probe", "eval-capacity-probe"}


def _iter_pm_records(pm_mod: Any, *, include_probe_records: bool = True) -> Iterable[tuple[Path, dict[str, Any]]]:
    inbox_dir = getattr(pm_mod, "PM_INBOX_DIR", HARNESS_DIR / "run" / "pm-inbox")
    if not inbox_dir.exists():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(inbox_dir.glob("pm-*.json")):
        record = _load_json(path, None)
        if not isinstance(record, dict):
            continue
        if not include_probe_records and _is_capacity_probe_record(pm_mod, record, path):
            continue
        records.append((path, record))
    return records


def _is_pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _normalize_report_payload(payload: dict[str, Any], *, lock_acquired: bool, mode: str, run_id: str) -> dict[str, Any]:
    payload["schema_version"] = SCHEMA_VERSION
    payload["run_id"] = run_id
    payload["mode"] = mode
    payload["lock_acquired"] = lock_acquired
    payload.setdefault("started_at", _iso_now())
    payload["finished_at"] = _iso_now()
    payload.setdefault("last_exit_code", 0)
    payload.setdefault("counters", {})
    payload.setdefault("backlog_delta", {"before": 0, "after": 0, "delta": 0})
    payload.setdefault("paths", {})
    payload["paths"].update(
        {
            "run_dir": str(RUN_DIR),
            "latest_json": str(LATEST_REPORT_PATH),
            "history_jsonl": str(HISTORY_PATH),
            "lock_file": str(LOCK_PATH),
        }
    )
    payload.setdefault("ok", payload.get("last_exit_code", 0) == 0)
    return payload


def run_watchdog(
    *,
    apply: bool = False,
    max_age_minutes: int = 45,
    mode: str = "once",
    lock_timeout_seconds: int = 5,
    lock_path: Path = LOCK_PATH,
    latest_path: Path = LATEST_REPORT_PATH,
    history_path: Path = HISTORY_PATH,
    run_id: str | None = None,
    pm_dispatch_module: Any | None = None,
    quota_refresh_module: Any | None = None,
    prune_module: Any | None = None,
    graph_drain_module: Any | None = None,
) -> dict[str, Any]:
    started_at = _iso_now()
    run_id = run_id or f"ohw-{_iso_now().replace(':', '').replace('-', '')}-{os.getpid()}"
    apply = bool(apply)
    max_age_minutes = max(1, _coerce_int(max_age_minutes, 45))
    lock_timeout_seconds = max(1, _coerce_int(lock_timeout_seconds, 5))

    operator_adapter_mod = None
    try:
        operator_adapter_mod = _load_tool("operator_health_watchdog_operator_adapters")
    except Exception:
        operator_adapter_mod = None

    pm_mod = pm_dispatch_module if pm_dispatch_module is not None else _load_tool("pm_dispatch")
    if quota_refresh_module is not None:
        quota_mod = quota_refresh_module
    elif operator_adapter_mod is not None and hasattr(operator_adapter_mod, "refresh_snapshot"):
        quota_mod = operator_adapter_mod
    else:
        quota_mod = _load_tool("quota_refresh")
    if prune_module is None:
        if operator_adapter_mod is not None and hasattr(operator_adapter_mod, "prune_expired_operator_config_blocks"):
            prune_module = operator_adapter_mod
        else:
            try:
                prune_module = _load_tool("operator_flow_control")
            except FileNotFoundError:
                prune_module = pm_mod
    runtime_mod = _load_tool("operator_runtime")
    graph_adapter_mod = None
    try:
        graph_adapter_mod = _load_tool("operator_health_watchdog_graph_adapters")
    except Exception:
        graph_adapter_mod = None
    lease_adapter_mod = None
    try:
        lease_adapter_mod = _load_tool("operator_health_watchdog_lease_adapters")
    except Exception:
        lease_adapter_mod = None
    graph_drain_mod = graph_drain_module
    if graph_drain_mod is None:
        try:
            graph_drain_mod = _load_tool("graph_drain_controller")
        except Exception:
            graph_drain_mod = None

    phases: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    blockers: list[str] = []

    capacity: dict[str, Any] = {"ok": True}
    backlog_before = _read_pm_backlog(pm_mod)
    counters = {
        "expired_blocks_pruned": 0,
        "pm_failures_reconciled": 0,
        "graph_nodes_released": 0,
        "stale_leases_released": 0,
        "drain_submitted": 0,
        "deterministic_eval_gate_checked": 0,
        "sidecar_closeout_enforced": 0,
        "evaluator_retry_routed": 0,
    }
    last_exit_code = 0
    summary = {
        "pruned_blocks": 0,
        "kept_blocks": 0,
        "reconcile_count": 0,
        "releases": 0,
        "ok": True,
        "applied": apply,
    }

    release = _acquire_lock(lock_path, timeout_seconds=lock_timeout_seconds)
    if release is None:
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "mode": mode,
            "lock_acquired": False,
            "lock_timeout_seconds": lock_timeout_seconds,
            "started_at": started_at,
            "finished_at": _iso_now(),
            "last_exit_code": 0,
            "ok": True,
            "phases": [
                _phase_entry("lock_acquire", "skipped", skipped=[{"reason": "lock_busy", "target": str(lock_path)}]),
            ],
            "actions": [],
            "skipped": [{"reason": "degraded", "details": "lock busy"}],
            "blockers": ["another watchdog run is in progress"],
            "counters": counters,
            "capacity": {
                "ok": True,
                "schema_version": "operator_health_watchdog_capacity.v1",
                "run_id": run_id,
                "backlog": backlog_before,
            },
            "backlog_delta": {"before": backlog_before, "after": backlog_before, "delta": 0},
            "summary": {"ok": True, "applied": apply, "pruned_blocks": 0, "kept_blocks": 0, "reconcile_count": 0, "releases": 0},
            "steps": [
                {
                    "step": "lock_acquire",
                    "applied": False,
                    "result": {
                        "ok": True,
                        "reason": "lock_busy",
                        "degraded": "degraded_report_written",
                    },
                },
            ],
            "degraded_reason": "lock_busy",
            "applied": apply,
            "max_age_minutes": max_age_minutes,
            "paths": {
                "run_dir": str(RUN_DIR),
                "latest_json": str(latest_path),
                "history_jsonl": str(history_path),
                "lock_file": str(lock_path),
            },
        }
        _atomic_write_text(latest_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        _append_jsonl(history_path, payload)
        return payload

    try:
        phases.append(_phase_entry("lock_acquire", "ok"))
        try:
            if apply:
                prune_fn = None
                if hasattr(prune_module, "prune_expired_operator_config_blocks"):
                    prune_fn = getattr(prune_module, "prune_expired_operator_config_blocks")
                elif hasattr(prune_module, "_prune_expired_operator_blocks"):
                    prune_fn = getattr(prune_module, "_prune_expired_operator_blocks")
                else:
                    raise RuntimeError("missing prune adapter")
                prune_result = prune_fn() if callable(prune_fn) else {"ok": False, "reason": "prune adapter not callable"}
                pruned = prune_result.get("pruned", []) if isinstance(prune_result.get("pruned"), list) else []
                kept = prune_result.get("kept", []) if isinstance(prune_result.get("kept"), list) else []
                counters["expired_blocks_pruned"] = len(pruned)
                summary["pruned_blocks"] = len(pruned)
                summary["kept_blocks"] = len(kept)
                phase_actions = [
                    _action("prune_expired_block", str(item.get("operator_id") or ""), "applied", f"{item.get('operator_id')}|{item.get('expires_at')}", reason=str(item.get("runtime_state") or "expired"))
                    for item in pruned
                ]
                for item in kept:
                    skipped.append(
                        {
                            "reason": "not_expired",
                            "target": str(item.get("operator_id") or ""),
                            "idempotency_key": f"{item.get('operator_id')}|{item.get('expires_at')}",
                        }
                    )
                phases.append(
                    _phase_entry(
                        "prune_expired_blocks",
                        "ok" if bool(prune_result.get("ok", True)) else "error",
                        actions=phase_actions,
                        counters={"pruned": len(pruned), "kept": len(kept)},
                        details={"pruned": pruned, "kept": kept},
                    )
                )
            else:
                phases.append(
                    _phase_entry(
                        "prune_expired_blocks",
                        "skipped",
                        skipped=[{"reason": "dry_run", "target": "operator_flow_control"}],
                    )
                )
        except Exception as exc:
            last_exit_code = 1
            blockers.append(str(exc))
            phases.append(_phase_entry("prune_expired_blocks", "error", blockers=[str(exc)]))

        try:
            capacity_payload = (
                quota_mod.refresh_snapshot(apply=apply)
                if hasattr(quota_mod, "refresh_snapshot")
                else {"ok": False, "reason": "quota adapter missing"}
            )
            if not isinstance(capacity_payload, dict):
                capacity_payload = {"ok": False, "reason": "quota adapter invalid response"}
            if capacity_payload.get("ok", True) is False:
                last_exit_code = max(last_exit_code, 1)
                blockers.append("quota_refresh_failed")
            capacity = capacity_payload | {"schema_version": "operator_health_watchdog_capacity.v1", "run_id": run_id}
            phases.append(_phase_entry("refresh_capacity_snapshot", "ok" if bool(capacity.get("ok", True)) else "warn"))
        except Exception as exc:
            last_exit_code = 1
            blockers.append(str(exc))
            capacity = {"ok": False, "reason": f"quota_refresh_failed:{type(exc).__name__}", "run_id": run_id}
            phases.append(_phase_entry("refresh_capacity_snapshot", "error", blockers=[str(exc)]))

        pm_ns = argparse.Namespace(apply=apply, max_age_minutes=max_age_minutes, json=True, limit=0)
        try:
            reconcile_payload = _capture_cmd_output(getattr(pm_mod, "cmd_reconcile", None), pm_ns)
            reconcile_ok = bool(reconcile_payload.get("ok", reconcile_payload.get("returncode", 1) == 0))
            if not reconcile_ok:
                last_exit_code = max(last_exit_code, 1)
                blockers.append("pm_reconcile_failed")
            reconcile_summary = reconcile_payload.get("summary") if isinstance(reconcile_payload.get("summary"), dict) else {}
            summary["reconcile_count"] = int(reconcile_summary.get("reconcile_count", 0) if isinstance(reconcile_summary.get("reconcile_count", 0), int) else 0)
            if summary["reconcile_count"] == 0 and isinstance(reconcile_summary, dict):
                summary["reconcile_count"] = sum(int(v) for v in reconcile_summary.values() if isinstance(v, int))
            phases.append(
                _phase_entry(
                    "reconcile_pm_failures",
                    "ok" if reconcile_ok else "warn",
                    actions=[
                        _action(
                            "pm_reconcile",
                            str(k),
                            "applied" if apply else "skipped",
                            f"pm_reconcile|{k}|{run_id}",
                            meta={"count": int(v) if isinstance(v, int) else v},
                        )
                        for k, v in reconcile_summary.items()
                    ],
                    details=reconcile_payload,
                )
            )
        except Exception as exc:
            last_exit_code = 1
            blockers.append(str(exc))
            phases.append(_phase_entry("reconcile_pm_failures", "error", blockers=[str(exc)]))
            reconcile_payload = {"ok": False, "error": str(exc)}

        evaluator_control_phase, evaluator_control_handled = _run_evaluator_closeout_control_plane_phase(
            graph_adapter_mod,
            pm_mod,
            apply=apply,
        )
        evaluator_control_counters = evaluator_control_phase.get("counters") if isinstance(evaluator_control_phase.get("counters"), dict) else {}
        counters["deterministic_eval_gate_checked"] += _coerce_int(
            evaluator_control_counters.get("deterministic_eval_gate_checked"), 0, min_value=0
        )
        counters["sidecar_closeout_enforced"] += _coerce_int(
            evaluator_control_counters.get("sidecar_closeout_enforced"), 0, min_value=0
        )
        counters["evaluator_retry_routed"] += _coerce_int(
            evaluator_control_counters.get("evaluator_retry_routed"), 0, min_value=0
        )
        routed_releases = _coerce_int(evaluator_control_counters.get("released"), 0, min_value=0)
        counters["graph_nodes_released"] += routed_releases
        summary["releases"] += routed_releases
        actions.extend(
            item for item in evaluator_control_phase.get("actions", []) if isinstance(item, dict) and item.get("status") == "applied"
        )
        phases.append(evaluator_control_phase)

        release_actions: list[dict[str, Any]] = []
        release_skips: list[dict[str, Any]] = []
        graph_node_releaser = getattr(
            graph_adapter_mod,
            "release_builder_assignment_on_transient_failure",
            getattr(pm_mod, "release_builder_assignment_on_transient_failure", None),
        )
        if graph_node_releaser is None:
            graph_node_releaser = getattr(
                pm_mod,
                "_release_graph_node_on_transient_operator_failure",
                lambda *_: {"ok": False, "released": False},
            )
        graph_eval_releaser = getattr(
            graph_adapter_mod,
            "release_evaluator_assignment_on_transient_failure",
            getattr(pm_mod, "release_evaluator_assignment_on_transient_failure", None),
        )
        if graph_eval_releaser is None:
            graph_eval_releaser = getattr(
                pm_mod,
                "_release_graph_eval_on_transient_operator_failure",
                lambda *_: {"ok": False, "released": False},
            )
        for path, record in _iter_pm_records(pm_mod, include_probe_records=False):
            if not isinstance(record, dict):
                continue
            task_id = str(record.get("task_id") or path.stem)
            status = str(record.get("status") or "")
            if not status.startswith("failed"):
                continue

            node_release = graph_node_releaser(record) if apply else {"ok": True, "released": False, "reason": "dry_run"}
            if task_id in evaluator_control_handled:
                eval_release = {"ok": True, "released": False, "reason": "handled_by_evaluator_closeout_control_plane"}
            else:
                eval_release = graph_eval_releaser(record) if apply else {"ok": True, "released": False, "reason": "dry_run"}
            if apply and isinstance(node_release, dict) and node_release.get("released"):
                counters["graph_nodes_released"] += 1
                summary["releases"] += 1
                action = _action(
                    "release_builder_graph_node",
                    task_id,
                    "applied",
                    f"{task_id}|{node_release.get('graph','')}|{node_release.get('node_id','')}",
                    meta=node_release,
                )
                release_actions.append(action)
                actions.append(action)
            if apply and isinstance(eval_release, dict) and eval_release.get("released"):
                counters["graph_nodes_released"] += 1
                summary["releases"] += 1
                action = _action(
                    "release_evaluator_graph_assignment",
                    task_id,
                    "applied",
                    f"{task_id}|{eval_release.get('graph','')}|{eval_release.get('node_id','')}",
                    meta=eval_release,
                )
                release_actions.append(action)
                actions.append(action)

            if not (isinstance(node_release, dict) and node_release.get("released")) and not (
                isinstance(eval_release, dict) and eval_release.get("released")
            ):
                release_skips.append(
                    {
                        "reason": str((node_release or {}).get("reason") or (eval_release or {}).get("reason") or "no_release"),
                        "target": task_id,
                    }
                )
            if apply:
                write_pm_task_record = getattr(pm_mod, "write_pm_task_record", None)
                if callable(write_pm_task_record):
                    try:
                        write_pm_task_record(task_id, record)
                    except Exception:
                        pass
        if release_actions or release_skips:
            release_phase = _phase_entry(
                "reconcile_pm_failures",
                "ok",
                actions=release_actions,
                skipped=release_skips,
            )
            phases.append(
                _attach_skipped_index(release_phase, release_skips)
            )
            counters["pm_failures_reconciled"] += len(release_actions)
        else:
            phases.append(_phase_entry("reconcile_pm_failures", "skipped", skipped=[{"reason": "nothing_to_reconcile"}]))

        lease_actions: list[dict[str, Any]] = []
        lease_skips: list[dict[str, Any]] = []
        if lease_adapter_mod is not None and hasattr(lease_adapter_mod, "reconcile_stale_leases"):
            lease_payload = lease_adapter_mod.reconcile_stale_leases(runtime_module=runtime_mod, apply=apply)
            if isinstance(lease_payload, dict):
                lease_actions = [
                    item for item in lease_payload.get("actions", []) if isinstance(item, dict)
                ]
                lease_skips = [
                    item for item in lease_payload.get("skipped", []) if isinstance(item, dict)
                ]
                released_count = int((lease_payload.get("summary") or {}).get("released") or 0)
                counters["stale_leases_released"] += released_count
                actions.extend(item for item in lease_actions if item.get("status") == "applied")
            else:
                lease_skips.append({"reason": "invalid_lease_adapter_response"})
        else:
            lease_dir = getattr(runtime_mod, "OPERATOR_LEASE_DIR", HARNESS_DIR / "run" / "operator-leases")
            status_dir = getattr(runtime_mod, "OPERATOR_STATUS_DIR", HARNESS_DIR / "run" / "operator-status")
            release_fn = getattr(runtime_mod, "release_operator_lease", None)
            for lease_path in sorted(lease_dir.glob("*.json")):
                lease = _load_json(lease_path, {})
                if not isinstance(lease, dict):
                    continue
                operator_id = str(lease_path.stem)
                lease_id = str(lease.get("lease_id") or lease.get("id") or "")
                expires_at = _parse_time(lease.get("expires_at"))
                state = str(lease.get("state") or "")
                status_data = _load_json(status_dir / f"{operator_id}.json", {})
                pid_raw = status_data.get("worker_pid") if isinstance(status_data, dict) else None
                worker_pid: int | None = None
                try:
                    worker_pid = int(pid_raw) if pid_raw is not None else None
                except Exception:
                    worker_pid = None
                stale_ttl = expires_at is not None and datetime.datetime.now(datetime.timezone.utc) >= expires_at
                dead_pid = worker_pid is not None and not _is_pid_alive(worker_pid)

                if not stale_ttl and not dead_pid:
                    lease_skips.append({"reason": "active_pid_or_ttl", "target": operator_id})
                    continue
                released = False
                if callable(release_fn):
                    try:
                        released = bool(release_fn(operator_id, reason="watchdog_stale_recovery"))
                    except Exception as exc:
                        lease_skips.append({"reason": str(exc), "target": operator_id, "lease_id": lease_id})
                if released:
                    counters["stale_leases_released"] += 1
                    action = _action(
                        "release_stale_lease",
                        operator_id,
                        "applied",
                        f"{lease_id}|{operator_id}",
                        reason="stale_lease",
                        meta={"state": state, "stale_ttl": stale_ttl, "dead_pid": dead_pid},
                    )
                    lease_actions.append(action)
                    actions.append(action)
                else:
                    lease_skips.append(
                        {"reason": "release_failed_or_not_mutated", "target": operator_id, "lease_id": lease_id}
                    )
        phases.append(
            _phase_entry(
                "reconcile_stale_leases",
                "ok" if lease_actions else "skipped",
                actions=lease_actions,
                skipped=lease_skips,
                counters={"released": len(lease_actions)},
            )
        )

        projection_actions: list[dict[str, Any]] = []
        projection_skips: list[dict[str, Any]] = []
        if lease_adapter_mod is not None and hasattr(lease_adapter_mod, "repair_status_projection"):
            for _path, record in _iter_pm_records(pm_mod, include_probe_records=False):
                if not isinstance(record, dict):
                    continue
                projection_payload = lease_adapter_mod.repair_status_projection(record, apply=apply)
                if not isinstance(projection_payload, dict):
                    projection_skips.append({"reason": "invalid_projection_adapter_response"})
                    continue
                projection_actions.extend(
                    item for item in projection_payload.get("actions", []) if isinstance(item, dict)
                )
                projection_skips.extend(
                    item for item in projection_payload.get("skipped", []) if isinstance(item, dict)
                )
            actions.extend(item for item in projection_actions if item.get("status") == "applied")
            projection_phase = _phase_entry(
                "repair_status_projection",
                "ok" if projection_actions else "skipped",
                actions=projection_actions,
                skipped=projection_skips,
                counters={"applied": len(projection_actions)},
            )
            phases.append(_attach_skipped_index(projection_phase, projection_skips))
        else:
            phases.append(_phase_entry("repair_status_projection", "skipped", skipped=[{"reason": "adapter_missing"}]))

        graph_drain_phase, graph_drain_submitted = _run_graph_drain_phase(
            graph_drain_mod,
            apply=apply,
            capacity=capacity,
        )
        counters["drain_submitted"] += graph_drain_submitted
        summary["graph_drain_submitted"] = graph_drain_submitted
        phases.append(graph_drain_phase)

        drain_phase, drain_submitted = _run_safe_drain_phase(pm_mod, apply=apply, capacity=capacity)
        counters["drain_submitted"] += drain_submitted
        summary["deterministic_eval_gate_checked"] = counters["deterministic_eval_gate_checked"]
        summary["sidecar_closeout_enforced"] = counters["sidecar_closeout_enforced"]
        summary["evaluator_retry_routed"] = counters["evaluator_retry_routed"]
        summary["pm_drain_submitted"] = drain_submitted
        summary["drain_submitted"] = counters["drain_submitted"]
        phases.append(drain_phase)
        backlog_after = _read_pm_backlog(pm_mod)
    finally:
        if release is not None:
            release()

    capacity.setdefault("schema_version", "operator_health_watchdog_capacity.v1")
    capacity.setdefault("run_id", run_id)
    capacity.setdefault("ok", last_exit_code == 0 if isinstance(capacity, dict) else False)
    backlog_delta = {
        "before": backlog_before,
        "after": backlog_after,
        "delta": backlog_after - backlog_before,
    }

    if capacity.get("groups", {}):
        hard_blocked_groups = [
            name
            for name, value in (capacity.get("groups") or {}).items()
            if isinstance(value, dict) and int(value.get("hard_blocked") or 0) > 0
        ]
    else:
        hard_blocked_groups = []

    old_steps = [
        {
            "step": "prune_rate_limits",
            "applied": bool(apply),
            "result": {
                "ok": summary.get("pruned_blocks", 0) >= 0,
                "reason": "dry_run" if not apply else "",
                "pruned": [],
                "kept": [],
            },
        },
        {"step": "quota_refresh", "applied": bool(apply), "result": capacity},
        {
            "step": "pm_reconcile",
            "applied": bool(apply),
            "result": {"ok": bool(reconcile_payload.get("ok", True)), "summary": reconcile_payload.get("summary", {})},
        },
    ]
    if phases:
        prune_phase = next((phase for phase in phases if phase["phase"] == "prune_expired_blocks"), None)
        if prune_phase is not None:
            old_steps[0]["result"]["pruned"] = [a for a in prune_phase.get("details", {}).get("pruned", [])]
            old_steps[0]["result"]["kept"] = [a for a in prune_phase.get("details", {}).get("kept", [])]

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": _iso_now(),
        "mode": mode,
        "lock_acquired": True,
        "lock_timeout_seconds": lock_timeout_seconds,
        "last_exit_code": last_exit_code,
        "phases": phases,
        "actions": actions,
        "skipped": skipped,
        "blockers": blockers,
        "counters": counters,
        "capacity": {
            "ok": bool(capacity.get("ok", False)),
            "recommended_level": capacity.get("recommended_level") or "N/A",
            "operators_total": int(capacity.get("operators_total", 0) or 0),
            "operators_usable": int(capacity.get("operators_usable", 0) or 0),
            "operators_hard_blocked": int(capacity.get("operators_hard_blocked", 0) or 0),
            "backlog": int(capacity.get("backlog", 0) or 0),
            "recommendation_reason": capacity.get("recommendation_reason", "N/A"),
        },
        "backlog_delta": backlog_delta,
        "summary": summary | {
            "ok": last_exit_code == 0,
            "applied": apply,
            "hard_blocked_groups": hard_blocked_groups,
        },
        "degraded_reason": next(iter(blockers), None) if blockers else None,
        "applied": apply,
        "max_age_minutes": max_age_minutes,
        "steps": old_steps,
        "paths": {
            "run_dir": str(RUN_DIR),
            "latest_json": str(latest_path),
            "history_jsonl": str(history_path),
            "lock_file": str(lock_path),
        },
        "run_once": {"interval": 0, "mode": mode},
        "ok": last_exit_code == 0,
    }
    if not phases:
        payload["degraded_reason"] = payload["degraded_reason"] or "no phases executed"
        payload["last_exit_code"] = 1
        payload["ok"] = False

    if not apply:
        _normalize_report_payload(payload, lock_acquired=True, mode=mode, run_id=run_id)

    _atomic_write_text(latest_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _append_jsonl(history_path, payload)
    return payload


def command_run_once(
    *,
    apply: bool,
    max_age_minutes: int,
    lock_path: Path = LOCK_PATH,
    latest_path: Path = LATEST_REPORT_PATH,
    history_path: Path = HISTORY_PATH,
) -> dict[str, Any]:
    return run_watchdog(
        apply=apply,
        max_age_minutes=max_age_minutes,
        mode="once",
        lock_timeout_seconds=5,
        lock_path=lock_path,
        latest_path=latest_path,
        history_path=history_path,
    )


def command_run_loop(
    *,
    interval: int,
    apply: bool,
    max_age_minutes: int,
    lock_path: Path = LOCK_PATH,
    latest_path: Path = LATEST_REPORT_PATH,
    history_path: Path = HISTORY_PATH,
    loop_max_iterations: int | None = None,
) -> list[dict[str, Any]]:
    if int(interval) <= 0:
        return [
            {
                "ok": False,
                "applied": bool(apply),
                "max_age_minutes": max_age_minutes,
                "lock_acquired": False,
                "degraded_reason": "interval must be > 0",
                "started_at": _iso_now(),
                "finished_at": _iso_now(),
                "phases": [],
                "steps": [],
            }
        ]
    interval = max(1, int(interval))
    results: list[dict[str, Any]] = []
    count = 0
    import time

    while loop_max_iterations is None or count < loop_max_iterations:
        payload = run_watchdog(
            apply=bool(apply),
            max_age_minutes=max_age_minutes,
            mode="loop",
            lock_timeout_seconds=5,
            lock_path=lock_path,
            latest_path=latest_path,
            history_path=history_path,
        )
        payload["run_once"] = {"interval": interval, "mode": "loop"}
        results.append(payload)
        count += 1
        if loop_max_iterations is not None and count >= loop_max_iterations:
            break
        time.sleep(interval)
    return results


def _launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def _launchagent_status() -> dict[str, Any]:
    plist_candidates = [LIBRARY_LAUNCH_AGENT_PATH, RUN_LAUNCH_AGENT_PATH]
    plist_path = next((path for path in plist_candidates if path.exists()), RUN_LAUNCH_AGENT_PATH)
    payload: dict[str, Any] = {
        "label": LAUNCH_AGENT_LABEL,
        "plist_path": str(plist_path),
        "plist_candidates": [str(path) for path in plist_candidates],
        "installed": any(path.exists() for path in plist_candidates),
        "launchd_loaded": False,
        "launchd_state": "unknown",
    }
    if shutil.which("launchctl") is None:
        payload["launchd_state"] = "launchctl_unavailable"
        return payload
    try:
        result = subprocess.run(
            ["launchctl", "print", f"{_launchd_domain()}/{LAUNCH_AGENT_LABEL}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        payload["launchd_state"] = f"launchctl_error:{type(exc).__name__}"
        return payload
    if result.returncode != 0:
        payload["launchd_state"] = "not_loaded"
        return payload
    output = result.stdout or result.stderr or ""
    payload["launchd_loaded"] = True
    state_match = re.search(r"^\s*state = ([^\n]+)", output, re.M)
    if state_match:
        payload["launchd_state"] = state_match.group(1).strip()
    return payload


def command_status(
    *,
    json_output: bool = True,
    latest_path: Path = LATEST_REPORT_PATH,
) -> dict[str, Any]:
    del json_output
    launchagent = _launchagent_status()
    if not latest_path.exists():
        payload = {
            "ok": False,
            "installed": bool(launchagent.get("installed", False)),
            "launchd_loaded": bool(launchagent.get("launchd_loaded", False)),
            "launchd_state": launchagent.get("launchd_state"),
            "last_run_at": None,
            "last_exit_code": None,
            "last_actions": {
                "expired_blocks_pruned": 0,
                "pm_failures_reconciled": 0,
                "graph_nodes_released": 0,
                "stale_leases_released": 0,
                "drain_submitted": 0,
                "deterministic_eval_gate_checked": 0,
                "sidecar_closeout_enforced": 0,
                "evaluator_retry_routed": 0,
            },
            "blockers": ["missing latest report"],
            "degraded_reason": "run latest.json not found; run --once first",
            "latest_report": str(latest_path),
        }
    else:
        latest_payload = _load_json(latest_path, {})
        if not isinstance(latest_payload, dict):
            payload = {
                "ok": False,
                "installed": bool(launchagent.get("installed", False)),
                "launchd_loaded": bool(launchagent.get("launchd_loaded", False)),
                "launchd_state": launchagent.get("launchd_state"),
                "latest_report": str(latest_path),
                "last_run_at": None,
                "last_exit_code": None,
                "last_actions": {
                    "expired_blocks_pruned": 0,
                    "pm_failures_reconciled": 0,
                    "graph_nodes_released": 0,
                    "stale_leases_released": 0,
                    "drain_submitted": 0,
                    "deterministic_eval_gate_checked": 0,
                    "sidecar_closeout_enforced": 0,
                    "evaluator_retry_routed": 0,
                },
                "blockers": ["latest report parse failed"],
                "degraded_reason": "latest report unreadable",
            }
        else:
            summary = latest_payload.get("summary", {}) if isinstance(latest_payload.get("summary"), dict) else {}
            steps = latest_payload.get("steps", []) if isinstance(latest_payload.get("steps"), list) else []
            payload = {
                "ok": bool(latest_payload.get("ok", False)),
                "installed": bool(launchagent.get("installed", latest_payload.get("installed", False))),
                "launchd_loaded": bool(launchagent.get("launchd_loaded", latest_payload.get("launchd_loaded", False))),
                "launchd_state": launchagent.get("launchd_state"),
                "last_run_at": latest_payload.get("finished_at") or latest_payload.get("started_at"),
                "last_exit_code": latest_payload.get("last_exit_code"),
                "last_actions": {
                    "expired_blocks_pruned": summary.get("pruned_blocks", 0),
                    "pm_failures_reconciled": summary.get("reconcile_count", 0),
                    "graph_nodes_released": summary.get("releases", 0),
                    "stale_leases_released": len(
                        [
                            p
                            for p in (latest_payload.get("actions", []) if isinstance(latest_payload.get("actions"), list) else [])
                            if p.get("action_type") == "release_stale_lease"
                        ]
                    ),
                    "drain_submitted": summary.get("drain_submitted", 0),
                    "deterministic_eval_gate_checked": summary.get("deterministic_eval_gate_checked", 0),
                    "sidecar_closeout_enforced": summary.get("sidecar_closeout_enforced", 0),
                    "evaluator_retry_routed": summary.get("evaluator_retry_routed", 0),
                },
                "blockers": latest_payload.get("blockers", []),
                "degraded_reason": latest_payload.get("degraded_reason"),
                "latest_report": str(latest_path),
                "recent_steps": steps[-3:],
            }
    payload["paths"] = payload.get("paths", {})
    payload["paths"]["latest_report"] = str(latest_path)
    payload["launchagent"] = launchagent
    return payload
