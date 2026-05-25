"""Model call ledger — log all model invocations with cost tracking.

Provides:
- ``log_call()``: insert a model call record.
- ``check_daily_cap()``: enforce configurable daily premium call limit.
- ``daily_spend()``: query daily spend by model.
- ``daily_call_count()``: count calls by date/purpose/model.

Spec: sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements
      model-report-contract.md §3.3 (model ledger) + §3.2 (gating rules)
Node: B8
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any


DEFAULT_DAILY_CAP = 20

# Config key for daily cap override
CONFIG_DAILY_CAP_KEY = "github_intelligence.daily_premium_cap"

# Models considered "premium" (cost money per call)
PREMIUM_MODELS = {
    "claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
    "gemini-3.1-pro", "gemini-2.5-pro",
    "gpt-4.1", "o3", "o4-mini",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_daily_cap() -> int:
    """Read daily premium call cap from env or config."""
    env_val = os.getenv("GITHUB_INTELLIGENCE_DAILY_CAP", "").strip()
    if env_val:
        try:
            return max(1, int(env_val))
        except ValueError:
            pass
    return DEFAULT_DAILY_CAP


def log_call(
    conn: sqlite3.Connection,
    *,
    model: str,
    call_purpose: str,
    repo_full_name: str = "",
    provider: str = "",
    input_type: str = "project_reasoning_packet",
    input_token_count: int = 0,
    output_token_count: int = 0,
    latency_ms: int = 0,
    cost_estimate_usd: float = 0.0,
    evidence_atom_count: int = 0,
    success: bool = True,
    error_message: str = "",
) -> int:
    """Log a model call to the ledger.

    Returns the ledger_id of the new row.
    """
    cursor = conn.execute(
        """INSERT INTO model_call_ledger
           (repo_full_name, model, provider, call_purpose, input_type,
            input_token_count, output_token_count, latency_ms,
            cost_estimate_usd, evidence_atom_count, success, error_message, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            repo_full_name, model, provider, call_purpose, input_type,
            input_token_count, output_token_count, latency_ms,
            cost_estimate_usd, evidence_atom_count,
            1 if success else 0, error_message, _utc_now(),
        ),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def check_daily_cap(
    conn: sqlite3.Connection,
    model: str,
    daily_cap: int | None = None,
) -> dict[str, Any]:
    """Check whether a premium model call is allowed under the daily cap.

    Returns a dict with:
    - ``allowed``: bool
    - ``used_today``: number of premium calls today
    - ``daily_cap``: the cap value
    - ``remaining``: remaining calls
    """
    if model not in PREMIUM_MODELS:
        return {
            "allowed": True,
            "used_today": 0,
            "daily_cap": 0,
            "remaining": -1,
            "reason": "not_premium",
        }

    cap = daily_cap if daily_cap is not None else _get_daily_cap()
    today = _today()

    row = conn.execute(
        """SELECT COUNT(*) FROM model_call_ledger
           WHERE model = ? AND DATE(created_at) = ? AND success = 1""",
        (model, today),
    ).fetchone()

    used = row[0] if row else 0
    remaining = max(0, cap - used)

    return {
        "allowed": used < cap,
        "used_today": used,
        "daily_cap": cap,
        "remaining": remaining,
        "reason": "under_cap" if used < cap else "cap_exhausted",
    }


def daily_spend(
    conn: sqlite3.Connection,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Query daily spend by model for a given date.

    Returns list of dicts with model, total_calls, total_cost, total_input_tokens, total_output_tokens.
    """
    target_date = date or _today()
    rows = conn.execute(
        """SELECT model,
                  COUNT(*) AS total_calls,
                  ROUND(SUM(cost_estimate_usd), 6) AS total_cost,
                  SUM(input_token_count) AS total_input_tokens,
                  SUM(output_token_count) AS total_output_tokens
           FROM model_call_ledger
           WHERE DATE(created_at) = ?
           GROUP BY model
           ORDER BY total_cost DESC""",
        (target_date,),
    ).fetchall()

    return [
        {
            "model": row[0],
            "total_calls": row[1],
            "total_cost": row[2],
            "total_input_tokens": row[3],
            "total_output_tokens": row[4],
        }
        for row in rows
    ]


def daily_call_count(
    conn: sqlite3.Connection,
    date: str | None = None,
    *,
    model: str | None = None,
    call_purpose: str | None = None,
) -> int:
    """Count model calls for a given date, optionally filtered."""
    target_date = date or _today()
    conditions = ["DATE(created_at) = ?"]
    params: list[Any] = [target_date]

    if model:
        conditions.append("model = ?")
        params.append(model)
    if call_purpose:
        conditions.append("call_purpose = ?")
        params.append(call_purpose)

    row = conn.execute(
        f"SELECT COUNT(*) FROM model_call_ledger WHERE {' AND '.join(conditions)}",
        params,
    ).fetchone()
    return row[0] if row else 0
