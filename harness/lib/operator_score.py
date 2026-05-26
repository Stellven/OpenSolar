"""operator_score.py — Explainable OperatorScore for actor selection.

Factors: TaskFit 0.30, HistoricalSuccess 0.20, FreshQuota 0.15,
LatencyFit 0.10, ContextAffinity 0.10, RiskFit 0.10, CostFit 0.05.
Penalties: RecentFailurePenalty, SameProviderVerifierPenalty, StaleContextPenalty.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HOME = Path.home()
HARNESS_DIR = Path.home() / ".solar" / "harness"

FACTOR_WEIGHTS = {
    "TaskFit": 0.30,
    "HistoricalSuccess": 0.20,
    "FreshQuota": 0.15,
    "LatencyFit": 0.10,
    "ContextAffinity": 0.10,
    "RiskFit": 0.10,
    "CostFit": 0.05,
}

# Penalties (subtracted from weighted score)
RECENT_FAILURE_PENALTY = 0.15
SAME_PROVIDER_VERIFIER_PENALTY = 0.20
STALE_CONTEXT_PENALTY = 0.10
ASYNC_BUSY_PENALTY = 0.10
REAUTH_PENALTY = 1.00


def classify_actor_type(actor_id: str, cfg: Dict[str, Any]) -> str:
    """Classify actors into precedence buckets for fallback ordering."""
    actor = str(actor_id or "").lower()
    model = str(cfg.get("model") or "").lower()
    capability_profile = cfg.get("capability_profile") or {}
    if "chatgpt" in actor or any(token in model for token in ("gpt", "o1", "o3", "o4")):
        return "chatgpt"
    if "gemini" in actor or "gemini" in model:
        return "gemini"
    if "browser" in actor or capability_profile.get("browser_use", 0):
        return "browser"
    if "thunder" in actor or any(token in model for token in ("qwen", "thunder", "local")):
        return "local"
    return "api"


def _fallback_precedence(actor_id: str, cfg: Dict[str, Any]) -> tuple[int, str]:
    actor_type = classify_actor_type(actor_id, cfg)
    model = str(cfg.get("model") or "").lower()
    if "gemini-deep-research" in model:
        return (0, actor_id)
    order = {
        "chatgpt": 1,
        "gemini": 2,
        "browser": 3,
        "api": 4,
        "local": 5,
    }
    return (order.get(actor_type, 9), actor_id)


def _cost_fit(cfg: Dict[str, Any]) -> float:
    tier = str((cfg.get("cost_profile") or {}).get("cost_tier") or "medium").lower()
    return {"low": 0.9, "medium": 0.6, "high": 0.2}.get(tier, 0.5)


def _risk_fit(cfg: Dict[str, Any]) -> float:
    risk = cfg.get("risk_profile") or {}
    if str(risk.get("destructive_actions") or "").lower() == "allowed":
        return 0.2
    if str(risk.get("allowed_network") or "").lower() == "denied":
        return 0.9
    return 0.7


class TaskEvidence:
    """Historical task evidence for computing HistoricalSuccess."""

    def __init__(self, records: Optional[List[Dict]] = None):
        self.records = records or []

    @classmethod
    def from_file(cls, path: Path) -> "TaskEvidence":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(data.get("records", []))
        except (json.JSONDecodeError, OSError):
            return cls()

    def success_rate(
        self,
        repo: Optional[str] = None,
        task_type: Optional[str] = None,
        logical_operator: Optional[str] = None,
        provider: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> float:
        """Compute success rate with optional filters."""
        filtered = self.records
        if repo:
            filtered = [r for r in filtered if r.get("repo") == repo]
        if task_type:
            filtered = [r for r in filtered if r.get("task_type") == task_type]
        if logical_operator:
            filtered = [r for r in filtered if r.get("logical_operator") == logical_operator]
        if provider:
            filtered = [r for r in filtered if r.get("provider") == provider]
        if actor_id:
            filtered = [r for r in filtered if r.get("actor_id") == actor_id]
        if not filtered:
            return 0.5  # neutral prior
        successes = sum(1 for r in filtered if r.get("outcome") == "success")
        return successes / len(filtered)


class OperatorScoreResult:
    """Score output with explanation."""

    def __init__(
        self,
        actor_id: str,
        total_score: float,
        factors: Dict[str, float],
        penalties: Dict[str, float],
        rejected: List[Dict[str, str]],
        selected: bool,
        fallback_actor_id: Optional[str] = None,
    ):
        self.actor_id = actor_id
        self.total_score = total_score
        self.factors = factors
        self.penalties = penalties
        self.rejected = rejected
        self.selected = selected
        self.fallback_actor_id = fallback_actor_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "total_score": round(self.total_score, 4),
            "factors": {k: round(v, 4) for k, v in self.factors.items()},
            "penalties": {k: round(v, 4) for k, v in self.penalties.items()},
            "selected": self.selected,
            "fallback_actor_id": self.fallback_actor_id,
            "rejected": self.rejected,
        }

    @property
    def explanation(self) -> str:
        lines = [f"Actor: {self.actor_id}, Score: {self.total_score:.4f}"]
        for name, val in sorted(self.factors.items()):
            weight = FACTOR_WEIGHTS.get(name, 0)
            lines.append(f"  {name}({weight:.0%}): {val:.4f}")
        for name, val in sorted(self.penalties.items()):
            lines.append(f"  Penalty[{name}]: -{val:.4f}")
        return "\n".join(lines)


def compute_score(
    actor_id: str,
    task_fit: float = 0.5,
    historical_success: float = 0.5,
    fresh_quota: float = 0.5,
    latency_fit: float = 0.5,
    context_affinity: float = 0.5,
    risk_fit: float = 0.5,
    cost_fit: float = 0.5,
    recent_failure: bool = False,
    same_provider_verifier: bool = False,
    stale_context: bool = False,
) -> Tuple[float, Dict[str, float], Dict[str, float]]:
    """Compute weighted score with penalties."""
    factors = {
        "TaskFit": task_fit * FACTOR_WEIGHTS["TaskFit"],
        "HistoricalSuccess": historical_success * FACTOR_WEIGHTS["HistoricalSuccess"],
        "FreshQuota": fresh_quota * FACTOR_WEIGHTS["FreshQuota"],
        "LatencyFit": latency_fit * FACTOR_WEIGHTS["LatencyFit"],
        "ContextAffinity": context_affinity * FACTOR_WEIGHTS["ContextAffinity"],
        "RiskFit": risk_fit * FACTOR_WEIGHTS["RiskFit"],
        "CostFit": cost_fit * FACTOR_WEIGHTS["CostFit"],
    }
    penalties: Dict[str, float] = {}
    if recent_failure:
        penalties["RecentFailurePenalty"] = RECENT_FAILURE_PENALTY
    if same_provider_verifier:
        penalties["SameProviderVerifierPenalty"] = SAME_PROVIDER_VERIFIER_PENALTY
    if stale_context:
        penalties["StaleContextPenalty"] = STALE_CONTEXT_PENALTY

    total = sum(factors.values()) - sum(penalties.values())
    return total, factors, penalties


def rank_actors(
    candidates: List[str],
    task_fit_fn=None,
    evidence: Optional[TaskEvidence] = None,
    writer_actor_id: Optional[str] = None,
    actors_cfg: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[OperatorScoreResult]:
    """Rank candidates by score. Returns sorted (best first) results."""
    results = []
    ev = evidence or TaskEvidence()
    actors_cfg = actors_cfg or {}
    for i, actor_id in enumerate(candidates):
        cfg = actors_cfg.get(actor_id, {})
        tf = task_fit_fn(actor_id) if task_fit_fn else 0.5
        hs = ev.success_rate(actor_id=actor_id)
        spv = (writer_actor_id is not None and actor_id == writer_actor_id)
        state = str(cfg.get("state") or cfg.get("login_state") or cfg.get("status") or "").lower()
        total, factors, penalties = compute_score(
            actor_id=actor_id,
            task_fit=tf,
            historical_success=hs,
            same_provider_verifier=spv,
            cost_fit=_cost_fit(cfg),
            risk_fit=_risk_fit(cfg),
        )
        if state in {"running", "waiting_human"}:
            penalties["AsyncBusyPenalty"] = ASYNC_BUSY_PENALTY
            total -= ASYNC_BUSY_PENALTY
        if state == "reauth_required":
            penalties["ReauthPenalty"] = REAUTH_PENALTY
            total -= REAUTH_PENALTY
        results.append(OperatorScoreResult(
            actor_id=actor_id,
            total_score=total,
            factors=factors,
            penalties=penalties,
            rejected=[],
            selected=False,
        ))

    results.sort(key=lambda r: (-r.total_score, *_fallback_precedence(r.actor_id, actors_cfg.get(r.actor_id, {}))))
    if results:
        results[0].selected = True
        for r in results[1:]:
            if not r.selected:
                results[0].fallback_actor_id = r.actor_id
                break
    return results
