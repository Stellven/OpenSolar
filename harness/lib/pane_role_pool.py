"""Shared pane role-pool discovery + dispatch-boundary hygiene helpers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pane_clear_manager import PaneClearManager
from pane_hygiene_registry import PaneHygieneRegistry, PaneState
from recover_detector import RecoverDetector


def harness_dir() -> Path:
    raw = os.environ.get("HARNESS_DIR")
    return Path(raw).expanduser() if raw else Path(__file__).resolve().parents[1]


SESSION = os.environ.get("SOLAR_HARNESS_SESSION", "solar-harness")
HARNESS_DIR = harness_dir()
REGISTRY_PATH = HARNESS_DIR / "run" / "pane-hygiene.json"


def list_tmux_panes() -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{session_name}:#{window_index}.#{pane_index}\t#{pane_title}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    rows: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        pane, _, title = line.partition("\t")
        rows.append({"pane": pane.strip(), "title": title.strip()})
    return rows


def _allowed_session(pane: str) -> bool:
    return pane.startswith(f"{SESSION}:") or pane.startswith("solar-harness-lab:") or pane.startswith("solar-harness-multi-task:")


def infer_role(pane: str, title: str) -> str:
    normalized = title or ""
    base = normalized.split("|", 1)[0].strip()
    lowered = base.lower()
    if pane.endswith(":0.0") and pane.startswith(f"{SESSION}:") and ("pm" in lowered or "产品经理" in base):
        return "pm"
    if "planner" in lowered or "规划者" in base:
        return "planner"
    if "evaluator" in lowered or "审判官" in base:
        return "evaluator"
    if "architect" in lowered or "架构师" in base:
        return "architect"
    if "observer" in lowered or "观察" in base:
        return "observer"
    if "builder" in lowered or "建设者" in base or "lab-builder" in lowered:
        return "builder"
    if pane.startswith("solar-harness-lab:") or pane.startswith("solar-harness-multi-task:"):
        return "builder"
    if pane == f"{SESSION}:0.0":
        return "pm"
    if pane == f"{SESSION}:0.1":
        return "planner"
    if pane == f"{SESSION}:0.3":
        return "evaluator"
    return "builder"


def _planner_rank(item: dict[str, str]) -> tuple[int, str]:
    role = item["host_role"]
    pane = item["pane"]
    if role == "planner":
        return (0, pane)
    if role == "architect":
        return (1, pane)
    if role == "builder":
        return (2, pane)
    return (9, pane)


def _evaluator_rank(item: dict[str, str]) -> tuple[int, str]:
    role = item["host_role"]
    pane = item["pane"]
    if role == "evaluator":
        return (0, pane)
    if role == "builder":
        return (1, pane)
    return (9, pane)


def _builder_rank(item: dict[str, str]) -> tuple[int, str]:
    pane = item["pane"]
    if pane.startswith("solar-harness-lab:"):
        return (0, pane)
    if pane.startswith("solar-harness-multi-task:"):
        return (1, pane)
    return (2, pane)


def discover_role_pool(role: str) -> list[dict[str, str]]:
    rows = []
    for item in list_tmux_panes():
        pane = item["pane"]
        if not _allowed_session(pane):
            continue
        host_role = infer_role(pane, item["title"])
        item = {"pane": pane, "title": item["title"], "host_role": host_role}
        if role == "pm":
            if host_role in {"pm", "observer"}:
                rows.append(item)
        elif role == "planner":
            if host_role in {"planner", "architect", "builder"}:
                rows.append(item)
        elif role == "builder":
            if host_role == "builder":
                rows.append(item)
        elif role == "evaluator":
            if host_role in {"evaluator", "builder"}:
                rows.append(item)
    if role == "planner":
        rows.sort(key=_planner_rank)
    elif role == "evaluator":
        rows.sort(key=_evaluator_rank)
    elif role == "builder":
        rows.sort(key=_builder_rank)
    else:
        rows.sort(key=lambda item: item["pane"])
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in rows:
        pane = item["pane"]
        if pane in seen:
            continue
        seen.add(pane)
        deduped.append(item)
    return deduped


def _entry_for_boundary(registry: PaneHygieneRegistry, pane: str, role: str):
    entry = registry.ensure_pane(pane, role)
    if entry.state == PaneState.clean:
        registry.transition_state(pane, PaneState.running, reason="dispatch_boundary_mark_running")
        entry = registry.transition_state(pane, PaneState.dirty, reason="dispatch_boundary_requires_clear")
    elif entry.state == PaneState.running:
        entry = registry.transition_state(pane, PaneState.dirty, reason="dispatch_boundary_requires_clear")
    elif entry.state == PaneState.dirty:
        entry = registry.get_pane_state(pane)
    return entry


def ensure_clean_for_dispatch(pane: str, role: str, registry_path: Path | None = None) -> dict[str, Any]:
    registry = PaneHygieneRegistry(str((registry_path or REGISTRY_PATH).expanduser()))
    entry = _entry_for_boundary(registry, pane, role)
    if entry.state in {PaneState.cooling, PaneState.needs_recover, PaneState.needs_respawn}:
        return {"ok": False, "pane": pane, "role": role, "reason": entry.state.value}
    manager = PaneClearManager(registry, RecoverDetector())
    result = manager.clear_with_retry(pane)
    if result.success:
        registry.update_context_fields(pane, persona=role)
    return {
        "ok": result.success,
        "pane": pane,
        "role": role,
        "reason": result.reason,
        "attempts": result.attempts,
        "final_state": result.final_state.value,
        "signal_empty": result.signal_empty,
        "signal_no_queued": result.signal_no_queued,
        "signal_no_confirm": result.signal_no_confirm,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pane role-pool + hygiene utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    discover_cmd = sub.add_parser("discover-role-pool")
    discover_cmd.add_argument("--role", required=True)

    clear_cmd = sub.add_parser("ensure-clean")
    clear_cmd.add_argument("--pane", required=True)
    clear_cmd.add_argument("--role", required=True)
    clear_cmd.add_argument("--registry", default=str(REGISTRY_PATH))

    args = parser.parse_args(argv)
    if args.cmd == "discover-role-pool":
        print(json.dumps({"role": args.role, "panes": discover_role_pool(args.role)}, ensure_ascii=False))
        return 0
    if args.cmd == "ensure-clean":
        result = ensure_clean_for_dispatch(
            args.pane,
            args.role,
            registry_path=Path(args.registry).expanduser(),
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
