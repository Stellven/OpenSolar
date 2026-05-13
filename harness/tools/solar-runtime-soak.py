#!/usr/bin/env python3
"""Periodic Solar-Harness runtime soak monitor.

Runs cheap, token-free control-plane checks:
  - runtime audit-writes --strict
  - runtime doctor for current sprint
  - autopilot monitor --apply --json

On failure, writes a report and enqueues a remediation item into the existing
autopilot queue. The persistent autopilot LaunchAgent owns dispatch/retry.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HOME = Path.home()
HARNESS = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness")).expanduser()
SOLAR = HARNESS / "solar-harness.sh"
STATE = HARNESS / "state" / "runtime-soak-latest.json"
REPORT_JSON = HARNESS / "reports" / "runtime-soak-latest.json"
REPORT_MD = HARNESS / "reports" / "runtime-soak-latest.md"
QUEUE = HARNESS / "run" / "autopilot-queue.jsonl"
LOCK = HARNESS / "run" / "runtime-soak.lock"
LOG = HARNESS / "run" / "runtime-soak.log"
DEFAULT_TARGET = os.environ.get("SOLAR_RUNTIME_SOAK_TARGET", "solar-harness:0.0")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_cmd(cmd: list[str], timeout: int = 45) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        return {
            "cmd": cmd,
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "duration_sec": round(time.time() - started, 3),
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "ok": False,
            "returncode": 124,
            "duration_sec": round(time.time() - started, 3),
            "stdout": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr": f"timeout after {timeout}s",
        }


def parse_json_step(step: dict[str, Any]) -> Any:
    if not step.get("stdout"):
        return None
    try:
        return json.loads(step["stdout"])
    except Exception:
        return None


def current_sprint() -> str:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/status", timeout=5) as resp:
            data = json.load(resp)
        sid = data.get("current_sprint", {}).get("sprint_id")
        if sid:
            return str(sid)
    except Exception:
        pass
    sprints = sorted((HARNESS / "sprints").glob("sprint-*.status.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in sprints:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sid = data.get("sprint_id") or data.get("id") or path.name.removesuffix(".status.json")
            if sid:
                return str(sid)
        except Exception:
            continue
    return ""


def load_queue() -> list[dict[str, Any]]:
    if not QUEUE.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in QUEUE.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def enqueue_failure(sid: str, failures: list[str], report_path: Path) -> bool:
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    item_key = f"{sid}:runtime_soak_failed:{DEFAULT_TARGET}"
    for item in load_queue():
        old_key = f"{item.get('sid','')}:{item.get('type','')}:{item.get('target','')}"
        if old_key == item_key:
            return False
    item = {
        "ts": now_iso(),
        "created_at_epoch": time.time(),
        "sid": sid,
        "type": "runtime_soak_failed",
        "target": DEFAULT_TARGET,
        "message": (
            "Runtime soak failed. 请检查 "
            f"{report_path}；优先修复 audit-writes / runtime doctor / autopilot 队列问题。"
        ),
        "reason": "runtime_soak_failure",
        "detail": {"failures": failures, "report": str(report_path)},
        "attempts": 0,
    }
    with QUEUE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    return True


def write_reports(report: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Runtime Soak Latest",
        "",
        f"Status: {'ok' if report.get('ok') else 'error'}",
        f"Checked at: {report.get('checked_at')}",
        f"Sprint: `{report.get('sprint_id') or 'N/A'}`",
        f"Failures: {', '.join(report.get('failures') or []) or 'none'}",
        f"Queued repair: {report.get('queued_repair')}",
        "",
        "## Steps",
    ]
    for name, step in report.get("steps", {}).items():
        lines.append(f"- {name}: {'ok' if step.get('ok') else 'error'} rc={step.get('returncode')} duration={step.get('duration_sec')}s")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_log(report: dict[str, Any]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": report.get("checked_at"),
            "ok": report.get("ok"),
            "sprint_id": report.get("sprint_id"),
            "failures": report.get("failures"),
            "queued_repair": report.get("queued_repair"),
        }, ensure_ascii=False) + "\n")


def acquire_lock() -> bool:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            pid = int(LOCK.read_text().strip() or "0")
            if pid and os.kill(pid, 0) is None:
                return False
        except Exception:
            pass
        try:
            LOCK.unlink()
        except OSError:
            return False
        return acquire_lock()


def release_lock() -> None:
    try:
        LOCK.unlink()
    except OSError:
        pass


def run_once() -> dict[str, Any]:
    sid = current_sprint()
    steps: dict[str, dict[str, Any]] = {}
    steps["audit_writes"] = run_cmd([str(SOLAR), "runtime", "audit-writes", "--json", "--strict"], timeout=30)
    if sid:
        steps["runtime_doctor"] = run_cmd([str(SOLAR), "runtime", "doctor", sid, "--json"], timeout=45)
    else:
        steps["runtime_doctor"] = {"ok": False, "returncode": 2, "stdout": "", "stderr": "no sprint_id", "duration_sec": 0}
    steps["autopilot"] = run_cmd(["python3", str(HARNESS / "tools" / "solar-autopilot-monitor.py"), "--apply", "--json"], timeout=90)

    failures = [name for name, step in steps.items() if not step.get("ok")]
    parsed = {name: parse_json_step(step) for name, step in steps.items()}
    report: dict[str, Any] = {
        "ok": not failures,
        "checked_at": now_iso(),
        "sprint_id": sid,
        "failures": failures,
        "steps": steps,
        "parsed": parsed,
        "report_json": str(REPORT_JSON),
        "report_md": str(REPORT_MD),
    }
    queued = False
    if failures:
        queued = enqueue_failure(sid, failures, REPORT_JSON)
    report["queued_repair"] = queued
    write_reports(report)
    append_log(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Solar-Harness runtime soak check.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on failed soak")
    args = parser.parse_args()

    if not acquire_lock():
        payload = {"ok": True, "skipped": "already_running", "checked_at": now_iso(), "lock": str(LOCK)}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload)
        return 0
    try:
        report = run_once()
    finally:
        release_lock()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"runtime_soak={'ok' if report['ok'] else 'error'} failures={','.join(report['failures']) or 'none'}")
    return 1 if args.strict and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

