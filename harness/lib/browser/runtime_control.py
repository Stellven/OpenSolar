"""Unified browser profile/lease/contract control plane helpers."""
from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path
from typing import Any

from . import contracts
from .login_recovery import build_login_recovery_report
from .profile_lease import ProfileLease
from .profile_registry import ProfileRegistry


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip())
    return text.strip("-._").lower() or "default"


def _env_flag(*names: str, default: bool = False) -> bool:
    for name in names:
        value = str(os.environ.get(name) or "").strip().lower()
        if not value:
            continue
        return value in {"1", "true", "yes", "on"}
    return default


def _parse_iso8601(value: str | None) -> datetime.datetime:
    if not value:
        return datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)
    safe = str(value).rstrip("Z") + "+00:00"
    try:
        return datetime.datetime.fromisoformat(safe)
    except ValueError:
        return datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)


def resolve_session_lineage(metadata: dict[str, Any] | None = None) -> str:
    meta = dict(metadata or {})
    candidates = [
        meta.get("session_lineage"),
        meta.get("lineage_key"),
        os.environ.get("BROWSER_AGENT_SESSION_LINEAGE"),
        os.environ.get("SOLAR_BROWSER_SESSION_LINEAGE"),
        os.environ.get("dispatch_id"),
        os.environ.get("DISPATCH_ID"),
        os.environ.get("SPRINT_ID"),
        os.environ.get("SOLAR_RUNTIME_SESSION_ID"),
        os.environ.get("TASK_ID"),
        meta.get("task_id"),
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value
    return ""


def session_reuse_enabled(metadata: dict[str, Any] | None = None, *, default: bool = True) -> bool:
    meta = dict(metadata or {})
    if meta.get("session_reuse") is not None:
        return bool(meta.get("session_reuse"))
    return _env_flag(
        "BROWSER_AGENT_SESSION_REUSE",
        "SOLAR_BROWSER_SESSION_REUSE",
        default=default,
    )


def default_profile_id(service: str, account_label: str | None = None, profile_directory: str | None = None) -> str:
    label = account_label or profile_directory or "default"
    return f"{_slug(service)}/{_slug(label)}"


def initialize_runtime_contract(
    *,
    request_dir: Path,
    service: str,
    runtime_owner: str,
    wrapper_kind: str,
    profile_directory: str,
    user_data_dir: str | None,
    staged_user_data_dir: str | None,
    account_identifier: str | None = None,
    allowed_account_identifiers: list[str] | tuple[str, ...] | None = None,
    explicit_profile_id: str | None = None,
    task_id: str | None = None,
    control_modes: dict[str, bool] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(metadata or {})
    lineage_key = resolve_session_lineage({**metadata, "task_id": task_id})
    reuse_enabled = session_reuse_enabled(metadata)
    request_dir.mkdir(parents=True, exist_ok=True)
    profile_id = explicit_profile_id or default_profile_id(
        service,
        account_label=(account_identifier or "").split("@", 1)[0] if account_identifier else None,
        profile_directory=profile_directory,
    )
    registry = ProfileRegistry()
    lease_manager = ProfileLease()
    task_ref = str(task_id or request_dir.name or "browser-task").strip()
    lease_result = lease_manager.acquire(
        profile_id=profile_id,
        task_id=task_ref,
        runtime=runtime_owner,
        mode="exclusive",
        allowed_attach=bool((control_modes or {}).get("playwright_cdp_attach")),
    )
    if not lease_result.get("acquired"):
        raise RuntimeError(
            "browser_profile_lease_acquire_failed:"
            + json.dumps(lease_result, ensure_ascii=False)
        )

    main_profile_root = str(user_data_dir or staged_user_data_dir or "").strip()
    profile_root = str(Path(main_profile_root).expanduser() / profile_directory) if main_profile_root else ""
    existing_meta = registry.read_meta(profile_id)
    existing_allowed = existing_meta.get("allowed_account_identifiers")
    if isinstance(existing_allowed, list):
        preserved_allowlist = [str(item) for item in existing_allowed if str(item or "").strip()]
    else:
        preserved_allowlist = []
    effective_allowlist = list(
        allowed_account_identifiers
        or preserved_allowlist
        or ([] if not account_identifier else [account_identifier])
    )
    meta_payload = {
        "schema_version": 1,
        "service": service,
        "profile_id": profile_id,
        "account_label": (
            (account_identifier or "").split("@", 1)[0]
            if account_identifier
            else existing_meta.get("account_label")
            or profile_directory
        ),
        "allowed_account_identifiers": effective_allowlist,
        "runtime_owner": runtime_owner,
        "supports_playwright_cdp_attach": bool((control_modes or {}).get("playwright_cdp_attach")),
        "headless_default": True,
        "headed_required_for_first_login": True,
        "status": "leased",
        "concurrency_policy": "exclusive",
        "never_log_cookie_values": True,
    }
    if profile_root:
        meta_payload["profile_dir"] = profile_root
    stored_meta = registry.write_meta(profile_id, meta_payload)
    profile_ref = contracts.browser_profile_ref(
        profile_id=profile_id,
        storage_state_ref=stored_meta.get("storage_state_ref"),
        allowed_account_identifiers=stored_meta.get("allowed_account_identifiers"),
    )
    session_contract = contracts.browser_session_contract(
        profile_ref=profile_ref,
        runtime=runtime_owner,
        mode="exclusive",
        metadata={
            "service": service,
            "wrapper_kind": wrapper_kind,
            "control_modes": dict(control_modes or {}),
            "session_lineage": lineage_key,
            "session_reuse": reuse_enabled,
            **metadata,
        },
    )
    _write_json(request_dir / "browser-profile-ref.json", profile_ref)
    _write_json(request_dir / "browser-session-contract.json", session_contract)
    _write_json(
        request_dir / "runtime.json",
        {
            "schema": "browser.runtime_context.v1",
            "service": service,
            "wrapper_kind": wrapper_kind,
            "runtime_owner": runtime_owner,
            "profile_id": profile_id,
            "session_lineage": lineage_key,
            "session_reuse": reuse_enabled,
            "lease": lease_result.get("lease"),
        },
    )
    return {
        "service": service,
        "wrapper_kind": wrapper_kind,
        "runtime_owner": runtime_owner,
        "request_dir": request_dir,
        "profile_id": profile_id,
        "profile_ref": profile_ref,
        "session_contract": session_contract,
        "registry": registry,
        "lease_manager": lease_manager,
        "lease": lease_result.get("lease") or {},
        "task_id": task_ref,
        "session_lineage": lineage_key,
        "session_reuse": reuse_enabled,
        "allowed_account_identifiers": stored_meta.get("allowed_account_identifiers") or [],
        "account_identifier": account_identifier or "",
    }


def update_runtime_endpoint(
    context: dict[str, Any],
    *,
    cdp_url: str | None = None,
    browser_session_ref: str | None = None,
) -> None:
    registry: ProfileRegistry = context["registry"]
    profile_id = str(context["profile_id"])
    payload = {
        "cdp_url": str(cdp_url or "").strip() or None,
        "browser_session_ref": str(browser_session_ref or "").strip() or None,
    }
    registry.write_cdp_last(profile_id, payload)
    session_contract = dict(context["session_contract"])
    metadata = dict(session_contract.get("metadata") or {})
    metadata.update(payload)
    session_contract["metadata"] = metadata
    _write_json(Path(context["request_dir"]) / "browser-session-contract.json", session_contract)
    context["session_contract"] = session_contract


def read_active_session(
    context: dict[str, Any] | None,
    *,
    require_lineage_match: bool = True,
    max_age_seconds: int = 1800,
) -> dict[str, Any] | None:
    if not context:
        return None
    registry: ProfileRegistry = context["registry"]
    profile_id = str(context["profile_id"])
    record = registry.read_active_session(profile_id)
    if not record:
        return None
    updated_at = _parse_iso8601(str(record.get("updated_at") or ""))
    age = (datetime.datetime.now(datetime.timezone.utc) - updated_at).total_seconds()
    if age > max(0, int(max_age_seconds)):
        registry.clear_active_session(profile_id)
        return None
    if require_lineage_match:
        current = str(context.get("session_lineage") or "").strip()
        existing = str(record.get("session_lineage") or "").strip()
        if not current or not existing or current != existing:
            return None
    return record


def activate_reusable_session(
    context: dict[str, Any] | None,
    *,
    cdp_url: str,
    browser_session_ref: str,
    headless: bool,
    attached: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not context:
        return None
    registry: ProfileRegistry = context["registry"]
    profile_id = str(context["profile_id"])
    payload = {
        "service": str(context["service"]),
        "wrapper_kind": str(context["wrapper_kind"]),
        "runtime_owner": str(context["runtime_owner"]),
        "task_id": str(context["task_id"]),
        "session_lineage": str(context.get("session_lineage") or ""),
        "session_reuse": bool(context.get("session_reuse")),
        "cdp_url": str(cdp_url or "").strip() or None,
        "browser_session_ref": str(browser_session_ref or "").strip() or None,
        "headless": bool(headless),
        "attached": bool(attached),
        "details": dict(details or {}),
    }
    return registry.write_active_session(profile_id, payload)


def clear_active_session(context: dict[str, Any] | None) -> bool:
    if not context:
        return False
    registry: ProfileRegistry = context["registry"]
    profile_id = str(context["profile_id"])
    return registry.clear_active_session(profile_id)


def finalize_runtime_contract(
    context: dict[str, Any] | None,
    *,
    success: bool,
    error_text: str | None = None,
    page_state: dict[str, Any] | None = None,
    logged_in_state_verified: bool = False,
    details: dict[str, Any] | None = None,
    requires_precise_page_control: bool = False,
) -> dict[str, Any] | None:
    if not context:
        return None
    request_dir = Path(context["request_dir"])
    lease_manager: ProfileLease = context["lease_manager"]
    task_id = str(context["task_id"])
    profile_id = str(context["profile_id"])
    release_result = lease_manager.release(profile_id, task_id)
    report = build_login_recovery_report(
        service=str(context["service"]),
        profile_ref=context["profile_ref"],
        runtime_owner=str(context["runtime_owner"]),
        wrapper_kind=str(context["wrapper_kind"]),
        error_text=error_text,
        page_state=page_state,
        account_identifier=str(context.get("account_identifier") or "").strip() or None,
        allowlist=context.get("allowed_account_identifiers") or [],
        requires_precise_page_control=requires_precise_page_control,
        lease_released=bool(release_result.get("released")),
        logged_in_state_verified=logged_in_state_verified if success else False,
        details={
            "success": success,
            "release": release_result,
            **dict(details or {}),
        },
    )
    _write_json(request_dir / "login-recovery-report.json", report)
    registry: ProfileRegistry = context["registry"]
    registry.write_health(
        profile_id,
        {
            "status": "healthy" if success else "reauth_required",
            "last_run_ok": bool(success),
            "last_error": str(error_text or "").strip() or None,
        },
    )
    session_contract = dict(context["session_contract"])
    session_contract["status"] = "completed" if success else "failed"
    session_contract["metadata"] = {
        **dict(session_contract.get("metadata") or {}),
        "login_recovery_report": "login-recovery-report.json",
        "lease_released": bool(release_result.get("released")),
    }
    _write_json(request_dir / "browser-session-contract.json", session_contract)
    return report
