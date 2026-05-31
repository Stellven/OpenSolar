#!/usr/bin/env python3
"""graph_scheduler.py — machine-executable DAG scheduler for Solar Harness.

This module turns planner output (`sprint-<sid>.task_graph.json`) into concrete
dispatch decisions. It intentionally stays in Python so it can plug into the
existing S6 control plane without adding a TypeScript runtime dependency.

Core guarantees:
  - invalid DAGs fail fast (missing deps, cycles, duplicate nodes)
  - ready nodes require all dependencies to be passed
  - nodes with overlapping write_scope never share a batch
  - nodes without declared write_scope are treated as exclusive writers
  - parent sprint cannot pass until every node and required gate has passed
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from prerequisite_resolver import evaluate_prerequisite, iter_blocked

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
STATE_DB = Path(os.environ.get("HARNESS_STATE_DB", HARNESS_DIR / "run" / "state.db"))

TERMINAL_STATUSES = {"passed", "failed", "skipped", "cancelled", "skipped_parent_passed"}
ACTIVE_STATUSES = {"assigned", "dispatched", "in_progress", "running", "reviewing"}
READY_STATUSES = {"pending", "queued", "blocked", "worker_blocked", ""}
PASS_STATUSES = {"passed"}
CLOSED_NON_PASS_STATUSES = {"skipped", "cancelled", "skipped_parent_passed"}
SPRINTS_DIR = Path(os.environ.get("HARNESS_SPRINTS_DIR", HARNESS_DIR / "sprints"))

LABEL_ALIAS_GROUPS = [
    {
        "solar-harness-control-plane",
        "control-plane",
        "workflow.planning",
        "governance",
        "autopilot",
        "routing",
        "diagnostics",
        "harness.contracts",
        "harness.dag",
        "harness.status",
    },
    {
        "architecture-writing",
        "technical-writing",
        "architecture",
        "markdown",
        "docs",
        "documentation",
        "spec.write",
    },
    {
        "algorithm_design",
        "algorithm",
        "optimization",
        "runtime_design",
        "scheduler.design",
        "state-machine.design",
        "architecture",
        "data-modeling",
        "api-design",
    },
    {
        "code_impl",
        "ImplementationWorker",
        "python",
        "typescript",
        "refactor",
        "integration",
        "subprocess",
        "sqlite",
        "sqlite3",
    },
    {
        "test_generation",
        "test_execution",
        "testing",
        "pytest",
        "regression",
        "regression-tests",
        "integration-testing",
        "integration-tests",
        "bash-tests",
        "test.tdd",
    },
    {
        "solar-harness-verification",
        "solar-harness-compat-review",
        "compat-review",
        "compatibility",
        "harness.verification",
        "verification",
        "verifier",
        "review",
        "testing",
        "test_execution",
        "code.review",
    },
    {
        "ai-rag-pipeline",
        "rag",
        "retrieval",
        "knowledge",
        "harness.knowledge",
        "context.inject",
    },
    {
        "reporting",
        "report",
        "report.compile",
        "research.report.compile",
        "harness.reporting",
        "documentation",
        "technical-writing",
    },
    {
        "model.routing",
        "harness.model_routing",
        "model_routing",
        "models.lab_matrix",
        "models.show",
    },
    {
        "api-adapter",
        "api_adapter",
        "api.adapter",
        "api",
        "integration",
        "subprocess",
        "python",
        "provider.contract",
        "api-design",
        "schema",
    },
    {
        "browser.browse",
        "browser.qa",
        "browser",
        "browser.automation",
        "browser.agent",
        "web",
        "web.capture",
        "scraping",
        "crawler",
        "collector",
    },
    {
        "social",
        "social.monitor",
        "social_signal",
        "social.signal",
        "social_links",
        "entity.extract",
        "link.extract",
        "url.extract",
        "cross_source.dispatch",
        "github.dispatch",
        "hf.dispatch",
        "youtube.dispatch",
    },
    {
        "policy",
        "policy.verdict",
        "governance",
        "harness.contracts",
        "solar-harness-control-plane",
    },
    {
        "quota",
        "quota-management",
        "quota_fallback",
        "quota.fallback",
        "fallback",
        "observability",
        "metrics",
    },
]


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_graph(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def save_graph(path: str | Path, graph: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(p.parent),
        prefix=f".{p.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        tmp = Path(handle.name)
        handle.write(json.dumps(graph, indent=2, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, p)


def _sprint_id_for_graph(graph: dict[str, Any], graph_path: str | Path | None = None) -> str:
    sid = str(graph.get("sprint_id") or "").strip()
    if sid:
        return sid
    legacy_id = str(graph.get("id") or "").strip()
    if legacy_id:
        return legacy_id
    if graph_path:
        return Path(graph_path).name.removesuffix(".task_graph.json")
    return ""


def _status_path_for_graph(graph: dict[str, Any], graph_path: str | Path | None = None) -> Path:
    sid = _sprint_id_for_graph(graph, graph_path)
    if graph_path:
        return Path(graph_path).expanduser().parent / f"{sid}.status.json"
    return SPRINTS_DIR / f"{sid}.status.json"


def _ensure_status_cache_exists_from_graph(
    graph: dict[str, Any],
    graph_path: str | Path | None,
    status_path: Path,
    *,
    actor: str,
    event: str,
) -> dict[str, Any] | None:
    """Create the legacy status cache for an in-flight graph if it is missing."""
    if status_path.exists():
        return None
    sid = _sprint_id_for_graph(graph, graph_path)
    if not sid:
        return None
    now = _now()
    open_nodes = [
        str(node.get("id") or "")
        for node in graph.get("nodes", [])
        if str(node.get("status") or "") not in TERMINAL_STATUSES
    ]
    failed_nodes = [
        str(node.get("id") or "")
        for node in graph.get("nodes", [])
        if str(node.get("status") or "") == "failed"
    ]
    status = {
        "id": sid,
        "sprint_id": sid,
        "title": str(graph.get("title") or sid),
        "status": "active",
        "phase": "graph_in_progress",
        "handoff_to": "builder_main",
        "target_role": "builder_main",
        "created_at": str(graph.get("created_at") or now),
        "updated_at": now,
        "task_graph": str(graph_path or ""),
        "graph_status_cache": True,
        "graph_parent_ready": parent_ready_check(graph),
        "active_node": open_nodes[0] if open_nodes else None,
        "open_nodes": open_nodes,
        "failed_nodes": failed_nodes,
        "history": [
            {
                "ts": now,
                "event": event,
                "by": actor,
                "note": "created missing status cache from task_graph",
            }
        ],
    }
    tmp = status_path.with_suffix(status_path.suffix + ".tmp")
    tmp.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, status_path)
    return status


def sync_status_cache_from_graph(
    graph: dict[str, Any],
    graph_path: str | Path | None = None,
    *,
    actor: str = "graph_scheduler",
    event: str = "graph_parent_ready_passed",
) -> dict[str, Any]:
    """Project a completed task_graph into the legacy sprint status cache.

    `task_graph.json` is the scheduler source of truth, while
    `status.json` is a compatibility projection used by epic activation,
    status UI, exports, and old monitors. Keeping this projection in the same
    write path as graph closeout prevents a passed DAG from looking active.
    """
    parent = parent_ready_check(graph)
    sid = _sprint_id_for_graph(graph, graph_path)
    status_path = _status_path_for_graph(graph, graph_path)
    result: dict[str, Any] = {
        "ok": True,
        "updated": False,
        "created": False,
        "sprint_id": sid,
        "status_path": str(status_path),
        "parent": parent,
    }
    if not sid:
        result.update({"ok": False, "reason": "missing_sprint_id"})
        return result
    created_status = _ensure_status_cache_exists_from_graph(
        graph,
        graph_path,
        status_path,
        actor=actor,
        event=event,
    )
    if created_status is not None:
        result.update({"created": True, "status": created_status})
    if not status_path.exists():
        result["reason"] = "status_missing"
        return result
    try:
        current = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result.update({"ok": False, "reason": "status_corrupt", "error": str(exc)})
        return result
    if not parent.get("ready"):
        now = _now()
        open_nodes = parent.get("open_nodes") or []
        failed_nodes = parent.get("failed_nodes") or []
        desired_active_node = open_nodes[0] if open_nodes else None
        history = current.get("history")
        if not isinstance(history, list):
            history = []
        if str(current.get("status") or "").lower() == "passed":
            history.append({
                "ts": now,
                "event": "graph_parent_ready_revoked",
                "by": actor,
                "note": "task_graph no longer satisfies parent_ready_check; reopening legacy status cache",
            })
            current.update({
                "status": "active",
                "phase": "graph_in_progress",
                "stage": "graph_in_progress",
                "active_node": desired_active_node,
                "open_nodes": open_nodes,
                "failed_nodes": failed_nodes,
                "graph_parent_ready": parent,
                "task_graph_status": "active",
                "updated_at": now,
                "completed_at": None,
                "history": history,
            })
            tmp = status_path.with_suffix(status_path.suffix + ".tmp")
            tmp.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, status_path)
            result.update({"updated": True, "status": current, "reason": "parent_reopened"})
            return result
        projection_changed = any([
            current.get("active_node") != desired_active_node,
            list(current.get("open_nodes") or []) != list(open_nodes),
            list(current.get("failed_nodes") or []) != list(failed_nodes),
            (current.get("graph_parent_ready") or {}) != parent,
            str(current.get("task_graph_status") or "") != "active",
        ])
        if projection_changed:
            history.append({
                "ts": now,
                "event": "graph_parent_projection_refreshed",
                "by": actor,
                "note": "task_graph changed while in flight; refreshing legacy status projection",
            })
            current.update({
                "active_node": desired_active_node,
                "open_nodes": open_nodes,
                "failed_nodes": failed_nodes,
                "graph_parent_ready": parent,
                "task_graph_status": "active",
                "updated_at": now,
                "history": history,
            })
            tmp = status_path.with_suffix(status_path.suffix + ".tmp")
            tmp.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, status_path)
            result.update({"updated": True, "status": current, "reason": "parent_projection_refreshed"})
            return result
        result["reason"] = "parent_not_ready"
        return result

    already_passed = str(current.get("status") or "").lower() == "passed"
    already_closed = not current.get("active_node") and str(current.get("stage") or "").lower() in {
        "completed",
        "done",
        "",
    }
    if already_passed and already_closed and (current.get("graph_parent_ready") or {}).get("ready") is True:
        result["reason"] = "already_synced"
        return result

    try:
        from runtime_status import transition_status  # noqa: WPS433

        updated, message = transition_status(
            status_path,
            "passed",
            event,
            actor,
            extra={
                "graph_sync": True,
                "graph_path": str(graph_path or ""),
                "status_fields": {
                    "phase": "completed",
                    "stage": "completed",
                    "active_node": None,
                    "graph_parent_ready": parent,
                    "task_graph_status": "passed",
                },
            },
        )
        result.update({"updated": True, "message": message, "status": updated})
    except Exception as exc:
        result.update({"ok": False, "reason": "transition_failed", "error": str(exc)})
    return result


def _source_text_for_graph(graph_path: str | Path | None, explicit_source: str | Path | None = None) -> str:
    paths: list[Path] = []
    if explicit_source:
        paths.append(Path(explicit_source))
    if graph_path:
        graph_p = Path(graph_path)
        if graph_p.name.endswith(".task_graph.json"):
            stem = graph_p.name[:-len(".task_graph.json")]
            paths.extend([
                graph_p.with_name(f"{stem}.contract.md"),
                graph_p.with_name(f"{stem}.plan.md"),
            ])
    chunks: list[str] = []
    seen: set[Path] = set()
    for path in paths:
        path = path.expanduser()
        if path in seen or not path.exists() or not path.is_file():
            continue
        seen.add(path)
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n\n".join(chunks)


def auto_enrich_graph(graph: dict[str, Any], graph_path: str | Path | None = None,
                      source: str | Path | None = None) -> dict[str, Any]:
    """Best-effort capability enrichment for default dispatch paths."""
    try:
        from capability_inference import enrich_graph  # noqa: WPS433

        return enrich_graph(graph, source_text=_source_text_for_graph(graph_path, source))
    except Exception:
        return graph


def _changed_nodes(graph: dict[str, Any]) -> list[str]:
    info = graph.get("capability_inference") or {}
    changed = info.get("changed_nodes") or []
    if isinstance(changed, list):
        return [str(item) for item in changed if str(item)]
    return []


def _required_capability_snapshot(graph: dict[str, Any]) -> dict[str, list[str]]:
    snapshot: dict[str, list[str]] = {}
    try:
        nodes = _nodes(graph)
    except Exception:
        return snapshot
    for node in nodes:
        node_id = str(node.get("id", ""))
        if not node_id:
            continue
        if "required_capabilities" not in node:
            snapshot[node_id] = ["__MISSING_REQUIRED_CAPABILITIES__"]
            continue
        snapshot[node_id] = _capability_list(node)
    return snapshot


def _nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("task_graph.nodes must be a list")
    return nodes


def _node_map(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for node in _nodes(graph):
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("every task graph node requires non-empty id")
        if node_id in result:
            raise ValueError(f"duplicate node id: {node_id}")
        result[node_id] = node
    return result


def _node_results(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = graph.get("node_results") or graph.get("results") or {}
    return results if isinstance(results, dict) else {}


def _parse_ts(value: Any) -> datetime.datetime | None:
    if not value:
        return None
    try:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.datetime.fromisoformat(raw)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _status_rank(status: str) -> int:
    value = str(status or "pending").lower()
    if value in {"passed", "failed", "skipped", "cancelled"}:
        return 5
    if value == "reviewing":
        return 4
    if value in {"in_progress", "running", "working"}:
        return 3
    if value in {"dispatched", "sent"}:
        return 2
    if value in {"assigned", "queued"}:
        return 1
    return 0


def _node_eval_json_candidates(graph: dict[str, Any], node_id: str) -> list[Path]:
    node = _node_map(graph)[node_id]
    result = _node_results(graph).get(node_id) if isinstance(_node_results(graph).get(node_id), dict) else {}
    sid = _sprint_id_for_graph(graph)
    artifacts = node.get("artifacts") if isinstance(node.get("artifacts"), dict) else {}
    result_artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
    raw_candidates = [
        node.get("eval_json"),
        result.get("eval_json"),
        artifacts.get("eval_json"),
        result_artifacts.get("eval_json"),
        str(SPRINTS_DIR / f"{sid}.{node_id}-eval.json") if sid else "",
    ]
    candidates: list[Path] = []
    for raw in raw_candidates:
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            candidates.append(Path(text).expanduser())
        except Exception:
            continue
    return candidates


def _first_existing_path(candidates: list[Path]) -> Path | None:
    for path in candidates:
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def _portable_artifact_ref(path: Path) -> str:
    try:
        resolved = path.expanduser().resolve()
        sprint_root = SPRINTS_DIR.expanduser().resolve()
        if resolved.parent == sprint_root:
            return resolved.name
        return str(resolved)
    except Exception:
        return str(path)


def _workspace_root() -> str:
    explicit = str(os.environ.get("SOLAR_WORKSPACE_ROOT") or "").strip()
    if explicit:
        return explicit
    cwd = str(Path.cwd())
    if cwd:
        return cwd
    return str(HARNESS_DIR.parent)


def _normalize_eval_sidecar_payload(
    payload: dict[str, Any],
    *,
    sid: str,
    node_id: str,
    command_line: str,
) -> tuple[dict[str, Any], bool]:
    changed = False
    normalized = dict(payload)
    defaults = {
        "schema_version": "solar.eval.v1",
        "sprint_id": sid,
        "node_id": node_id,
        "generated_by": "graph_scheduler.doctor",
        "generation_mode": "repair_backfill",
        "command_line": command_line,
        "workspace_root": _workspace_root(),
    }
    verdict = str(normalized.get("verdict") or "").strip().upper()
    proof_level = "independent_verification" if verdict in {"PASS", "FAIL"} else "unknown"
    defaults["proof_level"] = proof_level
    for key, value in defaults.items():
        current = normalized.get(key)
        if current in (None, ""):
            normalized[key] = value
            changed = True
    return normalized, changed


def _sync_node_evidence_refs(
    graph: dict[str, Any],
    node_id: str,
    *,
    repair: bool = False,
    command_line: str = "python3 lib/graph_scheduler.py doctor --repair",
) -> dict[str, Any]:
    node = _node_map(graph)[node_id]
    sid = _sprint_id_for_graph(graph)
    graph.setdefault("node_results", {})
    result = graph["node_results"].setdefault(node_id, {})
    artifacts = node.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
        node["artifacts"] = artifacts
    result_artifacts = result.get("artifacts")
    if not isinstance(result_artifacts, dict):
        result_artifacts = {}
        result["artifacts"] = result_artifacts

    outcome = {"issues": [], "repairs": []}

    handoff_path = _first_existing_path(_node_handoff_candidates(graph, node_id))
    if handoff_path is not None:
        handoff_ref = _portable_artifact_ref(handoff_path)
        if node.get("handoff_md") != handoff_ref:
            outcome["issues"].append({"type": "handoff_exists_inline_missing", "node": node_id, "path": str(handoff_path)})
            if repair:
                node["handoff_md"] = handoff_ref
                artifacts["handoff_md"] = handoff_ref
                result_artifacts["handoff_md"] = handoff_ref
                outcome["repairs"].append({"type": "handoff_exists_inline_missing", "node": node_id, "repair": "backfilled_handoff_md"})

    eval_path = _first_existing_path(_node_eval_json_candidates(graph, node_id))
    if eval_path is None:
        stale_eval_values = {
            "node": node.get("eval_json"),
            "result": result.get("eval_json"),
            "artifact": artifacts.get("eval_json"),
            "result_artifact": result_artifacts.get("eval_json"),
        }
        if any(str(value or "").strip() for value in stale_eval_values.values()):
            outcome["issues"].append({"type": "stale_eval_ref_missing_file", "node": node_id, "values": stale_eval_values})
            if repair:
                node.pop("eval_json", None)
                result.pop("eval_json", None)
                artifacts.pop("eval_json", None)
                result_artifacts.pop("eval_json", None)
                outcome["repairs"].append({"type": "stale_eval_ref_missing_file", "node": node_id, "repair": "cleared_stale_eval_json_refs"})
        return outcome
    eval_ref = _portable_artifact_ref(eval_path)
    inline_values = {
        "node": node.get("eval_json"),
        "result": result.get("eval_json"),
        "artifact": artifacts.get("eval_json"),
        "result_artifact": result_artifacts.get("eval_json"),
    }
    if any(not value for value in inline_values.values()):
        outcome["issues"].append({"type": "eval_exists_inline_missing", "node": node_id, "path": str(eval_path)})
        if repair:
            node["eval_json"] = eval_ref
            result["eval_json"] = eval_ref
            artifacts["eval_json"] = eval_ref
            result_artifacts["eval_json"] = eval_ref
            outcome["repairs"].append({"type": "eval_exists_inline_missing", "node": node_id, "repair": "backfilled_eval_json"})
    elif any(str(value) != eval_ref for value in inline_values.values()):
        outcome["issues"].append({"type": "eval_ref_drift", "node": node_id, "path": str(eval_path), "values": inline_values})
        if repair:
            node["eval_json"] = eval_ref
            result["eval_json"] = eval_ref
            artifacts["eval_json"] = eval_ref
            result_artifacts["eval_json"] = eval_ref
            outcome["repairs"].append({"type": "eval_ref_drift", "node": node_id, "repair": "normalized_eval_json_ref"})

    try:
        payload = json.loads(eval_path.read_text(encoding="utf-8"))
    except Exception:
        return outcome
    if not isinstance(payload, dict):
        return outcome
    normalized, changed = _normalize_eval_sidecar_payload(
        payload,
        sid=sid,
        node_id=node_id,
        command_line=command_line,
    )
    if changed:
        outcome["issues"].append({"type": "eval_missing_provenance", "node": node_id, "path": str(eval_path)})
        if repair:
            tmp = eval_path.with_suffix(eval_path.suffix + ".tmp")
            tmp.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, eval_path)
            outcome["repairs"].append({"type": "eval_missing_provenance", "node": node_id, "repair": "normalized_eval_sidecar_provenance"})
    return outcome


def _node_handoff_candidates(graph: dict[str, Any], node_id: str) -> list[Path]:
    node = _node_map(graph)[node_id]
    sid = _sprint_id_for_graph(graph)
    artifacts = node.get("artifacts") if isinstance(node.get("artifacts"), dict) else {}
    raw_candidates = [
        node.get("handoff_md"),
        artifacts.get("handoff_md"),
        str(SPRINTS_DIR / f"{sid}.{node_id}-handoff.md") if sid else "",
    ]
    candidates: list[Path] = []
    for raw in raw_candidates:
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            candidates.append(Path(text).expanduser())
        except Exception:
            continue
    return candidates


def _node_has_eval_json(graph: dict[str, Any], node_id: str) -> bool:
    return any(path.exists() for path in _node_eval_json_candidates(graph, node_id))


def _node_has_handoff(graph: dict[str, Any], node_id: str) -> bool:
    return any(path.exists() for path in _node_handoff_candidates(graph, node_id))


def _passed_without_required_eval(graph: dict[str, Any], node_id: str) -> bool:
    """Treat handoff-backed passed nodes without eval sidecar as not yet passed."""
    return _node_has_handoff(graph, node_id) and not _node_has_eval_json(graph, node_id)


def _assert_pass_mark_allowed(graph: dict[str, Any], node_id: str, status: str) -> None:
    normalized = str(status or "").lower()
    if normalized != "passed":
        return
    if _passed_without_required_eval(graph, node_id):
        raise ValueError(f"passed_requires_eval_json:{node_id}")


def _ensure_required_gate_node_mapping(graph: dict[str, Any]) -> int:
    ids = _node_map(graph)
    if not ids:
        return 0
    required = [str(g) for g in (graph.get("required_gates") or []) if g]
    if not required:
        return 0
    required_set = set(required)
    dag_variant = str(graph.get("dag_variant") or "").strip().lower()
    mapping: dict[str, str] = {}
    if dag_variant == "short" or required_set == {"G_IMPL", "G_TEST", "G_REVIEW"}:
        mapping = {"S1": "G_IMPL", "S2": "G_TEST", "S3": "G_REVIEW"}
    elif dag_variant == "standard" or required_set == {"G_PLAN", "G_IMPL", "G_VERIFY", "G_REVIEW"}:
        mapping = {
            "S1": "G_PLAN",
            "S2": "G_IMPL",
            "S3": "G_VERIFY",
            "S4": "G_REVIEW",
            "S5": "G_REVIEW",
        }
    elif dag_variant == "research" or required_set == {"G_SOURCE", "G_EVIDENCE", "G_SYNTHESIS", "G_REVIEW"}:
        mapping = {
            "R1": "G_SOURCE",
            "R2": "G_EVIDENCE",
            "R3": "G_EVIDENCE",
            "R4": "G_SYNTHESIS",
            "R5": "G_REVIEW",
            "R6": "G_REVIEW",
        }

    assigned = 0
    for node_id, node in ids.items():
        if node.get("gate"):
            continue
        gate = mapping.get(node_id)
        if gate and gate in required_set:
            node["gate"] = gate
            assigned += 1

    owners: dict[str, list[str]] = {gate: [] for gate in required}
    for node_id, node in ids.items():
        gate = str(node.get("gate") or "")
        if gate in owners:
            owners[gate].append(node_id)

    missing = [gate for gate in required if not owners.get(gate)]
    if not missing:
        return assigned

    try:
        ordered_ids = topo_order(graph)
    except Exception:
        ordered_ids = list(ids.keys())
    unassigned = [node_id for node_id in ordered_ids if not ids[node_id].get("gate")]
    for gate, node_id in zip(missing, unassigned):
        ids[node_id]["gate"] = gate
        assigned += 1
    return assigned


def node_status(graph: dict[str, Any], node_id: str) -> str:
    _ensure_required_gate_node_mapping(graph)
    results = _node_results(graph)
    node = _node_map(graph)[node_id]
    gate = node.get("gate")
    gate_results = graph.get("gate_results") or {}
    gate_passed = bool(
        gate
        and isinstance(gate_results.get(gate), dict)
        and gate_results[gate].get("status") == "passed"
    )
    if node_id in results and isinstance(results[node_id], dict):
        result_status = str(results[node_id].get("status", "") or "").lower()
        node_status_value = str(node.get("status", "pending") or "pending").lower()
        if gate_passed and "failed" not in {result_status, node_status_value}:
            status = "passed"
        else:
            result_rank = _status_rank(result_status)
            node_rank = _status_rank(node_status_value)
            if result_rank != node_rank:
                status = result_status if result_rank > node_rank else node_status_value
            else:
                result_ts = _parse_ts(results[node_id].get("updated_at"))
                node_ts = _parse_ts(node.get("updated_at"))
                if result_ts and node_ts and node_ts > result_ts:
                    status = node_status_value
                else:
                    status = result_status
    elif gate_passed and str(node.get("status", "pending") or "pending").lower() != "failed":
        status = "passed"
    else:
        status = str(node.get("status", "pending") or "pending").lower()

    if status == "passed" and _passed_without_required_eval(graph, node_id):
        return "reviewing"
    return status


def _depends_on(node: dict[str, Any]) -> list[str]:
    deps = node.get("depends_on", [])
    if deps is None:
        return []
    if not isinstance(deps, list):
        raise ValueError(f"{node.get('id')}.depends_on must be a list")
    return [str(d) for d in deps]


def _is_external_dependency(dep: str) -> bool:
    return str(dep or "").startswith("external:")


def _internal_depends_on(node: dict[str, Any]) -> list[str]:
    return [dep for dep in _depends_on(node) if not _is_external_dependency(dep)]


def _estimated_cost(node: dict[str, Any]) -> float:
    try:
        return float(node.get("estimated_cost", 1) or 1)
    except Exception:
        return 1.0


def validate_graph(graph: dict[str, Any]) -> dict[str, Any]:
    ids = _node_map(graph)
    errors: list[str] = []
    warnings: list[str] = []

    for node_id, node in ids.items():
        for dep in _depends_on(node):
            if _is_external_dependency(dep):
                continue
            if dep not in ids:
                errors.append(f"{node_id} depends on missing node {dep}")
        if "write_scope" not in node or not node.get("write_scope"):
            warnings.append(f"{node_id} missing write_scope; scheduler will serialize it")
        if "acceptance" not in node:
            warnings.append(f"{node_id} missing acceptance")
        if "required_capabilities" not in node:
            try:
                from capability_inference import infer_node_capabilities  # noqa: WPS433

                inferred = infer_node_capabilities(node)
                if inferred.get("capabilities"):
                    caps = ",".join(inferred["capabilities"])
                    warnings.append(f"{node_id} inferred capabilities available but missing required_capabilities: {caps}")
            except Exception:
                pass

    try:
        topo_order(graph)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        from architecture_guard import assess_graph  # noqa: WPS433

        arch = assess_graph(graph)
        errors.extend(f"architecture_guard:{e}" for e in arch.get("errors", []))
        warnings.extend(f"architecture_guard:{w}" for w in arch.get("warnings", []))
    except Exception as exc:
        warnings.append(f"architecture_guard unavailable: {type(exc).__name__}")

    return {
        "ok": not errors,
        "sprint_id": graph.get("sprint_id"),
        "node_count": len(ids),
        "errors": errors,
        "warnings": warnings,
    }


def topo_order(graph: dict[str, Any]) -> list[str]:
    ids = _node_map(graph)
    indegree = {node_id: 0 for node_id in ids}
    outgoing = {node_id: [] for node_id in ids}

    for node_id, node in ids.items():
        for dep in _depends_on(node):
            if _is_external_dependency(dep):
                continue
            if dep not in ids:
                raise ValueError(f"{node_id} depends on missing node {dep}")
            indegree[node_id] += 1
            outgoing[dep].append(node_id)

    queue = sorted([node_id for node_id, deg in indegree.items() if deg == 0])
    order: list[str] = []
    while queue:
        node_id = queue.pop(0)
        order.append(node_id)
        for child in sorted(outgoing[node_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
                queue.sort()

    if len(order) != len(ids):
        cycle_nodes = sorted([node_id for node_id, deg in indegree.items() if deg > 0])
        raise ValueError("cycle detected: " + ", ".join(cycle_nodes))
    return order


def topo_layers(graph: dict[str, Any]) -> list[list[str]]:
    ids = _node_map(graph)
    remaining = set(ids)
    passed: set[str] = set()
    layers: list[list[str]] = []

    while remaining:
        layer = sorted([
            node_id for node_id in remaining
            if all(dep in passed for dep in _internal_depends_on(ids[node_id]))
        ])
        if not layer:
            raise ValueError("cycle detected while building layers")
        layers.append(layer)
        remaining -= set(layer)
        passed.update(layer)
    return layers


def critical_path(graph: dict[str, Any]) -> dict[str, Any]:
    ids = _node_map(graph)
    order = topo_order(graph)
    best_cost: dict[str, float] = {}
    best_path: dict[str, list[str]] = {}

    for node_id in order:
        node = ids[node_id]
        deps = _internal_depends_on(node)
        if not deps:
            best_cost[node_id] = _estimated_cost(node)
            best_path[node_id] = [node_id]
            continue
        parent = max(deps, key=lambda dep: best_cost.get(dep, 0))
        best_cost[node_id] = best_cost.get(parent, 0) + _estimated_cost(node)
        best_path[node_id] = best_path.get(parent, [parent]) + [node_id]

    if not order:
        return {"cost": 0, "path": []}
    end = max(order, key=lambda node_id: best_cost.get(node_id, 0))
    return {"cost": best_cost[end], "path": best_path[end]}


def _is_passed(graph: dict[str, Any], node_id: str) -> bool:
    return node_status(graph, node_id) in PASS_STATUSES


def blocked_external_prerequisites(graph: dict[str, Any]) -> list[dict[str, Any]]:
    blocked = list(iter_blocked(graph, SPRINTS_DIR))
    seen = {str(item.get("requirement") or "") for item in blocked}
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        for dep in _depends_on(node):
            if not _is_external_dependency(dep):
                continue
            ok, detail = evaluate_prerequisite(dep, SPRINTS_DIR)
            detail["source"] = "depends_on"
            detail["node_id"] = node_id
            key = str(detail.get("requirement") or dep)
            if not ok and key not in seen:
                blocked.append(detail)
                seen.add(key)
    return blocked


def ready_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    validation = validate_graph(graph)
    if not validation["ok"]:
        raise ValueError("; ".join(validation["errors"]))
    if blocked_external_prerequisites(graph):
        return []

    ids = _node_map(graph)
    ready: list[dict[str, Any]] = []
    for node_id in topo_order(graph):
        status = node_status(graph, node_id)
        if status in TERMINAL_STATUSES or status in ACTIVE_STATUSES:
            continue
        if status not in READY_STATUSES:
            continue
        deps = _internal_depends_on(ids[node_id])
        if all(_is_passed(graph, dep) for dep in deps):
            ready.append(deepcopy(ids[node_id]))
    return ready


def _scope_list(node: dict[str, Any]) -> list[str]:
    scopes = node.get("write_scope")
    if not scopes:
        return []
    if isinstance(scopes, str):
        return [scopes]
    if not isinstance(scopes, list):
        raise ValueError(f"{node.get('id')}.write_scope must be a string or list")
    return [str(scope) for scope in scopes if str(scope)]


def _scope_overlap(a: str, b: str) -> bool:
    if a == b:
        return True
    a_norm = a.rstrip("/") + "/"
    b_norm = b.rstrip("/") + "/"
    return a_norm.startswith(b_norm) or b_norm.startswith(a_norm)


def write_scope_conflict(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a_scopes = _scope_list(a)
    b_scopes = _scope_list(b)

    # Missing write_scope means exclusive writer. It cannot safely share a batch.
    if not a_scopes or not b_scopes:
        return True
    return any(_scope_overlap(sa, sb) for sa in a_scopes for sb in b_scopes)


def _node_effect_union(node: dict[str, Any]) -> dict[str, list[str]]:
    for key in ("effect_union",):
        raw = node.get(key)
        if isinstance(raw, dict):
            return {str(k): [str(item) for item in (v or [])] for k, v in raw.items()}
    for key in ("physical_plan_ir", "capsule_plan_ir"):
        raw = node.get(key)
        if isinstance(raw, dict):
            effect_union = raw.get("effect_union")
            if isinstance(effect_union, dict):
                return {str(k): [str(item) for item in (v or [])] for k, v in effect_union.items()}
    return {}


def _node_has_exclusive_effect(node: dict[str, Any]) -> bool:
    effect_union = _node_effect_union(node)
    risks = {str(item) for item in effect_union.get("risk", [])}
    writes = {str(item) for item in effect_union.get("write", [])}
    executes = {str(item) for item in effect_union.get("execute", [])}
    if risks & {"secrets_access", "destructive_shell", "git_push", "patch_scope_drift"}:
        return True
    if "repo.worktree" in writes and executes:
        return True
    return False


def effect_conflict(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return _node_has_exclusive_effect(a) or _node_has_exclusive_effect(b)


def _batch_ready_nodes(nodes: list[dict[str, Any]], max_parallel: int | None = None) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    for node in nodes:
        placed = False
        for batch in batches:
            if max_parallel and len(batch) >= max_parallel:
                continue
            if any(write_scope_conflict(node, other) for other in batch):
                continue
            if any(effect_conflict(node, other) for other in batch):
                continue
            batch.append(node)
            placed = True
            break
        if not placed:
            batches.append([node])
    return batches


def make_batches(graph: dict[str, Any], max_parallel: int | None = None) -> dict[str, Any]:
    blocked = blocked_external_prerequisites(graph)
    nodes = ready_nodes(graph)
    batches = _batch_ready_nodes(nodes, max_parallel=max_parallel)
    return {
        "ok": True,
        "sprint_id": graph.get("sprint_id"),
        "blocked_prerequisites": blocked,
        "batch_count": len(batches),
        "batches": [
            {
                "id": f"batch-{idx + 1}",
                "join_gate": [node.get("gate") for node in batch if node.get("gate")],
                "nodes": [node["id"] for node in batch],
            }
            for idx, batch in enumerate(batches)
        ],
    }


def _worker_busy(worker: dict[str, Any]) -> bool:
    return bool(worker.get("busy")) or str(worker.get("status", "")).lower() in {"busy", "leased", "running"}


def _worker_unavailable_reason(worker: dict[str, Any]) -> str:
    return str(worker.get("unavailable_reason") or "").strip()


def _worker_quota_exhausted(worker: dict[str, Any], preferred_model: str | None = None) -> bool:
    exhausted = worker.get("quota_exhausted", False)
    if isinstance(exhausted, bool):
        return exhausted
    if isinstance(exhausted, list):
        exhausted_aliases: set[str] = set()
        for item in exhausted:
            exhausted_aliases.update(_model_aliases(str(item)))
        if preferred_model:
            return bool(_model_aliases(preferred_model) & exhausted_aliases)
        model_aliases = [_model_aliases(str(model)) for model in worker.get("models", []) or []]
        model_aliases = [aliases for aliases in model_aliases if aliases]
        return bool(model_aliases) and all(aliases & exhausted_aliases for aliases in model_aliases)
    return False


def _model_aliases(value: str | None) -> set[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return set()
    aliases = {raw}
    if raw in {"sonnet", "claude-sonnet", "anthropic-sonnet"}:
        aliases.update({"sonnet", "claude-sonnet", "anthropic-sonnet", "claude", "anthropic"})
    elif raw in {"opus", "claude-opus", "anthropic-opus", "opus-4.7", "opus-4-7", "claude-opus-4.7", "claude-opus-4-7"}:
        aliases.update({"opus", "claude-opus", "anthropic-opus", "opus-4.7", "opus-4-7", "claude", "anthropic"})
    elif raw in {"glm", "glm-5", "glm-5.1", "zhipu", "zhipu-glm-5.1"}:
        aliases.update({"glm", "glm-5", "glm-5.1", "zhipu", "zhipu-glm-5.1"})
    elif raw in {"deepseek", "deepseek-v4", "deepseek-v4-pro"}:
        aliases.update({"deepseek", "deepseek-v4", "deepseek-v4-pro"})
    return aliases


def _model_match(worker: dict[str, Any], preferred_model: str | None) -> bool:
    if not preferred_model:
        return True
    models = [str(m).lower() for m in worker.get("models", [])]
    if not models:
        return True
    preferred = _model_aliases(preferred_model)
    available: set[str] = set()
    for model in models:
        available.update(_model_aliases(model))
    return bool(preferred & available)


def _model_requires_strict_match(preferred_model: str | None, strict_model: bool = False) -> bool:
    if not preferred_model or not strict_model:
        return False
    normalized = preferred_model.lower()
    return normalized in {"glm", "glm-5", "glm-5.1", "zhipu"}


def _label_aliases(value: Any) -> set[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return set()
    aliases = {raw}
    parts = [part.strip() for part in raw.split(".") if part.strip()]
    if len(parts) > 1:
        for end in range(1, len(parts)):
            aliases.add(".".join(parts[:end]))
        aliases.add(parts[-1])
        if parts[-1] == "design":
            aliases.add("architecture")
    for group in LABEL_ALIAS_GROUPS:
        if raw in group:
            aliases.update(group)
    return aliases


def _skill_aliases(value: Any) -> set[str]:
    return _label_aliases(value)


def _skill_match_count(worker: dict[str, Any], required_skills: list[str]) -> int:
    if not required_skills:
        return 0
    worker_aliases: set[str] = set()
    for skill in worker.get("skills", []) or []:
        worker_aliases.update(_skill_aliases(skill))

    matches = 0
    for required in required_skills:
        if _skill_aliases(required) & worker_aliases:
            matches += 1
    return matches


def _skills_match(worker: dict[str, Any], required_skills: list[str],
                  required_capabilities: list[str] | None = None) -> bool:
    if not required_skills:
        return True
    matched = _skill_match_count(worker, required_skills)
    if matched >= len(required_skills):
        return True
    if required_capabilities:
        threshold = max(1, (len(required_skills) + 1) // 2)
        return matched >= threshold
    return False


def _capability_list(obj: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("required_capabilities", "capabilities"):
        raw = obj.get(key, [])
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, list):
            values.extend(str(item) for item in raw if str(item))
    return values


def _load_capability_scores() -> dict[str, float]:
    if not STATE_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(str(STATE_DB), timeout=2.0)
        rows = conn.execute("SELECT capability, provider, score FROM capability_scorecards").fetchall()
        conn.close()
    except Exception:
        return {}
    scores: dict[str, float] = {}
    for capability, provider, score in rows:
        try:
            value = float(score)
        except Exception:
            value = 0.0
        scores[f"{provider}::{capability}"] = max(value, scores.get(f"{provider}::{capability}", 0.0))
        scores[f"cap::{capability}"] = max(value, scores.get(f"cap::{capability}", 0.0))
    return scores


def _worker_capabilities(worker: dict[str, Any]) -> list[str]:
    caps = _capability_list(worker)
    # Worker topology has historically mixed skill-like labels (for example
    # "cli" or "frontend") into required_capabilities. Match against both
    # fields so enriched DAG nodes are not stranded as no_matching_worker when
    # the worker advertises the ability under skills instead of capabilities.
    for item in worker.get("skills", []) or []:
        text = str(item)
        if text and text not in caps:
            caps.append(text)
    expanded: list[str] = []
    seen: set[str] = set()
    for item in caps:
        for alias in _label_aliases(item):
            if alias not in seen:
                seen.add(alias)
                expanded.append(alias)
    return expanded


def _capabilities_match(worker: dict[str, Any], required_capabilities: list[str]) -> bool:
    if not required_capabilities:
        return True
    caps = set(_worker_capabilities(worker))
    for item in required_capabilities:
        if not (_label_aliases(item) & caps):
            return False
    return True


def _missing_skills(worker: dict[str, Any], required_skills: list[str]) -> list[str]:
    worker_aliases: set[str] = set()
    for skill in worker.get("skills", []) or []:
        worker_aliases.update(_skill_aliases(skill))
    missing: list[str] = []
    for required in required_skills:
        if not (_skill_aliases(required) & worker_aliases):
            missing.append(str(required))
    return missing


def _missing_capabilities(worker: dict[str, Any], required_capabilities: list[str]) -> list[str]:
    worker_aliases = set(_worker_capabilities(worker))
    missing: list[str] = []
    for required in required_capabilities:
        if not (_label_aliases(required) & worker_aliases):
            missing.append(str(required))
    return missing


def _capability_score(worker: dict[str, Any], required_capabilities: list[str],
                      scores: dict[str, float]) -> float:
    if not required_capabilities:
        return 0.0
    provider = str(worker.get("provider") or worker.get("capability_provider") or "").strip()
    total = 0.0
    for cap in required_capabilities:
        if provider:
            total += scores.get(f"{provider}::{cap}", 0.0)
        total += scores.get(f"cap::{cap}", 0.0)
    if total:
        return total
    # Manual worker score escape hatch for tests/local topology files.
    try:
        return float(worker.get("capability_score", 0) or 0)
    except Exception:
        return 0.0


def assign_workers(batch_nodes: list[dict[str, Any]], workers: list[dict[str, Any]]) -> dict[str, Any]:
    """Assign one batch to available workers.

    Matching order:
      1. exact preferred_model + required skills
      2. same skills with alternate model (Sonnet/DeepSeek fallback, etc.)
      3. queue when no safe worker exists
    """
    assigned: list[dict[str, Any]] = []
    queued: list[dict[str, Any]] = []
    used_panes: set[str] = set()
    capability_scores = _load_capability_scores()

    for node in batch_nodes:
        preferred_model = node.get("preferred_model")
        strict_model = bool(node.get("strict_model") or node.get("model_strict"))
        required_skills = [str(s) for s in node.get("required_skills", [])]
        required_capabilities = _capability_list(node)
        candidates: list[tuple[float, int, int, str, dict[str, Any]]] = []
        blocked_by_capacity = False
        blocked_by_runtime = False
        runtime_unavailable_reasons: set[str] = set()
        any_worker_seen = False
        missing_skill_union: set[str] = set()
        missing_cap_union: set[str] = set()

        for worker in workers:
            pane = str(worker.get("pane", ""))
            if not pane:
                continue
            any_worker_seen = True
            for item in _missing_skills(worker, required_skills):
                missing_skill_union.add(item)
            for item in _missing_capabilities(worker, required_capabilities):
                missing_cap_union.add(item)
            if not _skills_match(worker, required_skills, required_capabilities):
                continue
            if not _capabilities_match(worker, required_capabilities):
                continue
            if _worker_quota_exhausted(worker, preferred_model):
                continue
            if _model_requires_strict_match(preferred_model, strict_model) and not _model_match(worker, preferred_model):
                continue
            unavailable_reason = _worker_unavailable_reason(worker)
            if unavailable_reason:
                blocked_by_runtime = True
                runtime_unavailable_reasons.add(unavailable_reason)
                continue
            if pane in used_panes:
                blocked_by_capacity = True
                continue
            if _worker_busy(worker):
                blocked_by_capacity = True
                continue
            cap_score = _capability_score(worker, required_capabilities, capability_scores)
            skill_score = _skill_match_count(worker, required_skills)
            model_penalty = 0 if _model_match(worker, preferred_model) else 10
            load = int(worker.get("load", 0) or 0)
            candidates.append((-cap_score, -skill_score, model_penalty, load, pane, worker))

        if not candidates:
            if blocked_by_runtime:
                if len(runtime_unavailable_reasons) == 1:
                    reason = next(iter(runtime_unavailable_reasons))
                else:
                    reason = "worker_runtime_unavailable"
            elif blocked_by_capacity:
                reason = "worker_capacity_exhausted"
            else:
                reason = "no_matching_worker"
            details: dict[str, Any] = {
                "required_skills": required_skills,
                "required_capabilities": required_capabilities,
            }
            if blocked_by_runtime:
                details["unavailable_reasons"] = sorted(runtime_unavailable_reasons)
            if reason == "no_matching_worker":
                details["any_worker_seen"] = any_worker_seen
                details["missing_skills"] = sorted(missing_skill_union)
                details["missing_capabilities"] = sorted(missing_cap_union)
            queued.append({"node": node["id"], "reason": reason, "details": details})
            continue

        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4], item[5]))
        cap_rank, skill_rank, _model_penalty, _load, _pane, worker = candidates[0]
        used_panes.add(str(worker.get("pane")))
        assigned.append({
            "node": node["id"],
            "pane": worker.get("pane"),
            "preferred_model": preferred_model,
            "selected_models": worker.get("models", []),
            "fallback_model": not _model_match(worker, preferred_model),
            "required_capabilities": required_capabilities,
            "capability_score": round(-cap_rank, 3),
            "skill_match_count": int(-skill_rank),
        })

    return {"ok": True, "assigned": assigned, "queued": queued}


def assign_ready(graph: dict[str, Any], workers: list[dict[str, Any]],
                 max_parallel: int | None = None,
                 graph_path: str | Path | None = None,
                 source: str | Path | None = None) -> dict[str, Any]:
    graph = auto_enrich_graph(graph, graph_path=graph_path, source=source)
    blocked = blocked_external_prerequisites(graph)
    if blocked:
        return {"ok": True, "assigned": [], "queued": [], "batch": [], "blocked_prerequisites": blocked}
    ready = ready_nodes(graph)
    try:
        from apo_plan_compiler import compile_execution_plan_for_node  # noqa: WPS433

        for node in ready:
            if isinstance(node.get("effect_union"), dict) and isinstance(node.get("proof_obligations"), list):
                continue
            try:
                compiled = compile_execution_plan_for_node(
                    node,
                    request_type=str(graph.get("request_type") or node.get("type") or ""),
                    lane_hint=str(graph.get("lane") or ""),
                    registry_path=HARNESS_DIR / "config" / "capability-capsules.registry.yaml",
                    operators_path=HARNESS_DIR / "config" / "physical-operators.json",
                )
                capsule_plan = compiled.get("capsule_plan") or {}
                physical_plan = compiled.get("physical_plan") or {}
                if isinstance(capsule_plan, dict):
                    node["capsule_plan_ir"] = capsule_plan
                    node["effect_union"] = capsule_plan.get("effect_union", {})
                    node["proof_obligations"] = capsule_plan.get("proof_obligations", [])
                    node["artifact_types"] = capsule_plan.get("artifact_types", {})
                if isinstance(physical_plan, dict):
                    node["physical_plan_ir"] = physical_plan
            except Exception:
                continue
    except Exception:
        pass
    batches = _batch_ready_nodes(ready, max_parallel=max_parallel)
    if not batches:
        return {"ok": True, "assigned": [], "queued": [], "batch": []}
    first_batch = batches[0]
    result = assign_workers(first_batch, workers)
    result["batch"] = [node["id"] for node in first_batch]
    result["capability_enrichment"] = {
        "changed_nodes": _changed_nodes(graph),
        "auto": True,
    }
    return result


def mark_node_result(graph: dict[str, Any], node_id: str, status: str,
                     gate_status: str | None = None, note: str | None = None) -> dict[str, Any]:
    _ensure_required_gate_node_mapping(graph)
    ids = _node_map(graph)
    if node_id not in ids:
        raise ValueError(f"unknown node: {node_id}")
    _assert_pass_mark_allowed(graph, node_id, status)

    updated_at = _now()
    graph.setdefault("node_results", {})
    graph["node_results"][node_id] = {
        "status": status,
        "updated_at": updated_at,
    }
    if note:
        graph["node_results"][node_id]["note"] = note
    ids[node_id]["status"] = status
    ids[node_id]["updated_at"] = updated_at

    gate = ids[node_id].get("gate")
    if gate and status in {"failed", "cancelled"}:
        graph.setdefault("gate_results", {})
        graph["gate_results"][gate] = {
            "status": "blocked",
            "node": node_id,
            "reason": f"node_{status}",
            "updated_at": updated_at,
        }
    elif gate and (gate_status or status) == "passed":
        gate_nodes = [node for node in ids.values() if node.get("gate") == gate]
        open_gate_nodes = [
            str(node.get("id") or "")
            for node in gate_nodes
            if str(node.get("id") or "") != node_id and node_status(graph, str(node.get("id") or "")) != "passed"
        ]
        graph.setdefault("gate_results", {})
        if open_gate_nodes:
            graph["gate_results"][gate] = {
                "status": "blocked",
                "node": node_id,
                "reason": "waiting_for_shared_gate_nodes",
                "open_nodes": open_gate_nodes,
                "updated_at": updated_at,
            }
        else:
            graph["gate_results"][gate] = {"status": "passed", "node": node_id, "updated_at": updated_at}

    if str(status or "").lower() in {"passed", "failed", "reviewing"}:
        _sync_node_evidence_refs(
            graph,
            node_id,
            repair=True,
            command_line=f"python3 lib/graph_scheduler.py mark --node {node_id} --status {status}",
        )

    return parent_ready_check(graph)


def set_node_status(graph: dict[str, Any], node_id: str, status: str,
                    pane: str | None = None, dispatch_id: str | None = None) -> None:
    ids = _node_map(graph)
    if node_id not in ids:
        raise ValueError(f"unknown node: {node_id}")
    current = node_status(graph, node_id)
    if _status_rank(current) > _status_rank(status):
        return
    updated_at = _now()
    ids[node_id]["status"] = status
    ids[node_id]["updated_at"] = updated_at
    if pane:
        ids[node_id]["assigned_to"] = pane
    if dispatch_id:
        ids[node_id]["dispatch_id"] = dispatch_id
    graph.setdefault("node_results", {})
    graph["node_results"][node_id] = {
        "status": status,
        "updated_at": updated_at,
    }
    if pane:
        graph["node_results"][node_id]["assigned_to"] = pane
    if dispatch_id:
        graph["node_results"][node_id]["dispatch_id"] = dispatch_id


def enqueue_ready(graph: dict[str, Any], graph_path: str, workers: list[dict[str, Any]],
                  max_parallel: int | None = None, lease: bool = False,
                  ttl: int = 600, dry_run: bool = False) -> dict[str, Any]:
    """Assign ready graph nodes and enqueue them as old-control-plane payloads.

    This is the compatibility bridge: graph scheduler decides what is safe to
    run, while the existing queue/coordinator still performs the actual wake.
    """
    sys.path.insert(0, str(HARNESS_DIR / "lib"))
    from task_queue import enqueue  # noqa: WPS433

    if lease:
        from pane_lease import acquire  # noqa: WPS433
    else:
        acquire = None
    from apo_plan_compiler import (  # noqa: WPS433
        compile_execution_plan_for_node,
        materialize_execution_plan_artifacts,
    )

    graph = auto_enrich_graph(graph, graph_path=graph_path)
    sid = str(graph.get("sprint_id") or Path(graph_path).stem.replace(".task_graph", ""))
    assignment = assign_ready(graph, workers, max_parallel=max_parallel, graph_path=graph_path)
    queued: list[dict[str, Any]] = list(assignment.get("queued", []))
    enqueued: list[dict[str, Any]] = []

    nodes_by_id = _node_map(graph)
    for item in assignment.get("assigned", []):
        node_id = item["node"]
        pane = item["pane"]
        dispatch_id = f"graph-{sid}-{node_id}-{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
        node = nodes_by_id[node_id]
        try:
            compiled_plan = compile_execution_plan_for_node(
                node,
                request_type=str(graph.get("request_type") or node.get("type") or ""),
                lane_hint=str(graph.get("lane") or ""),
                registry_path=HARNESS_DIR / "config" / "capability-capsules.registry.yaml",
                operators_path=HARNESS_DIR / "config" / "physical-operators.json",
            )
            capsule_plan_ir = dict(compiled_plan.get("capsule_plan") or {})
            physical_plan_ir = dict(compiled_plan.get("physical_plan") or {})
            plan_artifacts = materialize_execution_plan_artifacts(
                sid,
                node_id,
                capsule_plan=capsule_plan_ir,
                physical_plan=physical_plan_ir,
                base_dir=SPRINTS_DIR,
            )
        except Exception:
            compiled_plan = {
                "logical_plan_node": {
                    "node_id": node.get("id"),
                    "logical_operator": node.get("logical_operator"),
                    "goal": node.get("goal"),
                    "depends_on": list(node.get("depends_on", []) or []),
                }
            }
            capsule_plan_ir = {
                "schema_version": "solar.capsule_plan_node.v1",
                "node_id": node_id,
                "logical_operator": str(node.get("logical_operator") or ""),
                "selected": False,
                "stages": [],
            }
            physical_plan_ir = {
                "schema_version": "solar.physical_plan_node.v1",
                "node_id": node_id,
                "logical_operator": str(node.get("logical_operator") or ""),
                "selected_operator_id": "",
                "execution_candidates": [],
                "attached_capsules": [],
                "verifier_plans": [],
            }
            plan_artifacts = materialize_execution_plan_artifacts(
                sid,
                node_id,
                capsule_plan=capsule_plan_ir,
                physical_plan=physical_plan_ir,
                base_dir=SPRINTS_DIR,
            )
        node["logical_plan_node"] = dict(compiled_plan.get("logical_plan_node") or {})
        node["capsule_plan_ir"] = capsule_plan_ir
        node["physical_plan_ir"] = physical_plan_ir
        if capsule_plan_ir.get("capability_capsule_id"):
            node["capability_native"] = True
            node["capability_capsule_id"] = str(capsule_plan_ir.get("capability_capsule_id") or "")
        artifacts = node.get("artifacts") if isinstance(node.get("artifacts"), dict) else {}
        artifacts["capsule_plan_ir"] = plan_artifacts["capsule_plan_ir_path"]
        artifacts["physical_plan_ir"] = plan_artifacts["physical_plan_ir_path"]
        if physical_plan_ir.get("selected_operator_id"):
            artifacts["selected_operator_id"] = str(physical_plan_ir.get("selected_operator_id") or "")
        node["artifacts"] = artifacts

        lease_result = {"acquired": True, "reason": "lease_disabled"}
        if acquire is not None and not dry_run:
            lease_result = acquire(pane, sid, dispatch_id, ttl)
            if not lease_result.get("acquired"):
                set_node_status(graph, node_id, "queued")
                graph.setdefault("node_results", {}).setdefault(node_id, {})
                graph["node_results"][node_id]["blocking_reason"] = lease_result.get("reason", "lease_failed")
                graph["node_results"][node_id]["queued_pane"] = pane
                graph["node_results"][node_id]["updated_at"] = _now()
                queued.append({
                    "node": node_id,
                    "pane": pane,
                    "reason": lease_result.get("reason", "lease_failed"),
                })
                continue

        payload = {
            "type": "graph_node",
            "graph": graph_path,
            "sprint_id": sid,
            "node": node,
            "assignment": item,
            "dispatch_id": dispatch_id,
            "lease": lease_result,
            "logical_plan_node": dict(compiled_plan.get("logical_plan_node") or {}),
            "capsule_plan_ir": capsule_plan_ir,
            "physical_plan_ir": physical_plan_ir,
            "plan_artifacts": plan_artifacts,
        }
        if dry_run:
            q = {"ok": True, "result": "dry_run", "id": ""}
        else:
            q = enqueue(sid, f"graph_node|node_id={node_id}|pane={pane}", 80, payload)
            # Queueing is not dispatch. The graph node becomes "dispatched"
            # only after graph_node_dispatcher writes the instruction file and
            # successfully submits it to the pane. Marking it dispatched here
            # creates a false-positive state when queue drain/send fails.
            set_node_status(graph, node_id, "assigned", pane=pane, dispatch_id=dispatch_id)
        enqueued_item = {"node": node_id, "pane": pane, "queue": q, "dispatch_id": dispatch_id}
        if dry_run:
            # Dry-run callers still need the exact payload so they can render
            # node dispatch files and validate worker-visible context without
            # mutating the persistent queue.
            enqueued_item["payload"] = payload
        enqueued.append(enqueued_item)

    blocked_workers: list[dict[str, Any]] = []
    for item in queued:
        if item.get("reason") != "no_matching_worker":
            continue
        node_id = str(item.get("node") or "")
        if not node_id or node_id not in nodes_by_id:
            continue
        set_node_status(graph, node_id, "worker_blocked")
        graph.setdefault("node_results", {}).setdefault(node_id, {})
        graph["node_results"][node_id]["blocking_reason"] = "no_matching_worker"
        graph["node_results"][node_id]["worker_match_details"] = item.get("details", {})
        graph["node_results"][node_id]["updated_at"] = _now()
        blocked_workers.append({"node": node_id, "reason": "no_matching_worker", "details": item.get("details", {})})

    return {
        "ok": True,
        "sprint_id": sid,
        "batch": assignment.get("batch", []),
        "blocked_prerequisites": assignment.get("blocked_prerequisites", []),
        "capability_enrichment": assignment.get("capability_enrichment", {}),
        "enqueued": enqueued,
        "queued": queued,
        "worker_blocked": blocked_workers,
        "dry_run": dry_run,
    }


def enrich_backlog(sprints_dir: str | Path, dry_run: bool = False,
                   backup_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(sprints_dir).expanduser()
    if not root.exists():
        raise ValueError(f"sprints dir not found: {root}")
    graphs = sorted(root.glob("*.task_graph.json"))
    backup_root = Path(backup_dir).expanduser() if backup_dir else (
        HARNESS_DIR / "state" / "task-graph-enrich-backups" / datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    )
    changed: list[dict[str, Any]] = []
    unchanged: list[str] = []
    errors: list[dict[str, str]] = []

    for graph_path in graphs:
        try:
            before_text = graph_path.read_text(encoding="utf-8")
            graph = json.loads(before_text)
            before_caps = _required_capability_snapshot(graph)
            enriched = auto_enrich_graph(graph, graph_path=graph_path)
            after_caps = _required_capability_snapshot(enriched)
            after_text = json.dumps(enriched, indent=2, ensure_ascii=False) + "\n"
            nodes = [node_id for node_id, caps in after_caps.items() if caps != before_caps.get(node_id, [])]
            if not nodes:
                unchanged.append(graph_path.name)
                continue
            if not dry_run:
                backup_root.mkdir(parents=True, exist_ok=True)
                shutil.copy2(graph_path, backup_root / graph_path.name)
                save_graph(graph_path, enriched)
            changed.append({
                "graph": str(graph_path),
                "changed_nodes": nodes,
                "node_count": len(_nodes(enriched)),
            })
        except Exception as exc:
            errors.append({"graph": str(graph_path), "error": str(exc)})

    return {
        "ok": not errors,
        "sprints_dir": str(root),
        "graph_count": len(graphs),
        "changed_count": len(changed),
        "unchanged_count": len(unchanged),
        "backup_dir": str(backup_root) if changed and not dry_run else "",
        "dry_run": dry_run,
        "changed": changed,
        "errors": errors,
    }


def parent_ready_check(graph: dict[str, Any]) -> dict[str, Any]:
    _ensure_required_gate_node_mapping(graph)
    ids = _node_map(graph)
    open_nodes = [
        node_id for node_id in ids
        if node_status(graph, node_id) not in (PASS_STATUSES | CLOSED_NON_PASS_STATUSES)
    ]
    failed_nodes = [node_id for node_id in ids if node_status(graph, node_id) == "failed"]

    required_gates = graph.get("required_gates")
    if required_gates is None:
        required_gates = [node.get("gate") for node in ids.values() if node.get("gate")]
    required_gates = [str(g) for g in required_gates if g]

    gate_results = graph.get("gate_results") or {}
    missing_gates = [
        gate for gate in required_gates
        if not isinstance(gate_results.get(gate), dict) or gate_results[gate].get("status") != "passed"
    ]

    ready = not open_nodes and not failed_nodes and not missing_gates and bool(ids)
    return {
        "ok": True,
        "sprint_id": graph.get("sprint_id"),
        "ready": ready,
        "node_count": len(ids),
        "open_nodes": open_nodes,
        "failed_nodes": failed_nodes,
        "required_gates": required_gates,
        "missing_gates": missing_gates,
    }


def epic_child_activation(graph: dict[str, Any]) -> dict[str, Any]:
    """Return per-child activation state for an epic-level task graph.

    Used by autopilot/wake to decide which child sprint to dispatch next
    without skipping cross-sprint dependencies. Locks in the policy:

      - A child is ``ready`` only when **every** entry in its ``depends_on``
        list points to a sibling child whose status is in PASS_STATUSES.
      - A child is ``blocked`` if any dependency is not yet passed; the
        ``unmet`` list records exactly which deps still need to clear.
      - The parent epic ``can_close`` only when every child has reached a
        terminal status and at least one is passed (i.e. all required work
        landed). Failed children prevent closure.

    Works on any graph that follows the in-sprint conventions (``nodes``
    with ``id``/``status``/``depends_on``), including
    ``solar.epic.task_graph.v1`` graphs whose nodes are sprint IDs.
    """
    ids = _node_map(graph)
    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    done: list[str] = []
    failed: list[str] = []
    pending_or_active: list[str] = []

    for child_id, node in ids.items():
        status = node_status(graph, child_id)
        if status in PASS_STATUSES:
            done.append(child_id)
            continue
        if status == "failed":
            failed.append(child_id)
            continue
        if status in CLOSED_NON_PASS_STATUSES:
            # skipped/cancelled children neither block nor unlock siblings.
            continue
        pending_or_active.append(child_id)

        deps = _internal_depends_on(node)
        unmet = [dep for dep in deps if not _is_passed(graph, dep)]
        record = {
            "child_id": child_id,
            "status": status,
            "depends_on": deps,
            "unmet": unmet,
        }
        if unmet:
            blocked.append(record)
        else:
            ready.append(record)

    epic_done = bool(ids) and not pending_or_active and not failed
    can_close = epic_done and bool(done)

    return {
        "ok": True,
        "epic_id": graph.get("epic_id") or graph.get("sprint_id"),
        "schema_version": graph.get("schema_version"),
        "children_total": len(ids),
        "ready": ready,
        "blocked": blocked,
        "done": done,
        "failed": failed,
        "epic_done": epic_done,
        "can_close": can_close,
    }


def doctor_graph(graph: dict[str, Any], repair: bool = False) -> dict[str, Any]:
    """Detect and optionally repair graph state drift.

    The scheduler historically stored status in both inline node fields and
    node_results. If the two disagree, a stale node_results entry can make a
    passed node look open forever. This doctor treats newer timestamps as the
    winner and can repair the older side.
    """
    issues: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    ids = _node_map(graph)
    results = _node_results(graph)

    for node_id, node in ids.items():
        evidence_sync = _sync_node_evidence_refs(graph, node_id, repair=repair)
        issues.extend(evidence_sync["issues"])
        repairs.extend(evidence_sync["repairs"])
        inline_status = str(node.get("status", "") or "").lower()
        result = results.get(node_id) if isinstance(results.get(node_id), dict) else {}
        result_status = str((result or {}).get("status", "") or "").lower()
        if _passed_without_required_eval(graph, node_id) and ("passed" in {inline_status, result_status}):
            issue = {
                "type": "passed_missing_eval",
                "node": node_id,
                "inline_status": inline_status,
                "inline_updated_at": node.get("updated_at", ""),
                "result_status": result_status,
                "result_updated_at": result.get("updated_at", ""),
                "effective_status": "reviewing",
            }
            issues.append(issue)
            if repair:
                now = _now()
                node["status"] = "reviewing"
                node["updated_at"] = now
                graph.setdefault("node_results", {})
                graph["node_results"].setdefault(node_id, {})
                graph["node_results"][node_id]["status"] = "reviewing"
                graph["node_results"][node_id]["updated_at"] = now
                repairs.append({**issue, "repair": "reopened_passed_missing_eval"})
            continue
        if not inline_status or not result_status or inline_status == result_status:
            continue
        inline_ts = _parse_ts(node.get("updated_at"))
        result_ts = _parse_ts(result.get("updated_at"))
        effective = node_status(graph, node_id)
        issue = {
            "type": "node_status_drift",
            "node": node_id,
            "inline_status": inline_status,
            "inline_updated_at": node.get("updated_at", ""),
            "result_status": result_status,
            "result_updated_at": result.get("updated_at", ""),
            "effective_status": effective,
        }
        issues.append(issue)
        if not repair:
            continue

        if inline_ts and result_ts and inline_ts > result_ts:
            result["status"] = inline_status
            result["updated_at"] = node.get("updated_at")
            repairs.append({**issue, "repair": "node_results_updated_from_inline"})
        elif result_ts and inline_ts and result_ts > inline_ts:
            node["status"] = result_status
            node["updated_at"] = result.get("updated_at")
            repairs.append({**issue, "repair": "inline_updated_from_node_results"})
        elif inline_status == "passed":
            result["status"] = inline_status
            result["updated_at"] = node.get("updated_at") or result.get("updated_at") or _now()
            repairs.append({**issue, "repair": "node_results_updated_from_inline_passed"})
        elif result_status == "passed":
            node["status"] = result_status
            node["updated_at"] = result.get("updated_at") or node.get("updated_at") or _now()
            repairs.append({**issue, "repair": "inline_updated_from_node_results_passed"})

    parent = parent_ready_check(graph)
    return {
        "ok": not issues,
        "sprint_id": graph.get("sprint_id"),
        "issues": issues,
        "repairs": repairs,
        "parent": parent,
        "repaired": bool(repairs),
    }


def _workers_from_file(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        workers = data.get("workers", [])
        if not isinstance(workers, list):
            return []
        return [_normalize_worker_entry(worker) for worker in workers if isinstance(worker, dict)]
    if isinstance(data, list):
        return [_normalize_worker_entry(worker) for worker in data if isinstance(worker, dict)]
    raise ValueError("workers file must be a list or {workers: [...]}")


def _normalize_worker_entry(worker: dict[str, Any]) -> dict[str, Any]:
    """Accept both scheduler workers and multi_task_screen.workers.v1 rows."""
    normalized = dict(worker)
    pane = str(normalized.get("pane") or normalized.get("id") or "").strip()
    if pane and not normalized.get("pane"):
        normalized["pane"] = pane
    role = str(normalized.get("role") or "").lower()
    if (role in {"builder", "lab", "lab-builder", "evaluator"} or "harness-lab" in pane) and not normalized.get("skills"):
        normalized["skills"] = [
            "bash",
            "shell",
            "python",
            "sqlite",
            "sqlite3",
            "ffmpeg",
            "testing",
            "test_execution",
            "code_impl",
            "test_generation",
            "planning",
            "state-machine",
            "state_machine",
            "data.modeling",
            "data-modeling",
            "observability",
            "optimization",
            "runtime_design",
            "solar-harness-verification",
            "solar-harness-compat-review",
            "compat-review",
            "compatibility",
            "harness.verification",
            "verification",
            "verifier",
            "review",
            "ai-rag-pipeline",
            "reporting",
        ]
    if (role in {"builder", "lab", "lab-builder", "evaluator"} or "harness-lab" in pane) and not normalized.get("capabilities"):
        normalized["capabilities"] = [
            "bash",
            "python",
            "sqlite",
            "sqlite3",
            "ffmpeg",
            "testing",
            "test_execution",
            "code_impl",
            "test_generation",
            "state-machine",
            "state_machine",
            "data.modeling",
            "data-modeling",
            "repair.pr-cot",
            "failure.structured_repair",
            "routing.complexity_budget",
            "optimization",
            "runtime_design",
            "solar-harness-verification",
            "solar-harness-compat-review",
            "compat-review",
            "compatibility",
            "harness.verification",
            "verification",
            "code.review",
            "ai-rag-pipeline",
            "reporting",
            "model.routing",
            "harness.model_routing",
        ]
    if not normalized.get("models"):
        if "lab" in pane or role in {"lab", "lab-builder"}:
            normalized["models"] = ["glm", "glm-5", "glm-5.1", "zhipu"]
        elif pane.endswith(".2") or pane.endswith(".3"):
            normalized["models"] = ["opus", "claude-opus", "anthropic-opus"]
    return normalized


def main() -> int:
    ap = argparse.ArgumentParser(prog="graph_scheduler.py")
    sub = ap.add_subparsers(dest="cmd")

    def add_graph(p: argparse.ArgumentParser) -> None:
        p.add_argument("--graph", required=True)

    p = sub.add_parser("validate")
    add_graph(p)

    p = sub.add_parser("topo")
    add_graph(p)

    p = sub.add_parser("layers")
    add_graph(p)

    p = sub.add_parser("critical-path")
    add_graph(p)

    p = sub.add_parser("ready")
    add_graph(p)

    p = sub.add_parser("batches")
    add_graph(p)
    p.add_argument("--max-parallel", type=int)
    p.add_argument("--out")

    p = sub.add_parser("enrich-capabilities")
    add_graph(p)
    p.add_argument("--source")
    p.add_argument("--out")
    p.add_argument("--in-place", action="store_true")
    p.add_argument("--overwrite", action="store_true")

    p = sub.add_parser("assign")
    add_graph(p)
    p.add_argument("--workers", required=True)
    p.add_argument("--max-parallel", type=int)
    p.add_argument("--source")

    p = sub.add_parser("mark")
    add_graph(p)
    p.add_argument("--node", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--note")
    p.add_argument("--in-place", action="store_true")

    p = sub.add_parser("parent-check")
    add_graph(p)

    p = sub.add_parser("doctor")
    add_graph(p)
    p.add_argument("--repair", action="store_true")
    p.add_argument("--in-place", action="store_true")

    p = sub.add_parser("enqueue-ready")
    add_graph(p)
    p.add_argument("--workers", required=True)
    p.add_argument("--max-parallel", type=int)
    p.add_argument("--lease", action="store_true")
    p.add_argument("--ttl", type=int, default=600)
    p.add_argument("--in-place", action="store_true")

    p = sub.add_parser("enrich-backlog")
    p.add_argument("--sprints-dir", default=str(HARNESS_DIR / "sprints"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup-dir")

    args = ap.parse_args()

    try:
        if args.cmd == "validate":
            print(json.dumps(validate_graph(load_graph(args.graph)), ensure_ascii=False))

        elif args.cmd == "topo":
            graph = load_graph(args.graph)
            print(json.dumps({"ok": True, "order": topo_order(graph)}, ensure_ascii=False))

        elif args.cmd == "layers":
            graph = load_graph(args.graph)
            print(json.dumps({"ok": True, "layers": topo_layers(graph)}, ensure_ascii=False))

        elif args.cmd == "critical-path":
            graph = load_graph(args.graph)
            result = critical_path(graph)
            result["ok"] = True
            print(json.dumps(result, ensure_ascii=False))

        elif args.cmd == "ready":
            graph = load_graph(args.graph)
            print(json.dumps({
                "ok": True,
                "nodes": [n["id"] for n in ready_nodes(graph)],
                "blocked_prerequisites": blocked_external_prerequisites(graph),
            }, ensure_ascii=False))

        elif args.cmd == "batches":
            graph = load_graph(args.graph)
            result = make_batches(graph, args.max_parallel)
            if args.out:
                Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps(result, ensure_ascii=False))

        elif args.cmd == "enrich-capabilities":
            from capability_inference import enrich_graph  # noqa: WPS433

            graph = load_graph(args.graph)
            source_text = ""
            if args.source:
                source_text = Path(args.source).read_text(encoding="utf-8", errors="replace")
            result_graph = enrich_graph(graph, source_text=source_text, overwrite=args.overwrite)
            if args.in_place:
                save_graph(args.graph, result_graph)
            elif args.out:
                save_graph(args.out, result_graph)
            print(json.dumps(result_graph.get("capability_inference", {"ok": True}), ensure_ascii=False))

        elif args.cmd == "assign":
            graph = load_graph(args.graph)
            workers = _workers_from_file(args.workers)
            print(json.dumps(assign_ready(graph, workers, args.max_parallel, args.graph, args.source), ensure_ascii=False))

        elif args.cmd == "mark":
            graph = load_graph(args.graph)
            result = mark_node_result(graph, args.node, args.status, note=args.note)
            if args.in_place:
                save_graph(args.graph, graph)
                result["status_sync"] = sync_status_cache_from_graph(
                    graph,
                    args.graph,
                    event=f"graph_mark_{args.node}_{args.status}",
                )
            print(json.dumps(result, ensure_ascii=False))

        elif args.cmd == "parent-check":
            print(json.dumps(parent_ready_check(load_graph(args.graph)), ensure_ascii=False))

        elif args.cmd == "doctor":
            graph = load_graph(args.graph)
            result = doctor_graph(graph, repair=args.repair)
            if args.in_place and result.get("repaired"):
                save_graph(args.graph, graph)
            if args.in_place and args.repair:
                result["status_sync"] = sync_status_cache_from_graph(
                    graph,
                    args.graph,
                    event="graph_doctor_repair_sync",
                )
            print(json.dumps(result, ensure_ascii=False))

        elif args.cmd == "enqueue-ready":
            graph = load_graph(args.graph)
            workers = _workers_from_file(args.workers)
            result = enqueue_ready(graph, args.graph, workers, args.max_parallel, args.lease, args.ttl)
            if args.in_place:
                save_graph(args.graph, graph)
            print(json.dumps(result, ensure_ascii=False))

        elif args.cmd == "enrich-backlog":
            print(json.dumps(enrich_backlog(args.sprints_dir, args.dry_run, args.backup_dir), ensure_ascii=False))

        else:
            ap.print_help()
            return 1

    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
