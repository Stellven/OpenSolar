"""Weekly report generator for GitHub Intelligence."""
from __future__ import annotations

import hashlib
import html
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def week_start(value: str | date) -> date:
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return d - timedelta(days=d.weekday())


def week_key(value: str | date) -> str:
    return week_start(value).isoformat()


def _report_id(report_week: str) -> str:
    return "weekly_" + hashlib.sha256(report_week.encode("utf-8")).hexdigest()[:16]


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _date_range(report_week: str) -> tuple[str, str]:
    start = week_start(report_week)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def build_weekly_sections(conn: sqlite3.Connection, report_week: str) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    start, end = _date_range(report_week)
    daily_rows = conn.execute(
        """SELECT * FROM daily_reports
           WHERE report_date BETWEEN ? AND ?
           ORDER BY report_date ASC""",
        (start, end),
    ).fetchall()
    briefs = conn.execute(
        """SELECT b.brief_id, b.repo_full_name, b.card_id, b.opportunity, b.mvp_sketch,
                  b.validation_metrics, c.tier, c.confidence, c.scores_json
           FROM repo_planning_briefs b
           JOIN repo_analysis_cards c ON c.card_id = b.card_id
           WHERE COALESCE(c.verified, 0) = 1
           ORDER BY c.confidence DESC, b.repo_full_name ASC"""
    ).fetchall()

    trend_scores: dict[str, float] = {}
    for row in daily_rows:
        sections = _loads(row["section_data_json"], {})
        for item in sections.get("sudden_hot", []) or []:
            repo = str(item.get("repo_full_name") or "")
            if repo:
                trend_scores[repo] = max(trend_scores.get(repo, 0.0), float(item.get("heat_score") or 0.0))
    top5_trends = sorted(
        [{"repo_full_name": repo, "heat_score": score} for repo, score in trend_scores.items()],
        key=lambda item: item["heat_score"],
        reverse=True,
    )[:5]
    top10_projects = [
        {
            "repo_full_name": row["repo_full_name"],
            "tier": row["tier"],
            "confidence": row["confidence"],
            "opportunity": row["opportunity"],
        }
        for row in briefs[:10]
    ]
    sections = {
        "weekly_summary": {
            "report_week": week_key(report_week),
            "daily_report_count": len(daily_rows),
            "repos_analyzed": sum(int(row["repos_analyzed"] or 0) for row in daily_rows),
        },
        "top5_trends": top5_trends,
        "top10_projects": top10_projects,
        "planning_pool": [dict(row) for row in briefs],
        "deep_analysis": {
            "count": len(briefs),
            "method": "verified analysis cards plus planning briefs",
        },
        "risk_review": {
            "detector_alerts_weekly": sum(int(row["detector_alerts"] or 0) for row in daily_rows),
        },
        "evidence_health": {
            "evidence_atoms_total": sum(int(row["evidence_atoms_total"] or 0) for row in daily_rows),
            "generated_at": _now(),
        },
    }
    return sections


def render_weekly_report_html(sections: dict[str, Any]) -> str:
    title = html.escape(f"AI Influence Weekly {sections.get('weekly_summary', {}).get('report_week', '')}".strip())
    parts = ["<!doctype html>", "<html><head><meta charset='utf-8'><title>AI Influence Weekly</title></head><body>", f"<h1>{title}</h1>"]
    for name, data in sections.items():
        parts.append(f"<section><h2>{html.escape(name.replace('_', ' ').title())}</h2>")
        parts.append(f"<pre>{html.escape(json.dumps(data, ensure_ascii=False, indent=2))}</pre>")
        parts.append("</section>")
    parts.append("</body></html>")
    return "\n".join(parts)


def generate_weekly_report(conn: sqlite3.Connection, report_week: str | None = None) -> dict[str, Any]:
    report_week = week_key(report_week or date.today())
    sections = build_weekly_sections(conn, report_week)
    daily_count = int(sections["weekly_summary"]["daily_report_count"])
    repos_analyzed = int(sections["weekly_summary"]["repos_analyzed"])
    detector_alerts = int(sections["risk_review"]["detector_alerts_weekly"])
    evidence_atoms = int(sections["evidence_health"]["evidence_atoms_total"])
    payload = {
        "report_id": _report_id(report_week),
        "report_week": report_week,
        "section_data_json": json.dumps(sections, ensure_ascii=False),
        "repos_analyzed": repos_analyzed,
        "premium_model_calls": daily_count,
        "deep_analysis_count": int(sections["deep_analysis"]["count"]),
        "detector_alerts_weekly": detector_alerts,
        "evidence_atoms_total": evidence_atoms,
        "generated_at": _now(),
        "html": render_weekly_report_html(sections),
    }
    conn.execute(
        """INSERT OR REPLACE INTO weekly_reports
           (report_id, report_week, section_data_json, repos_analyzed, premium_model_calls,
            deep_analysis_count, detector_alerts_weekly, evidence_atoms_total, generated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload["report_id"], payload["report_week"], payload["section_data_json"],
            payload["repos_analyzed"], payload["premium_model_calls"], payload["deep_analysis_count"],
            payload["detector_alerts_weekly"], payload["evidence_atoms_total"], payload["generated_at"],
        ),
    )
    conn.commit()
    return payload


__all__ = ["build_weekly_sections", "generate_weekly_report", "render_weekly_report_html", "week_key"]
