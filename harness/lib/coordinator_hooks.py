"""Coordinator pre-dispatch hook for Solar Experience Memory.

pre_dispatch(sid, action) → Decision
- Timeout: 50ms fail-open
- Audit log: experience/decisions.jsonl
- Disable: EXPERIENCE_HOOK=0
"""
import json
import logging
import os
import signal
import sys
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

HARNESS_DIR = os.path.expanduser("~/.solar/harness")
DECISIONS_LOG = os.path.join(HARNESS_DIR, "experience", "decisions.jsonl")
TIMEOUT_MS = 50

TERMINAL_STATUSES = {"passed", "failed", "cancelled", "quarantined"}
TERMINAL_PHASES = {"passed", "finalized", "cancelled", "quarantined"}


class Decision:
    def __init__(self, action: str, reason: str, advisory: str = "",
                 pattern: str = "", confidence: float = 0.0):
        self.action = action      # "allow" | "abort" | "advisory"
        self.reason = reason
        self.advisory = advisory
        self.pattern = pattern
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "advisory": self.advisory[:2000],
            "pattern": self.pattern,
            "confidence": self.confidence,
        }

    def __repr__(self) -> str:
        return f"Decision(action={self.action}, pattern={self.pattern}, confidence={self.confidence})"


def _load_sprint_status(sid: str) -> Dict[str, Any]:
    path = os.path.join(HARNESS_DIR, "sprints", f"{sid}.status.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _append_decision(sid: str, action_name: str, decision: Decision) -> None:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sid": sid,
        "action_requested": action_name,
        "decision": decision.to_dict(),
    }
    os.makedirs(os.path.dirname(DECISIONS_LOG), exist_ok=True)
    try:
        with open(DECISIONS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning("decisions.jsonl write failed: %s", e)


def _check_terminal_phase_wake(sid: str, status_data: Dict[str, Any]) -> Decision:
    """Detect and abort dispatches to terminal sprints."""
    status = status_data.get("status", "")
    phase = status_data.get("phase", "")
    if status in TERMINAL_STATUSES or phase in TERMINAL_PHASES:
        return Decision(
            action="abort",
            reason="terminal_phase_wake_detected",
            advisory=(
                f"Sprint {sid} is terminal (status={status}, phase={phase}). "
                "Aborting dispatch to prevent terminal_phase_wake anti-pattern. "
                "If this is incorrect, set EXPERIENCE_HOOK=0 to bypass."
            ),
            pattern="terminal_phase_wake",
            confidence=0.95,
        )
    return Decision(action="allow", reason="not_terminal")


def _check_patterns(sid: str) -> Decision:
    """Check experience memory for known failure patterns."""
    try:
        sys.path.insert(0, os.path.join(HARNESS_DIR, "lib"))
        from experience.query import query_for_sprint

        result = query_for_sprint(sid, limit=5)
        memories = result.get("memories", [])

        high_conf_aborts = [
            m for m in memories
            if m.get("pattern_class") in ("terminal_phase_wake",)
            and m.get("outcome") == "failure"
        ]
        if high_conf_aborts:
            m = high_conf_aborts[0]
            return Decision(
                action="abort",
                reason="experience_memory_abort",
                advisory=m.get("advisory", "")[:2000],
                pattern=m.get("pattern_class", ""),
                confidence=0.85,
            )

        advisory_patterns = [
            m for m in memories
            if m.get("pattern_class") in ("c_u_storm", "mis_dispatch", "queue_block",
                                           "status_corruption")
            and m.get("outcome") == "failure"
        ]
        if advisory_patterns:
            m = advisory_patterns[0]
            parts = [m.get("advisory", "") for m in advisory_patterns if m.get("advisory")]
            combined = " | ".join(parts[:3])[:2000]
            return Decision(
                action="advisory",
                reason="experience_memory_advisory",
                advisory=combined,
                pattern=m.get("pattern_class", ""),
                confidence=0.7,
            )
    except Exception as e:
        logger.debug("pattern check failed (fail-open): %s", e)

    return Decision(action="allow", reason="no_matching_patterns")


class _TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _TimeoutError()


def pre_dispatch(sid: str, action: str) -> Decision:
    """Main pre-dispatch hook. Called before coordinator dispatches a sprint.

    Returns a Decision. Always fail-open on error or timeout.
    Set EXPERIENCE_HOOK=0 to bypass entirely.
    """
    if os.environ.get("EXPERIENCE_HOOK", "1") == "0":
        return Decision(action="allow", reason="hook_disabled")

    start = time.time()
    decision = Decision(action="allow", reason="fail_open")

    try:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, TIMEOUT_MS / 1000.0)
        try:
            status_data = _load_sprint_status(sid)
            terminal_decision = _check_terminal_phase_wake(sid, status_data)
            if terminal_decision.action == "abort":
                decision = terminal_decision
            else:
                decision = _check_patterns(sid)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
    except _TimeoutError:
        elapsed_ms = (time.time() - start) * 1000
        logger.warning("pre_dispatch timeout after %.1fms, fail-open", elapsed_ms)
        decision = Decision(action="allow", reason="timeout_fail_open")
    except Exception as e:
        logger.warning("pre_dispatch error (fail-open): %s", e)
        decision = Decision(action="allow", reason=f"error_fail_open: {e}")

    _append_decision(sid, action, decision)
    return decision


def pre_dispatch_json(sid: str, action: str) -> str:
    """JSON-serializable wrapper for shell integration."""
    d = pre_dispatch(sid, action)
    return json.dumps(d.to_dict())
