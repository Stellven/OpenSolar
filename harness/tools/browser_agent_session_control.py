#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
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


def _collect_poll_sleep_seconds(base_interval: float, attempt: int, status: str) -> float:
    clean_status = str(status or "").strip().lower()
    base = max(0.2, float(base_interval or 0.2))
    if clean_status in {"completed", "failed"}:
        return base
    multiplier = min(max(int(attempt or 1), 1), 4)
    if clean_status == "submitted":
        return min(8.0, base * multiplier)
    return min(12.0, base * max(2, multiplier))


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


def submit_request(
    request: dict[str, Any],
    *,
    logical_operator: str = "DeepResearchBrowser",
    objective: str = "",
    task_id: str = "",
    request_field: str = "chatgpt_browser_agent_request",
    retry_attempts: int = 12,
    retry_wait_seconds: float = 5.0,
) -> dict[str, Any]:
    runtime = _runtime()
    resolved_task_id = str(task_id or _task_id())
    prompt = str(request.get("prompt") or "").strip()
    envelope = {
        "task_id": resolved_task_id,
        "objective": str(objective or prompt[:120] or logical_operator),
        "logical_operator": str(logical_operator or "DeepResearchBrowser"),
        str(request_field or "chatgpt_browser_agent_request"): dict(request or {}),
    }
    result = None
    max_attempts = max(1, int(retry_attempts or 1))
    for attempt in range(1, max_attempts + 1):
        result = runtime.submit(envelope, logical_operator=str(logical_operator or "DeepResearchBrowser"))
        error = str(getattr(result, "error", "") or "").strip()
        if getattr(result, "success", False):
            break
        if not error.startswith(f"lease_acquisition_failed_for_{DEFAULT_ACTOR_ID}"):
            break
        if attempt >= max_attempts:
            break
        time.sleep(max(0.2, float(retry_wait_seconds or 0.2)))
    assert result is not None
    payload = result.to_dict()
    payload["task_id"] = resolved_task_id
    payload["actor_id"] = DEFAULT_ACTOR_ID
    payload["inbox_task_file"] = _find_inbox_task(_mailbox(DEFAULT_ACTOR_ID), resolved_task_id)
    return payload


def poll_request(task_id: str, *, actor_id: str = DEFAULT_ACTOR_ID) -> dict[str, Any]:
    mailbox = _mailbox(actor_id)
    clean_task_id = str(task_id or "").strip()
    if not clean_task_id:
        raise RuntimeError("task_id is required")
    results = mailbox.read_results(clean_task_id)
    latest = results[-1] if results else {}
    status = str(latest.get("status") or "").strip().lower()
    inbox_task_file = _find_inbox_task(mailbox, clean_task_id)
    active_manifest = _harness_dir() / "run" / "browser-agent-session-active" / "chatgpt" / f"{clean_task_id}.json"
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
    return {
        "ok": True,
        "task_id": clean_task_id,
        "actor_id": actor_id,
        "status": status,
        "queued": bool(inbox_task_file),
        "inbox_task_file": inbox_task_file,
        "active_manifest_file": str(active_manifest) if active_manifest.exists() else "",
        "active_manifest": manifest,
        "latest_result": latest,
        "result_count": len(results),
    }


def collect_request(
    task_id: str,
    *,
    actor_id: str = DEFAULT_ACTOR_ID,
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 2.0,
    terminal_statuses: set[str] | None = None,
) -> tuple[int, dict[str, Any]]:
    terminal_statuses = {str(item).lower() for item in (terminal_statuses or {"completed", "failed"})}
    deadline = time.time() + max(1.0, float(timeout_seconds))
    last_payload: dict[str, Any] = {}
    attempts = 0
    while time.time() <= deadline:
        payload = poll_request(task_id, actor_id=actor_id)
        status = str(payload.get("status") or "").strip().lower()
        last_payload = payload
        if status in terminal_statuses:
            return (1 if status == "failed" else 0), payload
        attempts += 1
        time.sleep(_collect_poll_sleep_seconds(float(poll_interval_seconds), attempts, status))
    last_payload["timeout"] = True
    return 2, last_payload


def _submit(args: argparse.Namespace) -> int:
    prompt = _load_prompt(args)
    if not prompt:
        raise RuntimeError("prompt is required")
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
    payload = submit_request(
        request,
        logical_operator=str(args.logical_operator or "DeepResearchBrowser"),
        objective=str(args.objective or prompt[:120]),
        task_id=str(args.task_id or ""),
    )
    _json_dump(payload)
    return 0 if payload.get("success") else 1


def _poll(args: argparse.Namespace) -> int:
    payload = poll_request(str(args.task_id or ""), actor_id=str(args.actor_id or DEFAULT_ACTOR_ID))
    _json_dump(payload)
    return 0


def _collect(args: argparse.Namespace) -> int:
    rc, payload = collect_request(
        str(args.task_id or ""),
        actor_id=str(args.actor_id or DEFAULT_ACTOR_ID),
        timeout_seconds=float(args.timeout_seconds),
        poll_interval_seconds=float(args.poll_interval_seconds),
    )
    _json_dump(payload)
    return rc


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
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            try:
                os.kill(pid, signal.SIGTERM)
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
