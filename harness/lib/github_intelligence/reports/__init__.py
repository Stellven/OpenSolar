"""GitHub Project Intelligence — daily and weekly report generation.

Node: C4_cards_briefs_reports_pipeline
Write-scope: harness/lib/github_intelligence/reports/

S02 §A6 report generation flow:
1. Query analysis cards ordered by heat_score
2. Run detectors → alerts table
3. Compose sections
4. Insert into report tables (daily_reports / weekly_reports)
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))

from github_intelligence.schema import (
    AnalysisCard,
    DailyReport,
    WeeklyReport,
    Detection,
    apply_schema,
    insert_row,
    fetch_rows,
    utc_now_iso,
)


# ---------------------------------------------------------------------------
# Daily Report
# ---------------------------------------------------------------------------


def generate_daily_report(
    date: str,
    conn: sqlite3.Connection,
    model_used: str | None = None,
) -> DailyReport:
    """Generate a DailyReport for `date` from verified analysis cards + alerts.

    Sections populated:
    - sudden_hot: cards with heat_score ≥ 80
    - early_potential: cards with potential_score ≥ 75 AND heat_score < 80
    - tech_radar: top-5 cards by heat_score (all)
    - community_signals: alerts from today
    - planning_suggestions: cards with product_planning_ideas
    - watchlist: cards with watch_next items
    """
    # Fetch verified cards for this date
    rows = fetch_rows(conn, AnalysisCard.TABLE, "verified=1 AND analysis_date=?", (date,))
    cards = [AnalysisCard.from_row(r) for r in rows]
    cards.sort(key=lambda c: c.heat_score or 0.0, reverse=True)

    # Fetch today's alerts
    alert_rows = fetch_rows(
        conn, Detection.TABLE, "created_at LIKE ?", (f"{date}%",)
    )

    sudden_hot: list[dict[str, Any]] = []
    early_potential: list[dict[str, Any]] = []
    tech_radar: list[dict[str, Any]] = []
    planning_suggestions: list[dict[str, Any]] = []
    watchlist: list[dict[str, Any]] = []

    for card in cards:
        entry = {
            "repo": card.full_name,
            "heat_score": card.heat_score,
            "potential_score": card.potential_score,
            "positioning": card.project_positioning,
            "why_hot": card.why_it_is_hot,
        }
        if (card.heat_score or 0) >= 80:
            sudden_hot.append(entry)
        elif (card.potential_score or 0) >= 75:
            early_potential.append(entry)

        if len(tech_radar) < 5:
            tech_radar.append({
                "repo": card.full_name,
                "heat_score": card.heat_score,
                "core_idea": card.core_technical_idea,
                "trend_implication": card.trend_implication,
            })

        if card.product_planning_ideas:
            planning_suggestions.append({
                "repo": card.full_name,
                "suggestions": card.product_planning_ideas,
                "priority": "high" if (card.heat_score or 0) >= 80 else "medium",
            })

        if card.watch_next:
            watchlist.append({
                "repo": card.full_name,
                "reason": card.why_it_is_hot,
                "next_check": card.watch_next[0] if card.watch_next else None,
            })

    community_signals = [
        {
            "source": r.get("detector_name"),
            "repo": r.get("full_name"),
            "signal_type": r.get("severity"),
            "title": r.get("title"),
        }
        for r in alert_rows
    ]

    # Compose core_judgment
    n_hot = len(sudden_hot)
    n_ep = len(early_potential)
    core_judgment = (
        f"{date}: {n_hot} sudden-hot repo{'s' if n_hot != 1 else ''}, "
        f"{n_ep} early-potential repo{'s' if n_ep != 1 else ''} identified."
    )

    report = DailyReport(
        report_date=date,
        core_judgment=core_judgment,
        sudden_hot=sudden_hot,
        early_potential=early_potential,
        tech_radar=tech_radar,
        community_signals=community_signals,
        planning_suggestions=planning_suggestions,
        watchlist=watchlist,
        model_used=model_used,
    )
    insert_row(conn, report.TABLE, report.to_row())
    conn.commit()
    return report


# ---------------------------------------------------------------------------
# Weekly Report
# ---------------------------------------------------------------------------


def generate_weekly_report(
    week_start: str,
    conn: sqlite3.Connection,
) -> WeeklyReport:
    """Generate a WeeklyReport aggregating daily reports for Mon–Sun.

    Sections:
    - top5_trends: 5 most common tech themes across daily sudden_hot cards
    - top10_projects: top-10 verified cards by heat_score for the week
    - deep_analysis: full card entries for top-10
    - planning_pool: all planning briefs for the week
    - next_week_metrics: derived from watchlist items
    """
    from datetime import datetime, timedelta

    try:
        monday = datetime.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        monday = datetime.now()
    dates = [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    # Collect daily reports
    daily_rows: list[DailyReport] = []
    for d in dates:
        rows = fetch_rows(conn, DailyReport.TABLE, "report_date=?", (d,))
        if rows:
            daily_rows.append(DailyReport.from_row(rows[0]))

    # Top-10 verified cards across the week
    all_card_rows = fetch_rows(conn, AnalysisCard.TABLE, "verified=1", ())
    all_cards = [AnalysisCard.from_row(r) for r in all_card_rows
                 if r.get("analysis_date", "") in dates]
    all_cards.sort(key=lambda c: c.heat_score or 0.0, reverse=True)
    top10 = all_cards[:10]

    # Aggregate sudden_hot repos for trend extraction
    repo_counts: dict[str, int] = {}
    for dr in daily_rows:
        for item in dr.sudden_hot:
            repo = item.get("repo", "")
            repo_counts[repo] = repo_counts.get(repo, 0) + 1

    top5_trends = [
        {"trend": repo, "frequency": cnt}
        for repo, cnt in sorted(repo_counts.items(), key=lambda x: -x[1])[:5]
    ]

    top10_projects = [
        {
            "repo": c.full_name,
            "heat_score": c.heat_score,
            "potential_score": c.potential_score,
            "positioning": c.project_positioning,
        }
        for c in top10
    ]

    deep_analysis = [
        {
            "repo": c.full_name,
            "what_it_does": c.what_it_does,
            "why_hot": c.why_it_is_hot,
            "core_idea": c.core_technical_idea,
            "scores": {
                "heat": c.heat_score,
                "potential": c.potential_score,
                "tech_depth": c.technical_depth_score,
                "community": c.community_health_score,
            },
            "product_ideas": c.product_planning_ideas,
            "risks": c.risks,
        }
        for c in top10
    ]

    # Planning pool from briefs table
    from github_intelligence.schema import PlanningBrief
    brief_rows = fetch_rows(conn, PlanningBrief.TABLE)
    planning_pool = [
        {
            "repo": r.get("full_name"),
            "brief_id": r.get("brief_id"),
            "opportunity": r.get("opportunity_summary"),
            "next_steps": json.loads(r.get("next_steps") or "[]"),
        }
        for r in brief_rows
        if any(
            r.get("full_name") == c.full_name for c in top10
        )
    ]

    # next_week_metrics from watch_next of top cards
    next_week_metrics: list[str] = []
    for c in top10:
        for item in (c.watch_next or []):
            if item not in next_week_metrics:
                next_week_metrics.append(item)
    next_week_metrics = next_week_metrics[:10]

    one_sentence = (
        f"Week of {week_start}: {len(top10)} high-value repos tracked, "
        f"{len(top5_trends)} dominant trends identified."
    )

    report = WeeklyReport(
        week_start=week_start,
        one_sentence=one_sentence,
        top5_trends=top5_trends,
        top10_projects=top10_projects,
        deep_analysis=deep_analysis,
        planning_pool=planning_pool,
        next_week_metrics=next_week_metrics,
    )
    insert_row(conn, report.TABLE, report.to_row())
    conn.commit()
    return report


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _self_test() -> dict[str, Any]:
    import tempfile

    metrics: dict[str, Any] = {"tests_run": 0, "tests_passed": 0, "tests": []}

    def _ok(name: str) -> None:
        metrics["tests_run"] += 1
        metrics["tests_passed"] += 1
        metrics["tests"].append(name)

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        db_path = tf.name

    try:
        conn = sqlite3.connect(db_path)
        apply_schema(conn)

        date = "2026-05-27"

        # Seed some verified cards
        from github_intelligence.schema import AnalysisCard as AC
        from github_intelligence.cards import create_analysis_card, verify_card

        cards_data = [
            ("owner/hot-repo", 92.0, 88.0, 70.0, 80.0, ["Watch acceleration"], []),
            ("owner/early-repo", 55.0, 86.0, 50.0, 40.0, [], ["Check growth"]),
            ("owner/normal-repo", 40.0, 50.0, 45.0, 55.0, [], []),
        ]
        for full_name, heat, potential, tech_depth, community, ppi, watch_next in cards_data:
            card = create_analysis_card(
                full_name=full_name,
                analysis_date=date,
                evidence_ids=["ev1", "ev2", "ev3"],
                heat_score=heat,
                potential_score=potential,
                technical_depth_score=tech_depth,
                community_health_score=community,
                product_planning_ideas=ppi,
                watch_next=watch_next,
                why_it_is_hot="test why",
                conn=conn,
            )
            verify_card(card.analysis_id, conn)

        # 1. generate_daily_report produces correct sections
        report = generate_daily_report(date, conn)
        assert report.report_date == date
        _ok("daily_report.report_date_set")

        assert len(report.sudden_hot) >= 1
        hot_repos = [r["repo"] for r in report.sudden_hot]
        assert "owner/hot-repo" in hot_repos
        _ok("daily_report.sudden_hot_populated")

        assert len(report.early_potential) >= 1
        ep_repos = [r["repo"] for r in report.early_potential]
        assert "owner/early-repo" in ep_repos
        _ok("daily_report.early_potential_populated")

        assert len(report.tech_radar) <= 5
        _ok("daily_report.tech_radar_max5")

        assert report.core_judgment is not None and len(report.core_judgment) > 0
        _ok("daily_report.core_judgment_nonempty")

        # 2. daily report persisted to DB
        stored = fetch_rows(conn, DailyReport.TABLE, "report_date=?", (date,))
        assert len(stored) == 1
        _ok("daily_report.persisted_to_db")

        # 3. generate_weekly_report
        week_report = generate_weekly_report("2026-05-25", conn)
        assert week_report.week_start == "2026-05-25"
        _ok("weekly_report.week_start_set")

        assert isinstance(week_report.top10_projects, list)
        _ok("weekly_report.top10_is_list")

        assert week_report.one_sentence is not None
        _ok("weekly_report.one_sentence_set")

        # 4. weekly report persisted to DB
        stored_w = fetch_rows(conn, WeeklyReport.TABLE, "week_start=?", ("2026-05-25",))
        assert len(stored_w) == 1
        _ok("weekly_report.persisted_to_db")

        # 5. required sections present on DailyReport
        required_daily = ["sudden_hot", "early_potential", "tech_radar",
                          "community_signals", "planning_suggestions", "watchlist"]
        for s in required_daily:
            assert hasattr(report, s)
        _ok("daily_report.all_required_sections_present")

        # 6. required sections present on WeeklyReport
        required_weekly = ["one_sentence", "top5_trends", "top10_projects",
                           "deep_analysis", "planning_pool", "next_week_metrics"]
        for s in required_weekly:
            assert hasattr(week_report, s)
        _ok("weekly_report.all_required_sections_present")

        conn.close()
    finally:
        _os.unlink(db_path)

    return metrics


if __name__ == "__main__":
    m = _self_test()
    print(json.dumps(m, indent=2))
    if m["tests_run"] != m["tests_passed"]:
        _sys.exit(1)
