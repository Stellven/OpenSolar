#!/usr/bin/env python3
"""Shared flow-control helpers for operator-backed and direct model calls."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
TASK_CONTROL_FILENAME = "operator-task-control.json"
BLOCKING_STATES = {"cooldown", "quota_exhausted", "auth_expired"}
RATE_LIMIT_RE = re.compile(
    r"RESOURCE_EXHAUSTED|quota(?: exhausted)?|monthly usage limit|"
    r"rate[- ]?limit|429|too many requests|resets?\s+in|"
    r"Upgrade your plan|You've hit .*limit|capacity",
    re.I,
)
AUTH_RE = re.compile(
    r"not logged in|auth(?:entication)? failed|oauth|permission denied|"
    r"sign in|login wall|login required|logged out",
    re.I,
)


class FlowControlBlocked(RuntimeError):
    """Raised when a call is attempted during cooldown/auth-expired windows."""

    def __init__(self, operator_id: str, runtime_state: str, *, expires_at: str = "") -> None:
        self.operator_id = operator_id
        self.runtime_state = runtime_state
        self.expires_at = expires_at
        detail = f"operator {operator_id} blocked by flow control: state={runtime_state}"
        if expires_at:
            detail += f" until {expires_at}"
        super().__init__(detail)


def _operator_runtime_module():
    if str(HARNESS_DIR / "lib") not in sys.path:
        sys.path.insert(0, str(HARNESS_DIR / "lib"))
    import operator_runtime  # type: ignore

    return operator_runtime


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso_z(moment: dt.datetime | None = None) -> str:
    return (moment or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return dt.datetime.fromisoformat(raw).astimezone(dt.timezone.utc)
    except Exception:
        return None


def bool_value(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def int_value(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def classify_failure_state(text: str) -> str:
    if AUTH_RE.search(text or ""):
        return "auth_expired"
    if RATE_LIMIT_RE.search(text or ""):
        return "cooldown"
    return ""


def current_block_state(
    operator_id: str,
    *,
    allow_unregistered: bool = False,
    blocking_states: set[str] | None = None,
) -> dict[str, Any] | None:
    states = set(blocking_states or BLOCKING_STATES)
    runtime = _operator_runtime_module()
    status = runtime.get_operator_status(operator_id) or {}
    runtime_state = str(status.get("runtime_state") or "").strip()
    if runtime_state in states:
        return {
            "operator_id": operator_id,
            "runtime_state": runtime_state,
            "expires_at": str(status.get("expires_at") or "").strip(),
        }
    config = runtime.get_operator_config(operator_id)
    if config is None and allow_unregistered:
        return None
    if config is None:
        return None
    runtime_state = str(runtime.get_operator_runtime_state(operator_id) or "").strip()
    if runtime_state in states:
        return {
            "operator_id": operator_id,
            "runtime_state": runtime_state,
            "expires_at": str(status.get("expires_at") or "").strip(),
        }
    return None


def ensure_operator_available(
    operator_id: str,
    *,
    allow_unregistered: bool = False,
    blocking_states: set[str] | None = None,
) -> None:
    snapshot = current_block_state(
        operator_id,
        allow_unregistered=allow_unregistered,
        blocking_states=blocking_states,
    )
    if snapshot:
        raise FlowControlBlocked(
            operator_id,
            str(snapshot.get("runtime_state") or "cooldown"),
            expires_at=str(snapshot.get("expires_at") or ""),
        )


def set_operator_state(operator_id: str, runtime_state: str, *, ttl_seconds: int | None = None) -> dict[str, Any]:
    return _operator_runtime_module().set_operator_status(
        operator_id,
        runtime_state,
        ttl_seconds=ttl_seconds,
    )


def apply_success_cooldown(operator_id: str, *, success_cooldown_seconds: int) -> dict[str, Any] | None:
    if int(success_cooldown_seconds or 0) <= 0:
        return None
    return set_operator_state(operator_id, "cooldown", ttl_seconds=int(success_cooldown_seconds))


def task_control_path(task_dir: Path) -> Path:
    return Path(task_dir) / TASK_CONTROL_FILENAME


def clear_task_control(task_dir: Path) -> None:
    task_control_path(task_dir).unlink(missing_ok=True)


def write_task_control(
    task_dir: Path,
    *,
    operator_id: str,
    action: str,
    runtime_state: str,
    reason: str,
    delay_seconds: int = 0,
) -> dict[str, Any]:
    task_dir = Path(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    now = _now()
    payload: dict[str, Any] = {
        "operator_id": operator_id,
        "action": action,
        "runtime_state": runtime_state,
        "reason": reason,
        "written_at": _iso_z(now),
    }
    if delay_seconds > 0:
        next_attempt = now + dt.timedelta(seconds=int(delay_seconds))
        payload["delay_seconds"] = int(delay_seconds)
        payload["not_before"] = _iso_z(next_attempt)
    path = task_control_path(task_dir)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def read_task_control(task_dir: Path) -> dict[str, Any] | None:
    path = task_control_path(task_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def apply_failure_flow_control(
    task_dir: Path,
    *,
    operator_id: str,
    failure_text: str,
    rate_limit_cooldown_seconds: int,
    auth_cooldown_seconds: int,
    defer_on_cooldown: bool = False,
    defer_on_auth: bool = False,
) -> dict[str, Any]:
    runtime_state = classify_failure_state(failure_text)
    result = {"runtime_state": runtime_state, "task_control": None}
    if runtime_state == "cooldown":
        cooldown = int(rate_limit_cooldown_seconds or 0)
        if cooldown > 0:
            set_operator_state(operator_id, "cooldown", ttl_seconds=cooldown)
        if defer_on_cooldown and cooldown > 0:
            result["task_control"] = write_task_control(
                task_dir,
                operator_id=operator_id,
                action="defer",
                runtime_state="cooldown",
                reason="rate_limit",
                delay_seconds=cooldown,
            )
        return result
    if runtime_state == "auth_expired":
        cooldown = int(auth_cooldown_seconds or 0)
        set_operator_state(
            operator_id,
            "auth_expired",
            ttl_seconds=cooldown if cooldown > 0 else None,
        )
        if defer_on_auth and cooldown > 0:
            result["task_control"] = write_task_control(
                task_dir,
                operator_id=operator_id,
                action="defer",
                runtime_state="auth_expired",
                reason="auth_expired",
                delay_seconds=cooldown,
            )
        return result
    return result


def envelope_not_before_ready(envelope: dict[str, Any]) -> bool:
    not_before = _parse_time(envelope.get("not_before") or envelope.get("defer_until"))
    if not_before is None:
        return True
    return not_before <= _now()
