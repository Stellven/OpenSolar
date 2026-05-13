"""Solar Harness — Hands Runtime.

Disposable execution runtime adapters: mock, shell, pane, remote.
All adapters implement the HandRuntime protocol from runtime_interfaces.py.

Every execute() takes an idempotency_key — repeating the same key
will not duplicate side effects.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

HARNESS_DIR = os.path.expanduser("~/.solar/harness")

# Import interfaces for type hints
sys.path.insert(0, os.path.dirname(__file__))
from runtime_interfaces import (
    CapabilityPolicy,
    CommandEnvelope,
    HandRef,
    HandType,
    ResultEnvelope,
    ResultStatus,
)
from activity_runtime import ActivityRuntime

# Shell deny-list: commands that must never be executed
_SHELL_DENYLIST = frozenset({
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=/dev/zero",
    "chmod -R 777 /", "shutdown", "reboot", "halt",
    ":(){ :|:& };:", "fork bomb",
})

_SHELL_DESTRUCTIVE_PATTERN = re.compile(
    r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\s*$|"
    r"chmod\s+(-R\s+)?[0-7]{3,4}\s+/\s*$|"
    r"mkfs|dd\s+if=|shutdown|reboot|halt",
    re.IGNORECASE,
)


def _activity_id(hand_ref: HandRef, command_name: str, idempotency_key: str) -> str:
    safe_key = re.sub(r"[^A-Za-z0-9_.:-]+", "-", idempotency_key)[-80:]
    safe_cmd = re.sub(r"[^A-Za-z0-9_.:-]+", "-", command_name)[:40]
    return f"{hand_ref.hand_id}:{safe_cmd}:{safe_key}"


def _record_activity_start(
    hand_ref: HandRef,
    command_name: str,
    input_data: Dict[str, Any],
    idempotency_key: str,
) -> Optional[tuple[ActivityRuntime, str]]:
    """Best-effort command_issued/activity_started event emission."""
    try:
        session_id = str(input_data.get("session_id") or input_data.get("_session_id") or f"hand-{hand_ref.hand_id}")
        sprint_id = str(input_data.get("sprint_id") or input_data.get("_sprint_id") or session_id)
        act_id = str(input_data.get("activity_id") or input_data.get("_activity_id") or _activity_id(hand_ref, command_name, idempotency_key))
        rt = ActivityRuntime(sprint_id=sprint_id, session_id=session_id)
        rt.command_issued(
            act_id,
            actor="hand-runtime",
            target=hand_ref.hand_type.value,
            payload={
                "command_name": command_name,
                "hand_id": hand_ref.hand_id,
                "hand_type": hand_ref.hand_type.value,
                "idempotency_key": idempotency_key,
            },
        )
        rt.activity_started(
            act_id,
            actor=f"hand:{hand_ref.hand_type.value}",
            payload={"hand_id": hand_ref.hand_id, "command_name": command_name},
        )
        return rt, act_id
    except Exception:
        return None


def _record_activity_terminal(
    ctx: Optional[tuple[ActivityRuntime, str]],
    result: ResultEnvelope,
) -> ResultEnvelope:
    if ctx is None:
        return result
    rt, act_id = ctx
    try:
        payload = {
            "status": result.status.value if hasattr(result.status, "value") else str(result.status),
            "side_effects": result.side_effects,
            "metadata": result.metadata,
        }
        if result.status == ResultStatus.OK:
            rt.activity_succeeded(act_id, actor="hand-runtime", payload=payload)
        elif result.status == ResultStatus.CANCELLED:
            rt.activity_cancelled(act_id, actor="hand-runtime", reason=result.error or "cancelled", payload=payload)
        elif result.status != ResultStatus.DUPLICATE_SUPPRESSED:
            rt.activity_failed(act_id, actor="hand-runtime", error=result.error or payload["status"], payload=payload)
    except Exception:
        pass
    return result


class MockHand:
    """In-memory mock hand for testing. No real side effects."""

    def __init__(self, policy: Optional[CapabilityPolicy] = None) -> None:
        self._seen_keys: set[str] = set()
        self._provisioned: List[HandRef] = []
        self._disposed: List[str] = []
        self.policy = policy or CapabilityPolicy()

    def provision(
        self,
        *,
        capabilities: Optional[List[str]] = None,
        location: Optional[str] = None,
    ) -> HandRef:
        from uuid import uuid4
        ref = HandRef(
            hand_id=f"mock-{uuid4().hex[:8]}",
            hand_type=HandType.MOCK,
            provisioned_at=_now_ts(),
            capabilities=capabilities or [],
            location=location or "memory",
        )
        self._provisioned.append(ref)
        return ref

    def execute(
        self,
        hand_ref: HandRef,
        command_name: str,
        input_data: Dict[str, Any],
        *,
        idempotency_key: str,
        timeout_seconds: Optional[int] = None,
    ) -> ResultEnvelope:
        if idempotency_key in self._seen_keys:
            return ResultEnvelope(
                status=ResultStatus.DUPLICATE_SUPPRESSED,
                output={"message": "duplicate suppressed"},
                metadata={"hand_id": hand_ref.hand_id},
            )
        self._seen_keys.add(idempotency_key)
        activity_ctx = _record_activity_start(hand_ref, command_name, input_data, idempotency_key)
        return _record_activity_terminal(activity_ctx, ResultEnvelope(
            status=ResultStatus.OK,
            output={"command": command_name, "input": input_data, "mock": True},
            side_effects=[f"mock:{command_name}"],
            metadata={"hand_id": hand_ref.hand_id},
        ))

    def dispose(self, hand_ref: HandRef, *, reason: str = "completed") -> ResultEnvelope:
        self._disposed.append(hand_ref.hand_id)
        return ResultEnvelope(
            status=ResultStatus.OK,
            output={"disposed": hand_ref.hand_id, "reason": reason},
            metadata={"hand_id": hand_ref.hand_id},
        )


class ShellHand:
    """Local subprocess hand. Executes safe commands only."""

    def __init__(self, policy: Optional[CapabilityPolicy] = None) -> None:
        self._seen_keys: set[str] = set()
        self._provisioned: List[HandRef] = []
        self._disposed: List[str] = []
        self.policy = policy or CapabilityPolicy()

    def provision(
        self,
        *,
        capabilities: Optional[List[str]] = None,
        location: Optional[str] = None,
    ) -> HandRef:
        from uuid import uuid4
        ref = HandRef(
            hand_id=f"shell-{uuid4().hex[:8]}",
            hand_type=HandType.SHELL,
            provisioned_at=_now_ts(),
            capabilities=capabilities or [],
            location=location or "local",
        )
        self._provisioned.append(ref)
        return ref

    def execute(
        self,
        hand_ref: HandRef,
        command_name: str,
        input_data: Dict[str, Any],
        *,
        idempotency_key: str,
        timeout_seconds: Optional[int] = None,
    ) -> ResultEnvelope:
        if idempotency_key in self._seen_keys:
            return ResultEnvelope(
                status=ResultStatus.DUPLICATE_SUPPRESSED,
                output={"message": "duplicate suppressed"},
                metadata={"hand_id": hand_ref.hand_id},
            )
        self._seen_keys.add(idempotency_key)
        activity_ctx = _record_activity_start(hand_ref, command_name, input_data, idempotency_key)

        cmd = input_data.get("command", "")
        if self._is_denied(cmd):
            return _record_activity_terminal(activity_ctx, ResultEnvelope(
                status=ResultStatus.ERROR,
                error=f"command denied by policy: {cmd[:80]}",
                metadata={"hand_id": hand_ref.hand_id},
            ))

        timeout = timeout_seconds or self.policy.max_duration_seconds
        try:
            t0 = time.monotonic()
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=min(timeout, 60),
            )
            elapsed_ms = (time.monotonic() - t0) * 1000
            if result.returncode != 0:
                return _record_activity_terminal(activity_ctx, ResultEnvelope(
                    status=ResultStatus.ERROR,
                    error=result.stderr.strip() or f"exit code {result.returncode}",
                    duration_ms=round(elapsed_ms, 1),
                    side_effects=[f"shell:{command_name}"],
                    metadata={"hand_id": hand_ref.hand_id},
                ))
            output = result.stdout.strip()
            redacted = self._redact_secrets(output)
            return _record_activity_terminal(activity_ctx, ResultEnvelope(
                status=ResultStatus.OK,
                output=redacted,
                duration_ms=round(elapsed_ms, 1),
                side_effects=[f"shell:{command_name}"],
                redacted_secrets=self._find_secrets(output),
                metadata={"hand_id": hand_ref.hand_id},
            ))
        except subprocess.TimeoutExpired:
            return _record_activity_terminal(activity_ctx, ResultEnvelope(
                status=ResultStatus.TIMEOUT,
                error=f"command timed out after {timeout}s",
                side_effects=[f"shell:{command_name}"],
                metadata={"hand_id": hand_ref.hand_id},
            ))

    def dispose(self, hand_ref: HandRef, *, reason: str = "completed") -> ResultEnvelope:
        self._disposed.append(hand_ref.hand_id)
        return ResultEnvelope(
            status=ResultStatus.OK,
            output={"disposed": hand_ref.hand_id, "reason": reason},
            metadata={"hand_id": hand_ref.hand_id},
        )

    def _is_denied(self, cmd: str) -> bool:
        for denied in self.policy.denied_commands:
            if denied in cmd:
                return True
        if _SHELL_DESTRUCTIVE_PATTERN.search(cmd):
            return True
        return False

    def _redact_secrets(self, text: str) -> str:
        redacted = text
        for pattern in self.policy.secret_patterns:
            redacted = re.sub(pattern, "[REDACTED]", redacted, flags=re.IGNORECASE)
        return redacted

    def _find_secrets(self, text: str) -> List[str]:
        found = []
        for pattern in self.policy.secret_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found.extend(matches)
        return list(set(found))


class PaneHand:
    """Tmux pane hand. Dispatches via tmux send-keys."""

    def __init__(self, policy: Optional[CapabilityPolicy] = None) -> None:
        self._seen_keys: set[str] = set()
        self._provisioned: List[HandRef] = []
        self._disposed: List[str] = []
        self.policy = policy or CapabilityPolicy()

    def provision(
        self,
        *,
        capabilities: Optional[List[str]] = None,
        location: Optional[str] = None,
    ) -> HandRef:
        from uuid import uuid4
        pane_id = location or "0"
        ref = HandRef(
            hand_id=f"pane-{pane_id}-{uuid4().hex[:8]}",
            hand_type=HandType.PANE,
            provisioned_at=_now_ts(),
            capabilities=capabilities or [],
            location=pane_id,
        )
        self._provisioned.append(ref)
        return ref

    def execute(
        self,
        hand_ref: HandRef,
        command_name: str,
        input_data: Dict[str, Any],
        *,
        idempotency_key: str,
        timeout_seconds: Optional[int] = None,
    ) -> ResultEnvelope:
        if idempotency_key in self._seen_keys:
            return ResultEnvelope(
                status=ResultStatus.DUPLICATE_SUPPRESSED,
                output={"message": "duplicate suppressed"},
                metadata={"hand_id": hand_ref.hand_id},
            )
        self._seen_keys.add(idempotency_key)
        activity_ctx = _record_activity_start(hand_ref, command_name, input_data, idempotency_key)

        pane = hand_ref.location or "0"
        cmd_text = input_data.get("command", input_data.get("text", ""))

        try:
            import subprocess
            # Write command to pane
            subprocess.run(
                ["tmux", "send-keys", "-t", f"solar:{pane}", cmd_text, "Enter"],
                capture_output=True, text=True, timeout=10,
            )
            return _record_activity_terminal(activity_ctx, ResultEnvelope(
                status=ResultStatus.OK,
                output={"pane": pane, "command_sent": cmd_text[:200]},
                side_effects=[f"pane:{pane}:{command_name}"],
                metadata={"hand_id": hand_ref.hand_id},
            ))
        except Exception as exc:
            return _record_activity_terminal(activity_ctx, ResultEnvelope(
                status=ResultStatus.ERROR,
                error=f"pane dispatch failed: {exc}",
                metadata={"hand_id": hand_ref.hand_id},
            ))

    def dispose(self, hand_ref: HandRef, *, reason: str = "completed") -> ResultEnvelope:
        self._disposed.append(hand_ref.hand_id)
        return ResultEnvelope(
            status=ResultStatus.OK,
            output={"disposed": hand_ref.hand_id, "reason": reason},
            metadata={"hand_id": hand_ref.hand_id},
        )


class RemoteHand:
    """Remote Mac mini hand. Executes via SSH manifest."""

    def __init__(self, policy: Optional[CapabilityPolicy] = None) -> None:
        self._seen_keys: set[str] = set()
        self._provisioned: List[HandRef] = []
        self._disposed: List[str] = []
        self.policy = policy or CapabilityPolicy()
        self._remote_host = os.environ.get("SOLAR_REMOTE_HOST", "mac-mini")

    def provision(
        self,
        *,
        capabilities: Optional[List[str]] = None,
        location: Optional[str] = None,
    ) -> HandRef:
        from uuid import uuid4
        ref = HandRef(
            hand_id=f"remote-{uuid4().hex[:8]}",
            hand_type=HandType.REMOTE,
            provisioned_at=_now_ts(),
            capabilities=capabilities or [],
            location=location or self._remote_host,
        )
        self._provisioned.append(ref)
        return ref

    def execute(
        self,
        hand_ref: HandRef,
        command_name: str,
        input_data: Dict[str, Any],
        *,
        idempotency_key: str,
        timeout_seconds: Optional[int] = None,
    ) -> ResultEnvelope:
        if idempotency_key in self._seen_keys:
            return ResultEnvelope(
                status=ResultStatus.DUPLICATE_SUPPRESSED,
                output={"message": "duplicate suppressed"},
                metadata={"hand_id": hand_ref.hand_id},
            )
        self._seen_keys.add(idempotency_key)
        activity_ctx = _record_activity_start(hand_ref, command_name, input_data, idempotency_key)

        host = hand_ref.location or self._remote_host
        cmd = input_data.get("command", "")

        # Remote hand validates manifest/checksum if provided
        manifest = input_data.get("manifest")
        if manifest and not manifest.get("checksum"):
            return _record_activity_terminal(activity_ctx, ResultEnvelope(
                status=ResultStatus.ERROR,
                error="remote hand requires manifest checksum",
                metadata={"hand_id": hand_ref.hand_id, "host": host},
            ))

        try:
            timeout = timeout_seconds or self.policy.max_duration_seconds
            result = subprocess.run(
                ["ssh", host, cmd], capture_output=True, text=True,
                timeout=min(timeout, 120),
            )
            if result.returncode != 0:
                return _record_activity_terminal(activity_ctx, ResultEnvelope(
                    status=ResultStatus.ERROR,
                    error=result.stderr.strip() or f"remote exit {result.returncode}",
                    metadata={"hand_id": hand_ref.hand_id, "host": host},
                ))
            return _record_activity_terminal(activity_ctx, ResultEnvelope(
                status=ResultStatus.OK,
                output=result.stdout.strip(),
                side_effects=[f"remote:{host}:{command_name}"],
                metadata={"hand_id": hand_ref.hand_id, "host": host},
            ))
        except subprocess.TimeoutExpired:
            return _record_activity_terminal(activity_ctx, ResultEnvelope(
                status=ResultStatus.TIMEOUT,
                error=f"remote command timed out after {timeout}s",
                metadata={"hand_id": hand_ref.hand_id, "host": host},
            ))
        except FileNotFoundError:
            return _record_activity_terminal(activity_ctx, ResultEnvelope(
                status=ResultStatus.ERROR,
                error=f"ssh not found or host {host} unreachable",
                metadata={"hand_id": hand_ref.hand_id, "host": host},
            ))

    def dispose(self, hand_ref: HandRef, *, reason: str = "completed") -> ResultEnvelope:
        self._disposed.append(hand_ref.hand_id)
        return ResultEnvelope(
            status=ResultStatus.OK,
            output={"disposed": hand_ref.hand_id, "reason": reason},
            metadata={"hand_id": hand_ref.hand_id},
        )


# ------------------------------------------------------------------
# Hand registry
# ------------------------------------------------------------------

_HAND_REGISTRY: Dict[HandType, type] = {
    HandType.MOCK: MockHand,
    HandType.SHELL: ShellHand,
    HandType.PANE: PaneHand,
    HandType.REMOTE: RemoteHand,
}


def get_hand(hand_type: HandType, policy: Optional[CapabilityPolicy] = None):
    """Factory for hand instances."""
    cls = _HAND_REGISTRY.get(hand_type)
    if cls is None:
        raise ValueError(f"Unknown hand type: {hand_type}")
    return cls(policy=policy)


def available_hand_types() -> List[HandType]:
    return list(_HAND_REGISTRY.keys())


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
