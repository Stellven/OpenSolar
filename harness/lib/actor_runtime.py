"""actor_runtime.py — Main submit protocol for AgentActor runtime.

Grants lease, writes task_envelope to mailbox inbox,
writes evidence ledger, loads context packet, returns lease/result paths.
No direct tmux scheduler calls.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from actor_lease import LeaseBroker, LeaseState, READY, LEASED, RUNNING, FINALIZING
from actor_mailbox import ActorMailbox
from actor_profiles import ActorProfile, load_profiles
from logical_operator_router import LogicalOperatorRouter
from operator_score import OperatorScoreResult, rank_actors, TaskEvidence
from evidence_ledger import EvidenceLedger, build_scheduler_decision
from context_store import ContextStore
from capability_token import CapabilityToken
from verification_gate import VerificationGate

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))


class SubmitResult:
    """Result of actor_runtime.submit()."""

    def __init__(
        self,
        success: bool,
        lease: Optional[LeaseState] = None,
        inbox_path: Optional[str] = None,
        outbox_path: Optional[str] = None,
        evidence_ledger_path: Optional[str] = None,
        scheduler_decision: Optional[Dict] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.lease = lease
        self.inbox_path = inbox_path
        self.outbox_path = outbox_path
        self.evidence_ledger_path = evidence_ledger_path
        self.scheduler_decision = scheduler_decision
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "lease": self.lease.to_dict() if self.lease else None,
            "inbox_path": self.inbox_path,
            "outbox_path": self.outbox_path,
            "evidence_ledger_path": self.evidence_ledger_path,
            "scheduler_decision": self.scheduler_decision,
            "error": self.error,
        }


class ActorRuntime:
    """Main runtime for submitting tasks to actors."""

    def __init__(
        self,
        harness_dir: Optional[Path] = None,
        lease_broker: Optional[LeaseBroker] = None,
        mailbox_base: Optional[Path] = None,
        evidence_ledger: Optional[EvidenceLedger] = None,
        context_store: Optional[ContextStore] = None,
        profiles_path: Optional[Path] = None,
        bindings_path: Optional[Path] = None,
    ):
        self.harness_dir = harness_dir or HARNESS_DIR
        self.broker = lease_broker or LeaseBroker(self.harness_dir / "run" / "actor-leases")
        self.mailbox_base = mailbox_base or self.harness_dir / "actors"
        self.ledger = evidence_ledger or EvidenceLedger()
        self.ctx_store = context_store or ContextStore()
        self.profiles = load_profiles(profiles_path)
        self.router = LogicalOperatorRouter(bindings_path)

    def submit(
        self,
        task_envelope: Dict[str, Any],
        logical_operator: Optional[str] = None,
        actor_id: Optional[str] = None,
        sprint_id: str = "",
        node_id: str = "",
        ttl_sec: int = 2700,
        capability_token: Optional[CapabilityToken] = None,
    ) -> SubmitResult:
        """Submit a task envelope to an actor.

        1. Validate capability token if provided
        2. Resolve actor via logical operator or direct actor_id
        3. Acquire lease
        4. Write task envelope to mailbox inbox
        5. Write evidence ledger
        6. Return lease and paths
        """
        task_id = task_envelope.get("task_id", str(uuid.uuid4()))

        # Validate capability token
        if capability_token:
            validation = capability_token.validate_for_lease()
            if not validation["valid"]:
                return SubmitResult(success=False, error=f"capability_token_invalid: {validation['issues']}")

        # Resolve actor
        if not actor_id and logical_operator:
            selected, rejected = self.router.select_actor(logical_operator)
            if not selected:
                return SubmitResult(success=False, error=f"no_available_actor_for_{logical_operator}")
            actor_id = selected
        elif not actor_id:
            return SubmitResult(success=False, error="no_actor_id_or_logical_operator")

        # Check profile risk denial
        profile = self.profiles.get(actor_id)
        evidence_path = f"actors/{actor_id}/evidence/{task_id}"

        # Acquire lease
        lease = self.broker.acquire(
            actor_id=actor_id,
            task_id=task_id,
            sprint_id=sprint_id,
            node_id=node_id,
            ttl_sec=ttl_sec,
            evidence_path=evidence_path,
        )
        if not lease:
            return SubmitResult(success=False, error=f"lease_acquisition_failed_for_{actor_id}")

        # Write to mailbox
        mailbox = ActorMailbox(actor_id, self.mailbox_base)
        # Load context packet if referenced
        ctx_ref = task_envelope.get("context_packet_ref")
        if ctx_ref:
            ctx_data = self.ctx_store.resolve_ref(ctx_ref)
            if ctx_data:
                task_envelope["context_packet"] = ctx_data

        inbox_path = mailbox.submit_task(task_envelope)
        outbox_dir = str(mailbox.outbox)

        # Build scheduler decision
        sched_decision = build_scheduler_decision(
            selected_actor=actor_id,
            logical_operator=logical_operator or "",
            score_factors={},
            penalties={},
            rejected=[],
        )

        # Write evidence ledger
        ledger_path = self.ledger.write_run_entry(
            task_id=task_id,
            sprint_id=sprint_id,
            node_id=node_id,
            actor_id=actor_id,
            logical_operator=logical_operator or "",
            scheduler_decision=sched_decision,
            context_packet_id=ctx_ref.get("packet_id") if ctx_ref else None,
            final_report_target=f"run/{sprint_id}/final_report.md",
        )

        return SubmitResult(
            success=True,
            lease=lease,
            inbox_path=inbox_path,
            outbox_path=outbox_dir,
            evidence_ledger_path=ledger_path,
            scheduler_decision=sched_decision,
        )
