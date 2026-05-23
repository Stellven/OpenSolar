#!/usr/bin/env python3
"""multi_task_status.py — operator lifecycle observability for multi-task bridge.

Provides path-injected helpers for reading operator runtime artifacts
(lease, heartbeat/status) and producing enriched status dicts that
include operator_id, role, resolved_persona, lifecycle_state, and
heartbeat fields required by the monitor bridge.

Design
------
All functions accept explicit ``personas_dir``, ``status_dir``, and
``lease_dir`` keyword arguments so tests can inject tmp directories
without monkeypatching global constants.  The module-level defaults
mirror the paths used by operator_runtime.py.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
OPERATOR_LEASE_DIR = HARNESS_DIR / "run" / "operator-leases"
OPERATOR_STATUS_DIR = HARNESS_DIR / "run" / "operator-status"
OPERATOR_PERSONAS_DIR = HARNESS_DIR / "personas"
PHYSICAL_OPERATORS_PATH = Path(
    os.environ.get(
        "SOLAR_MULTI_TASK_OPERATORS",
        HARNESS_DIR / "config" / "physical-operators.json",
    )
)

# Must stay in sync with operator_runtime.VALID_STATES.
_VALID_STATES = frozenset({
    "idle",
    "leased",
    "running",
    "draining",
    "cooldown",
    "quota_exhausted",
    "auth_expired",
    "disabled",
})


# ---------------------------------------------------------------------------
# Disk-read helpers (path-injected, read-only)
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_heartbeat(op_id: str, status_dir: Path) -> Dict[str, Any]:
    """Return the daemon heartbeat dict for *op_id*, or ``{}`` if absent."""
    return _read_json(status_dir / f"{op_id}.json")


def _read_lease(op_id: str, lease_dir: Path) -> Dict[str, Any]:
    """Return the active lease dict for *op_id*, or ``{}`` if absent."""
    return _read_json(lease_dir / f"{op_id}.json")


# ---------------------------------------------------------------------------
# Lifecycle state resolution (mirrors operator_runtime logic, path-injected)
# ---------------------------------------------------------------------------

def _resolve_lifecycle_state(
    op_id: str,
    op_cfg: Dict[str, Any],
    lease_dir: Path,
    status_dir: Path,
) -> str:
    """Return the lifecycle state string for one operator.

    Resolution order (mirrors ``operator_runtime.get_operator_runtime_state``):
    1. Disabled in registry config.
    2. Active, non-expired lease.
    3. Dynamic status / heartbeat override.
    4. Registry ``state.runtime_state`` baseline.
    5. ``"idle"`` fallback.
    """
    if not op_cfg.get("enabled", True):
        return "disabled"

    reg_state = op_cfg.get("state", {})
    if isinstance(reg_state, dict):
        if (
            reg_state.get("availability") == "disabled"
            or reg_state.get("runtime_state") == "disabled"
        ):
            return "disabled"

    # Lease takes highest precedence when active and not expired.
    lease = _read_lease(op_id, lease_dir)
    if lease:
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if lease.get("expires_at", "") > now_str:
            state = lease.get("state")
            if state in _VALID_STATES:
                return str(state)
            return "leased"

    # Heartbeat / dynamic status override.
    hb = _read_heartbeat(op_id, status_dir)
    if hb:
        r_state = hb.get("runtime_state")
        if r_state in _VALID_STATES:
            return str(r_state)

    # Registry baseline.
    if isinstance(reg_state, dict):
        baseline = reg_state.get("runtime_state")
        if baseline in _VALID_STATES:
            return str(baseline)

    return "idle"


# ---------------------------------------------------------------------------
# Per-operator enriched status entry
# ---------------------------------------------------------------------------

def get_operator_status_entry(
    op_id: str,
    op_cfg: Dict[str, Any],
    *,
    personas_dir: Path = OPERATOR_PERSONAS_DIR,
    status_dir: Path = OPERATOR_STATUS_DIR,
    lease_dir: Path = OPERATOR_LEASE_DIR,
) -> Dict[str, Any]:
    """Return a fully-enriched status dict for one operator.

    Always-present fields
    ---------------------
    operator_id       Operator ID string.
    role              Role from registry config.
    resolved_persona  Persona name: config.persona → config.role → heartbeat → "N/A".
    lifecycle_state   Runtime lifecycle state (see _VALID_STATES).
    heartbeat_at      ISO-8601 timestamp from last daemon heartbeat, or "N/A".
    daemon_state      State recorded in last heartbeat, or "N/A".
    current_task_id   Task ID daemon is executing, or "N/A".
    submit_state      Active lease dict (task_id/sprint_id/node_id/state/…), or None.
    display_name      Human-readable name from config.
    profile           Persona/profile name from config.
    provider          Provider string from config.
    vendor            Vendor string from config.
    model             Model string from config.
    enabled           Whether operator is enabled in registry.
    surface           Surface config dict from registry (``operator.surface``), or None.
    billing_surface   Billing surface string from registry, or "N/A".
    billing_pool      Billing pool string from registry, or "N/A".
    """
    lifecycle_state = _resolve_lifecycle_state(op_id, op_cfg, lease_dir, status_dir)

    hb = _read_heartbeat(op_id, status_dir)
    heartbeat_at: str = str(hb.get("heartbeat_at") or "N/A")
    daemon_state: str = str(hb.get("state") or hb.get("runtime_state") or "N/A")
    current_task_id: str = str(hb.get("current_task_id") or "N/A")
    heartbeat_persona: Optional[str] = hb.get("resolved_persona") or None

    resolved_persona: str = (
        str(op_cfg.get("persona") or "")
        or str(op_cfg.get("role") or "")
        or str(heartbeat_persona or "")
        or "N/A"
    )

    # Submit state from the active, non-expired lease.
    lease = _read_lease(op_id, lease_dir)
    submit_state: Optional[Dict[str, Any]] = None
    if lease:
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if lease.get("expires_at", "") > now_str:
            submit_state = {
                "task_id": str(lease.get("task_id") or "N/A"),
                "sprint_id": str(lease.get("sprint_id") or "N/A"),
                "node_id": str(lease.get("node_id") or "N/A"),
                "state": str(lease.get("state") or "N/A"),
                "leased_at": str(lease.get("leased_at") or "N/A"),
                "expires_at": str(lease.get("expires_at") or "N/A"),
            }

    # Claude surface / billing fields from registry config.
    raw_surface = op_cfg.get("surface")
    surface: Optional[Dict[str, Any]] = raw_surface if isinstance(raw_surface, dict) else None

    return {
        "operator_id": op_id,
        "role": str(op_cfg.get("role") or "N/A"),
        "resolved_persona": resolved_persona,
        "lifecycle_state": lifecycle_state,
        "heartbeat_at": heartbeat_at,
        "daemon_state": daemon_state,
        "current_task_id": current_task_id,
        "submit_state": submit_state,
        "display_name": str(op_cfg.get("display_name") or op_id),
        "profile": str(op_cfg.get("profile") or op_cfg.get("persona") or "N/A"),
        "provider": str(op_cfg.get("provider") or "N/A"),
        "vendor": str(op_cfg.get("vendor") or "N/A"),
        "model": str(op_cfg.get("model") or "N/A"),
        "enabled": bool(op_cfg.get("enabled", True)),
        "surface": surface,
        "billing_surface": str(op_cfg.get("billing_surface") or "N/A"),
        "billing_pool": str(op_cfg.get("billing_pool") or "N/A"),
    }


# ---------------------------------------------------------------------------
# Fleet loader
# ---------------------------------------------------------------------------

def load_operator_fleet(
    operators_path: Path = PHYSICAL_OPERATORS_PATH,
    *,
    personas_dir: Path = OPERATOR_PERSONAS_DIR,
    status_dir: Path = OPERATOR_STATUS_DIR,
    lease_dir: Path = OPERATOR_LEASE_DIR,
) -> Dict[str, Any]:
    """Load all operators from *operators_path* and return an enriched fleet dict.

    Returns a ``{operator_id: enriched_entry}`` mapping.  Empty dict on any
    read/parse error so callers can always iterate safely.
    """
    try:
        registry = json.loads(operators_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(registry, dict):
        return {}
    operators = registry.get("operators", {})
    if not isinstance(operators, dict):
        return {}

    fleet: Dict[str, Any] = {}
    for op_id, op_cfg in operators.items():
        if not isinstance(op_cfg, dict):
            continue
        fleet[op_id] = get_operator_status_entry(
            op_id,
            op_cfg,
            personas_dir=personas_dir,
            status_dir=status_dir,
            lease_dir=lease_dir,
        )
    return fleet
