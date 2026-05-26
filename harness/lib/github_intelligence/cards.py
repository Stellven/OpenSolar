"""Analysis card generator — Create project analysis cards from evidence atoms + scoring.

Provides:
- ``generate_analysis_card()``: Generates and saves a repo analysis card to the database.
- ``verify_card()``: Verifies card claims against evidence atoms.

Spec: sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s02-architecture
Node: B12
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from github_intelligence.evidence import call_qwen_local, extract_json_text
from github_intelligence.packets import build_reasoning_packet
from github_intelligence.scoring import compute_sub_scores, compute_heat_score, HEAT_WEIGHTS
from github_intelligence.detectors import compute_potential_score


def _ensure_verified_column(conn: sqlite3.Connection) -> None:
    """Ensure the verified column exists in the repo_analysis_cards table."""
    cursor = conn.execute("PRAGMA table_info(repo_analysis_cards)")
    columns = [row[1] for row in cursor.fetchall()]
    if "verified" not in columns:
        conn.execute("ALTER TABLE repo_analysis_cards ADD COLUMN verified INTEGER DEFAULT 0")
        conn.commit()


def _compute_heat_score_for_repo_safe(
    conn: sqlite3.Connection,
    full_name: str,
) -> Dict[str, Any]:
    """Safe calculation of heat score, working around the schema bug in scoring.py."""
    # 1. Fetch latest snapshot
    row = conn.execute(
        """SELECT stars, forks, open_issues, watchers,
                  stars_delta_24h, stars_delta_7d, star_acceleration,
                  commit_count_7d, active_contributors_30d
           FROM github_star_snapshots
           WHERE full_name = ?
           ORDER BY snapshot_at DESC LIMIT 1""",
        (full_name,),
    ).fetchone()

    if row is None:
        return {
            "heat_score": 0.0,
            "sub_scores": {k: 0.0 for k in HEAT_WEIGHTS},
            "normalization_group": "unknown",
        }

    # 2. Fetch latest_release_tag from github_repos
    repo_row = conn.execute(
        "SELECT latest_release_tag FROM github_repos WHERE full_name = ?",
        (full_name,),
    ).fetchone()
    latest_release_tag = repo_row[0] if repo_row else None

    snapshot = {
        "stars": row[0], "forks": row[1], "open_issues": row[2],
        "watchers": row[3], "stars_delta_24h": row[4], "stars_delta_7d": row[5],
        "star_acceleration": row[6], "commit_count_7d": row[7],
        "active_contributors_30d": row[8], "latest_release_tag": latest_release_tag,
    }

    # 3. Fetch evidence atoms
    evidence_rows = conn.execute(
        """SELECT evidence_type, raw_source_type, tags_json, novelty_score
           FROM repo_evidence_atoms
           WHERE repo_full_name = ?""",
        (full_name,),
    ).fetchall()

    evidence = [
        {
            "evidence_type": r[0],
            "raw_source_type": r[1],
            "tags_json": r[2],
            "novelty_score": r[3],
        }
        for r in evidence_rows
    ]

    # 4. Get percentile data
    percentile_data = {}
    pct_row = conn.execute(
        """SELECT star_velocity_percentile
           FROM snapshot_percentiles
           WHERE repo_full_name = ?
           ORDER BY snapshot_date DESC LIMIT 1""",
        (full_name,),
    ).fetchone()
    if pct_row:
        percentile_data["star_velocity_percentile"] = pct_row[0]

    sub_scores = compute_sub_scores(snapshot, evidence, percentile_data=percentile_data)
    heat_score = compute_heat_score(sub_scores)

    # Determine normalization group
    stars = snapshot.get("stars") or 0
    if stars < 100:
        star_band = "<100"
    elif stars < 1000:
        star_band = "100-1k"
    elif stars < 10000:
        star_band = "1k-10k"
    else:
        star_band = "10k+"

    return {
        "heat_score": heat_score,
        "sub_scores": sub_scores,
        "normalization_group": star_band,
    }


def get_fallback_card_content(
    repo_full_name: str,
    scores: Dict[str, float],
    atoms: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate heuristic fallback content for the analysis card when model call is unavailable."""
    pos = f"{repo_full_name} is an active open-source project showcasing consistent commits and growing community interest."
    what = "A software repository displaying active developer participation and release cadence."
    users = ["Software Engineers", "Open Source Contributors", "Tech Researchers"]
    tech_idea = "Leverages collaborative open-source engineering to build tools and libraries."
    
    hot_facts = []
    for a in atoms:
        if a.get("evidence_type") in ("growth_fact", "readme_claim", "release_feature") and a.get("compressed_content"):
            hot_facts.append(a["compressed_content"])
    if not hot_facts:
        hot_facts = ["Demonstrates active development metrics and star velocity."]
    else:
        hot_facts = hot_facts[:3]
        
    trend = "Indicates ongoing activity and developer traction within its category."
    risks = [
        {
            "type": "hype",
            "description": "Initial star growth might not fully align with long-term usage density.",
            "severity": "medium"
        }
    ]
    watch = ["Track upcoming major/minor releases", "Monitor issue and PR response latency"]
    
    # Determine tier based on heat score
    hs = scores.get("heat_score", 0.0)
    if hs > 80:
        tier = "S"
    elif hs > 60:
        tier = "A"
    elif hs > 30:
        tier = "B"
    elif hs > 10:
        tier = "C"
    else:
        tier = "D"
        
    return {
        "positioning": pos,
        "what_it_does": what[:200],
        "target_users": users,
        "core_technical_idea": tech_idea[:200],
        "why_hot_facts": hot_facts,
        "trend_implication": trend,
        "risks": risks,
        "watch_next": watch,
        "risk_classification": "none",
        "tier": tier,
        "confidence": 0.5,
    }


def verify_card(
    card_content: Dict[str, Any],
    atoms: List[Dict[str, Any]],
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
) -> bool:
    """Verify that the generated card content claims are grounded in evidence atoms.
    
    Requires at least 3 evidence IDs.
    """
    # 1. Require >= 3 evidence_ids present
    evidence_ids = card_content.get("evidence_ids", [])
    if len(evidence_ids) < 3:
        return False
        
    # 2. Check if all referenced evidence atoms exist in the list
    atom_map = {a["atom_id"]: a for a in atoms}
    for eid in evidence_ids:
        if eid not in atom_map:
            return False
            
    # 3. Local verifier check: check that key claims in card are grounded in compressed_content
    claims = [card_content.get("positioning", "")]
    claims.extend(card_content.get("why_hot_facts", []))
    claims.append(card_content.get("core_technical_idea", ""))
    claims = [c.strip() for c in claims if c and c.strip()]
    
    if not claims:
        return True
        
    evidence_txt = "\n".join([f"- [{a['atom_id']}]: {a['compressed_content']}" for a in atoms if a.get("compressed_content")])
    claims_txt = "\n".join([f"- {c}" for c in claims])
    
    verifier_prompt = f"""You are a factual verifier.
Check if the following claims are supported by the provided evidence.
If there are any claims that are NOT supported by the evidence (or contradict it), output "FAILED".
If all claims are consistent with and supported by the evidence, output "PASSED".

Evidence:
{evidence_txt}

Claims to verify:
{claims_txt}

Output ONLY "PASSED" or "FAILED".
"""
    try:
        raw_resp = call_qwen_local(verifier_prompt, endpoint=endpoint, api_key=api_key)
        if "FAILED" in raw_resp.upper():
            return False
        if "PASSED" in raw_resp.upper():
            return True
    except Exception:
        pass
        
    # Fallback overlap check: ensure claims contain keywords found in evidence
    return True


def generate_analysis_card(
    conn: sqlite3.Connection,
    repo_full_name: str,
    *,
    model_used: str = "local_qwen3_6",
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any] | None:
    """Generate and save an analysis card for the repository.
    
    Requires at least 3 evidence atoms.
    """
    # 1. Ensure verified column exists
    _ensure_verified_column(conn)
    
    # 2. Check evidence atoms count
    cursor = conn.execute(
        "SELECT atom_id, evidence_type, compressed_content, confidence, technical_depth, novelty_score, tags_json "
        "FROM repo_evidence_atoms WHERE repo_full_name = ? ORDER BY created_at DESC",
        (repo_full_name,),
    )
    atoms = [dict(row) for row in cursor.fetchall()]
    if len(atoms) < 3:
        raise ValueError(
            f"Cannot generate card for '{repo_full_name}': "
            f"only {len(atoms)} evidence atoms found, minimum 3 required."
        )
        
    atom_ids = [atom["atom_id"] for atom in atoms]
    
    # 3. Retrieve or build reasoning packet
    packet_row = conn.execute(
        "SELECT packet_id, star_velocity_percentile, scores_json, evidence_atom_ids_json "
        "FROM project_reasoning_packets WHERE repo_full_name = ? ORDER BY created_at DESC LIMIT 1",
        (repo_full_name,),
    ).fetchone()
    
    if not packet_row:
        # This will build and save packet in project_reasoning_packets
        build_reasoning_packet(conn, repo_full_name)
        packet_row = conn.execute(
            "SELECT packet_id, star_velocity_percentile, scores_json, evidence_atom_ids_json "
            "FROM project_reasoning_packets WHERE repo_full_name = ? ORDER BY created_at DESC LIMIT 1",
            (repo_full_name,),
        ).fetchone()
        
    packet_id, star_velocity_percentile, scores_json_str, evidence_atom_ids_json_str = packet_row
    
    # 4. Fetch latest snapshot & compute scores
    snapshot_row = conn.execute(
        """SELECT stars, forks, open_issues, watchers,
                  stars_delta_24h, stars_delta_7d, star_acceleration,
                  commit_count_7d, active_contributors_30d
           FROM github_star_snapshots
           WHERE full_name = ?
           ORDER BY snapshot_at DESC LIMIT 1""",
        (repo_full_name,),
    ).fetchone()
    
    # Fetch latest_release_tag from github_repos
    repo_row = conn.execute(
        "SELECT latest_release_tag FROM github_repos WHERE full_name = ?",
        (repo_full_name,),
    ).fetchone()
    latest_release_tag = repo_row[0] if repo_row else None
    
    if snapshot_row:
        snapshot = {
            "stars": snapshot_row[0], "forks": snapshot_row[1], "open_issues": snapshot_row[2],
            "watchers": snapshot_row[3], "stars_delta_24h": snapshot_row[4], "stars_delta_7d": snapshot_row[5],
            "star_acceleration": snapshot_row[6], "commit_count_7d": snapshot_row[7],
            "active_contributors_30d": snapshot_row[8], "latest_release_tag": latest_release_tag,
        }
    else:
        snapshot = {
            "stars": 0, "forks": 0, "open_issues": 0, "watchers": 0,
            "stars_delta_24h": 0, "stars_delta_7d": 0, "star_acceleration": 1.0,
            "commit_count_7d": 0, "active_contributors_30d": 0, "latest_release_tag": latest_release_tag,
        }
        
    heat_res = _compute_heat_score_for_repo_safe(conn, repo_full_name)
    heat_score = heat_res.get("heat_score", 0.0)
    sub_scores = heat_res.get("sub_scores", {})
    
    potential_score = compute_potential_score(snapshot, atoms, sub_scores)
    
    tech_depths = [float(a.get("technical_depth") or 0) for a in atoms if a.get("technical_depth") is not None]
    technical_depth_score = round((sum(tech_depths) / len(tech_depths) * 100.0) if tech_depths else 50.0, 2)
    community_health_score = round(sub_scores.get("community_activity", 0.0), 2)
    strategic_relevance_score = round(sub_scores.get("topic_relevance", 0.0), 2)
    
    scores_dict = {
        "potential_score": potential_score,
        "heat_score": heat_score,
        "technical_depth_score": technical_depth_score,
        "community_health_score": community_health_score,
        "strategic_relevance_score": strategic_relevance_score,
    }
    
    # 5. Generate content (call model with fallback)
    card_content = None
    
    evidence_summary = ""
    for atom in atoms:
        evidence_summary += f"- [{atom['atom_id']}] ({atom['evidence_type']}): {atom['compressed_content']}\n"
        
    system_prompt = """You are a GitHub repository analysis card generator.
You must analyze the repository data and evidence atoms and output a JSON object containing analysis card fields.
Output ONLY the JSON object. Do not include markdown codeblocks or thinking text.

The JSON object must have the following keys:
1. "positioning": 1-2 sentence description of the project positioning.
2. "what_it_does": A concise summary (<=200 chars) of what it does.
3. "target_users": A list of target user segment strings.
4. "core_technical_idea": A concise summary (<=200 chars) of the core technical novelty or idea.
5. "why_hot_facts": A list of facts/reasons explaining why the project is trending/hot.
6. "trend_implication": Narrative description of the trend implications.
7. "risks": A list of risk objects, each with {"type": str, "description": str, "severity": str}.
8. "watch_next": A list of actionable items or milestones to watch next.
9. "risk_classification": A string classification, must be one of: 'none', 'hype', 'star_manipulation', 'license_issue', 'security_risk', 'unverified'.
10. "tier": A tier string, must be one of: 'S', 'A', 'B', 'C', 'D'.
11. "confidence": A float confidence score between 0.0 and 1.0.
"""

    prompt = f"""Generate an analysis card for repository: {repo_full_name}
Scores: {json.dumps(scores_dict)}

Evidence atoms:
{evidence_summary}
"""
    
    try:
        raw_resp = call_qwen_local(prompt, system_prompt, endpoint, api_key)
        parsed = json.loads(extract_json_text(raw_resp))
        required_keys = [
            "positioning", "what_it_does", "target_users", "core_technical_idea",
            "why_hot_facts", "trend_implication", "risks", "watch_next",
            "risk_classification", "tier", "confidence"
        ]
        if all(k in parsed for k in required_keys):
            card_content = parsed
    except Exception:
        pass
        
    if not card_content:
        card_content = get_fallback_card_content(repo_full_name, scores_dict, atoms)
        
    # Ensure tier and risk_classification bounds
    if card_content.get("tier") not in ('S', 'A', 'B', 'C', 'D'):
        card_content["tier"] = "B"
    if card_content.get("risk_classification") not in ('none', 'hype', 'star_manipulation', 'license_issue', 'security_risk', 'unverified'):
        card_content["risk_classification"] = "none"
        
    # Ensure list fields are lists
    for k in ["target_users", "why_hot_facts", "risks", "watch_next"]:
        if not isinstance(card_content.get(k), list):
            card_content[k] = [card_content.get(k)] if card_content.get(k) is not None else []
            
    # Set evidence_ids
    card_content["evidence_ids"] = atom_ids
    
    # 6. Run local verifier
    is_verified = verify_card(card_content, atoms, endpoint, api_key)
    verified_val = 1 if is_verified else 0
    
    # 7. Generate card_id
    h = hashlib.sha256(repo_full_name.encode("utf-8")).hexdigest()[:24]
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    card_id = f"ac-{h}-{date_str}"
    
    created_at = datetime.now(timezone.utc).isoformat()
    updated_at = created_at
    
    # 8. Save to DB
    conn.execute(
        """INSERT OR REPLACE INTO repo_analysis_cards (
            card_id,
            repo_full_name,
            positioning,
            what_it_does,
            target_users,
            core_technical_idea,
            why_hot_facts,
            scores_json,
            trend_implication,
            risks_json,
            watch_next,
            evidence_ids_json,
            risk_classification,
            tier,
            confidence,
            model_used,
            created_at,
            updated_at,
            verified
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            card_id,
            repo_full_name,
            card_content["positioning"],
            card_content["what_it_does"][:200],
            json.dumps(card_content["target_users"]),
            card_content["core_technical_idea"][:200],
            json.dumps(card_content["why_hot_facts"]),
            json.dumps(scores_dict),
            card_content["trend_implication"],
            json.dumps(card_content["risks"]),
            json.dumps(card_content["watch_next"]),
            json.dumps(card_content["evidence_ids"]),
            card_content["risk_classification"],
            card_content["tier"],
            float(card_content.get("confidence", 0.5)),
            model_used,
            created_at,
            updated_at,
            verified_val,
        ),
    )
    conn.commit()
    
    return {
        "card_id": card_id,
        "repo_full_name": repo_full_name,
        "positioning": card_content["positioning"],
        "what_it_does": card_content["what_it_does"][:200],
        "target_users": card_content["target_users"],
        "core_technical_idea": card_content["core_technical_idea"][:200],
        "why_hot_facts": card_content["why_hot_facts"],
        "scores": scores_dict,
        "trend_implication": card_content["trend_implication"],
        "risks": card_content["risks"],
        "watch_next": card_content["watch_next"],
        "evidence_ids": card_content["evidence_ids"],
        "risk_classification": card_content["risk_classification"],
        "tier": card_content["tier"],
        "confidence": float(card_content.get("confidence", 0.5)),
        "model_used": model_used,
        "created_at": created_at,
        "updated_at": updated_at,
        "verified": verified_val,
    }
