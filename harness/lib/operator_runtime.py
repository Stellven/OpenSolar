#!/usr/bin/env python3
"""operator_runtime.py — S6 Control Plane: Operator runtime lease and state helper.

Classifies runtime state of physical operators and manages atomic process-safe leases.
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from operator_persona import resolve_persona

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
OPERATOR_LEASE_DIR = HARNESS_DIR / "run" / "operator-leases"
OPERATOR_STATUS_DIR = HARNESS_DIR / "run" / "operator-status"
OPERATOR_INBOX_DIR = HARNESS_DIR / "run" / "operator-inbox"
OPERATOR_RESULTS_DIR = HARNESS_DIR / "run" / "operator-results"
OPERATOR_PERSONAS_DIR = HARNESS_DIR / "personas"
PHYSICAL_OPERATORS_PATH = Path(os.environ.get("SOLAR_MULTI_TASK_OPERATORS", HARNESS_DIR / "config" / "physical-operators.json"))

# Valid runtime states
VALID_STATES = {
    "idle",
    "leased",
    "running",
    "draining",
    "cooldown",
    "quota_exhausted",
    "auth_expired",
    "disabled"
}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dirs() -> None:
    OPERATOR_LEASE_DIR.mkdir(parents=True, exist_ok=True)
    OPERATOR_STATUS_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_inbox_dir(operator_id: str) -> Path:
    inbox = OPERATOR_INBOX_DIR / operator_id
    inbox.mkdir(parents=True, exist_ok=True)
    return inbox


# ── Registry Access ───────────────────────────────────────────────────────────

def load_registry() -> Dict[str, Any]:
    """Loads the physical operators registry from config."""
    if not PHYSICAL_OPERATORS_PATH.exists():
        return {"version": 1, "operators": {}}
    try:
        return json.loads(PHYSICAL_OPERATORS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "operators": {}}


def get_operator_config(operator_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves config for a specific operator from the registry."""
    registry = load_registry()
    operators = registry.get("operators", {})
    if operator_id in operators:
        return dict(operators[operator_id])
    return None


# ── Dynamic Status/Override Management ────────────────────────────────────────

def get_operator_status(operator_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves the dynamic status override for an operator, if set and not expired."""
    path = OPERATOR_STATUS_DIR / f"{operator_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "expires_at" in data:
            if _now() > data["expires_at"]:
                return None
        return data
    except Exception:
        return None


def set_operator_status(
    operator_id: str,
    runtime_state: str,
    ttl_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """Sets a dynamic status override (e.g. cooldown, quota_exhausted, auth_expired)."""
    if runtime_state not in VALID_STATES:
        raise ValueError(f"Invalid runtime state: {runtime_state}. Must be one of {VALID_STATES}")
    
    _ensure_dirs()
    path = OPERATOR_STATUS_DIR / f"{operator_id}.json"
    lock_path = OPERATOR_STATUS_DIR / f"{operator_id}.lock"
    
    data = {
        "operator_id": operator_id,
        "runtime_state": runtime_state,
        "updated_at": _now()
    }
    if ttl_seconds is not None:
        expires_at = (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=ttl_seconds)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        data["expires_at"] = expires_at
        
    with open(lock_path, "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            tmp = str(path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, str(path))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
            
    return data


def clear_operator_status(operator_id: str) -> None:
    """Clears the dynamic status override for an operator."""
    path = OPERATOR_STATUS_DIR / f"{operator_id}.json"
    lock_path = OPERATOR_STATUS_DIR / f"{operator_id}.lock"
    
    with open(lock_path, "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if path.exists():
                path.unlink()
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# ── Lease Management ──────────────────────────────────────────────────────────

def get_operator_lease(operator_id: str) -> Optional[Dict[str, Any]]:
    """Gets the active, non-expired lease for an operator if exists."""
    path = OPERATOR_LEASE_DIR / f"{operator_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("expires_at", "") <= _now():
            return None
        return data
    except Exception:
        return None


def acquire_operator_lease(
    operator_id: str,
    task_id: str,
    sprint_id: str,
    node_id: str,
    ttl_seconds: int,
    initial_state: str = "leased"
) -> Dict[str, Any]:
    """Acquires an active lease for the operator. Prevents duplicates."""
    if initial_state not in VALID_STATES:
        raise ValueError(f"Invalid initial lease state: {initial_state}. Must be one of {VALID_STATES}")

    # Verify operator exists and is enabled in registry
    config = get_operator_config(operator_id)
    if not config:
        raise ValueError(f"Operator '{operator_id}' not found in registry")
        
    if not config.get("enabled", True):
        raise RuntimeError(f"Cannot lease disabled operator '{operator_id}'")

    _ensure_dirs()
    path = OPERATOR_LEASE_DIR / f"{operator_id}.json"
    lock_path = OPERATOR_LEASE_DIR / f"{operator_id}.lock"
    
    with open(lock_path, "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            # Check for existing active lease
            if path.exists():
                existing = None
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    pass  # Overwrite corrupt lease files
                if existing and existing.get("expires_at", "") > _now():
                    raise RuntimeError(f"Duplicate active lease rejected: operator '{operator_id}' is already leased")
            
            # Create new lease
            now_str = _now()
            expires_at = (
                datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=ttl_seconds)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            lease = {
                "operator_id": operator_id,
                "task_id": task_id,
                "sprint_id": sprint_id,
                "node_id": node_id,
                "leased_at": now_str,
                "expires_at": expires_at,
                "state": initial_state
            }
            
            tmp = str(path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(lease, f, indent=2)
            os.replace(tmp, str(path))
            return lease
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def update_operator_lease_state(operator_id: str, state: str) -> Dict[str, Any]:
    """Updates the state of an active lease (e.g. from 'leased' to 'running')."""
    if state not in VALID_STATES:
        raise ValueError(f"Invalid lease state: {state}. Must be one of {VALID_STATES}")

    _ensure_dirs()
    path = OPERATOR_LEASE_DIR / f"{operator_id}.json"
    lock_path = OPERATOR_LEASE_DIR / f"{operator_id}.lock"
    
    with open(lock_path, "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if not path.exists():
                raise RuntimeError(f"No active lease exists for operator '{operator_id}'")
            
            lease = json.loads(path.read_text(encoding="utf-8"))
            if lease.get("expires_at", "") <= _now():
                raise RuntimeError(f"Lease for operator '{operator_id}' has expired")
                
            lease["state"] = state
            
            tmp = str(path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(lease, f, indent=2)
            os.replace(tmp, str(path))
            return lease
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def release_operator_lease(operator_id: str, reason: str = "completed") -> bool:
    """Releases the active lease for the operator."""
    _ensure_dirs()
    path = OPERATOR_LEASE_DIR / f"{operator_id}.json"
    lock_path = OPERATOR_LEASE_DIR / f"{operator_id}.lock"
    
    with open(lock_path, "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if not path.exists():
                return False
            path.unlink()
            return True
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# ── State Classification ──────────────────────────────────────────────────────

def get_operator_runtime_state(operator_id: str) -> str:
    """Classifies the current runtime state of the operator."""
    config = get_operator_config(operator_id)
    if not config:
        return "disabled"
        
    # Standard check: check registry level enabled/disabled status
    if not config.get("enabled", True):
        return "disabled"
        
    # Check if registry state properties specify disabled
    reg_state = config.get("state", {})
    if isinstance(reg_state, dict):
        if reg_state.get("availability") == "disabled" or reg_state.get("runtime_state") == "disabled":
            return "disabled"
            
    # Check active lease (highest precedence for active state)
    lease = get_operator_lease(operator_id)
    if lease:
        state = lease.get("state")
        if state in VALID_STATES:
            return state
        return "leased"
        
    # Check dynamic status override
    status = get_operator_status(operator_id)
    if status:
        r_state = status.get("runtime_state")
        if r_state in VALID_STATES:
            return r_state
            
    # Check registry baseline runtime_state
    if isinstance(reg_state, dict):
        baseline = reg_state.get("runtime_state")
        if baseline in VALID_STATES:
            return baseline
            
    return "idle"


# ── Submit ───────────────────────────────────────────────────────────────────

# States that prevent task submission
_NON_DISPATCHABLE_STATES = {"disabled", "leased", "running", "quota_exhausted", "auth_expired"}

# Required keys in a task envelope
_REQUIRED_ENVELOPE_KEYS = {"task_id", "sprint_id", "node_id", "operator_id", "task_type", "objective"}

_DEFAULT_LEASE_TTL = 3600


def submit(task_envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Validates a task, checks operator dispatchability, acquires a lease,
    and writes the task envelope to the operator's inbox.

    Args:
        task_envelope: Must contain task_id, sprint_id, node_id, operator_id,
            task_type, and objective. Optional: lease_ttl_seconds.

    Returns:
        dict with task_id, operator_id, lease_id, inbox_path, status, submitted_at.

    Raises:
        ValueError: Malformed envelope or unknown operator.
        RuntimeError: Operator not dispatchable (disabled/leased/running/
            quota_exhausted/auth_expired) or missing persona binding.
    """
    # ── 1. Envelope validation ─────────────────────────────────────────────
    missing = _REQUIRED_ENVELOPE_KEYS - set(task_envelope.keys())
    if missing:
        raise ValueError(f"Task envelope missing required keys: {sorted(missing)}")

    operator_id = task_envelope["operator_id"]
    task_id = task_envelope["task_id"]
    sprint_id = task_envelope["sprint_id"]
    node_id = task_envelope["node_id"]
    ttl = int(task_envelope.get("lease_ttl_seconds", _DEFAULT_LEASE_TTL))

    # ── 2. Operator existence check ────────────────────────────────────────
    config = get_operator_config(operator_id)
    if config is None:
        raise ValueError(f"Unknown operator: '{operator_id}' not found in registry")

    # ── 3. Dispatchability check ───────────────────────────────────────────
    current_state = get_operator_runtime_state(operator_id)
    if current_state in _NON_DISPATCHABLE_STATES:
        raise RuntimeError(
            f"Operator '{operator_id}' is not dispatchable: state={current_state}"
        )

    # ── 4. Persona binding check ───────────────────────────────────────────
    resolve_persona(operator_id, config, OPERATOR_PERSONAS_DIR, load_content=False)

    # ── 5. Acquire lease ──────────────────────────────────────────────────
    lease = acquire_operator_lease(
        operator_id=operator_id,
        task_id=task_id,
        sprint_id=sprint_id,
        node_id=node_id,
        ttl_seconds=ttl,
        initial_state="leased",
    )

    # ── 6. Write envelope to inbox (atomic) ───────────────────────────────
    inbox_dir = _ensure_inbox_dir(operator_id)
    inbox_path = inbox_dir / f"{task_id}.json"
    tmp_path = str(inbox_path) + ".tmp"
    submitted_at = _now()
    payload = dict(task_envelope)
    payload["submitted_at"] = submitted_at
    payload["lease_expires_at"] = lease["expires_at"]

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp_path, str(inbox_path))

    lease_id = f"{operator_id}:{task_id}:{lease['leased_at']}"

    return {
        "task_id": task_id,
        "operator_id": operator_id,
        "lease_id": lease_id,
        "inbox_path": str(inbox_path),
        "status": "submitted",
        "submitted_at": submitted_at,
    }


# ── Secret Scrubbing ─────────────────────────────────────────────────────────

# Compiled once at module load for performance.
_SECRET_PATTERNS: list = [
    (re.compile(r'sk-[a-zA-Z0-9]{32,}'), '[SCRUBBED]'),
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), '[SCRUBBED]'),
    (re.compile(r'github_pat_[a-zA-Z0-9_]{82}'), '[SCRUBBED]'),
    (re.compile(r'AKIA[0-9A-Z]{16}'), '[SCRUBBED]'),
    (re.compile(r'Bearer [a-zA-Z0-9\-._~+/=]{20,}'), 'Bearer [SCRUBBED]'),
    (re.compile(r'(?i)(api[_-]?key|apikey|api_secret)\s*[=:]\s*[^\s"\']{8,}'), r'\1=[SCRUBBED]'),
    (re.compile(r'(?i)(password|passwd)\s*[=:]\s*[^\s"\']{4,}'), r'\1=[SCRUBBED]'),
    (re.compile(r'(?i)(token|secret)\s*[=:]\s*[^\s"\']{8,}'), r'\1=[SCRUBBED]'),
]


def scrub_secrets(text: str) -> str:
    """Replace known credential patterns with [SCRUBBED]."""
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ── Inbox Helpers ─────────────────────────────────────────────────────────────

def list_inbox_tasks(operator_id: str) -> List[tuple]:
    """Return pending task envelopes from the operator inbox.

    Returns a list of ``(task_id, envelope_dict, envelope_path)`` tuples
    sorted by file name (oldest first, assuming task_id timestamps sort
    lexicographically).
    """
    inbox = OPERATOR_INBOX_DIR / operator_id
    if not inbox.exists():
        return []
    results = []
    for p in sorted(inbox.glob("*.json")):
        try:
            envelope = json.loads(p.read_text(encoding="utf-8"))
            results.append((p.stem, envelope, p))
        except Exception:
            pass
    return results


# ── Heartbeat ─────────────────────────────────────────────────────────────────

def write_heartbeat(
    operator_id: str,
    state: str,
    *,
    current_task_id: Optional[str] = None,
    resolved_persona: Optional[str] = None,
) -> None:
    """Write a daemon heartbeat to the operator status file.

    Uses ``runtime_state`` as the primary key so that
    ``get_operator_runtime_state`` picks it up correctly, and also writes
    ``state`` for daemon-readable convenience.
    """
    _ensure_dirs()
    path = OPERATOR_STATUS_DIR / f"{operator_id}.json"
    lock_path = OPERATOR_STATUS_DIR / f"{operator_id}.lock"

    data: Dict[str, Any] = {
        "operator_id": operator_id,
        "runtime_state": state,
        "state": state,
        "heartbeat_at": _now(),
    }
    if current_task_id is not None:
        data["current_task_id"] = current_task_id
    if resolved_persona is not None:
        data["resolved_persona"] = resolved_persona

    with open(lock_path, "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            tmp = str(path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, str(path))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# ── Result Artifacts ──────────────────────────────────────────────────────────

def write_result(
    operator_id: str,
    task_id: str,
    sprint_id: str,
    node_id: str,
    status: str,
    exit_code: int,
    started_at: str,
    finished_at: str,
    log_tail: str,
) -> Path:
    """Write the result.json artifact for a completed task.

    ``log_tail`` is scrubbed for secrets before writing.  The artifact is
    written atomically via a .tmp rename.

    Returns the path to the written result.json.
    """
    result_dir = OPERATOR_RESULTS_DIR / operator_id / task_id
    result_dir.mkdir(parents=True, exist_ok=True)

    result: Dict[str, Any] = {
        "task_id": task_id,
        "operator_id": operator_id,
        "sprint_id": sprint_id,
        "node_id": node_id,
        "status": status,
        "exit_code": exit_code,
        "started_at": started_at,
        "finished_at": finished_at,
        "log_tail": scrub_secrets(log_tail),
    }

    result_path = result_dir / "result.json"
    tmp_path = str(result_path) + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    os.replace(tmp_path, str(result_path))
    return result_path


# ── CLI Interface ─────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Solar Operator Runtime State & Lease Helper")
    subparsers = parser.add_subparsers(dest="cmd", help="Sub-commands")
    
    # status
    status_parser = subparsers.add_parser("status", help="Get operator runtime state")
    status_parser.add_argument("--operator", required=True, help="Operator ID")
    
    # acquire
    acq_parser = subparsers.add_parser("acquire", help="Acquire operator lease")
    acq_parser.add_argument("--operator", required=True, help="Operator ID")
    acq_parser.add_argument("--task-id", required=True, help="Task ID")
    acq_parser.add_argument("--sprint-id", required=True, help="Sprint ID")
    acq_parser.add_argument("--node-id", required=True, help="Node ID")
    acq_parser.add_argument("--ttl", type=int, required=True, help="TTL in seconds")
    acq_parser.add_argument("--state", default="leased", help="Initial lease state")
    
    # update-state
    update_parser = subparsers.add_parser("update-state", help="Update lease state")
    update_parser.add_argument("--operator", required=True, help="Operator ID")
    update_parser.add_argument("--state", required=True, help="New lease state")
    
    # release
    rel_parser = subparsers.add_parser("release", help="Release operator lease")
    rel_parser.add_argument("--operator", required=True, help="Operator ID")
    rel_parser.add_argument("--reason", default="completed", help="Release reason")
    
    # set-override
    override_parser = subparsers.add_parser("set-override", help="Set dynamic status override")
    override_parser.add_argument("--operator", required=True, help="Operator ID")
    override_parser.add_argument("--state", required=True, help="Override state")
    override_parser.add_argument("--ttl", type=int, help="Optional TTL in seconds")
    
    # clear-override
    clear_parser = subparsers.add_parser("clear-override", help="Clear dynamic status override")
    clear_parser.add_argument("--operator", required=True, help="Operator ID")

    # submit
    submit_parser = subparsers.add_parser("submit", help="Submit a task envelope to an operator inbox")
    submit_parser.add_argument("--envelope", required=True, help="Path to task envelope JSON file")
    
    args = parser.parse_args()
    
    try:
        if args.cmd == "status":
            state = get_operator_runtime_state(args.operator)
            lease = get_operator_lease(args.operator)
            override = get_operator_status(args.operator)
            
            output = {
                "operator_id": args.operator,
                "runtime_state": state,
                "lease": lease,
                "override": override
            }
            print(json.dumps(output, indent=2))
            return 0
            
        elif args.cmd == "acquire":
            lease = acquire_operator_lease(
                operator_id=args.operator,
                task_id=args.task_id,
                sprint_id=args.sprint_id,
                node_id=args.node_id,
                ttl_seconds=args.ttl,
                initial_state=args.state
            )
            print(json.dumps({"acquired": True, "lease": lease}, indent=2))
            return 0
            
        elif args.cmd == "update-state":
            lease = update_operator_lease_state(
                operator_id=args.operator,
                state=args.state
            )
            print(json.dumps({"updated": True, "lease": lease}, indent=2))
            return 0
            
        elif args.cmd == "release":
            released = release_operator_lease(args.operator, args.reason)
            print(json.dumps({"released": released}, indent=2))
            return 0 if released else 1
            
        elif args.cmd == "set-override":
            override = set_operator_status(
                operator_id=args.operator,
                runtime_state=args.state,
                ttl_seconds=args.ttl
            )
            print(json.dumps({"override_set": True, "override": override}, indent=2))
            return 0
            
        elif args.cmd == "clear-override":
            clear_operator_status(args.operator)
            print(json.dumps({"override_cleared": True}, indent=2))
            return 0

        elif args.cmd == "submit":
            envelope_path = Path(args.envelope)
            if not envelope_path.exists():
                print(json.dumps({"error": f"Envelope file not found: {args.envelope}"}), file=sys.stderr)
                return 1
            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            result = submit(envelope)
            print(json.dumps(result, indent=2))
            return 0

        else:
            parser.print_help()
            return 1
            
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
