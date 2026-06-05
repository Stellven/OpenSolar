#!/usr/bin/env python3
"""Adapters for operator health watchdog prune/quota phases.

The adapter layer is intentionally small: it delegates to real runtime helpers and
normalizes outputs for watchdog caller contracts.
"""
from __future__ import annotations

import datetime as dt
import importlib
from typing import Any

BLOCKED_RUNTIME_STATES = {"cooldown", "quota_exhausted", "auth_expired"}


def _load_flow_control_module():
    try:
        return importlib.import_module("operator_flow_control")
    except ModuleNotFoundError as exc:
        raise RuntimeError("operator_flow_control module not found") from exc


def _load_quota_refresh_module():
    try:
        return importlib.import_module("quota_refresh")
    except ModuleNotFoundError as exc:
        raise RuntimeError("quota_refresh module not found") from exc


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_iso(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _sanitize_entry(entry: dict[str, Any], *, now: dt.datetime) -> dict[str, Any]:
    operator_id = str(entry.get("operator_id") or entry.get("operator") or "").strip()
    state = str(entry.get("runtime_state") or "").strip()
    expires_at = str(
        entry.get("expires_at")
        or entry.get("expired_at")
        or entry.get("quota_refresh_at")
        or entry.get("retry_at")
        or ""
    ).strip()
    parsed = _parse_iso(expires_at)
    return {
        "operator_id": operator_id,
        "runtime_state": state,
        "expires_at": expires_at,
        "expired_at": expires_at if parsed is not None and parsed <= now else (expires_at or "N/A"),
        "idempotency_key": f"{operator_id}|{expires_at or 'N/A'}",
    }


def _degradation_summary(*, ok: bool, reason: str = "", blocker: str | None = None) -> dict[str, Any]:
    return {
        "degraded": not bool(ok),
        "ok": bool(ok),
        "reason": reason,
        "blocker": blocker,
    }


def prune_expired_operator_config_blocks(
    *,
    flow_control_module: Any | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Call flow-control prune and normalize action accounting.

    Expired blocked operators are cleared, non-expired blocked operators are kept,
    and items that are preserved by runtime/registry are marked as kept.
    """
    flow_control = flow_control_module or _load_flow_control_module()
    if not hasattr(flow_control, "prune_expired_operator_config_blocks"):
        return {
            "ok": False,
            "reason": "missing_flow_control_adaptor",
            "checked": 0,
            "pruned": [],
            "kept": [],
            "summary": {"pruned": 0, "kept": 0},
            "degradation_summary": {
                "degraded": True,
                "ok": False,
                "reason": "missing flow-control adapter",
                "blocker": "prune_adaptor_missing",
            },
        }

    now = now or _now()
    try:
        raw = flow_control.prune_expired_operator_config_blocks()
    except Exception as exc:
        return {
            "ok": False,
            "reason": f"prune_failed:{type(exc).__name__}",
            "checked": 0,
            "pruned": [],
            "kept": [],
            "summary": {"pruned": 0, "kept": 0},
            "degradation_summary": {
                "degraded": True,
                "ok": False,
                "reason": str(exc)[:256],
                "blocker": "prune_failed",
            },
        }
    if not isinstance(raw, dict):
        return {
            "ok": False,
            "reason": "invalid_prune_result",
            "checked": 0,
            "pruned": [],
            "kept": [],
            "summary": {"pruned": 0, "kept": 0},
            "degradation_summary": {
                "degraded": True,
                "ok": False,
                "reason": "prune result is not a dict",
                "blocker": "prune_failed",
            },
        }

    pruned_entries: list[dict[str, Any]] = []
    kept_entries: list[dict[str, Any]] = []

    for item in raw.get("pruned", []) if isinstance(raw.get("pruned"), list) else []:
        if not isinstance(item, dict):
            continue
        entry = _sanitize_entry(item, now=now)
        if str(entry.get("runtime_state", "")).strip() not in BLOCKED_RUNTIME_STATES:
            kept_entries.append(
                {
                    **entry,
                    "source": "invalid_block_state_recovered",
                    "retry_at": _now().isoformat().replace("+00:00", "Z"),
                }
            )
            continue
        if _parse_iso(entry.get("expires_at")) is not None and _parse_iso(entry.get("expires_at")) > now:
            kept_entries.append(
                {
                    **entry,
                    "source": "future_expiry_retained",
                    "retry_at": entry.get("expires_at"),
                }
            )
            continue
        pruned_entries.append(
            {
                **entry,
                "source": "expired_block_cleared",
                "retry_at": "N/A",
            }
        )

    for item in raw.get("kept", []) if isinstance(raw.get("kept"), list) else []:
        if not isinstance(item, dict):
            continue
        entry = _sanitize_entry(item, now=now)
        kept_entries.append(
            {
                **entry,
                "source": "preserved_by_flow_control",
                "retry_at": entry.get("expires_at") or _now().isoformat().replace("+00:00", "Z"),
            }
        )

    return {
        "ok": bool(raw.get("ok", True)),
        "checked": int(raw.get("checked") or 0) or (len(pruned_entries) + len(kept_entries)),
        "pruned": pruned_entries,
        "kept": kept_entries,
        "summary": {"pruned": len(pruned_entries), "kept": len(kept_entries)},
        "degradation_summary": {
            "degraded": not bool(raw.get("ok", True)),
            "ok": bool(raw.get("ok", True)),
            "reason": str(raw.get("reason", "")),
            "blocker": None if bool(raw.get("ok", True)) else "prune_failed",
        },
    }


def refresh_snapshot(
    *,
    apply: bool = False,
    quota_refresh_module: Any | None = None,
    include_details: bool = True,
) -> dict[str, Any]:
    """Call quota_refresh and always return a dict with degradation summary."""
    quota = quota_refresh_module or _load_quota_refresh_module()
    if not hasattr(quota, "refresh_snapshot"):
        payload = {
            "ok": False,
            "reason": "missing_quota_snapshot_adapter",
            "operators_total": 0,
            "operators_usable": 0,
            "operators_hard_blocked": 0,
            "groups": {},
            "degraded": True,
        }
    else:
        try:
            payload = quota.refresh_snapshot(apply=bool(apply))
        except Exception as exc:
            payload = {
                "ok": False,
                "reason": f"quota_refresh_failed:{type(exc).__name__}",
                "error": str(exc),
                "operators_total": 0,
                "operators_usable": 0,
                "operators_hard_blocked": 0,
                "groups": {},
            }

    if not isinstance(payload, dict):
        payload = {
            "ok": False,
            "reason": "invalid_quota_snapshot",
            "operators_total": 0,
            "operators_usable": 0,
            "operators_hard_blocked": 0,
            "groups": {},
        }

    payload.setdefault("ok", False)
    payload.setdefault("generated_at", _now().isoformat().replace("+00:00", "Z"))
    payload["degradation_summary"] = _degradation_summary(
        ok=bool(payload.get("ok")),
        reason=str(payload.get("reason", "")),
        blocker=("quota_refresh failed; proceeding with existing block states" if not bool(payload.get("ok")) else None),
    )
    payload["degraded"] = not bool(payload.get("ok"))
    payload["apply_requested"] = bool(apply)
    if include_details:
        payload["degradation_details"] = {
            "summary": payload["degradation_summary"]["reason"] or ("ok" if bool(payload.get("ok")) else "degraded"),
            "timestamp": _now().isoformat().replace("+00:00", "Z"),
            "apply": bool(apply),
        }
    return payload


def summarize_quota_refresh_failure(payload: dict[str, Any]) -> str:
    """Return concise failure marker used by summary surfaces."""
    if not isinstance(payload, dict):
        return "quota_refresh_payload_invalid"
    if payload.get("ok"):
        return "quota_refresh_ok"
    return f"quota_refresh_degraded:{str(payload.get('reason') or 'quota_refresh_failed')}"


def prune_and_refresh(
    *,
    apply: bool = False,
    flow_control_module: Any | None = None,
    quota_refresh_module: Any | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for tests and future B2 wiring."""
    prune_payload = prune_expired_operator_config_blocks(
        flow_control_module=flow_control_module,
        now=now,
    )
    capacity_payload = refresh_snapshot(apply=apply, quota_refresh_module=quota_refresh_module, include_details=False)
    blockers: list[str] = []
    if not prune_payload.get("ok"):
        blockers.append(f"prune_failed:{prune_payload.get('reason','unknown')}")
    if not capacity_payload.get("ok"):
        blockers.append(f"quota_refresh_failed:{capacity_payload.get('reason', 'quota_refresh_failed')}")
    return {
        "ok": bool(prune_payload.get("ok")) and bool(capacity_payload.get("ok")),
        "prune": prune_payload,
        "quota_refresh": capacity_payload,
        "blockers": blockers,
        "degradation_summary": {
            "degraded": bool(blockers),
            "quota": capacity_payload.get("degradation_summary", {}),
            "prune": prune_payload.get("degradation_summary", {}),
        },
    }
