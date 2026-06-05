#!/usr/bin/env python3
"""Lease and projection adapters for operator health watchdog.

These adapters expose deterministic helpers for S03 adapter integration:
- stale lease reconciliation (dead-PID or TTL-expired)
- status projection repair for builder/evaluator records
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("HOME", ""))
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
DEFAULT_LEASE_DIR = HARNESS_DIR / "run" / "operator-leases"
DEFAULT_STATUS_DIR = HARNESS_DIR / "run" / "operator-status"


def _resolve_sprints_dir() -> Path:
    return Path(os.environ.get("SOLAR_HARNESS_SPRINTS_DIR", str(HARNESS_DIR / "sprints")))


def _resolve_lease_dir(lease_dir: Path | None) -> Path:
    return lease_dir or DEFAULT_LEASE_DIR


def _resolve_status_dir(status_dir: Path | None) -> Path:
    return status_dir or DEFAULT_STATUS_DIR


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _pid_exists(pid: int | None) -> bool:
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


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.stem, suffix=".tmp", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
    os.replace(tmp, str(path))


def _load_operator_runtime_module():
    try:
        import operator_runtime
        return operator_runtime
    except Exception as exc:
        raise RuntimeError(f"operator_runtime unavailable:{type(exc).__name__}") from exc


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


def _lease_id(lease: dict[str, Any], operator_id: str) -> str:
    lease_id = str(lease.get("lease_id") or lease.get("id") or "").strip()
    if lease_id:
        return lease_id
    return f"missing_lease_id_for_{operator_id}"


def _iter_lease_records(lease_dir: Path):
    if not lease_dir.exists():
        return []
    return [
        path
        for path in sorted(lease_dir.glob("*.json"))
        if path.is_file()
    ]


def _load_graph(graph_path: Path) -> dict[str, Any] | None:
    if not graph_path.exists():
        return None
    payload = _load_json(graph_path)
    return payload if isinstance(payload, dict) else None


def _iter_graph_nodes(graph: dict[str, Any]):
    nodes = graph.get("nodes")
    if isinstance(nodes, dict):
        return list(nodes.items())
    if not isinstance(nodes, list):
        return []
    result: list[tuple[str, dict[str, Any]]] = []
    for entry in nodes:
        if not isinstance(entry, dict):
            continue
        result.append((str(entry.get("id") or entry.get("node_id") or ""), entry))
    return result


def _find_node(graph: dict[str, Any], node_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    target = None
    for candidate_id, node in _iter_graph_nodes(graph):
        if candidate_id == node_id:
            target = node
            break
    if target is None:
        return None, None

    node_results = graph.get("node_results") if isinstance(graph.get("node_results"), dict) else {}
    return target, node_results.get(node_id) if isinstance(node_results.get(node_id), dict) else {}


def _dispatch_ids_for_item(item: dict[str, Any] | None) -> set[str]:
    if not isinstance(item, dict):
        return set()
    dispatch_keys = ("dispatch_id", "pm_task_id", "eval_dispatch_id", "dispatch_identity")
    values = {str(item.get(key) or "").strip() for key in dispatch_keys}
    task_id = str(item.get("task_id") or "").strip()
    if task_id:
        values.add(task_id)
    return {value for value in values if value}


def _node_handoff_path(sprint_id: str, node_id: str) -> Path:
    return _resolve_sprints_dir() / f"{sprint_id}.{node_id}-handoff.md"


def _eval_sidecar_path(sprint_id: str, node_id: str) -> Path | None:
    base = _resolve_sprints_dir()
    direct = base / f"{sprint_id}.{node_id}-eval.md"
    if direct.exists() and direct.stat().st_size > 0:
        return direct

    glob_match = sorted(base.glob(f"{sprint_id}.{node_id}-eval*.md"))
    if glob_match:
        existing = [path for path in glob_match if path.exists()]
        if existing:
            return existing[0]
    return None


def _clear_fields(target: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        target.pop(key, None)


def reconcile_stale_leases(
    *,
    runtime_module: Any | None = None,
    lease_dir: Path | None = None,
    status_dir: Path | None = None,
    now: dt.datetime | None = None,
    apply: bool = True,
) -> dict[str, Any]:
    """Release stale leases with dead PIDs or expired TTLs."""
    now = now or dt.datetime.now(dt.timezone.utc)
    lease_dir = _resolve_lease_dir(lease_dir)
    status_dir = _resolve_status_dir(status_dir)
    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    lease_files = _iter_lease_records(lease_dir)
    if lease_dir is None or not lease_dir.exists():
        return {
            "ok": False,
            "actions": [],
            "skipped": [{"reason": "lease_dir_missing", "target": str(lease_dir)}],
            "summary": {"checked": 0, "released": 0, "skipped": 1},
        }

    try:
        runtime = runtime_module if runtime_module is not None else _load_operator_runtime_module()
    except Exception as exc:
        return {
            "ok": False,
            "actions": [],
            "skipped": [{"reason": "runtime_import_failed", "error": str(exc)}],
            "summary": {"checked": len(lease_files), "released": 0, "skipped": 1},
        }

    release_fn = getattr(runtime, "release_operator_lease", None)
    if not callable(release_fn):
        return {
            "ok": False,
            "actions": [],
            "skipped": [{"reason": "runtime_release_adapter_missing", "target": "operator_runtime.release_operator_lease"}],
            "summary": {"checked": len(lease_files), "released": 0, "skipped": 1},
        }

    for lease_path in lease_files:
        operator_id = lease_path.stem
        lease = _load_json(lease_path)
        if not isinstance(lease, dict):
            skipped.append(
                {
                    "reason": "invalid_lease_file",
                    "target": operator_id,
                    "lease_path": str(lease_path),
                }
            )
            continue

        lease_identifier = _lease_id(lease, operator_id)
        status_path = status_dir / f"{operator_id}.json"
        status = _load_json(status_path)
        if not isinstance(status, dict):
            status = {}

        expires_at = _parse_time(lease.get("expires_at") or lease.get("expires_at_iso"))
        worker_pid = status.get("worker_pid")
        try:
            worker_pid_int = int(worker_pid) if worker_pid is not None else None
        except Exception:
            worker_pid_int = None

        stale_ttl = expires_at is not None and now >= expires_at
        dead_pid = _pid_exists(worker_pid_int) is False if worker_pid_int is not None else False

        if not stale_ttl and not dead_pid:
            skipped.append(
                _action(
                    "release_stale_lease",
                    operator_id,
                    "skipped",
                    f"{lease_identifier}|{operator_id}",
                    reason="active_pid_or_ttl",
                    meta={
                        "state_file": str(status_path),
                        "lease_file": str(lease_path),
                        "stale_ttl": False,
                        "dead_pid": False,
                        "lease_has_expires_at": expires_at is not None,
                    },
                )
            )
            continue

        if not apply:
            skipped.append(
                _action(
                    "release_stale_lease",
                    operator_id,
                    "skipped",
                    f"{lease_identifier}|{operator_id}",
                    reason="dry_run",
                    meta={
                        "state_file": str(status_path),
                        "lease_file": str(lease_path),
                        "stale_ttl": stale_ttl,
                        "dead_pid": dead_pid,
                    },
                )
            )
            continue

        try:
            released = bool(release_fn(operator_id, reason="watchdog_stale_recovery"))
        except Exception as exc:
            skipped.append(
                {
                    "reason": f"release_failed:{type(exc).__name__}",
                    "target": operator_id,
                    "lease_id": lease_identifier,
                    "lease_file": str(lease_path),
                    "error": str(exc),
                }
            )
            continue

        if released:
            actions.append(
                _action(
                    "release_stale_lease",
                    operator_id,
                    "applied",
                    f"{lease_identifier}|{operator_id}",
                    meta={
                        "lease_id": lease_identifier,
                        "lease_file": str(lease_path),
                        "stale_ttl": stale_ttl,
                        "dead_pid": dead_pid,
                    },
                )
            )
        else:
            skipped.append({
                "reason": "release_adapter_returned_false",
                "target": operator_id,
                "lease_id": lease_identifier,
                "lease_file": str(lease_path),
            })

    return {
        "ok": not any(item.get("reason", "") not in {"active_pid_or_ttl", "dry_run"} for item in skipped),
        "actions": actions,
        "skipped": skipped,
        "summary": {
            "checked": len(lease_files),
            "released": len(actions),
            "skipped": len(skipped),
        },
    }


def repair_status_projection(
    record: dict[str, Any],
    *,
    graph_dir: Path | None = None,
    apply: bool = True,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Repair builder/evaluator status projection using PM record evidence."""
    now = now or dt.datetime.now(dt.timezone.utc)
    now_s = now.isoformat().replace("+00:00", "Z")

    if not isinstance(record, dict):
        return {
            "ok": False,
            "actions": [],
            "skipped": [{"reason": "invalid_record", "target": "global"}],
            "summary": {"applied": 0, "skipped": 1},
        }

    sprint_id = str(record.get("sprint_id") or "").strip()
    node_id = str(record.get("node_id") or "").strip()
    task_id = str(record.get("task_id") or "").strip()
    if not sprint_id or not node_id or not task_id:
        return {
            "ok": False,
            "actions": [],
            "skipped": [
                {
                    "reason": "missing_graph_identity",
                    "sprint_id": sprint_id,
                    "node_id": node_id,
                    "task_id": task_id,
                }
            ],
            "summary": {"applied": 0, "skipped": 1},
        }

    base = graph_dir or _resolve_sprints_dir()
    graph_path = base / f"{sprint_id}.task_graph.json"
    graph = _load_graph(graph_path)
    if not graph:
        return {
            "ok": False,
            "actions": [],
            "skipped": [{"reason": "graph_missing", "graph": str(graph_path)}],
            "summary": {"applied": 0, "skipped": 1},
        }

    target, result_entry = _find_node(graph, node_id)
    if target is None:
        return {
            "ok": False,
            "actions": [],
            "skipped": [{"reason": "node_missing", "node_id": node_id, "graph": str(graph_path)}],
            "summary": {"applied": 0, "skipped": 1},
        }

    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    changed = False

    dispatch_ids = _dispatch_ids_for_item(target) | _dispatch_ids_for_item(result_entry)
    handoff_path = _node_handoff_path(sprint_id, node_id)

    if task_id in dispatch_ids:
        if handoff_path.exists() and handoff_path.stat().st_size > 0:
            if str(target.get("status") or "") == "reviewing":
                skipped.append(
                    {
                        "reason": "already_in_reviewing",
                        "sprint_id": sprint_id,
                        "node_id": node_id,
                        "task_id": task_id,
                    }
                )
            elif not apply:
                skipped.append(
                    {
                        "reason": "dry_run",
                        "sprint_id": sprint_id,
                        "node_id": node_id,
                        "task_id": task_id,
                        "target": "builder",
                    }
                )
            else:
                previous = {
                    k: target.get(k)
                    for k in ("status", "assigned_to", "dispatch_id", "dispatched_via", "pm_task_id", "operator_id")
                    if target.get(k) is not None
                }
                target.setdefault("completion_history", []).append(
                    {
                        "ts": now_s,
                        "reason": "pm_builder_complete",
                        "task_id": task_id,
                        "previous_dispatch": previous,
                        "handoff": str(handoff_path),
                    }
                )
                target["status"] = "reviewing"
                target["updated_at"] = now_s
                target["handoff_path"] = str(handoff_path)
                _clear_fields(target, ("assigned_to", "dispatch_id", "dispatched_via", "pm_task_id", "operator_id"))
                if isinstance(result_entry, dict):
                    result_entry["status"] = str(result_entry.get("status") or "reviewing")
                    result_entry["updated_at"] = now_s
                    result_entry["handoff_path"] = str(handoff_path)
                    result_entry.setdefault("completion_history", []).append(
                        {
                            "ts": now_s,
                            "reason": "pm_builder_complete",
                            "task_id": task_id,
                        }
                    )
                    _clear_fields(
                        result_entry,
                        ("assigned_to", "dispatch_id", "dispatched_via", "pm_task_id", "operator_id"),
                    )

                actions.append(
                    _action(
                        "mark_builder_reviewing",
                        task_id,
                        "applied",
                        f"{sprint_id}|{node_id}|{task_id}|{handoff_path}",
                        meta={"graph": str(graph_path), "handoff": str(handoff_path)},
                    )
                )
                changed = True
        else:
            skipped.append(
                {
                    "reason": "missing_handoff",
                    "task_id": task_id,
                    "node_id": node_id,
                    "graph": str(graph_path),
                    "handoff": str(handoff_path),
                }
            )
    else:
        skipped.append(
            {
                "reason": "dispatch_mismatch",
                "task_id": task_id,
                "node_id": node_id,
                "graph": str(graph_path),
                "dispatch_ids": sorted(dispatch_ids),
            }
        )

    eval_sidecar = _eval_sidecar_path(sprint_id, node_id)
    eval_dispatch_ids = _dispatch_ids_for_item(target) | _dispatch_ids_for_item(result_entry)
    eval_task_id = task_id

    if not eval_sidecar:
        if target.get("eval_assignments") or target.get("eval_dispatch_id"):
            skipped.append(
                {
                    "reason": "missing_eval_sidecar",
                    "node_id": node_id,
                    "task_id": eval_task_id,
                    "graph": str(graph_path),
                }
            )
    elif eval_task_id and eval_task_id in eval_dispatch_ids:
        assignments = target.get("eval_assignments")
        assignment_changed = False
        if isinstance(assignments, list):
            retained: list[Any] = []
            for item in assignments:
                if not (isinstance(item, dict) and str(item.get("task_id") or "") == eval_task_id):
                    retained.append(item)
            if retained != assignments:
                assignment_changed = True
            target["eval_assignments"] = retained
            if not retained:
                target.pop("eval_assignments", None)

        dispatch_matches = str(target.get("eval_dispatch_id") or "") == eval_task_id
        if dispatch_matches:
            _clear_fields(target, ("eval_dispatch_id", "eval_dispatched_at", "eval_operator_id"))
            assignment_changed = True

        if assignment_changed:
            if apply and isinstance(result_entry, dict):
                result_entry.setdefault("eval_requeue_history", []).append(
                    {
                        "ts": now_s,
                        "reason": "watchdog_projection_repair",
                        "task_id": eval_task_id,
                    }
                )
                if str(result_entry.get("eval_dispatch_id") or "") == eval_task_id:
                    _clear_fields(result_entry, ("eval_dispatch_id", "eval_dispatched_at", "eval_operator_id"))
                result_entry["updated_at"] = now_s
                target["updated_at"] = now_s

            if apply:
                actions.append(
                    _action(
                        "clear_evaluator_assignment",
                        eval_task_id,
                        "applied",
                        f"{sprint_id}|{node_id}|{eval_task_id}|eval",
                        meta={"graph": str(graph_path), "eval_sidecar": str(eval_sidecar)},
                    )
                )
                changed = True
            elif not apply:
                skipped.append(
                    {
                        "reason": "dry_run",
                        "sprint_id": sprint_id,
                        "node_id": node_id,
                        "task_id": eval_task_id,
                        "target": "evaluator",
                    }
                )
        elif apply and not assignment_changed:
            skipped.append(
                {
                    "reason": "no_eval_assignment_to_clear",
                    "sprint_id": sprint_id,
                    "node_id": node_id,
                    "task_id": eval_task_id,
                    "graph": str(graph_path),
                }
            )
    elif target.get("eval_assignments") or target.get("eval_dispatch_id"):
        skipped.append(
            {
                "reason": "dispatch_identity_mismatch",
                "node_id": node_id,
                "task_id": eval_task_id,
                "candidate_dispatch_ids": sorted(eval_dispatch_ids),
            }
        )

    if apply and changed:
        try:
            _write_json(graph_path, graph)
        except Exception as exc:
            return {
                "ok": False,
                "actions": actions,
                "skipped": skipped + [{"reason": f"graph_write_failed:{type(exc).__name__}", "task_id": task_id}],
                "summary": {"applied": len(actions), "skipped": len(skipped)},
            }

    return {
        "ok": bool(actions),
        "actions": actions,
        "skipped": skipped,
        "summary": {"applied": len(actions), "skipped": len(skipped)},
    }
