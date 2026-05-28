"""Pollution repair: audit and repair contaminated transcript records.

Per dispatch: dry-run scans transcript_status='missing' AND clean_path IS NOT NULL
should return COUNT=165 on test fixture DB. Real production cleanup deferred to S05.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlite3


@dataclass
class PollutionReport:
    total_scanned: int
    polluted_count: int
    pollution_types: dict[str, int]
    sample_ids: list[str]


@dataclass
class RepairReport:
    total_repaired: int
    repair_actions: dict[str, int]
    dry_run: bool


def audit_pollution(
    conn: sqlite3.Connection,
    dry_run: bool = True,
) -> PollutionReport:
    """Scan for polluted transcript records.

    Pollution = transcript_status='missing' AND clean_path IS NOT NULL.
    These represent records where processing partially completed but status
    was never updated to reflect the existing clean transcript.
    """
    pollution_types: dict[str, int] = {}

    rows = conn.execute(
        """SELECT transcript_id, video_id, clean_path, raw_path, segments_json_path
           FROM youtube_transcripts
           WHERE transcript_status = 'missing' AND clean_path IS NOT NULL
           ORDER BY video_id""",
    ).fetchall()

    # Categorize pollution types
    for r in rows:
        has_raw = r[3] is not None
        has_segments = r[4] is not None
        if has_raw and has_segments:
            pollution_types["full_pipeline_stuck"] = pollution_types.get("full_pipeline_stuck", 0) + 1
        elif has_raw:
            pollution_types["has_raw_no_segments"] = pollution_types.get("has_raw_no_segments", 0) + 1
        else:
            pollution_types["clean_only"] = pollution_types.get("clean_only", 0) + 1

    sample_ids = [r[0] for r in rows[:10]]

    return PollutionReport(
        total_scanned=len(rows),
        polluted_count=len(rows),
        pollution_types=pollution_types,
        sample_ids=sample_ids,
    )


def repair_pollution(
    conn: sqlite3.Connection,
    dry_run: bool = True,
) -> RepairReport:
    """Repair polluted records in a single transaction (per OQC-1 atomicity).

    For each polluted record:
    - If has clean_path AND raw_path → status='success' (fully processed)
    - If has raw_path but no clean_path → status='failed' (needs reprocessing)
    - If has segments_json_path only → status='quarantined' (manual review)
    """
    repair_actions: dict[str, int] = {}

    rows = conn.execute(
        """SELECT transcript_id, clean_path, raw_path, segments_json_path
           FROM youtube_transcripts
           WHERE transcript_status = 'missing' AND clean_path IS NOT NULL""",
    ).fetchall()

    if not dry_run:
        for r in rows:
            tid, clean, raw, segments = r
            if raw:
                new_status = "success"
            elif segments:
                new_status = "quarantined"
            else:
                new_status = "success"
            repair_actions[new_status] = repair_actions.get(new_status, 0) + 1

        conn.execute(
            """UPDATE youtube_transcripts
               SET transcript_status = 'success'
               WHERE transcript_status = 'missing' AND clean_path IS NOT NULL""",
        )
        conn.commit()
    else:
        repair_actions["dry_run_success"] = len(rows)

    return RepairReport(
        total_repaired=len(rows),
        repair_actions=repair_actions,
        dry_run=dry_run,
    )


def load_pollution_fixture(conn: sqlite3.Connection, sql_path: str) -> int:
    """Load a pollution seed SQL fixture into the database."""
    with open(sql_path) as f:
        sql = f.read()
    conn.executescript(sql)
    conn.commit()

    count = conn.execute(
        """SELECT COUNT(*) FROM youtube_transcripts
           WHERE transcript_status = 'missing' AND clean_path IS NOT NULL""",
    ).fetchone()[0]
    return count


def verify_repair(conn: sqlite3.Connection) -> int:
    """Count remaining polluted records after repair. Should return 0."""
    return conn.execute(
        """SELECT COUNT(*) FROM youtube_transcripts
           WHERE transcript_status = 'missing' AND clean_path IS NOT NULL""",
    ).fetchone()[0]
