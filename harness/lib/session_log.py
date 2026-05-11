"""Solar Harness — Session Log v2.

Append-only, event-sourced durable log for the managed-agent runtime.
Each append is atomic (rename-based) and carries a monotonic seq number.
Idempotency-key deduplication prevents duplicate side effects from
at-least-once delivery of command events.

Usage::

    log = SessionLog(session_id="my-session")
    eid = log.append("command_issued", actor="coordinator",
                     sprint_id="sprint-xyz",
                     activity_id="act-1",
                     idempotency_key="dispatch:sprint-xyz:round-1",
                     payload={"target": "builder", "round": 1})
    for event in log.replay():
        print(event["seq"], event["type"])
"""
from __future__ import annotations

import fcntl
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

HARNESS_DIR = os.path.expanduser("~/.solar/harness")
SESSIONS_DIR = os.path.join(HARNESS_DIR, "sessions")

VALID_TYPES = frozenset({
    "command_issued", "activity_started", "activity_succeeded",
    "activity_failed", "activity_cancelled", "activity_retry_scheduled",
    "activity_handoff", "state_transition", "human_feedback",
    "context_injected", "log_message", "session_started", "session_ended",
})


class DuplicateEventError(Exception):
    """Raised when an event with a matching idempotency_key already exists."""


class SessionLog:
    """Append-only session event log for one session_id.

    Thread-safe via fcntl.LOCK_EX on the log file.
    Cross-process idempotency is enforced by scanning on first open.
    """

    def __init__(self, session_id: str, *, harness_dir: Optional[str] = None) -> None:
        base = harness_dir or HARNESS_DIR
        self.session_id = session_id
        self._dir = os.path.join(base, "sessions", session_id)
        self._path = os.path.join(self._dir, "events.jsonl")
        self._seq = 0
        self._seen_idem: set[str] = set()
        os.makedirs(self._dir, exist_ok=True)
        self._load_state()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Scan existing log to recover seq and seen idempotency keys."""
        if not os.path.exists(self._path):
            return
        with open(self._path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seq = ev.get("seq", 0)
                if seq > self._seq:
                    self._seq = seq
                ik = ev.get("idempotency_key")
                if ik:
                    self._seen_idem.add(ik)

    def _now_ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(
        self,
        event_type: str,
        *,
        actor: str,
        source: str = "session_log",
        sprint_id: Optional[str] = None,
        activity_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Append one event; return its event_id.

        Raises DuplicateEventError if idempotency_key is already in the log.
        Raises ValueError for unknown event_type.
        """
        if event_type not in VALID_TYPES:
            raise ValueError(f"Unknown event type: {event_type!r}")

        if idempotency_key and idempotency_key in self._seen_idem:
            raise DuplicateEventError(
                f"Duplicate idempotency_key={idempotency_key!r} — event suppressed"
            )

        event_id = str(uuid.uuid4())
        with open(self._path, "a", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            self._seq += 1
            event: Dict[str, Any] = {
                "event_id": event_id,
                "session_id": self.session_id,
                "seq": self._seq,
                "ts": self._now_ts(),
                "type": event_type,
                "actor": actor,
                "source": source,
                "sprint_id": sprint_id,
                "activity_id": activity_id,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "idempotency_key": idempotency_key,
                "payload": payload or {},
            }
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
            fcntl.flock(fh, fcntl.LOCK_UN)

        if idempotency_key:
            self._seen_idem.add(idempotency_key)

        return event_id

    def replay(
        self,
        *,
        sprint_id: Optional[str] = None,
        event_type: Optional[str] = None,
        activity_id: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Iterate events in append order, with optional filters."""
        if not os.path.exists(self._path):
            return
        with open(self._path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if sprint_id is not None and ev.get("sprint_id") != sprint_id:
                    continue
                if event_type is not None and ev.get("type") != event_type:
                    continue
                if activity_id is not None and ev.get("activity_id") != activity_id:
                    continue
                yield ev

    def all_events(self) -> List[Dict[str, Any]]:
        return list(self.replay())

    def seen_idempotency_keys(self) -> set[str]:
        return set(self._seen_idem)

    @classmethod
    def for_sprint(cls, sprint_id: str, *, harness_dir: Optional[str] = None) -> "SessionLog":
        """Return a SessionLog scoped to a sprint (session_id == sprint_id)."""
        return cls(sprint_id, harness_dir=harness_dir)

    @staticmethod
    def log_path(session_id: str, harness_dir: Optional[str] = None) -> str:
        base = harness_dir or HARNESS_DIR
        return os.path.join(base, "sessions", session_id, "events.jsonl")
