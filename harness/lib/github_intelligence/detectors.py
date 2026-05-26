"""Detector framework — 7 detector implementations conforming to Detector protocol.

Provides:
- ``Detection``: Data class for holding triggering detector state.
- ``Detector``: Protocol that all detectors conform to.
- ``compute_potential_score()``: Calculates the repository potential score.
- ``run_all_detectors()``: Executes all 7 detectors with error boundary isolation.

Spec: sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s02-architecture
Node: B10
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger("github_intelligence.detectors")


@dataclass
class Detection:
    """Holds a detector alert output."""
    detector_name: str
    severity: str
    evidence_ids: List[str]
    repo_full_name: str
    trigger_condition: str
    conditions_met_json: Dict[str, Any] = field(default_factory=dict)
    recommended_action: str = ""


class Detector(Protocol):
    """Protocol for all 7 GitHub trend/risk detectors."""
    def detect(
        self,
        conn: sqlite3.Connection,
        repo_full_name: str,
        snapshot: Dict[str, Any] | None = None,
        evidence_atoms: List[Dict[str, Any]] | None = None,
        sub_scores: Dict[str, float] | None = None,
        heat_score: float | None = None,
    ) -> List[Detection]:
        """Run anomaly detection and return triggered alerts."""
        ...


def compute_potential_score(
    snapshot: Dict[str, Any],
    evidence_atoms: List[Dict[str, Any]],
    sub_scores: Dict[str, float],
) -> float:
    """Calculate potential score (0-100) based on early indicators."""
    # 1. Community activity (0-100)
    commits_7d = float(snapshot.get("commit_count_7d") or 0)
    contributors = float(snapshot.get("active_contributors_30d") or 0)
    community_activity = sub_scores.get("community_activity")
    if community_activity is None:
        community_activity = min(100.0, min(50.0, commits_7d * 0.5) + min(50.0, contributors * 2.0))
        
    # 2. Release signal (0-100)
    release_signal = sub_scores.get("release_signal")
    if release_signal is None:
        has_release = bool(snapshot.get("latest_release_tag"))
        release_evidence = [a for a in evidence_atoms if a.get("evidence_type") == "release_feature"]
        release_signal = min(100.0, (30.0 if has_release else 0.0) + min(70.0, len(release_evidence) * 20.0))

    # 3. Maintainer signal (0-100)
    maintainer_signal = sub_scores.get("maintainer_signal")
    if maintainer_signal is None:
        maintainer_evidence = [a for a in evidence_atoms if a.get("evidence_type") in ("issue_signal", "pr_signal")]
        maintainer_signal = min(100.0, len(maintainer_evidence) * 25.0)

    # 4. Technical depth (0-1.0 mapped to 0-100)
    tech_depths = [float(a.get("technical_depth") or 0) for a in evidence_atoms if a.get("technical_depth") is not None]
    tech_depth_score = (sum(tech_depths) / len(tech_depths) * 100.0) if tech_depths else 50.0

    # 5. Novelty (0-1.0 mapped to 0-100)
    novelty_scores = [float(a.get("novelty_score") or 0) for a in evidence_atoms if a.get("novelty_score") is not None]
    novelty_score = (sum(novelty_scores) / len(novelty_scores) * 100.0) if novelty_scores else 50.0

    # Weighted potential score formula
    potential = (
        0.30 * tech_depth_score +
        0.20 * novelty_score +
        0.20 * release_signal +
        0.15 * community_activity +
        0.15 * maintainer_signal
    )
    return round(max(0.0, min(100.0, potential)), 2)


def _resolve_repo_data(conn: sqlite3.Connection, repo_full_name: str) -> Dict[str, Any]:
    """Helper to query all necessary intelligence fields for a repository from SQLite."""
    # 1. Fetch latest snapshot
    snapshot_row = conn.execute(
        """SELECT stars, forks, open_issues, watchers,
                  stars_delta_1h, stars_delta_6h, stars_delta_24h, stars_delta_7d, stars_delta_30d,
                  forks_delta_24h, issues_delta_24h, prs_delta_24h,
                  commit_count_7d, active_contributors_30d,
                  star_acceleration
           FROM github_star_snapshots
           WHERE full_name = ?
           ORDER BY snapshot_at DESC LIMIT 1""",
        (repo_full_name,),
    ).fetchone()

    # 2. Fetch repo details from github_repos (like latest_release_tag, description, etc.)
    repo_row = conn.execute(
        """SELECT latest_release_tag, description, topics, language, stars, forks, open_issues, watchers
           FROM github_repos
           WHERE full_name = ?""",
        (repo_full_name,),
    ).fetchone()

    latest_release_tag = repo_row[0] if repo_row else None
    description = repo_row[1] if repo_row else ""
    
    if snapshot_row:
        snapshot = {
            "stars": snapshot_row[0],
            "forks": snapshot_row[1],
            "open_issues": snapshot_row[2],
            "watchers": snapshot_row[3],
            "stars_delta_1h": snapshot_row[4],
            "stars_delta_6h": snapshot_row[5],
            "stars_delta_24h": snapshot_row[6],
            "stars_delta_7d": snapshot_row[7],
            "stars_delta_30d": snapshot_row[8],
            "forks_delta_24h": snapshot_row[9],
            "issues_delta_24h": snapshot_row[10],
            "prs_delta_24h": snapshot_row[11],
            "commit_count_7d": snapshot_row[12],
            "active_contributors_30d": snapshot_row[13],
            "star_acceleration": snapshot_row[14],
            "latest_release_tag": latest_release_tag,
        }
    else:
        if repo_row:
            snapshot = {
                "stars": repo_row[4],
                "forks": repo_row[5],
                "open_issues": repo_row[6],
                "watchers": repo_row[7],
                "latest_release_tag": latest_release_tag,
                "description": description,
                "stars_delta_24h": 0,
                "stars_delta_7d": 0,
                "star_acceleration": 1.0,
                "commit_count_7d": 0,
                "active_contributors_30d": 0,
            }
        else:
            snapshot = {
                "stars": 0,
                "forks": 0,
                "open_issues": 0,
                "watchers": 0,
                "latest_release_tag": None,
                "description": "",
                "stars_delta_24h": 0,
                "stars_delta_7d": 0,
                "star_acceleration": 1.0,
                "commit_count_7d": 0,
                "active_contributors_30d": 0,
            }

    # 3. Fetch evidence atoms
    evidence_rows = conn.execute(
        """SELECT atom_id, evidence_type, compressed_content, confidence, technical_depth, novelty_score, raw_source_type, tags_json
           FROM repo_evidence_atoms
           WHERE repo_full_name = ?""",
        (repo_full_name,),
    ).fetchall()
    
    evidence_atoms = [
        {
            "atom_id": r[0],
            "evidence_type": r[1],
            "compressed_content": r[2],
            "confidence": r[3],
            "technical_depth": r[4],
            "novelty_score": r[5],
            "raw_source_type": r[6],
            "tags_json": r[7],
        }
        for r in evidence_rows
    ]

    # 4. Compute sub-scores and heat score
    from github_intelligence.scoring import compute_sub_scores, compute_heat_score
    
    percentile_data = {}
    pct_row = conn.execute(
        """SELECT star_velocity_percentile
           FROM snapshot_percentiles
           WHERE repo_full_name = ?
           ORDER BY snapshot_date DESC LIMIT 1""",
        (repo_full_name,),
    ).fetchone()
    if pct_row:
        percentile_data["star_velocity_percentile"] = pct_row[0]

    sub_scores = compute_sub_scores(snapshot, evidence_atoms, percentile_data=percentile_data)
    heat_score = compute_heat_score(sub_scores)

    return {
        "snapshot": snapshot,
        "evidence_atoms": evidence_atoms,
        "sub_scores": sub_scores,
        "heat_score": heat_score,
    }


class SuddenHotDetector:
    """1. sudden_hot: star_acceleration > 8.0."""
    def detect(
        self,
        conn: sqlite3.Connection,
        repo_full_name: str,
        snapshot: Dict[str, Any] | None = None,
        evidence_atoms: List[Dict[str, Any]] | None = None,
        sub_scores: Dict[str, float] | None = None,
        heat_score: float | None = None,
    ) -> List[Detection]:
        if snapshot is None:
            data = _resolve_repo_data(conn, repo_full_name)
            snapshot = data["snapshot"]
            evidence_atoms = data["evidence_atoms"]
            
        acceleration = snapshot.get("star_acceleration")
        if acceleration is not None and acceleration > 8.0:
            severity = "critical" if acceleration > 20.0 else "high"
            evidence_ids = [a["atom_id"] for a in (evidence_atoms or []) if a.get("evidence_type") == "growth_fact"]
            if not evidence_ids and evidence_atoms:
                evidence_ids = [evidence_atoms[0]["atom_id"]]
            return [
                Detection(
                    detector_name="sudden_hot",
                    severity=severity,
                    evidence_ids=evidence_ids,
                    repo_full_name=repo_full_name,
                    trigger_condition=f"star_acceleration {acceleration} > 8.0",
                    conditions_met_json={"star_acceleration": acceleration},
                    recommended_action="Create project intelligence card and run why-hot attribution.",
                )
            ]
        return []


class EarlyPotentialDetector:
    """2. early_potential: potential_score > 85.0 AND stars < 2000."""
    def detect(
        self,
        conn: sqlite3.Connection,
        repo_full_name: str,
        snapshot: Dict[str, Any] | None = None,
        evidence_atoms: List[Dict[str, Any]] | None = None,
        sub_scores: Dict[str, float] | None = None,
        heat_score: float | None = None,
    ) -> List[Detection]:
        if snapshot is None or evidence_atoms is None or sub_scores is None:
            data = _resolve_repo_data(conn, repo_full_name)
            if snapshot is None:
                snapshot = data["snapshot"]
            if evidence_atoms is None:
                evidence_atoms = data["evidence_atoms"]
            if sub_scores is None:
                sub_scores = data["sub_scores"]

        stars = snapshot.get("stars") or 0
        potential_score = compute_potential_score(snapshot, evidence_atoms, sub_scores)
        
        if potential_score > 85.0 and stars < 2000:
            evidence_ids = [a["atom_id"] for a in evidence_atoms if a.get("evidence_type") in ("readme_claim", "release_feature")]
            if not evidence_ids and evidence_atoms:
                evidence_ids = [evidence_atoms[0]["atom_id"]]
            return [
                Detection(
                    detector_name="early_potential",
                    severity="high",
                    evidence_ids=evidence_ids,
                    repo_full_name=repo_full_name,
                    trigger_condition=f"potential_score {potential_score} > 85 AND stars {stars} < 2000",
                    conditions_met_json={"potential_score": potential_score, "stars": stars},
                    recommended_action="Add to watchlist and monitor community activity.",
                )
            ]
        return []


class FoundationInfraCandidateDetector:
    """3. foundation_infra_candidate: infrastructure alignment AND technical_depth >= 0.55."""
    def detect(
        self,
        conn: sqlite3.Connection,
        repo_full_name: str,
        snapshot: Dict[str, Any] | None = None,
        evidence_atoms: List[Dict[str, Any]] | None = None,
        sub_scores: Dict[str, float] | None = None,
        heat_score: float | None = None,
    ) -> List[Detection]:
        if evidence_atoms is None:
            data = _resolve_repo_data(conn, repo_full_name)
            evidence_atoms = data["evidence_atoms"]
            
        topics, description, language = "", "", ""
        repo_row = conn.execute(
            "SELECT topics, description, language FROM github_repos WHERE full_name = ?",
            (repo_full_name,),
        ).fetchone()
        if repo_row:
            topics = str(repo_row[0] or "").lower()
            description = str(repo_row[1] or "").lower()
            language = str(repo_row[2] or "").lower()

        infra_keywords = {"infra", "kernel", "os", "runtime", "compiler", "database", "mcp", "library", "framework", "llm-app-framework", "inference-compute", "training-framework", "security-ai"}
        is_infra = any(kw in topics or kw in description or kw in language for kw in infra_keywords)

        tech_depths = [float(a.get("technical_depth") or 0) for a in evidence_atoms if a.get("technical_depth") is not None]
        avg_depth = sum(tech_depths) / len(tech_depths) if tech_depths else 0.5

        if is_infra and avg_depth >= 0.55:
            evidence_ids = [a["atom_id"] for a in evidence_atoms if a.get("technical_depth", 0) >= 0.55]
            if not evidence_ids and evidence_atoms:
                evidence_ids = [evidence_atoms[0]["atom_id"]]
            return [
                Detection(
                    detector_name="foundation_infra_candidate",
                    severity="medium",
                    evidence_ids=evidence_ids,
                    repo_full_name=repo_full_name,
                    trigger_condition=f"is_infra {is_infra} AND technical_depth {round(avg_depth, 4)} >= 0.55",
                    conditions_met_json={"technical_depth": round(avg_depth, 4), "is_infra": is_infra},
                    recommended_action="Conduct code-level architecture analysis and check for licensing.",
                )
            ]
        return []


class HypeOrNoiseDetector:
    """4. hype_or_noise: heat_score > 65.0 AND technical_depth < 0.35."""
    def detect(
        self,
        conn: sqlite3.Connection,
        repo_full_name: str,
        snapshot: Dict[str, Any] | None = None,
        evidence_atoms: List[Dict[str, Any]] | None = None,
        sub_scores: Dict[str, float] | None = None,
        heat_score: float | None = None,
    ) -> List[Detection]:
        if heat_score is None or evidence_atoms is None:
            data = _resolve_repo_data(conn, repo_full_name)
            if heat_score is None:
                heat_score = data["heat_score"]
            if evidence_atoms is None:
                evidence_atoms = data["evidence_atoms"]
                
        tech_depths = [float(a.get("technical_depth") or 0) for a in evidence_atoms if a.get("technical_depth") is not None]
        avg_depth = sum(tech_depths) / len(tech_depths) if tech_depths else 0.5

        if heat_score > 65.0 and avg_depth < 0.35:
            evidence_ids = [a["atom_id"] for a in evidence_atoms if a.get("evidence_type") in ("social_mention", "youtube_mention")]
            if not evidence_ids and evidence_atoms:
                evidence_ids = [evidence_atoms[0]["atom_id"]]
            return [
                Detection(
                    detector_name="hype_or_noise",
                    severity="medium",
                    evidence_ids=evidence_ids,
                    repo_full_name=repo_full_name,
                    trigger_condition=f"heat_score {heat_score} > 65.0 AND technical_depth {round(avg_depth, 4)} < 0.35",
                    conditions_met_json={"heat_score": heat_score, "technical_depth": round(avg_depth, 4)},
                    recommended_action="Identify wrappers/packaging; perform unverified/hype risk classification.",
                )
            ]
        return []


class StarManipulationSuspicionDetector:
    """5. star_manipulation_suspicion: anomalous growth signals with low developer activity."""
    def detect(
        self,
        conn: sqlite3.Connection,
        repo_full_name: str,
        snapshot: Dict[str, Any] | None = None,
        evidence_atoms: List[Dict[str, Any]] | None = None,
        sub_scores: Dict[str, float] | None = None,
        heat_score: float | None = None,
    ) -> List[Detection]:
        if snapshot is None:
            data = _resolve_repo_data(conn, repo_full_name)
            snapshot = data["snapshot"]
            evidence_atoms = data["evidence_atoms"]
            
        stars_delta_24h = snapshot.get("stars_delta_24h") or 0
        forks_delta_24h = snapshot.get("forks_delta_24h") or 0
        forks = snapshot.get("forks") or 0
        acceleration = snapshot.get("star_acceleration") or 1.0
        contributors = snapshot.get("active_contributors_30d") or 0
        commits_7d = snapshot.get("commit_count_7d") or 0

        triggered = False
        reason = ""
        conditions = {}

        if acceleration > 20.0 and stars_delta_24h > 50:
            triggered = True
            reason = f"star_acceleration {acceleration} > 20.0 AND stars_delta_24h {stars_delta_24h} > 50"
            conditions = {"acceleration": acceleration, "stars_delta_24h": stars_delta_24h}
        elif stars_delta_24h > 100 and forks_delta_24h <= 0 and forks < 5:
            triggered = True
            reason = f"stars_delta_24h {stars_delta_24h} > 100 AND forks_delta_24h {forks_delta_24h} <= 0 AND forks {forks} < 5"
            conditions = {"stars_delta_24h": stars_delta_24h, "forks_delta_24h": forks_delta_24h, "forks": forks}
        elif stars_delta_24h > 100 and contributors <= 1 and commits_7d <= 1:
            triggered = True
            reason = f"stars_delta_24h {stars_delta_24h} > 100 AND contributors {contributors} <= 1 AND commits_7d {commits_7d} <= 1"
            conditions = {"stars_delta_24h": stars_delta_24h, "active_contributors_30d": contributors, "commit_count_7d": commits_7d}

        if triggered:
            evidence_ids = [a["atom_id"] for a in (evidence_atoms or []) if a.get("evidence_type") == "growth_fact"]
            if not evidence_ids and evidence_atoms:
                evidence_ids = [evidence_atoms[0]["atom_id"]]
            return [
                Detection(
                    detector_name="star_manipulation_suspicion",
                    severity="medium",
                    evidence_ids=evidence_ids,
                    repo_full_name=repo_full_name,
                    trigger_condition=reason,
                    conditions_met_json=conditions,
                    recommended_action="Audit commit history, check watcher list, and flag for manual verification.",
                )
            ]
        return []


class MajorReleaseSignalDetector:
    """6. major_release_signal: major release tags or release note features."""
    def detect(
        self,
        conn: sqlite3.Connection,
        repo_full_name: str,
        snapshot: Dict[str, Any] | None = None,
        evidence_atoms: List[Dict[str, Any]] | None = None,
        sub_scores: Dict[str, float] | None = None,
        heat_score: float | None = None,
    ) -> List[Detection]:
        if snapshot is None or evidence_atoms is None:
            data = _resolve_repo_data(conn, repo_full_name)
            if snapshot is None:
                snapshot = data["snapshot"]
            if evidence_atoms is None:
                evidence_atoms = data["evidence_atoms"]
                
        release_tag = snapshot.get("latest_release_tag")
        is_major_tag = False
        if release_tag:
            is_major_tag = bool(re.match(r"^v?\d+\.0(\.0)?$", str(release_tag)))
            
        release_atoms = [a for a in evidence_atoms if a.get("evidence_type") == "release_feature"]
        
        if is_major_tag or release_atoms:
            evidence_ids = [a["atom_id"] for a in release_atoms]
            if not evidence_ids and evidence_atoms:
                evidence_ids = [evidence_atoms[0]["atom_id"]]
            trigger_tag_str = release_tag if release_tag else "N/A"
            return [
                Detection(
                    detector_name="major_release_signal",
                    severity="medium",
                    evidence_ids=evidence_ids,
                    repo_full_name=repo_full_name,
                    trigger_condition=f"latest_release_tag {trigger_tag_str} is major tag ({is_major_tag}) OR has release_feature evidence atoms ({len(release_atoms)})",
                    conditions_met_json={"latest_release_tag": release_tag, "release_atoms_count": len(release_atoms)},
                    recommended_action="Compile release highlights and draft a product release feature overview.",
                )
            ]
        return []


class CrossSourceResonanceDetector:
    """7. cross_source_resonance: simultaneous trending, social, and youtube mentions."""
    def detect(
        self,
        conn: sqlite3.Connection,
        repo_full_name: str,
        snapshot: Dict[str, Any] | None = None,
        evidence_atoms: List[Dict[str, Any]] | None = None,
        sub_scores: Dict[str, float] | None = None,
        heat_score: float | None = None,
    ) -> List[Detection]:
        if sub_scores is None or evidence_atoms is None:
            data = _resolve_repo_data(conn, repo_full_name)
            if sub_scores is None:
                sub_scores = data["sub_scores"]
            if evidence_atoms is None:
                evidence_atoms = data["evidence_atoms"]
                
        cross_source_signal = sub_scores.get("cross_source_signal") or 0.0
        has_social = any(a.get("evidence_type") == "social_mention" for a in evidence_atoms)
        has_youtube = any(a.get("evidence_type") == "youtube_mention" for a in evidence_atoms)

        if cross_source_signal >= 50.0 or (has_social and has_youtube):
            severity = "critical" if (has_social and has_youtube and cross_source_signal >= 75.0) else "high"
            evidence_ids = [a["atom_id"] for a in evidence_atoms if a.get("evidence_type") in ("social_mention", "youtube_mention")]
            if not evidence_ids and evidence_atoms:
                evidence_ids = [evidence_atoms[0]["atom_id"]]
            return [
                Detection(
                    detector_name="cross_source_resonance",
                    severity=severity,
                    evidence_ids=evidence_ids,
                    repo_full_name=repo_full_name,
                    trigger_condition=f"cross_source_signal {cross_source_signal} >= 50.0 OR (has_social {has_social} AND has_youtube {has_youtube})",
                    conditions_met_json={"cross_source_signal": cross_source_signal, "has_social": has_social, "has_youtube": has_youtube},
                    recommended_action="Compile cross-source mention highlights and check community velocity.",
                )
            ]
        return []


def run_all_detectors(
    conn: sqlite3.Connection,
    repo_full_name: str,
    snapshot: Dict[str, Any] | None = None,
    evidence_atoms: List[Dict[str, Any]] | None = None,
    sub_scores: Dict[str, float] | None = None,
    heat_score: float | None = None,
) -> List[Detection]:
    """Execute all 7 detectors on a repository.

    Each detector is run inside an error boundary; crashes are logged
    and return an empty list, allowing other detectors to proceed.
    """
    detectors = [
        SuddenHotDetector(),
        EarlyPotentialDetector(),
        FoundationInfraCandidateDetector(),
        HypeOrNoiseDetector(),
        StarManipulationSuspicionDetector(),
        MajorReleaseSignalDetector(),
        CrossSourceResonanceDetector(),
    ]
    
    try:
        resolved = _resolve_repo_data(conn, repo_full_name)
        if snapshot is None:
            snapshot = resolved["snapshot"]
        if evidence_atoms is None:
            evidence_atoms = resolved["evidence_atoms"]
        if sub_scores is None:
            sub_scores = resolved["sub_scores"]
        if heat_score is None:
            heat_score = resolved["heat_score"]
    except Exception as e:
        logger.exception("Failed to resolve repository data for %s: %s", repo_full_name, e)

    all_detections: List[Detection] = []
    for detector in detectors:
        name = detector.__class__.__name__
        try:
            detections = detector.detect(
                conn,
                repo_full_name,
                snapshot=snapshot,
                evidence_atoms=evidence_atoms,
                sub_scores=sub_scores,
                heat_score=heat_score,
            )
            all_detections.extend(detections)
        except Exception as e:
            logger.exception("Detector %s crashed for repo %s: %s", name, repo_full_name, e)
            continue
            
    return all_detections
