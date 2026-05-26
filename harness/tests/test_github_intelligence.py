from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from github_intelligence.briefs import generate_planning_brief
from github_intelligence.reports.daily import generate_daily_report
from github_intelligence.reports.weekly import generate_weekly_report
from github_intelligence.pipeline import run_daily_pipeline


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE repo_evidence_atoms (atom_id TEXT PRIMARY KEY, repo_full_name TEXT NOT NULL);
        CREATE TABLE repo_analysis_cards (
            card_id TEXT PRIMARY KEY, repo_full_name TEXT NOT NULL,
            positioning TEXT NOT NULL DEFAULT '', what_it_does TEXT NOT NULL DEFAULT '',
            target_users TEXT NOT NULL DEFAULT '[]', core_technical_idea TEXT NOT NULL DEFAULT '',
            why_hot_facts TEXT NOT NULL DEFAULT '[]', scores_json TEXT NOT NULL DEFAULT '{}',
            trend_implication TEXT NOT NULL DEFAULT '', risks_json TEXT NOT NULL DEFAULT '[]',
            watch_next TEXT NOT NULL DEFAULT '[]', evidence_ids_json TEXT NOT NULL DEFAULT '[]',
            risk_classification TEXT NOT NULL DEFAULT 'none', tier TEXT NOT NULL DEFAULT 'B',
            confidence REAL NOT NULL DEFAULT 0.5, model_used TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, verified INTEGER DEFAULT 0
        );
        CREATE TABLE repo_planning_briefs (
            brief_id TEXT PRIMARY KEY, repo_full_name TEXT NOT NULL, card_id TEXT NOT NULL,
            opportunity TEXT NOT NULL DEFAULT '', user_pain TEXT NOT NULL DEFAULT '',
            mvp_sketch TEXT NOT NULL DEFAULT '', architecture_hint TEXT NOT NULL DEFAULT '',
            go_to_market TEXT NOT NULL DEFAULT '', risks_json TEXT NOT NULL DEFAULT '[]',
            validation_metrics TEXT NOT NULL DEFAULT '[]', model_used TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE alerts (alert_id TEXT PRIMARY KEY, detector TEXT NOT NULL, repo_full_name TEXT NOT NULL, triggered_at TEXT NOT NULL, trigger_condition TEXT NOT NULL DEFAULT '', severity TEXT NOT NULL, acknowledged INTEGER DEFAULT 0);
        CREATE TABLE model_call_ledger (created_at TEXT NOT NULL);
        CREATE TABLE daily_reports (report_id TEXT PRIMARY KEY, report_date TEXT NOT NULL UNIQUE, section_data_json TEXT NOT NULL DEFAULT '{}', repos_analyzed INTEGER NOT NULL DEFAULT 0, premium_model_calls INTEGER NOT NULL DEFAULT 0, detector_alerts INTEGER NOT NULL DEFAULT 0, evidence_atoms_total INTEGER NOT NULL DEFAULT 0, generated_at TEXT NOT NULL);
        CREATE TABLE weekly_reports (report_id TEXT PRIMARY KEY, report_week TEXT NOT NULL UNIQUE, section_data_json TEXT NOT NULL DEFAULT '{}', repos_analyzed INTEGER NOT NULL DEFAULT 0, premium_model_calls INTEGER NOT NULL DEFAULT 0, deep_analysis_count INTEGER NOT NULL DEFAULT 0, detector_alerts_weekly INTEGER NOT NULL DEFAULT 0, evidence_atoms_total INTEGER NOT NULL DEFAULT 0, generated_at TEXT NOT NULL);
        """
    )
    return conn


def seed_five_repos(conn: sqlite3.Connection):
    for i in range(5):
        repo = f"org/repo{i}"
        ev_ids = []
        for j in range(3):
            atom = f"ev_{i}_{j}"
            ev_ids.append(atom)
            conn.execute("INSERT INTO repo_evidence_atoms VALUES (?, ?)", (atom, repo))
        conn.execute(
            """INSERT INTO repo_analysis_cards
               (card_id, repo_full_name, positioning, what_it_does, target_users, core_technical_idea,
                why_hot_facts, scores_json, risks_json, watch_next, evidence_ids_json, tier, confidence,
                model_used, created_at, updated_at, verified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                f"card_{i}", repo, "infra platform", "does work", json.dumps(["engineers"]),
                "architecture", json.dumps(["hot"]), json.dumps({"heat_score": 100-i}),
                json.dumps([]), json.dumps(["watch"]), json.dumps(ev_ids), "A", 0.9,
                "test", "2026-05-26T00:00:00Z", "2026-05-26T00:00:00Z",
            ),
        )
    conn.execute("INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?, 0)", ("a1", "cross_source_resonance", "org/repo0", "2026-05-26T10:00:00Z", "hit", "high"))
    conn.commit()


def test_five_repos_flow_through_reports_and_pipeline_consistency():
    conn = make_conn()
    seed_five_repos(conn)
    for i in range(5):
        generate_planning_brief(conn, f"org/repo{i}")
    daily = generate_daily_report(conn, "2026-05-26")
    weekly = generate_weekly_report(conn, "2026-05-26")
    pipeline = run_daily_pipeline(dry_run=True)

    assert pipeline.status == "passed"
    assert conn.execute("SELECT COUNT(*) FROM repo_planning_briefs").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM daily_reports").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM weekly_reports").fetchone()[0] == 1
    assert json.loads(daily["section_data_json"])["evidence_health"]["verified_cards"] == 5
    assert json.loads(weekly["section_data_json"])["weekly_summary"]["daily_report_count"] == 1
    for row in conn.execute("SELECT evidence_ids_json FROM repo_analysis_cards"):
        for atom_id in json.loads(row[0]):
            assert conn.execute("SELECT 1 FROM repo_evidence_atoms WHERE atom_id=?", (atom_id,)).fetchone()
