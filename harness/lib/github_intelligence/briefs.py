"""Planning brief generator for GitHub Intelligence analysis cards."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _brief_id(repo_full_name: str, card_id: str) -> str:
    digest = hashlib.sha256(f"{repo_full_name}\0{card_id}".encode("utf-8")).hexdigest()[:24]
    return f"brief_{digest}"


def _latest_verified_card(conn: sqlite3.Connection, repo_full_name: str) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """SELECT * FROM repo_analysis_cards
           WHERE repo_full_name = ? AND COALESCE(verified, 0) = 1
           ORDER BY updated_at DESC, created_at DESC LIMIT 1""",
        (repo_full_name,),
    ).fetchone()


def generate_planning_brief(
    conn: sqlite3.Connection,
    repo_full_name: str,
    *,
    model_used: str = "local_heuristic_planner",
) -> dict[str, Any]:
    """Create or update a planning brief from the latest verified analysis card.

    Raises ValueError when no verified analysis card exists. This enforces the
    B13 contract that planning briefs are generated only from verified cards.
    """
    card = _latest_verified_card(conn, repo_full_name)
    if card is None:
        raise ValueError(f"No verified analysis card found for {repo_full_name}")

    card_id = str(card["card_id"])
    scores = _json_loads(card["scores_json"], {})
    risks = _json_loads(card["risks_json"], [])
    watch_next = _json_loads(card["watch_next"], [])
    target_users = _json_loads(card["target_users"], [])
    why_hot = _json_loads(card["why_hot_facts"], [])

    brief = {
        "brief_id": _brief_id(repo_full_name, card_id),
        "repo_full_name": repo_full_name,
        "card_id": card_id,
        "opportunity": f"Build around {card['positioning']} for {', '.join(target_users[:2]) or 'developer users'}.",
        "user_pain": f"Users need a clearer path to evaluate and adopt {repo_full_name}: {card['what_it_does']}.",
        "mvp_sketch": f"Package the core idea ({card['core_technical_idea']}) into a small workflow with onboarding, examples, and measurable adoption hooks.",
        "architecture_hint": f"Use a thin integration layer around the repository, backed by evidence-linked analysis and score signals: {json.dumps(scores, ensure_ascii=False)[:300]}.",
        "go_to_market": f"Target {', '.join(target_users) or 'technical adopters'}; lead with evidence: {'; '.join(str(x) for x in why_hot[:3])}.",
        "risks_json": json.dumps(risks, ensure_ascii=False),
        "validation_metrics": json.dumps(watch_next or ["weekly active adopters", "integration success rate", "issue response latency"], ensure_ascii=False),
        "model_used": model_used,
        "created_at": _now(),
    }

    required = [
        "brief_id", "repo_full_name", "card_id", "opportunity", "user_pain",
        "mvp_sketch", "architecture_hint", "go_to_market", "risks_json",
        "validation_metrics", "model_used", "created_at",
    ]
    missing = [key for key in required if brief.get(key) in (None, "", [], {})]
    if missing:
        raise ValueError(f"Planning brief missing required fields: {missing}")

    conn.execute(
        """INSERT OR REPLACE INTO repo_planning_briefs
           (brief_id, repo_full_name, card_id, opportunity, user_pain, mvp_sketch,
            architecture_hint, go_to_market, risks_json, validation_metrics,
            model_used, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        tuple(brief[key] for key in required),
    )
    conn.commit()
    return brief


__all__ = ["generate_planning_brief"]
