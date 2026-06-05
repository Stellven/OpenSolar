#!/usr/bin/env python3
"""Bounded graph drain controller for watchdog-driven DAG progress."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from harness_paths import resolve_runtime_harness_dir

SCHEMA_VERSION = "graph_drain_controller.v1"

HARNESS_DIR = resolve_runtime_harness_dir()
SPRINTS_DIR = HARNESS_DIR / "sprints"
LIB_DIR = HARNESS_DIR / "lib"


def _coerce_int(value: object, default: int, min_value: int | None = None) -> int:
    try:
        int_value = int(value)
    except Exception:
        return default
    if min_value is not None and int_value < min_value:
        return default
    return int_value


def _load_graph_dispatcher() -> Any:
    path = LIB_DIR / "graph_node_dispatcher.py"
    if not path.exists():
        source_path = Path(__file__).resolve().with_name("graph_node_dispatcher.py")
        if source_path.exists():
            path = source_path
    if not path.exists():
        raise FileNotFoundError(f"graph_node_dispatcher.py not found under {LIB_DIR}")
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("graph_drain_controller_dispatcher", path)
    if not spec or not spec.loader:
        raise FileNotFoundError(f"unable to load graph dispatcher: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _iter_graph_paths(max_graphs: int) -> list[Path]:
    if not SPRINTS_DIR.exists():
        return []
    paths = sorted(
        SPRINTS_DIR.glob("*.task_graph.json"),
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=True,
    )
    if max_graphs > 0:
        return paths[:max_graphs]
    return paths


def _list_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = graph.get("nodes")
    return [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []


def _existing_eval_json(gnd: Any, sid: str, node_id: str) -> Path | None:
    candidates: list[Path] = [SPRINTS_DIR / f"{sid}.{node_id}-eval.json"]
    eval_json_file = getattr(gnd, "_eval_json_file", None)
    if callable(eval_json_file):
        try:
            candidates.insert(0, Path(eval_json_file(sid, node_id)))
        except Exception:
            pass
    for path in candidates:
        if path.exists():
            return path
    return None


def _existing_handoff(gnd: Any, sid: str, node: dict[str, Any], graph: dict[str, Any]) -> Path | None:
    helper = getattr(gnd, "_existing_node_handoff", None)
    if callable(helper):
        try:
            handoff = helper(sid, node, graph)
            if handoff:
                return Path(handoff)
        except Exception:
            pass
    node_id = str(node.get("id") or "")
    fallback = SPRINTS_DIR / f"{sid}.{node_id}-handoff.md"
    return fallback if fallback.exists() else None


def _node_eval_needed(gnd: Any, graph: dict[str, Any], sid: str, node: dict[str, Any]) -> bool:
    helper = getattr(gnd, "_node_eval_needed", None)
    if callable(helper):
        try:
            return bool(helper(graph, sid, node, force=False))
        except Exception:
            pass
    return str(node.get("status") or "").lower() == "reviewing" and _existing_eval_json(gnd, sid, str(node.get("id") or "")) is None


def _has_builder_ready_nodes(gnd: Any, graph: dict[str, Any]) -> bool:
    ready_checker = getattr(gnd, "ready_nodes", None)
    if callable(ready_checker):
        try:
            return bool(ready_checker(graph))
        except Exception:
            pass
    return any(str(node.get("status") or "").lower() in {"pending", "queued"} for node in _list_nodes(graph))


def _count_builder_dispatches(result: dict[str, Any], *, dry_run: bool) -> int:
    drain = result.get("drain") if isinstance(result.get("drain"), dict) else {}
    results = drain.get("results") if isinstance(drain.get("results"), list) else []
    ok_results = []
    for item in results:
        if not isinstance(item, dict) or not bool(item.get("ok", True)):
            continue
        reason = str(item.get("reason") or "")
        unavailable = "unavailable" in reason or "retry_later" in reason
        if unavailable and not dry_run:
            continue
        if not dry_run and not (item.get("instruction_file") or item.get("pm_task_id") or item.get("task_id")):
            continue
        ok_results.append(item)
    if ok_results:
        return len(ok_results)
    enqueue = result.get("enqueue") if isinstance(result.get("enqueue"), dict) else {}
    enqueued = enqueue.get("enqueued") if isinstance(enqueue.get("enqueued"), list) else []
    if dry_run and not drain and enqueued:
        return len(enqueued)
    return 0


def run_graph_drain(
    *,
    apply: bool = False,
    max_graphs: int | None = None,
    max_evals: int | None = None,
    max_builders: int | None = None,
    ttl: int = 900,
    force_eval: bool = False,
) -> dict[str, Any]:
    """Scan recent task graphs and consume bounded eval/builder-ready work."""
    del force_eval
    max_graphs = _coerce_int(max_graphs if max_graphs is not None else os.environ.get("SOLAR_GRAPH_DRAIN_MAX_GRAPHS", "30"), 30, min_value=0)
    max_evals = _coerce_int(max_evals if max_evals is not None else os.environ.get("SOLAR_GRAPH_DRAIN_MAX_EVALS", "2"), 2, min_value=0)
    max_builders = _coerce_int(max_builders if max_builders is not None else os.environ.get("SOLAR_GRAPH_DRAIN_MAX_BUILDERS", "1"), 1, min_value=0)
    ttl = _coerce_int(ttl, 900, min_value=60)
    dry_run = not bool(apply)
    gnd = _load_graph_dispatcher()

    counters = {
        "graphs_scanned": 0,
        "eval_candidates": 0,
        "builder_candidates": 0,
        "evals_dispatched": 0,
        "builders_dispatched": 0,
        "eval_attempts": 0,
        "builder_attempts": 0,
        "reconciled": 0,
        "skipped": 0,
        "drain_submitted": 0,
    }
    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for graph_path in _iter_graph_paths(max_graphs):
        counters["graphs_scanned"] += 1
        try:
            graph = gnd.load_graph(str(graph_path))
        except Exception as exc:
            counters["skipped"] += 1
            skipped.append({"graph": str(graph_path), "reason": f"load_failed:{type(exc).__name__}"})
            continue
        if not isinstance(graph, dict):
            counters["skipped"] += 1
            skipped.append({"graph": str(graph_path), "reason": "invalid_graph"})
            continue
        sid = str(graph.get("sprint_id") or graph_path.name.replace(".task_graph.json", ""))
        eval_nodes: list[dict[str, Any]] = []
        for node in _list_nodes(graph):
            node_id = str(node.get("id") or "")
            if not node_id:
                continue
            handoff = _existing_handoff(gnd, sid, node, graph)
            if not handoff:
                continue
            if not _node_eval_needed(gnd, graph, sid, node):
                continue
            eval_nodes.append(
                {
                    "node": node_id,
                    "handoff": str(handoff),
                    "eval_json": str(_existing_eval_json(gnd, sid, node_id) or ""),
                }
            )
        has_builder_ready = _has_builder_ready_nodes(gnd, graph)
        if eval_nodes:
            counters["eval_candidates"] += len(eval_nodes)
        if has_builder_ready:
            counters["builder_candidates"] += 1
        if eval_nodes or has_builder_ready:
            candidates.append(
                {
                    "sprint_id": sid,
                    "graph": str(graph_path),
                    "eval_nodes": eval_nodes,
                    "builder_ready": has_builder_ready,
                }
            )

        eval_budget = max(0, int(max_evals) - counters["eval_attempts"])
        if eval_nodes and eval_budget > 0:
            counters["eval_attempts"] += 1
            try:
                eval_result = gnd.dispatch_node_evals(
                    str(graph_path),
                    dry_run=dry_run,
                    ttl=ttl,
                    max_items=min(eval_budget, len(eval_nodes)),
                )
            except Exception as exc:
                counters["skipped"] += 1
                skipped.append({"graph": str(graph_path), "reason": f"eval_dispatch_failed:{type(exc).__name__}"})
                eval_result = {"ok": False, "error": str(exc)}
            dispatched = eval_result.get("dispatched") if isinstance(eval_result.get("dispatched"), list) else []
            reconciled = eval_result.get("reconciled") if isinstance(eval_result.get("reconciled"), list) else []
            eval_would_submit = len(dispatched)
            eval_submitted = 0 if dry_run else eval_would_submit
            counters["evals_dispatched"] += eval_submitted
            counters["reconciled"] += len(reconciled)
            if eval_would_submit or reconciled:
                actions.append(
                    {
                        "action_type": "graph_eval_drain",
                        "target": sid,
                        "status": "skipped" if dry_run else "applied",
                        "graph": str(graph_path),
                        "submitted": eval_submitted,
                        "would_submit": eval_would_submit,
                        "reconciled": len(reconciled),
                        "payload": eval_result,
                    }
                )
            eval_skipped = eval_result.get("skipped") if isinstance(eval_result.get("skipped"), list) else []
            for item in eval_skipped:
                if isinstance(item, dict):
                    skipped.append({"graph": str(graph_path), **item})
                    counters["skipped"] += 1
            if not eval_would_submit and not reconciled and not eval_skipped:
                counters["skipped"] += 1
                skipped.append(
                    {
                        "graph": str(graph_path),
                        "sprint_id": sid,
                        "reason": "eval_drain_no_dispatch",
                        "ok": bool(eval_result.get("ok", True)),
                    }
                )

        builder_budget = max(0, int(max_builders) - counters["builder_attempts"])
        if has_builder_ready and builder_budget > 0:
            counters["builder_attempts"] += 1
            try:
                ready_result = gnd.dispatch_ready(
                    str(graph_path),
                    dry_run=dry_run,
                    ttl=ttl,
                    max_parallel=builder_budget,
                )
            except Exception as exc:
                counters["skipped"] += 1
                skipped.append({"graph": str(graph_path), "reason": f"builder_dispatch_failed:{type(exc).__name__}"})
                ready_result = {"ok": False, "error": str(exc)}
            builder_would_submit = _count_builder_dispatches(ready_result, dry_run=dry_run)
            builder_submitted = 0 if dry_run else builder_would_submit
            counters["builders_dispatched"] += builder_submitted
            ready_reconciled = ready_result.get("reconciled") if isinstance(ready_result.get("reconciled"), list) else []
            counters["reconciled"] += len(ready_reconciled)
            if builder_would_submit or ready_reconciled:
                actions.append(
                    {
                        "action_type": "graph_builder_drain",
                        "target": sid,
                        "status": "skipped" if dry_run else "applied",
                        "graph": str(graph_path),
                        "submitted": builder_submitted,
                        "would_submit": builder_would_submit,
                        "reconciled": len(ready_reconciled),
                        "payload": ready_result,
                    }
                )
            if not builder_would_submit and not ready_reconciled:
                drain = ready_result.get("drain") if isinstance(ready_result.get("drain"), dict) else {}
                enqueue = ready_result.get("enqueue") if isinstance(ready_result.get("enqueue"), dict) else {}
                results = drain.get("results") if isinstance(drain.get("results"), list) else []
                counters["skipped"] += 1
                skipped.append(
                    {
                        "graph": str(graph_path),
                        "sprint_id": sid,
                        "reason": "builder_drain_no_dispatch",
                        "ok": bool(ready_result.get("ok", True)),
                        "enqueue_count": len(enqueue.get("enqueued") or []) if isinstance(enqueue.get("enqueued"), list) else 0,
                        "drain_processed": _coerce_int(drain.get("processed"), 0, min_value=0),
                        "drain_reasons": [
                            str(item.get("reason") or "")
                            for item in results
                            if isinstance(item, dict) and str(item.get("reason") or "")
                        ][:5],
                    }
                )

        if counters["eval_attempts"] >= max_evals and counters["builder_attempts"] >= max_builders:
            break

    counters["drain_submitted"] = counters["evals_dispatched"] + counters["builders_dispatched"]
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "dry_run": dry_run,
        "limits": {"max_graphs": max_graphs, "max_evals": max_evals, "max_builders": max_builders, "ttl": ttl},
        "counters": counters,
        "candidates": candidates,
        "actions": actions,
        "skipped": skipped,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Drain Solar task_graph eval/builder work with bounded budgets.")
    parser.add_argument("--apply", action="store_true", help="Actually dispatch graph work.")
    parser.add_argument("--max-graphs", type=int, default=None)
    parser.add_argument("--max-evals", type=int, default=None)
    parser.add_argument("--max-builders", type=int, default=None)
    parser.add_argument("--ttl", type=int, default=900)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    payload = run_graph_drain(
        apply=bool(args.apply),
        max_graphs=args.max_graphs,
        max_evals=args.max_evals,
        max_builders=args.max_builders,
        ttl=int(args.ttl),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        counters = payload.get("counters", {})
        print(
            "graph_drain_controller "
            f"dry_run={payload.get('dry_run')} "
            f"drain_submitted={counters.get('drain_submitted', 0)} "
            f"eval_candidates={counters.get('eval_candidates', 0)} "
            f"builder_candidates={counters.get('builder_candidates', 0)}"
        )
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
