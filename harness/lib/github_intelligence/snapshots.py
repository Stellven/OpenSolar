"""Snapshot ingestion — append-only INSERT with delta computation.

Provides:
- ``insert_snapshot()``: append a new snapshot row (never UPDATE).
- ``compute_deltas()``: post-insertion delta computation for 1h/6h/24h/7d/30d.
- ``compute_acceleration()``: star acceleration ratio against 7-day baseline.
- ``ensure_delta_columns()``: idempotent ALTER TABLE to add missing columns.

All delta fields default to NULL when history is insufficient. The
``history_status`` column tracks whether deltas are valid or
``insufficient_history``.

Spec: sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade
      scoring-contract.md §3 (star acceleration) + outcomes.md O2 (snapshots/deltas)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


# Delta intervals: (column_name, hours)
DELTA_INTERVALS = [
    ("stars_delta_1h", 1),
    ("stars_delta_6h", 6),
    ("stars_delta_24h", 24),
    ("stars_delta_7d", 168),
    ("stars_delta_30d", 720),
]

# Additional fork/issue deltas
FORK_DELTA_INTERVALS = [
    ("forks_delta_24h", 24, "forks"),
    ("issues_delta_24h", 24, "open_issues"),
]

# Columns that the migration should add
_REQUIRED_COLUMNS = {
    "stars_delta_1h": "INTEGER",
    "stars_delta_6h": "INTEGER",
    "stars_delta_24h": "INTEGER",
    "stars_delta_7d": "INTEGER",
    "stars_delta_30d": "INTEGER",
    "forks_delta_24h": "INTEGER",
    "issues_delta_24h": "INTEGER",
    "prs_delta_24h": "INTEGER",
    "commit_count_7d": "INTEGER",
    "active_contributors_30d": "INTEGER",
    "star_acceleration": "REAL",
    "history_status": "TEXT NOT NULL DEFAULT 'insufficient_history'",
}


def _col_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def ensure_delta_columns(conn: sqlite3.Connection) -> list[str]:
    """Add missing delta columns to github_star_snapshots.

    Returns list of columns that were added.
    """
    added: list[str] = []
    for col, col_type in _REQUIRED_COLUMNS.items():
        if not _col_exists(conn, "github_star_snapshots", col):
            conn.execute(
                f"ALTER TABLE github_star_snapshots ADD COLUMN {col} {col_type}"
            )
            added.append(col)
    if added:
        conn.commit()
    return added


def insert_snapshot(
    conn: sqlite3.Connection,
    full_name: str,
    stars: int,
    forks: int = 0,
    open_issues: int = 0,
    watchers: int = 0,
    snapshot_at: str | None = None,
) -> int:
    """Append a new snapshot row. Never modifies existing rows.

    Returns the snapshot_id of the new row.
    Raises ValueError if (full_name, snapshot_at) already exists.
    """
    if snapshot_at is None:
        snapshot_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        cursor = conn.execute(
            """INSERT INTO github_star_snapshots
               (full_name, snapshot_at, stars, forks, open_issues, watchers)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (full_name, snapshot_at, stars, forks, open_issues, watchers),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    except sqlite3.IntegrityError:
        raise ValueError(
            f"Snapshot already exists for {full_name} at {snapshot_at}"
        )


def compute_deltas(
    conn: sqlite3.Connection,
    full_name: str,
    snapshot_at: str,
) -> dict[str, Any]:
    """Compute all deltas for a newly inserted snapshot.

    Looks up prior snapshots at 1h/6h/24h/7d/30d offsets and computes
    the star delta. If fewer than 3 snapshots exist in the 7-day window,
    sets ``history_status = 'insufficient_history'`` and all deltas to NULL.

    Returns a dict with computed values for verification.
    """
    # Parse the current snapshot time
    try:
        now = datetime.fromisoformat(snapshot_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        now = datetime.now(timezone.utc)

    results: dict[str, Any] = {}
    any_computed = False

    # Compute star deltas
    for col, hours in DELTA_INTERVALS:
        cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = conn.execute(
            """SELECT stars FROM github_star_snapshots
               WHERE full_name = ? AND snapshot_at <= ? AND snapshot_at < ?
               ORDER BY snapshot_at DESC LIMIT 1""",
            (full_name, cutoff, snapshot_at),
        ).fetchone()

        if row is not None:
            delta = conn.execute(
                """SELECT s1.stars - s2.stars AS delta
                   FROM github_star_snapshots s1, github_star_snapshots s2
                   WHERE s1.full_name = ? AND s1.snapshot_at = ?
                     AND s2.full_name = ? AND s2.snapshot_at <= ? AND s2.snapshot_at < ?
                   ORDER BY s2.snapshot_at DESC LIMIT 1""",
                (full_name, snapshot_at, full_name, cutoff, snapshot_at),
            ).fetchone()
            if delta is not None:
                results[col] = delta[0]
                any_computed = True
            else:
                results[col] = None
        else:
            results[col] = None

    # Compute fork/issue deltas (24h only)
    for col, hours, db_col in FORK_DELTA_INTERVALS:
        cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

        prior = conn.execute(
            f"""SELECT {db_col} FROM github_star_snapshots
                WHERE full_name = ? AND snapshot_at <= ? AND snapshot_at < ?
                ORDER BY snapshot_at DESC LIMIT 1""",
            (full_name, cutoff, snapshot_at),
        ).fetchone()

        current = conn.execute(
            f"""SELECT {db_col} FROM github_star_snapshots
                WHERE full_name = ? AND snapshot_at = ?""",
            (full_name, snapshot_at),
        ).fetchone()

        if prior is not None and current is not None:
            results[col] = current[0] - prior[0]
        else:
            results[col] = None

    # Determine history status
    # Count snapshots in the 7-day window before this one
    cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prior_count = conn.execute(
        """SELECT COUNT(*) FROM github_star_snapshots
           WHERE full_name = ? AND snapshot_at >= ? AND snapshot_at < ?""",
        (full_name, cutoff_7d, snapshot_at),
    ).fetchone()[0]

    if prior_count >= 3:
        history_status = "ok"
    else:
        history_status = "insufficient_history"
        # If insufficient history, set all deltas to NULL
        if not any_computed:
            for col, _ in DELTA_INTERVALS:
                results[col] = None
            for col, _, _ in FORK_DELTA_INTERVALS:
                results[col] = None

    results["history_status"] = history_status
    return results


def compute_acceleration(
    conn: sqlite3.Connection,
    full_name: str,
    snapshot_at: str,
) -> float | None:
    """Compute star acceleration = delta_24h / max(avg_delta_24h_7d, 1).

    Returns None if insufficient history.
    """
    try:
        now = datetime.fromisoformat(snapshot_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        now = datetime.now(timezone.utc)

    cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Get current snapshot stars
    current = conn.execute(
        "SELECT stars FROM github_star_snapshots WHERE full_name = ? AND snapshot_at = ?",
        (full_name, snapshot_at),
    ).fetchone()
    if current is None:
        return None

    # Get the closest snapshot ~24h ago
    cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prior_24h = conn.execute(
        """SELECT stars FROM github_star_snapshots
           WHERE full_name = ? AND snapshot_at <= ? AND snapshot_at < ?
           ORDER BY snapshot_at DESC LIMIT 1""",
        (full_name, cutoff_24h, snapshot_at),
    ).fetchone()

    if prior_24h is None:
        return None

    delta_24h = current[0] - prior_24h[0]

    # Get all snapshots in the 7-day window and compute avg delta_24h
    snapshots = conn.execute(
        """SELECT snapshot_at, stars FROM github_star_snapshots
           WHERE full_name = ? AND snapshot_at >= ? AND snapshot_at < ?
           ORDER BY snapshot_at ASC""",
        (full_name, cutoff_7d, snapshot_at),
    ).fetchall()

    if len(snapshots) < 3:
        return None  # insufficient_history

    # Compute average daily delta across the 7-day window
    daily_deltas: list[int] = []
    for i in range(1, len(snapshots)):
        time_diff = (
            datetime.fromisoformat(snapshots[i][0].replace("Z", "+00:00"))
            - datetime.fromisoformat(snapshots[i - 1][0].replace("Z", "+00:00"))
        )
        hours_diff = time_diff.total_seconds() / 3600
        if hours_diff > 0:
            # Normalize to 24h delta
            normalized_delta = (snapshots[i][1] - snapshots[i - 1][1]) / (hours_diff / 24)
            daily_deltas.append(int(normalized_delta))

    if not daily_deltas:
        return None

    avg_delta_24h = sum(daily_deltas) / len(daily_deltas)
    acceleration = delta_24h / max(avg_delta_24h, 1)

    return round(acceleration, 4)


def update_snapshot_deltas(
    conn: sqlite3.Connection,
    full_name: str,
    snapshot_at: str,
) -> dict[str, Any]:
    """Compute and write deltas + acceleration for a snapshot row.

    This is the main entry point: call after insert_snapshot().
    Returns the computed values for verification.
    """
    ensure_delta_columns(conn)

    deltas = compute_deltas(conn, full_name, snapshot_at)
    acceleration = compute_acceleration(conn, full_name, snapshot_at)

    # Build UPDATE SET clause
    set_parts: list[str] = []
    values: list[Any] = []

    for col in [c for c, _ in DELTA_INTERVALS] + [c for c, _, _ in FORK_DELTA_INTERVALS]:
        if col in deltas:
            set_parts.append(f"{col} = ?")
            values.append(deltas[col])

    set_parts.append("star_acceleration = ?")
    values.append(acceleration)

    set_parts.append("history_status = ?")
    values.append(deltas.get("history_status", "insufficient_history"))

    values.extend([full_name, snapshot_at])

    conn.execute(
        f"""UPDATE github_star_snapshots
            SET {', '.join(set_parts)}
            WHERE full_name = ? AND snapshot_at = ?""",
        values,
    )
    conn.commit()

    deltas["star_acceleration"] = acceleration
    return deltas
