"""evidence_ledger.py — Run evidence ledger for actor task dispatch.

Writes ledger before dispatch including dag.yaml reference,
scheduler_decision.json, per-node paths, and final_report.md target.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import datetime

HOME = Path.home()
HARNESS_DIR = Path.home() / ".solar" / "harness"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EvidenceLedger:
    """Append-only JSONL evidence ledger."""

    def __init__(self, ledger_dir: Optional[Path] = None):
        self.ledger_dir = ledger_dir or HARNESS_DIR / "run" / "actor-evidence"

    def write_run_entry(
        self,
        task_id: str,
        sprint_id: str,
        node_id: str,
        actor_id: str,
        logical_operator: str,
        scheduler_decision: Dict[str, Any],
        dag_ref: Optional[str] = None,
        context_packet_id: Optional[str] = None,
        final_report_target: Optional[str] = None,
    ) -> str:
        """Write a run evidence entry before dispatch."""
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "event_type": "run_dispatched",
            "timestamp": _now_iso(),
            "task_id": task_id,
            "sprint_id": sprint_id,
            "node_id": node_id,
            "actor_id": actor_id,
            "logical_operator": logical_operator,
            "dag_ref": dag_ref,
            "scheduler_decision": scheduler_decision,
            "context_packet_id": context_packet_id,
            "per_node": {
                "snapshot_path": f"run/{sprint_id}/{node_id}/snapshot.json",
                "log_path": f"run/{sprint_id}/{node_id}/task.log",
                "result_path": f"run/{sprint_id}/{node_id}/result.json",
            },
            "final_report_target": final_report_target,
        }
        ledger_path = self.ledger_dir / f"{sprint_id}.jsonl"
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return str(ledger_path)


def build_scheduler_decision(
    selected_actor: str,
    logical_operator: str,
    score_factors: Dict[str, float],
    penalties: Dict[str, float],
    rejected: List[Dict[str, str]],
    quota_reason: Optional[str] = None,
    risk_reason: Optional[str] = None,
    context_affinity_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a scheduler_decision.json record."""
    return {
        "selected_actor": selected_actor,
        "logical_operator": logical_operator,
        "score_factors": score_factors,
        "penalties": penalties,
        "rejected_candidates": rejected,
        "quota_reason": quota_reason,
        "risk_reason": risk_reason,
        "context_affinity_reason": context_affinity_reason,
        "timestamp": _now_iso(),
    }
