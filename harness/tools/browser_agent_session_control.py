#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "lib"))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from actor_mailbox import ActorMailbox  # noqa: E402
from actor_runtime import ActorRuntime  # noqa: E402
from browser_agent_session_actor import (  # noqa: E402
    DEFAULT_ACTOR_ID,
    ensure_supervisor_running,
    request_supervisor_drain,
    request_supervisor_stop,
    supervisor_status,
)


def _json_dump(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _harness_dir() -> Path:
    return Path(os.environ.get("HARNESS_DIR") or (Path.home() / ".solar" / "harness")).expanduser()


def _runtime() -> ActorRuntime:
    return ActorRuntime(harness_dir=_harness_dir())


def _mailbox(actor_id: str) -> ActorMailbox:
    return ActorMailbox(actor_id, _harness_dir() / "actors")


def _task_id(prefix: str = "browser-agent-session") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _find_inbox_task(mailbox: ActorMailbox, task_id: str) -> str:
    for path in sorted(mailbox.inbox.glob(f"task-{task_id}-*.json")):
        return str(path)
    return ""


def _load_prompt(args: argparse.Namespace) -> str:
    text = str(args.prompt or "").strip()
    if text:
        return text
    prompt_file = str(args.prompt_file or "").strip()
    if prompt_file:
        return Path(prompt_file).expanduser().read_text(encoding="utf-8")
    return sys.stdin.read().strip()


def _submit(args: argparse.Namespace) -> int:
    prompt = _load_prompt(args)
    if not prompt:
        raise RuntimeError("prompt is required")
    runtime = _runtime()
    request = {
        "prompt": prompt,
        "expected_output": str(args.expected_output or "markdown"),
        "model": str(args.model or "chatgpt-5.5"),
        "reasoning_effort": str(args.reasoning_effort or "high"),
        "project_name": str(args.project_name or "杂项"),
        "action": "submit" if args.async_mode else "run",
        "headless": not bool(args.headed),
        "session_reuse": True,
        "session_lineage": str(args.session_lineage or "").strip(),
    }
    task_id = str(args.task_id or _task_id())
    envelope = {
        "task_id": task_id,
        "objective": str(args.objective or prompt[:120]),
        "logical_operator": str(args.logical_operator or "DeepResearchBrowser"),
        "chatgpt_browser_agent_request": request,
    }
    result = runtime.submit(envelope, logical_operator=str(args.logical_operator or "DeepResearchBrowser"))
    payload = result.to_dict()
    payload["task_id"] = task_id
    payload["actor_id"] = DEFAULT_ACTOR_ID
    payload["inbox_task_file"] = _find_inbox_task(_mailbox(DEFAULT_ACTOR_ID), task_id)
    _json_dump(payload)
    return 0 if result.success else 1


def _poll(args: argparse.Namespace) -> int:
    actor_id = str(args.actor_id or DEFAULT_ACTOR_ID)
    mailbox = _mailbox(actor_id)
    task_id = str(args.task_id or "").strip()
    if not task_id:
        raise RuntimeError("task_id is required")
    results = mailbox.read_results(task_id)
    latest = results[-1] if results else {}
    status = str(latest.get("status") or "").strip().lower()
    inbox_task_file = _find_inbox_task(mailbox, task_id)
    active_manifest = _harness_dir() / "run" / "browser-agent-session-active" / "chatgpt" / f"{task_id}.json"
    manifest = {}
    if active_manifest.exists():
        try:
            data = json.loads(active_manifest.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                manifest = data
        except Exception:
            manifest = {}
    if not status:
        if manifest:
            status = str(manifest.get("status") or "running")
        elif inbox_task_file:
            status = "queued"
        else:
            status = "unknown"
    payload = {
        "ok": True,
        "task_id": task_id,
        "actor_id": actor_id,
        "status": status,
        "queued": bool(inbox_task_file),
        "inbox_task_file": inbox_task_file,
        "active_manifest_file": str(active_manifest) if active_manifest.exists() else "",
        "active_manifest": manifest,
        "latest_result": latest,
        "result_count": len(results),
    }
    _json_dump(payload)
    return 0


def _collect(args: argparse.Namespace) -> int:
    timeout_seconds = max(1.0, float(args.timeout_seconds))
    poll_interval_seconds = max(0.2, float(args.poll_interval_seconds))
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] = {}
    while time.time() <= deadline:
        actor_id = str(args.actor_id or DEFAULT_ACTOR_ID)
        mailbox = _mailbox(actor_id)
        task_id = str(args.task_id or "").strip()
        results = mailbox.read_results(task_id)
        latest = results[-1] if results else {}
        status = str(latest.get("status") or "").strip().lower()
        active_manifest = _harness_dir() / "run" / "browser-agent-session-active" / "chatgpt" / f"{task_id}.json"
        manifest = {}
        if active_manifest.exists():
            try:
                data = json.loads(active_manifest.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    manifest = data
            except Exception:
                manifest = {}
        if not status and manifest:
            status = str(manifest.get("status") or "running")
        last_payload = {
            "ok": True,
            "task_id": task_id,
            "actor_id": actor_id,
            "status": status or "unknown",
            "latest_result": latest,
            "active_manifest": manifest,
            "result_count": len(results),
        }
        if status in {"completed", "failed"}:
            _json_dump(last_payload)
            return 0 if status == "completed" else 1
        time.sleep(poll_interval_seconds)
    last_payload["timeout"] = True
    _json_dump(last_payload)
    return 2


def _supervisor_status_cmd(args: argparse.Namespace) -> int:
    payload = supervisor_status(str(args.actor_id or DEFAULT_ACTOR_ID), mailbox_base=_harness_dir() / "actors")
    _json_dump(payload)
    return 0


def _supervisor_drain_cmd(args: argparse.Namespace) -> int:
    path = request_supervisor_drain(str(args.actor_id or DEFAULT_ACTOR_ID))
    _json_dump({"ok": True, "actor_id": str(args.actor_id or DEFAULT_ACTOR_ID), "drain_flag": str(path)})
    return 0


def _supervisor_stop_cmd(args: argparse.Namespace) -> int:
    actor_id = str(args.actor_id or DEFAULT_ACTOR_ID)
    path = request_supervisor_stop(actor_id)
    payload = supervisor_status(actor_id, mailbox_base=_harness_dir() / "actors")
    pid = int(payload.get("pid") or 0)
    if pid > 0:
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    _json_dump({"ok": True, "actor_id": actor_id, "stop_flag": str(path), "pid": pid})
    return 0


def _supervisor_ensure_cmd(args: argparse.Namespace) -> int:
    result = ensure_supervisor_running(
        actor_id=str(args.actor_id or DEFAULT_ACTOR_ID),
        mailbox_base=_harness_dir() / "actors",
        lease_dir=_harness_dir() / "run" / "actor-leases",
        poll_interval_seconds=float(args.poll_interval_seconds),
    )
    _json_dump(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="solar-harness browser session", description="Browser agent session control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    submit = sub.add_parser("submit")
    submit.add_argument("--task-id", default="")
    submit.add_argument("--logical-operator", default="DeepResearchBrowser")
    submit.add_argument("--objective", default="")
    submit.add_argument("--prompt", default="")
    submit.add_argument("--prompt-file", default="")
    submit.add_argument("--model", default="chatgpt-5.5")
    submit.add_argument("--reasoning-effort", default="high")
    submit.add_argument("--expected-output", default="markdown")
    submit.add_argument("--project-name", default="杂项")
    submit.add_argument("--session-lineage", default="")
    submit.add_argument("--headed", action="store_true")
    submit.add_argument("--async", dest="async_mode", action="store_true")
    submit.set_defaults(func=_submit)

    poll = sub.add_parser("poll")
    poll.add_argument("--actor-id", default=DEFAULT_ACTOR_ID)
    poll.add_argument("--task-id", required=True)
    poll.set_defaults(func=_poll)

    collect = sub.add_parser("collect")
    collect.add_argument("--actor-id", default=DEFAULT_ACTOR_ID)
    collect.add_argument("--task-id", required=True)
    collect.add_argument("--timeout-seconds", type=float, default=60.0)
    collect.add_argument("--poll-interval-seconds", type=float, default=2.0)
    collect.set_defaults(func=_collect)

    supervisor = sub.add_parser("supervisor")
    supervisor_sub = supervisor.add_subparsers(dest="supervisor_command", required=True)

    ensure = supervisor_sub.add_parser("ensure")
    ensure.add_argument("--actor-id", default=DEFAULT_ACTOR_ID)
    ensure.add_argument("--poll-interval-seconds", type=float, default=2.0)
    ensure.set_defaults(func=_supervisor_ensure_cmd)

    status = supervisor_sub.add_parser("status")
    status.add_argument("--actor-id", default=DEFAULT_ACTOR_ID)
    status.set_defaults(func=_supervisor_status_cmd)

    drain = supervisor_sub.add_parser("drain")
    drain.add_argument("--actor-id", default=DEFAULT_ACTOR_ID)
    drain.set_defaults(func=_supervisor_drain_cmd)

    stop = supervisor_sub.add_parser("stop")
    stop.add_argument("--actor-id", default=DEFAULT_ACTOR_ID)
    stop.set_defaults(func=_supervisor_stop_cmd)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
