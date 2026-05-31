"""harness.py — CompileGEPAAdapter: connects CompileEval to GEPA optimizer.

This module bridges the compile evaluation harness (dimensions + hard
validators) with the existing GEPA optimizer infrastructure at
``integrations/gepa_optimizer/``.

Core principle: GEPA only optimises profiles, never touches canonical
artifacts directly; production compile pipeline stays deterministic.

Integration points (read-only reuse):
* ``integrations/gepa_optimizer/adapter.py`` — ``GEPAAdapter.run()``
* ``integrations/gepa_optimizer/promote.py`` — ``Promoter.promote/rollback``
* ``integrations/gepa_optimizer/artifact_store.py`` — candidate storage
* ``integrations/gepa_optimizer/budgets.py`` — budget control
"""
from __future__ import annotations

import dataclasses
import datetime
import datetime as _dt
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

from .dimensions import evaluate as _evaluate_dimensions
from .hard_validators import run_hard_validators as _run_hard_validators
from .asi_trace import ASITrace, init_trace_db, write_trace as _write_trace

__all__ = ["CompileGEPAAdapter", "CompileEvalResult"]

# Weights for ASI composite score
_DIMENSION_WEIGHTS: dict[str, float] = {
    "ir_schema_compliance": 0.15,
    "contract_completeness": 0.15,
    "dag_executability": 0.15,
    "acceptance_coverage": 0.15,
    "prd_contract_dag_alignment": 0.15,
    "trace_consistency": 0.10,
    "coverage_score": 0.15,
}


@dataclasses.dataclass
class CompileEvalResult:
    """Result of evaluating compiled artifacts."""

    asi_score: float
    dimension_scores: dict[str, float]
    hard_validators_passed: bool
    hard_validator_failures: list[str]
    hard_validator_details: dict[str, tuple[bool, str]]
    compile_artifacts: dict[str, Any] = dataclasses.field(default_factory=dict)
    side_info: dict[str, Any] = dataclasses.field(default_factory=dict)


def _load_codex_pm_router_module():
    tools_dir = Path(__file__).resolve().parents[2] / "tools"
    module_path = tools_dir / "codex_pm_router.py"
    if "compile_eval_codex_pm_router" in sys.modules:
        return sys.modules["compile_eval_codex_pm_router"]
    spec = importlib.util.spec_from_file_location("compile_eval_codex_pm_router", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["compile_eval_codex_pm_router"] = module
    spec.loader.exec_module(module)
    return module


def _profile_policy_params(profile: dict[str, Any], key: str) -> dict[str, Any]:
    policies = profile.get("policies") if isinstance(profile.get("policies"), dict) else {}
    policy = policies.get(key) if isinstance(policies, dict) else None
    if not isinstance(policy, dict):
        return {}
    params = policy.get("params")
    return params if isinstance(params, dict) else {}


def _normalize_compiled_artifacts(payload: dict[str, Any], candidate_profile: dict[str, Any]) -> dict[str, Any]:
    requirement_ir = dict(payload.get("requirement_ir") or {})
    compiled = dict(payload.get("compiled_artifacts") or {})
    task_dag = dict(compiled.get("task_dag") or payload.get("task_graph_skeleton") or {})
    contract_files = compiled.get("contract_files") if isinstance(compiled.get("contract_files"), dict) else {}
    product_contract = contract_files.get("product") if isinstance(contract_files, dict) else {}
    product_contract = product_contract if isinstance(product_contract, dict) else {}
    acceptance_list = list(product_contract.get("acceptance") or [])
    acceptance_map = {
        f"ACC-{idx + 1}": str(item)
        for idx, item in enumerate(acceptance_list)
        if str(item).strip()
    }
    contract_goal = str(product_contract.get("goal") or requirement_ir.get("normalized_goal") or "").strip()
    traces = {
        "planner": {"nodes": [str(node.get("id") or "") for node in (task_dag.get("nodes") or []) if str(node.get("id") or "")]},
        "builder": {"nodes": [str(node.get("id") or "") for node in (task_dag.get("nodes") or []) if str(node.get("id") or "")]},
        "evaluator": {"nodes": [str(node.get("id") or "") for node in (task_dag.get("nodes") or []) if str(node.get("id") or "")]},
    }
    return {
        "requirement_ir": {
            "goal": requirement_ir.get("normalized_goal") or requirement_ir.get("user_intent") or "",
            "success_metrics": acceptance_list,
            "non_goals": list(product_contract.get("non_goals") or []),
            "schema_version": requirement_ir.get("schema_version", ""),
            "source_requirement_ir": requirement_ir,
        },
        "contracts": {
            "goal": contract_goal,
            "policies": candidate_profile.get("policies", {}),
            "acceptance": acceptance_map,
            "manifest": compiled.get("contracts_bundle") or {},
            "product_contract": product_contract,
        },
        "dag": task_dag,
        "traces": traces,
        "closure": compiled.get("closure_record") or {},
        "task_dag_state": compiled.get("task_dag_state") or {},
    }


def _expected_case_payload(case: Any) -> dict[str, Any]:
    return {
        "requirement_text": getattr(case, "input", ""),
        "expected_ir": getattr(case, "expected_ir", {}) or {},
        "expected_contracts": getattr(case, "expected_contracts", []) or [],
        "expected_dag": getattr(case, "expected_dag", {}) or {},
        "sprint_id": getattr(case, "sprint_id", "") or "",
    }


class CompileGEPAAdapter:
    """Bridge between compile evaluation and GEPA optimizer.

    Usage::

        adapter = CompileGEPAAdapter(trace_db="/tmp/asi_traces.db")
        result = adapter.evaluate(artifacts, expected)
        fitness = adapter.fitness_function(candidate_profile, golden_cases)
    """

    def __init__(
        self,
        *,
        trace_db: Optional[str] = None,
        profile_id: str = "",
        profile_version: int = 0,
        task_type: str = "compile",
        sprint_id: str = "",
    ) -> None:
        self._trace_db = trace_db
        self._profile_id = profile_id
        self._profile_version = profile_version
        self._task_type = task_type
        self._sprint_id = sprint_id

        if trace_db:
            init_trace_db(trace_db)

    def evaluate(
        self,
        artifacts: dict[str, Any],
        expected: dict[str, Any],
        *,
        golden_case_id: str = "",
        side_info: Optional[dict[str, Any]] = None,
    ) -> CompileEvalResult:
        """Evaluate artifacts and compute ASI score + dimension breakdown.

        Parameters
        ----------
        artifacts : dict
            Compiled artifacts (requirement_ir, contracts, dag, traces).
        expected : dict
            Expected ground truth for comparison.
        golden_case_id : str
            ID of the golden case being evaluated (for trace recording).

        Returns
        -------
        CompileEvalResult
        """
        # Compute dimension scores
        dimension_scores = _evaluate_dimensions(artifacts, expected)

        # Run hard validators
        hv_result = _run_hard_validators(artifacts)

        # Compute ASI composite score
        asi_score = 0.0
        for dim_name, weight in _DIMENSION_WEIGHTS.items():
            asi_score += dimension_scores.get(dim_name, 0.0) * weight

        # Hard failure penalty: drop ASI to 0 if any validator fails
        if not hv_result.passed:
            asi_score = 0.0

        result = CompileEvalResult(
            asi_score=asi_score,
            dimension_scores=dimension_scores,
            hard_validators_passed=hv_result.passed,
            hard_validator_failures=hv_result.failures,
            hard_validator_details=hv_result.details,
            compile_artifacts=artifacts,
            side_info=side_info or {},
        )

        # Record trace
        if self._trace_db:
            trace = ASITrace(
                trace_id=uuid.uuid4().hex[:16],
                timestamp=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                profile_id=self._profile_id,
                profile_version=self._profile_version,
                task_type=self._task_type,
                sprint_id=self._sprint_id,
                asi_score=asi_score,
                dimension_scores=dimension_scores,
                hard_validators_passed=[
                    code for code, (passed, _) in hv_result.details.items() if passed
                ],
                hard_validators_failed=[
                    code for code, (passed, _) in hv_result.details.items() if not passed
                ],
                golden_case_used=golden_case_id,
            )
            _write_trace(self._trace_db, trace)

        return result

    def compile_case(
        self,
        candidate_profile: dict[str, Any],
        case: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Compile one golden case via the deterministic requirement compiler."""
        router = _load_codex_pm_router_module()
        intake_kwargs: dict[str, Any] = {
            "text": getattr(case, "input", ""),
            "sprint_id": getattr(case, "sprint_id", "") or "",
            "compiler_profile": candidate_profile,
        }
        raw_payload = router.build_pm_intake(**intake_kwargs)
        normalized = _normalize_compiled_artifacts(raw_payload, candidate_profile)
        compile_side_info = {
            "profile_id": candidate_profile.get("profile_id", ""),
            "profile_version": candidate_profile.get("version", 0),
            "golden_case_id": getattr(case, "sprint_id", "") or "",
            "request_text": getattr(case, "input", ""),
            "raw_payload_summary": {
                "classification": raw_payload.get("classification"),
                "canonical_request_type": raw_payload.get("canonical_request_type"),
                "dag_variant": raw_payload.get("dag_variant"),
                "node_count": len((raw_payload.get("compiled_artifacts") or {}).get("task_dag", {}).get("nodes", []) or []),
            },
        }
        return normalized, compile_side_info

    def fitness_function(
        self,
        candidate_profile: dict[str, Any],
        golden_cases: list[Any],
    ) -> float:
        """Evaluate a candidate profile across golden cases.

        Parameters
        ----------
        candidate_profile : dict
            The compiler profile being evaluated by GEPA.
        golden_cases : list
            List of GoldenCase objects to evaluate against.

        Returns
        -------
        float
            Mean ASI score across all golden cases.
        """
        if not golden_cases:
            return 0.0

        scores: list[float] = []
        for case in golden_cases:
            artifacts, compile_side_info = self.compile_case(candidate_profile, case)
            expected = _expected_case_payload(case)

            result = self.evaluate(
                artifacts, expected,
                golden_case_id=case.sprint_id,
                side_info=compile_side_info,
            )
            scores.append(result.asi_score)

        return sum(scores) / len(scores) if scores else 0.0

    def propose(self, base_profile: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Propose a new candidate profile variant.

        This delegates to the existing GEPA optimizer for actual proposal
        generation.  Here we provide a thin wrapper that records intent.

        Parameters
        ----------
        base_profile : dict
            The base profile to mutate from.
        **kwargs
            Forwarded to GEPA proposal mechanism.

        Returns
        -------
        dict
            A candidate profile dict (may be the base with perturbed params).
        """
        import copy
        candidate = copy.deepcopy(base_profile)

        # Increment version for the candidate
        candidate["version"] = candidate.get("version", 1) + 1

        # Apply parameter perturbations if provided
        perturbations = kwargs.get("perturbations", {})
        policies = candidate.get("policies", {})
        for policy_key, param_changes in perturbations.items():
            if policy_key in policies:
                params = policies[policy_key].get("params", {})
                params.update(param_changes)
                policies[policy_key]["params"] = params

        return candidate

    def promote(
        self,
        candidate_profile: dict[str, Any],
        *,
        profiles_dir: Optional[str] = None,
        db_path: Optional[str] = None,
    ) -> dict[str, Any]:
        """Promote a candidate profile to the registry.

        Delegates to the registry module for persistence.

        Returns
        -------
        dict
            Registration result with profile_id, version, path.
        """
        from ..compiler_profile.registry import register

        return register(
            candidate_profile,
            profiles_dir=profiles_dir and __import__("pathlib").Path(profiles_dir),
            db_path=db_path and __import__("pathlib").Path(db_path),
        )

    def rollback(
        self,
        profile_id: str,
        target_version: int,
        *,
        db_path: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Rollback to a previous profile version by activating it.

        Returns
        -------
        dict or None
            The activated profile, or None if not found.
        """
        from ..compiler_profile.registry import activate

        return activate(
            profile_id,
            version=target_version,
            db_path=db_path and __import__("pathlib").Path(db_path),
        )
