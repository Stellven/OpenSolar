#!/usr/bin/env python3
"""Operator health watchdog CLI and compatibility facade."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import importlib.util

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_MODULE_PATH = REPO_ROOT / "lib" / "operator_health_watchdog.py"
RUN_DIR = HARNESS_DIR / "run" / "operator-health-watchdog"
LOCK_PATH = RUN_DIR / "lock"
LATEST_REPORT_PATH = RUN_DIR / "latest.json"
HISTORY_PATH = RUN_DIR / "history.jsonl"
LAUNCH_AGENT_LABEL = "com.solar.harness.operator-health-watchdog"
LAUNCH_AGENT_PLIST_PATH = RUN_DIR / f"{LAUNCH_AGENT_LABEL}.plist"
OUT_LOG = HARNESS_DIR / "logs" / "operator-health-watchdog.out.log"
ERR_LOG = HARNESS_DIR / "logs" / "operator-health-watchdog.err.log"



def _load_core() -> Any:
    core_lib_dir = str(CORE_MODULE_PATH.parent)
    if core_lib_dir not in sys.path:
        sys.path.insert(0, core_lib_dir)
    spec = importlib.util.spec_from_file_location("solar_watchdog_core", CORE_MODULE_PATH)
    if not spec or not spec.loader:
        raise FileNotFoundError(f"core module not found: {CORE_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_tool(name: str):
    candidates = [
        HARNESS_DIR / "tools" / f"{name}.py",
        REPO_ROOT / "tools" / f"{name}.py",
    ]
    for path in candidates:
        if not path.exists():
            continue
        spec = importlib.util.spec_from_file_location(f"operator_health_watchdog_{name}", path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(f"tool not found: {name}")


def run_watchdog(
    *,
    apply: bool = False,
    max_age_minutes: int = 45,
) -> dict[str, Any]:
    core = _load_core()
    pm_mod = _load_tool("pm_dispatch")
    quota_mod = _load_tool("quota_refresh")
    prune_mod = pm_mod if apply else None

    payload = core.run_watchdog(
        apply=bool(apply),
        max_age_minutes=max(1, int(max_age_minutes or 45)),
        pm_dispatch_module=pm_mod,
        quota_refresh_module=quota_mod,
        prune_module=prune_mod,
        lock_path=LOCK_PATH,
        latest_path=LATEST_REPORT_PATH,
        history_path=HISTORY_PATH,
    )

    payload.setdefault("applied", bool(apply))
    payload.setdefault("ok", payload.get("last_exit_code", 0) == 0)
    payload.setdefault("max_age_minutes", max(1, int(max_age_minutes or 45)))
    payload.setdefault("summary", {}).setdefault("ok", payload.get("ok", False))
    payload["summary"]["applied"] = bool(apply)
    return payload


def command_run_once(
    *,
    apply: bool,
    max_age_minutes: int,
    lock_path: Path = LOCK_PATH,
    latest_path: Path = LATEST_REPORT_PATH,
    history_path: Path = HISTORY_PATH,
) -> dict[str, Any]:
    core = _load_core()
    return core.command_run_once(
        apply=bool(apply),
        max_age_minutes=max(1, int(max_age_minutes or 45)),
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
    core = _load_core()
    return core.command_run_loop(
        interval=int(interval),
        apply=bool(apply),
        max_age_minutes=max(1, int(max_age_minutes or 45)),
        lock_path=lock_path,
        latest_path=latest_path,
        history_path=history_path,
        loop_max_iterations=loop_max_iterations,
    )


def command_status(
    *,
    json_output: bool = True,
    latest_path: Path = LATEST_REPORT_PATH,
) -> dict[str, Any]:
    del json_output
    core = _load_core()
    return core.command_status(latest_path=latest_path)


def command_install_launchagent(
    *,
    dry_run: bool = False,
    apply: bool = False,
    run_dir: Path = RUN_DIR,
) -> dict[str, Any]:
    script_candidates = [
        HARNESS_DIR / "scripts" / "operator-health-watchdog-daemon.sh",
        REPO_ROOT / "scripts" / "operator-health-watchdog-daemon.sh",
    ]
    daemon_script = next((p for p in script_candidates if p.exists()), None)
    payload = {
        "ok": False,
        "installed": False,
        "launchd_loaded": False,
        "label": LAUNCH_AGENT_LABEL,
        "plist_path": str(LAUNCH_AGENT_PLIST_PATH),
        "out_log": str(OUT_LOG),
        "err_log": str(ERR_LOG),
        "run_dir": str(run_dir),
    }

    if daemon_script is None:
        payload["degraded_reason"] = "launchagent helper script is not available in this installation"
        payload["plan"] = {
            "note": "N2 will provide daemon installer; for now expose path-only status.",
            "run_dir": str(run_dir),
            "expected_label": LAUNCH_AGENT_LABEL,
        }
        return payload

    payload["daemon_script"] = str(daemon_script)
    payload["dry_run"] = bool(dry_run)
    if dry_run or not apply:
        payload["ok"] = True
        payload["plan"] = {
            "action": "install-launchagent (dry-run)",
            "command": f"{daemon_script} install --plist {LAUNCH_AGENT_PLIST_PATH}",
        }
        return payload

    proc = subprocess.run(
        [str(daemon_script), "install", "--plist", str(LAUNCH_AGENT_PLIST_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )
    payload["ok"] = proc.returncode == 0
    payload["returncode"] = proc.returncode
    if proc.stdout.strip():
        payload["stdout"] = proc.stdout.strip()
    if proc.stderr.strip():
        payload["stderr"] = proc.stderr.strip()
    if proc.returncode == 0:
        payload["installed"] = True
        payload["launchd_loaded"] = True
    else:
        payload["degraded_reason"] = "launchagent install command returned non-zero"
    return payload


def _print_table(payload: dict[str, Any], stream=sys.stdout) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print("operator_health_watchdog", file=stream)
    print("┌──────────────────────────────┬────────┬──────────────────────────────────────────────┐", file=stream)
    print("│ 项目                         │ 状态   │ 证据                                         │", file=stream)
    print("├──────────────────────────────┼────────┼──────────────────────────────────────────────┤", file=stream)
    rows = [
        ("applied", "ok" if payload.get("applied") else "pending", str(payload.get("applied", False))),
        ("operators_usable", "ok" if summary.get("operators_usable", 0) else "warn", f"{summary.get('operators_usable', 0)}/{summary.get('operators_total', 0)}"),
        ("hard_blocked", "warn" if summary.get("operators_hard_blocked") else "ok", str(summary.get("operators_hard_blocked", 0))),
        ("quota_level", "ok", str(summary.get("quota_recommended_level", "N/A"))),
        ("backlog", "warn" if int(summary.get("quota_backlog") or 0) else "ok", str(summary.get("quota_backlog", 0))),
        ("pruned_blocks", "ok", str(summary.get("pruned_blocks", 0))),
        ("kept_blocks", "warn" if summary.get("kept_blocks") else "ok", str(summary.get("kept_blocks", 0))),
    ]
    for name, status, evidence in rows:
        stream.write(f"│ {name:<28} │ {status:<6} │ {evidence:<44} │\n")
    print("└──────────────────────────────┴────────┴──────────────────────────────────────────────┘", file=stream)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Solar operator cooldown/quota health watchdog.")
    parser.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--max-age-minutes", type=int, default=45, help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=False)

    run = sub.add_parser("run", help="Execute watchdog once or loop")
    mode = run.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run once and write latest report.")
    mode.add_argument("--loop", action="store_true", help="Run loop with interval (seconds).")
    run.add_argument("--interval", type=int, default=120, help="Loop interval (seconds).")
    run.add_argument("--apply", action="store_true", help="Actually clear expired blocks and reconcile stale PM records.")
    run.add_argument("--max-age-minutes", type=int, default=45, help="Stale PM record threshold for reconcile.")
    run.add_argument("--json", action="store_true", help="Output JSON.")

    status = sub.add_parser("status", help="Read latest watchdog report.")
    status.add_argument("--json", action="store_true", help="Output JSON.")

    install = sub.add_parser("install-launchagent", help="Install watchdog LaunchAgent (if available).")
    install.add_argument("--dry-run", action="store_true", help="Return install plan only.")
    install.add_argument("--apply", action="store_true", help="Actually run installer script.")
    install.add_argument("--json", action="store_true", help="Output JSON.")
    return parser


def _has_legacy_root_flags(args: argparse.Namespace) -> bool:
    return bool(args.apply or args.json or int(args.max_age_minutes or 45) != 45)


def main() -> int:
    parser = _build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    args = parser.parse_args()

    if args.command is None and _has_legacy_root_flags(args):
        payload = command_run_once(
            apply=bool(args.apply),
            max_age_minutes=int(args.max_age_minutes or 45),
            lock_path=LOCK_PATH,
            latest_path=LATEST_REPORT_PATH,
            history_path=HISTORY_PATH,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_table(payload)
            if not payload.get("ok", False):
                print(f"degraded_reason={payload.get('degraded_reason', 'N/A')}")
        return 0 if payload.get("ok") else 1

    if args.command == "run":
        if args.loop and int(args.interval) <= 0:
            print("degraded: --loop requires --interval > 0", file=sys.stderr)
            return 1

        if args.once:
            payload = command_run_once(
                apply=bool(args.apply),
                max_age_minutes=int(args.max_age_minutes or 45),
                lock_path=LOCK_PATH,
                latest_path=LATEST_REPORT_PATH,
                history_path=HISTORY_PATH,
            )
        else:
            payloads = command_run_loop(
                interval=int(args.interval),
                apply=bool(args.apply),
                max_age_minutes=int(args.max_age_minutes or 45),
                lock_path=LOCK_PATH,
                latest_path=LATEST_REPORT_PATH,
                history_path=HISTORY_PATH,
            )
            payload = payloads[-1] if payloads else {"ok": False}

        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_table(payload)
            if not payload.get("ok", False):
                print(f"degraded_reason={payload.get('degraded_reason', 'N/A')}")
        return 0 if payload.get("ok") else 1

    if args.command == "status":
        payload = command_status(json_output=True, latest_path=LATEST_REPORT_PATH)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_table(payload)
            print(f"latest_json={payload.get('latest_report', LATEST_REPORT_PATH)}")
            if payload.get("blockers"):
                print(f"blockers={payload.get('blockers')}")
        return 0 if payload.get("ok") else 2

    if args.command == "install-launchagent":
        payload = command_install_launchagent(
            dry_run=bool(args.dry_run),
            apply=bool(args.apply),
            run_dir=RUN_DIR,
        )
        if args.json or args.dry_run:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_table(payload)
            print(f"installed={payload.get('installed')} loaded={payload.get('launchd_loaded')}")
            if payload.get("degraded_reason"):
                print(f"degraded_reason={payload.get('degraded_reason')}")
        return 0 if payload.get("ok") else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
