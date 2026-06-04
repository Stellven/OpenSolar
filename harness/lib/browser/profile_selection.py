"""Helpers for selecting browser profiles with lease awareness."""
from __future__ import annotations

import hashlib
from typing import Any

from .profile_lease import ProfileLease
from .runtime_control import default_profile_id


def _slug(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in str(value or "").strip().lower())
    return clean.strip("-._") or "default"


def _account_label(account_identifier: str) -> str:
    return str(account_identifier or "").split("@", 1)[0].strip()


def alternate_profile_id(service: str, *, account_identifier: str, profile_directory: str) -> str:
    account = _slug(_account_label(account_identifier))
    profile = _slug(profile_directory)
    return f"{_slug(service)}/{account}-{profile}"


def profile_id_for_candidate(
    service: str,
    *,
    account_identifier: str,
    profile_directory: str,
    is_primary_profile: bool,
) -> str:
    if is_primary_profile:
        return default_profile_id(
            service,
            account_label=_account_label(account_identifier) or None,
            profile_directory=profile_directory or None,
        )
    return alternate_profile_id(
        service,
        account_identifier=account_identifier,
        profile_directory=profile_directory,
    )


def ordered_profiles(purpose: str, profiles: list[str], selection: str) -> list[str]:
    clean = [str(item).strip() for item in profiles if str(item).strip()]
    if len(clean) <= 1 or selection == "first":
        return clean
    digest = hashlib.sha256(str(purpose or "").encode("utf-8")).hexdigest()
    start = int(digest[:8], 16) % len(clean)
    return clean[start:] + clean[:start]


def peek_profile_lease(profile_id: str, *, lease_manager: ProfileLease | None = None) -> dict[str, Any] | None:
    manager = lease_manager or ProfileLease()
    return manager.peek(profile_id)


def pick_available_profile(
    *,
    service: str,
    purpose: str,
    allowed_profiles: list[str],
    selection: str,
    account_identifier: str,
    explicit_profile: str = "",
    explicit_profile_id: str = "",
    lease_manager: ProfileLease | None = None,
) -> dict[str, Any]:
    manager = lease_manager or ProfileLease()
    if explicit_profile:
        resolved_profile_id = explicit_profile_id or default_profile_id(
            service,
            account_label=_account_label(account_identifier) or None,
            profile_directory=explicit_profile or None,
        )
        return {
            "selected_profile_directory": explicit_profile,
            "selected_profile_id": resolved_profile_id,
            "lease_blocked_profiles": [],
            "lease_probe": [{"profile_directory": explicit_profile, "profile_id": resolved_profile_id, "blocked": False}],
            "selection_reason": "explicit_profile",
        }

    ordered = ordered_profiles(purpose, allowed_profiles, selection)
    if not ordered:
        return {
            "selected_profile_directory": "",
            "selected_profile_id": "",
            "lease_blocked_profiles": [],
            "lease_probe": [],
            "selection_reason": "no_allowed_profiles",
        }

    primary = ordered[0]
    probes: list[dict[str, Any]] = []
    blocked: list[str] = []
    for profile_directory in ordered:
        profile_id = profile_id_for_candidate(
            service,
            account_identifier=account_identifier,
            profile_directory=profile_directory,
            is_primary_profile=(profile_directory == primary),
        )
        lease = peek_profile_lease(profile_id, lease_manager=manager)
        is_blocked = lease is not None
        probe = {
            "profile_directory": profile_directory,
            "profile_id": profile_id,
            "blocked": is_blocked,
        }
        if lease:
            probe["held_by"] = str(lease.get("task_id") or "")
            probe["expires_at"] = str(lease.get("expires_at") or "")
            blocked.append(profile_directory)
        probes.append(probe)
        if not is_blocked:
            return {
                "selected_profile_directory": profile_directory,
                "selected_profile_id": profile_id,
                "lease_blocked_profiles": blocked,
                "lease_probe": probes,
                "selection_reason": "lease_available",
            }

    first_probe = probes[0]
    return {
        "selected_profile_directory": str(first_probe["profile_directory"]),
        "selected_profile_id": str(first_probe["profile_id"]),
        "lease_blocked_profiles": blocked,
        "lease_probe": probes,
        "selection_reason": "all_candidates_leased",
    }
