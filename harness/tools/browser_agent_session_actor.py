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


def _active_runs_dir() -> Path:
    path = _current_harness_dir() / "run" / "browser-agent-session-active" / "chatgpt"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _active_run_path(task_id: str) -> Path:
    return _active_runs_dir() / f"{task_id}.json"


def _write_active_run(manifest: dict[str, Any]) -> Path:
    path = _active_run_path(str(manifest["task_id"]))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _delete_active_run(task_id: str) -> None:
    _active_run_path(task_id).unlink(missing_ok=True)


def _iter_active_runs() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(_active_runs_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                items.append(data)
        except Exception:
            continue
    return items


def _load_operator_result(task_dir: Path) -> dict[str, Any]:
    path = task_dir / "chatgpt-browser-agent-result.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _parse_json_text(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(str(text or "").strip())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


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


def _active_run_manifest(
    *,
    envelope: dict[str, Any],
    slot: dict[str, Any],
    task_dir: Path,
    request_dir: str,
    submit_status: dict[str, Any],
) -> dict[str, Any]:
    request = dict(envelope.get("chatgpt_browser_agent_request") or {})
    request["request_dir"] = request_dir
    request["action"] = "submit"
    return {
        "task_id": str(envelope.get("task_id") or ""),
        "logical_operator": str(envelope.get("logical_operator") or ""),
        "task_dir": str(task_dir),
        "request": request,
        "slot": {
            "slot_id": str(slot.get("slot_id") or ""),
            "session_lineage": str(slot.get("session_lineage") or ""),
        },
        "conversation_url": str(submit_status.get("url") or ""),
        "conversation_id": str(submit_status.get("conversation_id") or ""),
        "status": str(submit_status.get("status") or "submitted"),
        "submitted_at": str(submit_status.get("submitted_at") or _now_iso()),
        "updated_at": _now_iso(),
        "collect_attempts": 0,
    }


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
    request = dict(envelope.get("chatgpt_browser_agent_request") or {})
    action = str(request.get("action") or "run").strip().lower()
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

        operator_result = _load_operator_result(task_dir)
        operator_text = str(operator_result.get("text") or "").strip()

        if proc.returncode == 0:
            if action == "submit":
                submit_status = _parse_json_text(operator_text)
                if not submit_status:
                    raise RuntimeError("browser_agent_session_submit_missing_json_status")
                manifest = _active_run_manifest(
                    envelope=envelope,
                    slot=slot,
                    task_dir=task_dir,
                    request_dir=str(operator_result.get("request_dir") or ""),
                    submit_status=submit_status,
                )
                _write_active_run(manifest)
                payload = _result_payload(
                    actor_id=actor_id,
                    envelope=envelope,
                    task_dir=task_dir,
                    status=str(submit_status.get("status") or "submitted"),
                    returncode=0,
                    slot=slot,
                )
                payload["active_run_manifest"] = str(_active_run_path(str(envelope.get("task_id") or "")))
                payload["active_run_created"] = True
                mailbox.write_result(str(envelope.get("task_id") or ""), payload)
                broker.transition(actor_id, READY)
                mailbox.write_heartbeat("idle", {"task_id": envelope.get("task_id"), "status": "submitted"})
                task_file.unlink(missing_ok=True)
                return payload
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


def process_active_runs_once(
    *,
    actor_id: str,
    mailbox: ActorMailbox,
    broker: LeaseBroker,
    skip_task_ids: set[str] | None = None,
) -> int:
    processed = 0
    skip_task_ids = skip_task_ids or set()
    for manifest in _iter_active_runs():
        task_id = str(manifest.get("task_id") or "").strip()
        if not task_id:
            continue
        if task_id in skip_task_ids:
            continue
        task_dir = Path(str(manifest.get("task_dir") or "")).expanduser()
        envelope_path = task_dir / "envelope.json"
        if not envelope_path.exists():
            continue
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        request = dict(manifest.get("request") or {})
        request["action"] = "collect"
        request["conversation_url"] = str(manifest.get("conversation_url") or "")
        request["request_dir"] = str(manifest.get("request_dir") or request.get("request_dir") or "")
        request.setdefault("prompt", "")
        envelope["chatgpt_browser_agent_request"] = request
        envelope_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        broker.transition(actor_id, RUNNING)
        mailbox.write_heartbeat("running", {"task_id": task_id, "mode": "collect"})
        command = resolve_command(envelope)
        slot = dict(manifest.get("slot") or {})
        env = os.environ.copy()
        env["HARNESS_DIR"] = str(_current_harness_dir())
        env["TASK_DIR"] = str(task_dir)
        env["SOLAR_OPERATOR_ENVELOPE_JSON"] = str(envelope_path)
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
        (task_dir / "collect-output.log").write_text(combined, encoding="utf-8")
        broker.transition(actor_id, FINALIZING)
        operator_result = _load_operator_result(task_dir)
        operator_text = str(operator_result.get("text") or "").strip()
        status_json = _parse_json_text(operator_text)
        if proc.returncode == 0 and status_json and str(status_json.get("status") or "").strip().lower() in {"running", "submitted"}:
            manifest["status"] = str(status_json.get("status") or manifest.get("status") or "running")
            manifest["updated_at"] = _now_iso()
            manifest["collect_attempts"] = int(manifest.get("collect_attempts") or 0) + 1
            _write_active_run(manifest)
            broker.transition(actor_id, READY)
            mailbox.write_heartbeat("idle", {"task_id": task_id, "status": manifest["status"]})
            processed += 1
            continue
        if proc.returncode == 0:
            payload = _result_payload(
                actor_id=actor_id,
                envelope=envelope,
                task_dir=task_dir,
                status="completed",
                returncode=0,
                slot=slot,
            )
            mailbox.write_result(task_id, payload)
            BrowserAgentSessionPool(_current_harness_dir() / "run" / "browser-agent-session-pool", pool_size=_pool_size()).release_slot(
                str(slot.get("slot_id") or ""),
                keep_warm=True,
            )
            _delete_active_run(task_id)
            broker.transition(actor_id, READY)
            mailbox.write_heartbeat("idle", {"task_id": task_id, "status": "completed"})
            processed += 1
            continue
        payload = _result_payload(
            actor_id=actor_id,
            envelope=envelope,
            task_dir=task_dir,
            status="failed",
            returncode=proc.returncode,
            error=combined[-2000:],
            slot=slot,
        )
        mailbox.write_result(task_id, payload)
        BrowserAgentSessionPool(_current_harness_dir() / "run" / "browser-agent-session-pool", pool_size=_pool_size()).release_slot(
            str(slot.get("slot_id") or ""),
            keep_warm=False,
        )
        _delete_active_run(task_id)
        broker.transition(actor_id, READY)
        mailbox.write_heartbeat("idle", {"task_id": task_id, "status": "failed"})
        processed += 1
    return processed


def drain_once(*, actor_id: str, mailbox_base: Path, lease_dir: Path) -> int:
    mailbox = ActorMailbox(actor_id, mailbox_base)
    broker = LeaseBroker(lease_dir)
    mailbox.ensure_dirs()
    task_files = sorted(mailbox.inbox.glob("task-*.json"))
    processed = 0
    submitted_task_ids: set[str] = set()
    for task_file in task_files:
        payload = process_task_file(actor_id=actor_id, mailbox=mailbox, broker=broker, task_file=task_file)
        if payload.get("active_run_created"):
            submitted_task_ids.add(str(payload.get("task_id") or ""))
        processed += 1
    processed += process_active_runs_once(
        actor_id=actor_id,
        mailbox=mailbox,
        broker=broker,
        skip_task_ids=submitted_task_ids,
    )
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
