"""GitHub Intelligence schema — migration for 9 new tables.

Adds repo-centric evidence, reasoning packets, analysis cards, planning
briefs, model call ledger, daily/weekly reports, snapshot percentiles,
and detector alerts to the existing tech-hotspot-radar.sqlite database.

All tables use CREATE TABLE IF NOT EXISTS for idempotent migration.

Spec: sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements
      outcomes.md (O3, O4, O5, O6) + scoring-contract.md + model-report-contract.md
Node: B1
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


MIGRATION_SQL = """\
-- ============================================================
-- B1 Migration: 9 new tables for AI Influence GitHub Intelligence
-- All use IF NOT EXISTS for idempotent re-runs.
-- ============================================================

-- 1. repo_evidence_atoms
-- Per-repo evidence atoms produced by ThunderOMLX / Qwen3.6 local preprocessing.
-- Distinct from the existing source-level evidence_atoms table.
CREATE TABLE IF NOT EXISTS repo_evidence_atoms (
    atom_id           TEXT PRIMARY KEY,
    repo_full_name    TEXT NOT NULL,
    evidence_type     TEXT NOT NULL
        CHECK(evidence_type IN ('readme_claim','release_feature','issue_signal','pr_signal',
                                'social_mention','youtube_mention','growth_fact')),
    compressed_content TEXT NOT NULL DEFAULT '',
    entities_json     TEXT NOT NULL DEFAULT '[]',
    tags_json         TEXT NOT NULL DEFAULT '[]',
    confidence        REAL NOT NULL DEFAULT 0.5,
    technical_depth   REAL,
    novelty_score     REAL,
    raw_source_type   TEXT NOT NULL DEFAULT '',
    raw_source_id     TEXT NOT NULL DEFAULT '',
    span_start        INTEGER,
    span_end          INTEGER,
    model_used        TEXT NOT NULL DEFAULT 'local_qwen3_6',
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rea_repo ON repo_evidence_atoms(repo_full_name);
CREATE INDEX IF NOT EXISTS idx_rea_type ON repo_evidence_atoms(evidence_type);
CREATE INDEX IF NOT EXISTS idx_rea_confidence ON repo_evidence_atoms(confidence);

-- 2. project_reasoning_packets
-- Aggregated per-repo evidence sent to premium models for analysis.
-- Distinct from the existing cluster-level reasoning_packets table.
CREATE TABLE IF NOT EXISTS project_reasoning_packets (
    packet_id         TEXT PRIMARY KEY,
    repo_full_name    TEXT NOT NULL,
    star_velocity_percentile REAL,
    acceleration      REAL,
    acceleration_tier TEXT
        CHECK(acceleration_tier IS NULL OR acceleration_tier IN ('normal','warming','breakout','sudden_hot','needs_attribution')),
    evidence_atom_count INTEGER NOT NULL DEFAULT 0,
    evidence_atom_ids_json TEXT NOT NULL DEFAULT '[]',
    scores_json       TEXT NOT NULL DEFAULT '{}',
    detector_results_json TEXT NOT NULL DEFAULT '[]',
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    schema_version    TEXT NOT NULL DEFAULT 'v1',
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prp_repo ON project_reasoning_packets(repo_full_name);

-- 3. repo_analysis_cards
-- Project intelligence cards for high-value repos (O4).
CREATE TABLE IF NOT EXISTS repo_analysis_cards (
    card_id           TEXT PRIMARY KEY,
    repo_full_name    TEXT NOT NULL,
    positioning       TEXT NOT NULL DEFAULT '',
    what_it_does      TEXT NOT NULL DEFAULT '',
    target_users      TEXT NOT NULL DEFAULT '',
    core_technical_idea TEXT NOT NULL DEFAULT '',
    why_hot_facts     TEXT NOT NULL DEFAULT '[]',
    scores_json       TEXT NOT NULL DEFAULT '{}',
    trend_implication TEXT NOT NULL DEFAULT '',
    risks_json        TEXT NOT NULL DEFAULT '[]',
    watch_next        TEXT NOT NULL DEFAULT '[]',
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    risk_classification TEXT NOT NULL DEFAULT 'none'
        CHECK(risk_classification IN ('none','hype','star_manipulation','license_issue','security_risk','unverified')),
    tier              TEXT NOT NULL DEFAULT 'B'
        CHECK(tier IN ('S','A','B','C','D')),
    confidence        REAL NOT NULL DEFAULT 0.5,
    model_used        TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rac_repo ON repo_analysis_cards(repo_full_name);
CREATE INDEX IF NOT EXISTS idx_rac_tier ON repo_analysis_cards(tier);

-- 4. repo_planning_briefs
-- Optional planning briefs for top-tier repos (O4).
CREATE TABLE IF NOT EXISTS repo_planning_briefs (
    brief_id          TEXT PRIMARY KEY,
    repo_full_name    TEXT NOT NULL,
    card_id           TEXT NOT NULL REFERENCES repo_analysis_cards(card_id),
    opportunity       TEXT NOT NULL DEFAULT '',
    user_pain         TEXT NOT NULL DEFAULT '',
    mvp_sketch        TEXT NOT NULL DEFAULT '',
    architecture_hint TEXT NOT NULL DEFAULT '',
    go_to_market      TEXT NOT NULL DEFAULT '',
    risks_json        TEXT NOT NULL DEFAULT '[]',
    validation_metrics TEXT NOT NULL DEFAULT '[]',
    model_used        TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rpb_repo ON repo_planning_briefs(repo_full_name);

-- 5. model_call_ledger
-- Tracks every model call for cost monitoring and audit (O3).
CREATE TABLE IF NOT EXISTS model_call_ledger (
    ledger_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_full_name    TEXT NOT NULL DEFAULT '',
    model             TEXT NOT NULL,
    provider          TEXT NOT NULL DEFAULT '',
    call_purpose      TEXT NOT NULL
        CHECK(call_purpose IN ('evidence_compression','analysis_card','planning_brief',
                               'why_hot_attribution','deep_analysis','counter_evidence')),
    input_type        TEXT NOT NULL DEFAULT 'project_reasoning_packet'
        CHECK(input_type IN ('project_reasoning_packet','raw_readme_bypass')),
    input_token_count INTEGER NOT NULL DEFAULT 0,
    output_token_count INTEGER NOT NULL DEFAULT 0,
    latency_ms        INTEGER NOT NULL DEFAULT 0,
    cost_estimate_usd REAL NOT NULL DEFAULT 0.0,
    evidence_atom_count INTEGER NOT NULL DEFAULT 0,
    success           INTEGER NOT NULL DEFAULT 1,
    error_message     TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mcl_repo ON model_call_ledger(repo_full_name);
CREATE INDEX IF NOT EXISTS idx_mcl_model ON model_call_ledger(model);
CREATE INDEX IF NOT EXISTS idx_mcl_purpose ON model_call_ledger(call_purpose);
CREATE INDEX IF NOT EXISTS idx_mcl_created ON model_call_ledger(created_at);

-- 6. daily_reports
-- Daily AI Influence report envelope and section data (O6).
CREATE TABLE IF NOT EXISTS daily_reports (
    report_id         TEXT PRIMARY KEY,
    report_date       TEXT NOT NULL,
    section_data_json TEXT NOT NULL DEFAULT '{}',
    repos_analyzed    INTEGER NOT NULL DEFAULT 0,
    premium_model_calls INTEGER NOT NULL DEFAULT 0,
    detector_alerts   INTEGER NOT NULL DEFAULT 0,
    evidence_atoms_total INTEGER NOT NULL DEFAULT 0,
    generated_at      TEXT NOT NULL,
    UNIQUE(report_date)
);

CREATE INDEX IF NOT EXISTS idx_dr_date ON daily_reports(report_date);

-- 7. weekly_reports
-- Weekly AI Influence report envelope and section data (O6).
CREATE TABLE IF NOT EXISTS weekly_reports (
    report_id         TEXT PRIMARY KEY,
    report_week       TEXT NOT NULL,
    section_data_json TEXT NOT NULL DEFAULT '{}',
    repos_analyzed    INTEGER NOT NULL DEFAULT 0,
    premium_model_calls INTEGER NOT NULL DEFAULT 0,
    deep_analysis_count INTEGER NOT NULL DEFAULT 0,
    detector_alerts_weekly INTEGER NOT NULL DEFAULT 0,
    evidence_atoms_total INTEGER NOT NULL DEFAULT 0,
    generated_at      TEXT NOT NULL,
    UNIQUE(report_week)
);

CREATE INDEX IF NOT EXISTS idx_wr_week ON weekly_reports(report_week);

-- 8. snapshot_percentiles
-- Per-repo velocity percentile within {topic, age_band, star_band} buckets (O2/O5).
CREATE TABLE IF NOT EXISTS snapshot_percentiles (
    percentile_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_full_name    TEXT NOT NULL,
    snapshot_date     TEXT NOT NULL,
    topic             TEXT NOT NULL DEFAULT 'untagged',
    age_band          TEXT NOT NULL
        CHECK(age_band IN ('<7d','8-30d','31-180d','181-365d','1y+')),
    star_band         TEXT NOT NULL
        CHECK(star_band IN ('<100','100-1k','1k-10k','10k+')),
    star_velocity_percentile REAL NOT NULL DEFAULT 0.0,
    bucket_peer_count INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    UNIQUE(repo_full_name, snapshot_date, topic, age_band, star_band)
);

CREATE INDEX IF NOT EXISTS idx_sp_repo ON snapshot_percentiles(repo_full_name);
CREATE INDEX IF NOT EXISTS idx_sp_bucket ON snapshot_percentiles(topic, age_band, star_band);

-- 9. alerts
-- Detector alerts from scoring-contract.md (O5).
-- Distinct from the existing hotspot_alerts table which uses different detector rules.
CREATE TABLE IF NOT EXISTS alerts (
    alert_id          TEXT PRIMARY KEY,
    detector          TEXT NOT NULL
        CHECK(detector IN ('sudden_hot','early_potential','foundation_infra_candidate',
                           'hype_or_noise','star_manipulation_suspicion',
                           'major_release_signal','cross_source_resonance')),
    repo_full_name    TEXT NOT NULL,
    triggered_at      TEXT NOT NULL,
    trigger_condition TEXT NOT NULL DEFAULT '',
    conditions_met_json TEXT NOT NULL DEFAULT '{}',
    supporting_evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    severity          TEXT NOT NULL
        CHECK(severity IN ('critical','high','medium','low','info')),
    recommended_action TEXT NOT NULL DEFAULT '',
    acknowledged      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_al_detector ON alerts(detector);
CREATE INDEX IF NOT EXISTS idx_al_repo ON alerts(repo_full_name);
CREATE INDEX IF NOT EXISTS idx_al_severity ON alerts(severity, triggered_at);
CREATE INDEX IF NOT EXISTS idx_al_triggered ON alerts(triggered_at);
"""

# Table names for verification
NEW_TABLES = (
    "repo_evidence_atoms",
    "project_reasoning_packets",
    "repo_analysis_cards",
    "repo_planning_briefs",
    "model_call_ledger",
    "daily_reports",
    "weekly_reports",
    "snapshot_percentiles",
    "alerts",
)


def run_migration(db_path: str | Path) -> dict[str, Any]:
    """Run the B1 migration on the given SQLite database.

    Returns a dict with migration results for verification.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    # Capture existing tables before migration
    existing_before = set(
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    )

    # Run migration
    conn.executescript(MIGRATION_SQL)
    conn.commit()

    # Capture tables after migration
    existing_after = set(
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    )

    # Verify all 9 new tables exist
    new_tables_found = []
    new_tables_missing = []
    for table in NEW_TABLES:
        if table in existing_after:
            new_tables_found.append(table)
        else:
            new_tables_missing.append(table)

    # Verify no existing tables were dropped
    dropped = existing_before - existing_after
    preserved = existing_before & existing_after

    # Get column info for each new table
    table_columns = {}
    for table in NEW_TABLES:
        if table in existing_after:
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            table_columns[table] = [
                {"name": col[1], "type": col[2], "notnull": bool(col[3])}
                for col in cols
            ]

    conn.close()

    return {
        "ok": len(new_tables_missing) == 0,
        "new_tables_found": new_tables_found,
        "new_tables_missing": new_tables_missing,
        "tables_before": sorted(existing_before),
        "tables_after": sorted(existing_after),
        "dropped_tables": sorted(dropped),
        "preserved_tables": sorted(preserved),
        "table_columns": table_columns,
    }


def verify_idempotent(db_path: str | Path) -> bool:
    """Run migration twice and verify results are identical."""
    result1 = run_migration(db_path)
    result2 = run_migration(db_path)
    return result1["tables_after"] == result2["tables_after"]


def get_new_table_names() -> tuple[str, ...]:
    """Return the names of the 9 new tables."""
    return NEW_TABLES
