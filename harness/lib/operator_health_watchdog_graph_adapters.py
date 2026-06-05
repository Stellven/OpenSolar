#!/usr/bin/env python3
"""Graph assignment adapters used by operator-health-watchdog.

These adapters intentionally stay small and deterministic so watchdog can
reconcile only true transient provider failures and only when dispatch identity
matches exactly.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("HOME", ""))
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
SPRINTS_DIR = Path(os.environ.get("SOLAR_HARNESS_SPRINTS_DIR", HARNESS_DIR / "sprints"))

TRANSIENT_OPERATOR_FAILURE_RE = re.compile(
    r"runtime_state=(?:cooldown|quota_exhausted|auth_expired)|"
    r"you(?:'|’)ve hit .*limit|usage limit|rate[- ]?limit|quota(?:\s+exhausted)?|"
    r"auth_expired|not logged in|not authenticated",
    re.I,
)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.stem, suffix=".tmp", dir=str(path.parent))
    with open(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, str(path))


def _load_graph(graph_path: Path) -> dict[str, Any]:
    if not graph_path.exists():
        return {}
    try:
        return json.loads(graph_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _iter_graph_nodes(graph: dict[str, Any]):
    nodes = graph.get("nodes")
    if isinstance(nodes, dict):
        return nodes.items()
    if isinstance(nodes, list):
        return (
            (str(item.get("id") or item.get("node_id") or ""), item)
            for item in nodes
            if isinstance(item, dict)
        )
    return []


def _dispatch_ids_for_item(item: dict[str, Any] | None) -> set[str]:
    if not isinstance(item, dict):
        return set()
    keys = (
        "dispatch_id",
        "pm_task_id",
        "eval_dispatch_id",
    )
    values = []
    for key in keys:
        value = str(item.get(key) or "").strip()
        if value:
            values.append(value)
    task_id = str(item.get("task_id") or "").strip()
    if task_id:
        values.append(task_id)
    return set(values)


def _find_node_and_result(graph: dict[str, Any], node_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    target: dict[str, Any] | None = None
    for candidate_id, candidate in _iter_graph_nodes(graph):
        if str(candidate_id) != node_id:
            continue
        target = candidate
        break
    if target is None:
        return None, None
    node_results = graph.get("node_results")
    if not isinstance(node_results, dict):
        node_results = {}
    result_entry = node_results.get(node_id)
    if not isinstance(result_entry, dict):
        result_entry = None
    return target, result_entry


def _is_transient_provider_failure(reason: str) -> bool:
    pattern = TRANSIENT_OPERATOR_FAILURE_RE
    try:
        from pm_dispatch import TRANSIENT_OPERATOR_FAILURE_RE as pm_pattern

        if isinstance(pm_pattern, re.Pattern):
            pattern = pm_pattern
    except Exception:
        pass
    return bool(pattern.search(str(reason or "")))


def _is_exact_task_dispatch_match(task_id: str, target: dict[str, Any] | None, result_entry: dict[str, Any] | None) -> bool:
    dispatch_ids = set()
    dispatch_ids.update(_dispatch_ids_for_item(target))
    dispatch_ids.update(_dispatch_ids_for_item(result_entry))
    return str(task_id).strip() in dispatch_ids


def _clear_builder_assignment_fields(item: dict[str, Any]) -> None:
    if not isinstance(item, dict):
        return
    for key in ("assigned_to", "dispatch_id", "dispatched_via", "pm_task_id", "operator_id"):
        item.pop(key, None)


def _clear_evaluator_assignment_fields(item: dict[str, Any]) -> None:
    if not isinstance(item, dict):
        return
    for key in ("eval_dispatch_id", "eval_dispatched_at", "eval_operator_id"):
        item.pop(key, None)


def _write_graph(graph_path: Path, graph: dict[str, Any]) -> None:
    _atomic_write(graph_path, graph)


def release_builder_assignment_on_transient_provider_failure(record: dict[str, Any]) -> dict[str, Any]:
    """Release a builder node assignment only on transient provider failure and exact task identity."""
    reason = str(record.get("failure_reason") or "").strip()
    if not _is_transient_provider_failure(reason):
        return {"ok": False, "released": False, "reason": "not_transient_provider_failure"}

    sprint_id = str(record.get("sprint_id") or "").strip()
    node_id = str(record.get("node_id") or "").strip()
    task_id = str(record.get("task_id") or "").strip()
    if not sprint_id or not node_id or not task_id:
        return {"ok": False, "released": False, "reason": "missing_graph_identity"}

    graph_path = SPRINTS_DIR / f"{sprint_id}.task_graph.json"
    graph = _load_graph(graph_path)
    if not graph:
        return {"ok": False, "released": False, "reason": "graph_missing", "graph": str(graph_path)}

    target, result_entry = _find_node_and_result(graph, node_id)
    if target is None:
        return {"ok": False, "released": False, "reason": "node_missing", "graph": str(graph_path), "node_id": node_id}

    if not _is_exact_task_dispatch_match(task_id, target, result_entry):
        return {"ok": False, "released": False, "reason": "dispatch_mismatch", "graph": str(graph_path), "node_id": node_id}

    now = _now()
    previous_dispatch = {
        key: target.get(key)
        for key in ("status", "assigned_to", "dispatch_id", "dispatched_via", "pm_task_id", "operator_id")
        if target.get(key) is not None
    }
    target.setdefault("dispatch_requeue_history", []).append(
        {
            "ts": now,
            "reason": "transient_provider_failure",
            "task_id": task_id,
            "failure_reason": reason[:500],
            "previous_dispatch": previous_dispatch,
        }
    )
    target["status"] = "pending"
    target["updated_at"] = now
    target["requeue_reason"] = "transient_provider_failure"
    _clear_builder_assignment_fields(target)

    if isinstance(result_entry, dict):
        result_entry.setdefault("dispatch_requeue_history", []).append(
            {
                "ts": now,
                "reason": "transient_provider_failure",
                "task_id": task_id,
                "failure_reason": reason[:500],
            }
        )
        result_entry["status"] = "pending"
        result_entry["updated_at"] = now
        result_entry["requeue_reason"] = "transient_provider_failure"
        _clear_builder_assignment_fields(result_entry)
        if "operator_id" not in result_entry and record.get("operator_id"):
            result_entry["last_operator_id"] = str(record.get("operator_id"))

    _write_graph(graph_path, graph)
    return {
        "ok": True,
        "released": True,
        "graph": str(graph_path),
        "sprint_id": sprint_id,
        "node_id": node_id,
    }


def release_builder_assignment_on_transient_failure(record: dict[str, Any]) -> dict[str, Any]:
    """Public watchdog helper name used by the core runtime."""
    return release_builder_assignment_on_transient_provider_failure(record)


def release_evaluator_assignment_on_transient_provider_failure(record: dict[str, Any]) -> dict[str, Any]:
    """Clear evaluator assignment only on transient provider failure and exact task identity."""
    if str(record.get("requested_role") or "").strip().lower() != "evaluator":
        return {"ok": False, "released": False, "reason": "not_evaluator_task"}

    reason = str(record.get("failure_reason") or "").strip()
    if not _is_transient_provider_failure(reason):
        return {"ok": False, "released": False, "reason": "not_transient_provider_failure"}

    sprint_id = str(record.get("sprint_id") or "").strip()
    node_id = str(record.get("node_id") or "").strip()
    task_id = str(record.get("task_id") or "").strip()
    if not sprint_id or not node_id or not task_id:
        return {"ok": False, "released": False, "reason": "missing_graph_identity"}

    graph_path = SPRINTS_DIR / f"{sprint_id}.task_graph.json"
    graph = _load_graph(graph_path)
    if not graph:
        return {"ok": False, "released": False, "reason": "graph_missing", "graph": str(graph_path)}

    target, result_entry = _find_node_and_result(graph, node_id)
    if target is None:
        return {"ok": False, "released": False, "reason": "node_missing", "graph": str(graph_path), "node_id": node_id}

    had_assignment = False
    assignments = target.get("eval_assignments")
    if isinstance(assignments, list):
        retained = []
        for item in assignments:
            if isinstance(item, dict) and str(item.get("task_id") or "") == task_id:
                had_assignment = True
                continue
            retained.append(item)
        if retained:
            target["eval_assignments"] = retained
        else:
            target.pop("eval_assignments", None)
    elif assignments is not None:
        target.pop("eval_assignments", None)

    eval_dispatch_id = str(target.get("eval_dispatch_id") or "")
    if eval_dispatch_id == task_id:
        had_assignment = True
        for key in ("eval_dispatch_id", "eval_dispatched_at", "eval_operator_id"):
            target.pop(key, None)

    if not had_assignment:
        return {"ok": True, "released": False, "reason": "dispatch_mismatch", "graph": str(graph_path), "node_id": node_id}

    now = _now()
    target["updated_at"] = now
    target.setdefault("eval_requeue_history", []).append(
        {
            "ts": now,
            "reason": "transient_provider_failure",
            "task_id": task_id,
            "failure_reason": reason[:500],
        }
    )

    if isinstance(result_entry, dict):
        if str(result_entry.get("eval_dispatch_id") or "") == task_id:
            _clear_evaluator_assignment_fields(result_entry)
        result_entry["updated_at"] = now

    _write_graph(graph_path, graph)
    return {
        "ok": True,
        "released": True,
        "graph": str(graph_path),
        "sprint_id": sprint_id,
        "node_id": node_id,
    }


def release_evaluator_assignment_on_transient_failure(record: dict[str, Any]) -> dict[str, Any]:
    """Public watchdog helper name used by the core runtime."""
    return release_evaluator_assignment_on_transient_provider_failure(record)
