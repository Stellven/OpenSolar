"""Daily report generator for GitHub Intelligence."""
from __future__ import annotations

import hashlib
import html
import json
import sqlite3
from datetime import date, datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _report_id(report_date: str) -> str:
    return "daily_" + hashlib.sha256(report_date.encode("utf-8")).hexdigest()[:16]


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def build_daily_sections(conn: sqlite3.Connection, report_date: str) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    cards = conn.execute(
        """SELECT card_id, repo_full_name, positioning, what_it_does, why_hot_facts,
                  scores_json, tier, confidence, created_at
           FROM repo_analysis_cards
           WHERE COALESCE(verified, 0) = 1
           ORDER BY datetime(created_at) DESC, repo_full_name ASC"""
    ).fetchall()
    alerts = conn.execute(
        """SELECT alert_id, detector, repo_full_name, severity, trigger_condition, triggered_at
           FROM alerts
           WHERE substr(triggered_at, 1, 10) = ?
           ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END,
                    triggered_at DESC""",
        (report_date,),
    ).fetchall()

    def heat(row: sqlite3.Row) -> float:
        return float((_loads(row["scores_json"], {}) or {}).get("heat_score") or 0.0)

    sudden_hot = sorted(
        [row for row in cards if heat(row) > 0 or str(row["tier"]) in {"S", "A"}],
        key=heat,
        reverse=True,
    )
    top_cards = cards[:10]
    sections = {
        "executive_summary": {
            "report_date": report_date,
            "headline": f"{len(cards)} verified analysis cards and {len(alerts)} detector alerts reviewed.",
        },
        "sudden_hot": [
            {"repo_full_name": row["repo_full_name"], "heat_score": heat(row), "tier": row["tier"]}
            for row in sudden_hot
        ],
        "early_potential": [
            {"repo_full_name": row["repo_full_name"], "confidence": row["confidence"], "tier": row["tier"]}
            for row in cards if str(row["tier"]) in {"A", "B"}
        ],
        "foundation_infra": [
            {"repo_full_name": row["repo_full_name"], "positioning": row["positioning"]}
            for row in cards if "infra" in (row["positioning"] or "").lower() or "platform" in (row["positioning"] or "").lower()
        ],
        "cross_source_resonance": [dict(row) for row in alerts if row["detector"] == "cross_source_resonance"],
        "risk_watch": [dict(row) for row in alerts if row["severity"] in {"critical", "high"}],
        "planning_pool": [
            {"repo_full_name": row["repo_full_name"], "what_it_does": row["what_it_does"], "why_hot_facts": _loads(row["why_hot_facts"], [])}
            for row in top_cards
        ],
        "evidence_health": {
            "verified_cards": len(cards),
            "alerts": len(alerts),
            "generated_at": _now(),
        },
    }
    return sections


def render_daily_report_html(sections: dict[str, Any]) -> str:
    title = html.escape(str(sections.get("executive_summary", {}).get("headline", "AI Influence Daily Report")))
    parts = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'><title>AI Influence Daily</title>",
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;line-height:1.45}section{margin:18px 0}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:6px;text-align:left}</style>",
        "</head><body>",
        f"<h1>{title}</h1>",
    ]
    for name, data in sections.items():
        parts.append(f"<section><h2>{html.escape(name.replace('_', ' ').title())}</h2>")
        if isinstance(data, list):
            parts.append("<ul>")
            for item in data:
                parts.append(f"<li><pre>{html.escape(json.dumps(item, ensure_ascii=False, indent=2))}</pre></li>")
            parts.append("</ul>")
        else:
            parts.append(f"<pre>{html.escape(json.dumps(data, ensure_ascii=False, indent=2))}</pre>")
        parts.append("</section>")
    parts.append("</body></html>")
    return "\n".join(parts)


def generate_daily_report(conn: sqlite3.Connection, report_date: str | None = None) -> dict[str, Any]:
    report_date = report_date or date.today().isoformat()
    sections = build_daily_sections(conn, report_date)
    section_json = json.dumps(sections, ensure_ascii=False)
    premium_calls = conn.execute("SELECT COUNT(*) FROM model_call_ledger WHERE substr(created_at,1,10)=?", (report_date,)).fetchone()[0]
    evidence_total = conn.execute("SELECT COUNT(*) FROM repo_evidence_atoms").fetchone()[0]
    detector_alerts = len(sections["risk_watch"]) + len(sections["cross_source_resonance"])
    payload = {
        "report_id": _report_id(report_date),
        "report_date": report_date,
        "section_data_json": section_json,
        "repos_analyzed": len({item.get("repo_full_name") for item in sections["planning_pool"]}),
        "premium_model_calls": int(premium_calls or 0),
        "detector_alerts": int(detector_alerts),
        "evidence_atoms_total": int(evidence_total or 0),
        "generated_at": _now(),
        "html": render_daily_report_html(sections),
    }
    conn.execute(
        """INSERT OR REPLACE INTO daily_reports
           (report_id, report_date, section_data_json, repos_analyzed, premium_model_calls,
            detector_alerts, evidence_atoms_total, generated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload["report_id"], payload["report_date"], payload["section_data_json"],
            payload["repos_analyzed"], payload["premium_model_calls"], payload["detector_alerts"],
            payload["evidence_atoms_total"], payload["generated_at"],
        ),
    )
    conn.commit()
    return payload


__all__ = ["build_daily_sections", "generate_daily_report", "render_daily_report_html"]
