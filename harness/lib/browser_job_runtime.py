"""browser_job_runtime.py — Async Browser Agent job control client and mock adapter.

Provides helper client to submit, poll, collect, and cancel jobs executed by the browser execution daemon.
Provides mock/dry-run adapter functionality to simulate async state transitions.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from capability_token import CapabilityToken

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
BROWSER_JOBS_DIR = HARNESS_DIR / "run" / "browser-jobs"
OPERATOR_RESULTS_DIR = HARNESS_DIR / "run" / "operator-results"

# Regex patterns for scrubbing sensitive information
_SECRET_PATTERNS = [
    (re.compile(r'(?i)Set-Cookie:\s*[^\n]+'), 'Set-Cookie: [SCRUBBED]'),
    (re.compile(r'(?i)Cookie:\s*[^\n]+'), 'Cookie: [SCRUBBED]'),
    (re.compile(r'(?i)Authorization:\s*[^\n]+'), 'Authorization: [SCRUBBED]'),
    (re.compile(r'(?i)Bearer\s+[a-zA-Z0-9\-._~+/=]+'), 'Bearer [SCRUBBED]'),
    (re.compile(r'sk-[a-zA-Z0-9]{32,}'), '[SCRUBBED]'),
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), '[SCRUBBED]'),
    (re.compile(r'github_pat_[a-zA-Z0-9_]{82}'), '[SCRUBBED]'),
    (re.compile(r'AKIA[0-9A-Z]{16}'), '[SCRUBBED]'),
    (re.compile(r'(?i)\b(api[_-]?key|apikey|api_secret)\s*[=:]\s*[^\s"\']{4,}'), r'\1=[SCRUBBED]'),
    (re.compile(r'(?i)\b(password|passwd)\s*[=:]\s*[^\s"\']{4,}'), r'\1=[SCRUBBED]'),
    (re.compile(r'(?i)\b(token|secret)\s*[=:]\s*[^\s"\']{4,}'), r'\1=[SCRUBBED]'),
]


def scrub_secrets(text: str) -> str:
    """Scrub raw cookies, tokens, headers, and secrets from text."""
    if not isinstance(text, str):
        return text
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def scrub_dict(d: Any) -> Any:
    """Deep-scrub a dictionary, allowing profile_ref and account_label but redacting secrets."""
    if isinstance(d, dict):
        cleaned = {}
        for k, v in d.items():
            if k in {"profile_ref", "account_label"}:
                cleaned[k] = v  # Allowed explicitly
            elif any(x in k.lower() for x in ["cookie", "token", "password", "secret", "auth", "api_key", "key"]):
                cleaned[k] = "[SCRUBBED]"
            else:
                cleaned[k] = scrub_dict(v)
        return cleaned
    elif isinstance(d, list):
        return [scrub_dict(item) for item in d]
    elif isinstance(d, str):
        return scrub_secrets(d)
    return d


def validate_browser_job_policy(envelope: Dict[str, Any], capability_token: Optional[CapabilityToken] = None) -> None:
    """Enforces capability-token policy checks for browser jobs.

    Denies payment, secrets form fill, and destructive actions.
    """
    objective = (envelope.get("objective") or "").lower()

    # 1. Deny payment actions always
    payment_keywords = ["payment", "checkout", "buy ", "purchase", "billing", "subscribe", "pay ", "credit card"]
    for kw in payment_keywords:
        if kw in objective:
            raise PermissionError(f"Denying browser job submission: objective requests prohibited payment action '{kw}'")

    # 2. Deny secrets form fill / secrets access unless explicitly allowed by token
    secrets_keywords = ["password", "secret", "private key", "api_key", "api-key", "credentials"]
    
    # Check if envelope or objective explicitly requests secrets / secrets form filling
    secrets_requested = "secret_form" in envelope or any(k in envelope for k in ["secrets_allowed", "fill_secrets"])
    if not secrets_requested:
        for kw in secrets_keywords:
            if kw in objective:
                secrets_requested = True
                break

    if secrets_requested:
        if not capability_token:
            raise PermissionError("Denying browser job submission: secrets/credentials access requested but no capability token provided")
        token_dict = capability_token.to_dict()
        secrets_allowed = token_dict.get("secrets", {}).get("allowed", False) or \
                          token_dict.get("file_scope", {}).get("secret_paths_allowed", False)
        if not secrets_allowed:
            raise PermissionError("Denying browser job submission: secrets/credentials access requested but capability token denies it")

    # 3. Deny destructive actions unless explicitly allowed by token
    destructive_keywords = ["delete", "rm -rf", "drop database", "destructive", "uninstall", "format "]
    destructive_requested = "destructive_action" in envelope or envelope.get("destructive") is True
    if not destructive_requested:
        for kw in destructive_keywords:
            if kw in objective:
                destructive_requested = True
                break

    if destructive_requested:
        if not capability_token:
            raise PermissionError("Denying browser job submission: destructive action requested but no capability token provided")
        token_dict = capability_token.to_dict()
        destructive_allowed = token_dict.get("file_scope", {}).get("destructive_allowed", False) or \
                              token_dict.get("shell_scope", {}).get("destructive_commands_allowed", False)
        if not destructive_allowed:
            raise PermissionError("Denying browser job submission: destructive action requested but capability token denies it")


class BrowserSessionBroker:
    """Manages browser session profile health and authentication state.

    Ensures zero logging of raw session credentials, cookies, or tokens.
    """

    def __init__(self, harness_dir: Optional[Path] = None):
        self.harness_dir = harness_dir or HARNESS_DIR

    def get_profile_health(self, profile_ref: str, account_label: str) -> Dict[str, Any]:
        """Check login/auth health of a browser profile.

        Does not print or write cookies/tokens/raw credentials to any logs.
        """
        # Scrub inputs to be safe
        scrubbed_ref = scrub_secrets(profile_ref)
        scrubbed_label = scrub_secrets(account_label)

        # In mock scenarios, we check if reauth is requested
        is_healthy = True
        if "reauth" in scrubbed_ref.lower() or "reauth" in scrubbed_label.lower():
            is_healthy = False

        status = "healthy" if is_healthy else "reauth_required"
        projected = "WAITING_HUMAN" if not is_healthy else "running"

        return {
            "profile_ref": scrubbed_ref,
            "account_label": scrubbed_label,
            "status": status,
            "projected_state": projected,
            "login_health": "OK" if is_healthy else "REQUIRES_2FA"
        }


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_jobs_dir() -> None:
    BROWSER_JOBS_DIR.mkdir(parents=True, exist_ok=True)


def submit_browser_job(
    actor_id: str,
    envelope: Dict[str, Any],
    mock_sequence: Optional[List[str]] = None,
    capability_token: Optional[CapabilityToken] = None
) -> str:
    """Submits a browser job envelope and initializes state.json.

    Enforces capability-token policy checks and scrubs secrets.
    """
    # Enforce policy checks
    validate_browser_job_policy(envelope, capability_token)

    _ensure_jobs_dir()
    job_id = f"job-{uuid.uuid4()}"
    job_dir = BROWSER_JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Define initial state
    initial_state = "submitted"
    mock_index = 0
    if mock_sequence:
        mock_index = -1

    # Scrub envelope and initial logs of any secrets
    scrubbed_envelope = scrub_dict(envelope)
    initial_logs = scrub_secrets(f"Job {job_id} submitted for actor {actor_id} at {_now()}.\n")

    state_data = {
        "job_id": job_id,
        "actor_id": actor_id,
        "state": initial_state,
        "envelope": scrubbed_envelope,
        "logs": initial_logs,
        "artifacts": [],
        "mock_sequence": mock_sequence,
        "mock_index": mock_index,
        "created_at": _now(),
        "updated_at": _now()
    }

    state_file = job_dir / "state.json"
    state_file.write_text(json.dumps(state_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return job_id


def poll_browser_job(job_id: str) -> Dict[str, Any]:
    """Polls the state of a browser job, simulating state transitions if mock_sequence is defined."""
    job_dir = BROWSER_JOBS_DIR / job_id
    state_file = job_dir / "state.json"
    if not state_file.exists():
        raise ValueError(f"Job {job_id} not found")

    state_data = json.loads(state_file.read_text(encoding="utf-8"))

    # State transition logic for mock sequence
    mock_sequence = state_data.get("mock_sequence")
    if mock_sequence and isinstance(mock_sequence, list):
        current_state = state_data.get("state")
        terminal_states = {"done", "failed", "timeout"}
        if current_state not in terminal_states:
            idx = state_data.get("mock_index", -1)
            if idx + 1 < len(mock_sequence):
                idx += 1
                new_state = mock_sequence[idx]
                state_data["state"] = new_state
                state_data["mock_index"] = idx
                state_data["logs"] += f"[{_now()}] Transitioned to state: {new_state}\n"

                # Add mock artifacts on done/failed/timeout
                if new_state == "done":
                    state_data["artifacts"] = [
                        {"name": "screenshot.png", "type": "screenshot", "content": "mock_png_bytes"},
                        {"name": "logs.txt", "type": "logs", "content": state_data["logs"]}
                    ]
                elif new_state in {"failed", "timeout"}:
                    state_data["artifacts"] = [
                        {"name": "logs.txt", "type": "logs", "content": state_data["logs"] + "\nTerminal failure encountered."}
                    ]

                state_data["updated_at"] = _now()

    # Scrub logs & artifacts before saving/returning
    state_data["logs"] = scrub_secrets(state_data["logs"])
    for art in state_data.get("artifacts", []):
        if "content" in art and isinstance(art["content"], str):
            art["content"] = scrub_secrets(art["content"])

    # Surface WAITING_HUMAN when reauth_required is detected
    if state_data.get("state") == "reauth_required":
        state_data["projected_state"] = "WAITING_HUMAN"
    else:
        state_data["projected_state"] = state_data.get("state")

    state_file.write_text(json.dumps(state_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return state_data


def collect_browser_job(job_id: str, output_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Collects job results, writes structured result.json, and writes artifacts to output_dir."""
    job_dir = BROWSER_JOBS_DIR / job_id
    state_file = job_dir / "state.json"
    if not state_file.exists():
        raise ValueError(f"Job {job_id} not found")

    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    state = state_data.get("state")
    terminal_states = {"done", "failed", "timeout"}
    if state not in terminal_states:
        raise RuntimeError(f"Cannot collect job {job_id}: current state is '{state}', not terminal.")

    envelope = state_data.get("envelope") or {}
    operator_id = envelope.get("operator_id") or state_data.get("actor_id")
    task_id = envelope.get("task_id") or job_id
    sprint_id = envelope.get("sprint_id") or "sprint-unknown"
    node_id = envelope.get("node_id") or "node-unknown"

    # Determine exit code and final status
    status = "completed" if state == "done" else state
    exit_code = 0 if state == "done" else (1 if state == "failed" else 2)

    # Resolve output directory
    if output_dir is None:
        output_dir = OPERATOR_RESULTS_DIR / operator_id / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write artifacts to output_dir with secret scrubbing
    artifacts_written = []
    for artifact in state_data.get("artifacts", []):
        name = artifact.get("name")
        content = artifact.get("content", "")
        if name:
            art_file = output_dir / name
            if isinstance(content, str):
                art_file.write_text(scrub_secrets(content), encoding="utf-8")
            else:
                art_file.write_bytes(content)
            artifacts_written.append(str(art_file))

    # Write structured result.json
    result = {
        "task_id": task_id,
        "operator_id": operator_id,
        "sprint_id": sprint_id,
        "node_id": node_id,
        "status": status,
        "exit_code": exit_code,
        "started_at": state_data.get("created_at"),
        "finished_at": state_data.get("updated_at"),
        "log_tail": scrub_secrets(state_data.get("logs")[-8000:]),
        "artifacts": artifacts_written
    }

    result_path = output_dir / "result.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


def cancel_browser_job(job_id: str) -> bool:
    """Cancels a browser job and marks it as failed."""
    job_dir = BROWSER_JOBS_DIR / job_id
    state_file = job_dir / "state.json"
    if not state_file.exists():
        return False

    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    state_data["state"] = "failed"
    state_data["logs"] += f"[{_now()}] Job cancelled by controller.\n"
    state_data["updated_at"] = _now()
    
    state_data["logs"] = scrub_secrets(state_data["logs"])
    state_file.write_text(json.dumps(state_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True
