#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "lib"))

from actor_lease import FINALIZING, READY, RUNNING, LeaseBroker
from actor_mailbox import ActorMailbox
from browser_agent_session_pool import BrowserAgentSessionPool


DEFAULT_ACTOR_ID = "browser_agent_session"
CHATGPT_TASK_OPERATOR = ROOT / "tools" / "chatgpt_browser_agent_task_operator.py"
CHATGPT_REQUIREMENT_WRITER = ROOT / "tools" / "chatgpt_requirement_writer_operator.py"


def _now_iso() -> str:
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _current_harness_dir() -> Path:
    return Path(os.environ.get("HARNESS_DIR") or (Path.home() / ".solar" / "harness")).expanduser()


def _task_dir(mailbox: ActorMailbox, envelope: dict[str, Any]) -> Path:
    task_id = str(envelope.get("task_id") or "unknown")
    task_dir = mailbox.logs / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def _pool_size() -> int:
    raw = str(os.environ.get("BROWSER_AGENT_SESSION_POOL_SIZE") or "2").strip()
    try:
        return max(1, int(raw))
    except Exception:
        return 2


def resolve_command(envelope: dict[str, Any]) -> list[str]:
    override = envelope.get("command")
    if override:
        if isinstance(override, list):
            return [str(item) for item in override]
        return ["bash", "-lc", str(override)]

    logical_operator = str(envelope.get("logical_operator") or "").strip()
    if logical_operator in {"DeepResearchBrowser", "DeepResearchChatGPT"}:
        return [sys.executable, str(CHATGPT_TASK_OPERATOR)]
    if logical_operator == "GPTRequirementWriter":
        return [sys.executable, str(CHATGPT_REQUIREMENT_WRITER)]
    raise RuntimeError(f"unsupported_browser_agent_session_logical_operator:{logical_operator or 'N/A'}")


def _result_payload(
    *,
    actor_id: str,
    envelope: dict[str, Any],
    task_dir: Path,
    status: str,
    returncode: int,
    error: str = "",
    slot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task_id = str(envelope.get("task_id") or "")
    payload = {
        "task_id": task_id,
        "actor_id": actor_id,
        "logical_operator": str(envelope.get("logical_operator") or ""),
        "status": status,
        "returncode": returncode,
        "task_dir": str(task_dir),
        "completed_at": _now_iso(),
    }
    if error:
        payload["error"] = error
    if slot:
        payload["pool_slot_id"] = str(slot.get("slot_id") or "")
        payload["pool_session_lineage"] = str(slot.get("session_lineage") or "")
    result_file = task_dir / "chatgpt-browser-agent-result.json"
    if result_file.exists():
        payload["result_file"] = str(result_file)
        try:
            result_json = json.loads(result_file.read_text(encoding="utf-8"))
            payload["request_dir"] = str(result_json.get("request_dir") or "")
            payload["expected_output"] = str(result_json.get("expected_output") or "")
            payload["project_name"] = str(result_json.get("project_name") or "")
        except Exception:
            pass
    req_writer_file = task_dir / "gpt-requirement-writer-output.md"
    if req_writer_file.exists():
        payload["artifact_file"] = str(req_writer_file)
    return payload


def process_task_file(
    *,
    actor_id: str,
    mailbox: ActorMailbox,
    broker: LeaseBroker,
    task_file: Path,
) -> dict[str, Any]:
    envelope = json.loads(task_file.read_text(encoding="utf-8"))
    task_dir = _task_dir(mailbox, envelope)
    (task_dir / "envelope.json").write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    broker.transition(actor_id, RUNNING)
    mailbox.write_heartbeat("running", {"task_id": envelope.get("task_id"), "logical_operator": envelope.get("logical_operator")})
    pool = BrowserAgentSessionPool(_current_harness_dir() / "run" / "browser-agent-session-pool", pool_size=_pool_size())
    request_lineage = str(
        envelope.get("session_lineage")
        or envelope.get("chatgpt_browser_agent_request", {}).get("session_lineage")
        or envelope.get("purpose")
        or envelope.get("objective")
        or ""
    ).strip()
    slot = pool.acquire_slot(
        task_id=str(envelope.get("task_id") or ""),
        request_lineage=request_lineage,
        request_dir=str(task_dir),
    )
    (task_dir / "browser-agent-session-slot.json").write_text(
        json.dumps(slot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        command = resolve_command(envelope)
        env = os.environ.copy()
        env["HARNESS_DIR"] = str(_current_harness_dir())
        env["TASK_DIR"] = str(task_dir)
        env["SOLAR_OPERATOR_ENVELOPE_JSON"] = str(task_dir / "envelope.json")
        env["BROWSER_AGENT_SESSION_REUSE"] = "true"
        env["SOLAR_BROWSER_SESSION_REUSE"] = "true"
        env["BROWSER_AGENT_SESSION_LINEAGE"] = str(slot.get("session_lineage") or "")
        env["SOLAR_BROWSER_SESSION_LINEAGE"] = str(slot.get("session_lineage") or "")
        env["BROWSER_AGENT_POOL_SLOT_ID"] = str(slot.get("slot_id") or "")
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        combined = str(proc.stdout or "")
        (task_dir / "output.log").write_text(combined, encoding="utf-8")
        broker.transition(actor_id, FINALIZING)

        if proc.returncode == 0:
            payload = _result_payload(
                actor_id=actor_id,
                envelope=envelope,
                task_dir=task_dir,
                status="completed",
                returncode=0,
                slot=slot,
            )
            mailbox.write_result(str(envelope.get("task_id") or ""), payload)
            broker.transition(actor_id, READY)
            mailbox.write_heartbeat("idle", {"task_id": envelope.get("task_id"), "status": "completed"})
            pool.release_slot(str(slot.get("slot_id") or ""), keep_warm=True)
            task_file.unlink(missing_ok=True)
            return payload

        payload = _result_payload(
            actor_id=actor_id,
            envelope=envelope,
            task_dir=task_dir,
            status="failed",
            returncode=proc.returncode,
            error=combined[-2000:],
            slot=slot,
        )
        mailbox.write_result(str(envelope.get("task_id") or ""), payload)
        broker.transition(actor_id, READY)
        mailbox.write_heartbeat("idle", {"task_id": envelope.get("task_id"), "status": "failed"})
        pool.release_slot(str(slot.get("slot_id") or ""), keep_warm=False)
        task_file.unlink(missing_ok=True)
        return payload
    except Exception as exc:
        broker.transition(actor_id, FINALIZING)
        payload = _result_payload(
            actor_id=actor_id,
            envelope=envelope,
            task_dir=task_dir,
            status="failed",
            returncode=1,
            error=f"{type(exc).__name__}:{exc}",
            slot=slot,
        )
        mailbox.write_result(str(envelope.get("task_id") or ""), payload)
        broker.transition(actor_id, READY)
        mailbox.write_heartbeat("idle", {"task_id": envelope.get("task_id"), "status": "failed"})
        pool.release_slot(str(slot.get("slot_id") or ""), keep_warm=False)
        task_file.unlink(missing_ok=True)
        return payload


def drain_once(*, actor_id: str, mailbox_base: Path, lease_dir: Path) -> int:
    mailbox = ActorMailbox(actor_id, mailbox_base)
    broker = LeaseBroker(lease_dir)
    mailbox.ensure_dirs()
    task_files = sorted(mailbox.inbox.glob("task-*.json"))
    if not task_files:
        mailbox.write_heartbeat("idle", {"processed": 0})
        return 0
    processed = 0
    for task_file in task_files:
        process_task_file(actor_id=actor_id, mailbox=mailbox, broker=broker, task_file=task_file)
        processed += 1
    mailbox.write_heartbeat("idle", {"processed": processed})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process browser_agent_session actor mailbox tasks")
    parser.add_argument("--actor-id", default=DEFAULT_ACTOR_ID)
    default_harness_dir = _current_harness_dir()
    parser.add_argument("--mailbox-base", default=str(default_harness_dir / "actors"))
    parser.add_argument("--lease-dir", default=str(default_harness_dir / "run" / "actor-leases"))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)

    mailbox_base = Path(str(args.mailbox_base)).expanduser()
    lease_dir = Path(str(args.lease_dir)).expanduser()
    return drain_once(actor_id=str(args.actor_id), mailbox_base=mailbox_base, lease_dir=lease_dir)


if __name__ == "__main__":
    raise SystemExit(main())
