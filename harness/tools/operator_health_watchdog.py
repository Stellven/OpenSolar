#!/usr/bin/env python3
"""Operator health watchdog for cooldown/quota recovery.

This tool composes the existing safe recovery primitives into one periodic
health pass:

1. prune expired operator cooldown/auth/rate-limit blocks when --apply is set;
2. refresh quota/capacity snapshot;
3. reconcile stale PM inbox projections without bypassing artifact gates.

Default mode is observation-first: it writes the quota snapshot, but does not
clear operator blocks or mutate PM task status unless --apply is provided.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
REPO_TOOLS_DIR = Path(__file__).resolve().parent


def _load_tool(name: str) -> ModuleType:
    candidates = [
        HARNESS_DIR / "tools" / f"{name}.py",
        REPO_TOOLS_DIR / f"{name}.py",
    ]
    for path in candidates:
        if not path.exists():
            continue
        spec = importlib.util.spec_from_file_location(f"solar_watchdog_{name}", path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(f"tool not found: {name}")


def _capture_json_call(func: Any, args: argparse.Namespace) -> dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = int(func(args) or 0)
    out = stdout.getvalue().strip()
    payload: dict[str, Any]
    try:
        payload = json.loads(out) if out else {}
    except Exception:
        payload = {"raw_stdout": out}
    payload.setdefault("ok", rc == 0)
    payload["returncode"] = rc
    if stderr.getvalue().strip():
        payload["stderr"] = stderr.getvalue().strip()
    return payload


def run_watchdog(*, apply: bool = False, max_age_minutes: int = 45) -> dict[str, Any]:
    pm_dispatch = _load_tool("pm_dispatch")
    quota_refresh = _load_tool("quota_refresh")

    steps: list[dict[str, Any]] = []

    if apply:
        prune = pm_dispatch._prune_expired_operator_blocks()
        steps.append({"step": "prune_rate_limits", "applied": True, "result": prune})
    else:
        steps.append(
            {
                "step": "prune_rate_limits",
                "applied": False,
                "result": {
                    "ok": True,
                    "reason": "dry_run",
                    "note": "use --apply to clear expired cooldown/auth/rate-limit blocks",
                },
            }
        )

    quota = quota_refresh.refresh_snapshot(apply=apply)
    steps.append({"step": "quota_refresh", "applied": True, "result": quota})

    reconcile = _capture_json_call(
        pm_dispatch.cmd_reconcile,
        argparse.Namespace(
            max_age_minutes=max(1, int(max_age_minutes or 45)),
            apply=apply,
            json=True,
            limit=0,
        ),
    )
    steps.append({"step": "pm_reconcile", "applied": apply, "result": reconcile})

    pruned = 0
    kept_blocks = 0
    if apply and isinstance(steps[0].get("result"), dict):
        first = steps[0]["result"]
        pruned = len(first.get("pruned") if isinstance(first.get("pruned"), list) else [])
        kept_blocks = len(first.get("kept") if isinstance(first.get("kept"), list) else [])
    rec_summary = reconcile.get("summary") if isinstance(reconcile.get("summary"), dict) else {}
    quota_groups = quota.get("groups") if isinstance(quota.get("groups"), dict) else {}
    hard_blocked_groups = {
        key: value
        for key, value in quota_groups.items()
        if isinstance(value, dict) and int(value.get("hard_blocked") or 0) > 0
    }

    return {
        "ok": all(bool((step.get("result") or {}).get("ok", True)) for step in steps),
        "applied": apply,
        "max_age_minutes": max(1, int(max_age_minutes or 45)),
        "summary": {
            "operators_total": quota.get("operators_total", 0),
            "operators_usable": quota.get("operators_usable", 0),
            "operators_hard_blocked": quota.get("operators_hard_blocked", 0),
            "quota_recommended_level": quota.get("recommended_level", "N/A"),
            "quota_backlog": quota.get("backlog", 0),
            "pruned_blocks": pruned,
            "kept_blocks": kept_blocks,
            "reconcile_actions": rec_summary,
            "hard_blocked_groups": sorted(hard_blocked_groups),
        },
        "steps": steps,
    }


def _print_table(payload: dict[str, Any]) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print("operator_health_watchdog")
    print("┌──────────────────────────────┬────────┬──────────────────────────────────────────────┐")
    print("│ 项目                         │ 状态   │ 证据                                         │")
    print("├──────────────────────────────┼────────┼──────────────────────────────────────────────┤")
    rows = [
        ("applied", "ok" if payload.get("applied") else "pending", str(payload.get("applied"))),
        ("operators_usable", "ok", f"{summary.get('operators_usable', 0)}/{summary.get('operators_total', 0)}"),
        ("hard_blocked", "warn" if summary.get("operators_hard_blocked") else "ok", str(summary.get("operators_hard_blocked", 0))),
        ("quota_level", "ok", str(summary.get("quota_recommended_level", "N/A"))),
        ("backlog", "warn" if int(summary.get("quota_backlog") or 0) else "ok", str(summary.get("quota_backlog", 0))),
        ("pruned_blocks", "ok", str(summary.get("pruned_blocks", 0))),
        ("kept_blocks", "warn" if summary.get("kept_blocks") else "ok", str(summary.get("kept_blocks", 0))),
    ]
    for name, status, evidence in rows:
        print(f"│ {name:<28} │ {status:<6} │ {evidence:<44} │")
    print("└──────────────────────────────┴────────┴──────────────────────────────────────────────┘")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Solar operator cooldown/quota health watchdog.")
    parser.add_argument("--apply", action="store_true", help="Actually clear expired blocks and reconcile stale PM records.")
    parser.add_argument("--max-age-minutes", type=int, default=45, help="Stale PM record threshold for reconcile.")
    parser.add_argument("--json", action="store_true", help="Output JSON.")
    args = parser.parse_args()

    payload = run_watchdog(apply=bool(args.apply), max_age_minutes=int(args.max_age_minutes or 45))
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_table(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
