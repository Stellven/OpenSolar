"""apo_plan_compiler.py — explicit APO compile stages.

LogicalPlan -> CapsulePlan -> PhysicalPlan
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from capability_capsules import (
    CAPSULE_REGISTRY_PATH,
    default_capability_plan_for_logical_operator,
    get_registry_entry,
    load_capability_capsule_manifest,
)

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
LOGICAL_OPERATORS_PATH = HARNESS_DIR / "config" / "logical-operators.json"
PHYSICAL_OPERATORS_PATH = HARNESS_DIR / "config" / "physical-operators.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _logical_operator_def(logical_operator: str, path: Optional[Path] = None) -> Dict[str, Any]:
    payload = _load_json(path or LOGICAL_OPERATORS_PATH)
    return dict((payload.get("logical_operators") or {}).get(logical_operator, {}))


def logical_role_for_operator(logical_operator: str, path: Optional[Path] = None) -> str:
    entry = _logical_operator_def(logical_operator, path=path)
    return str(entry.get("primary_role") or "builder")


def _capsule_manifest(capsule_id: str, registry_path: Optional[Path] = None) -> Dict[str, Any]:
    entry = get_registry_entry(capsule_id, path=registry_path or CAPSULE_REGISTRY_PATH, include_nonstable=True)
    if entry is None:
        return {}
    return load_capability_capsule_manifest(Path(entry.manifest_path))


def _make_stage(
    *,
    stage_id: str,
    stage_kind: str,
    capsule_id: str,
    dispatch_mode: str,
    reason: str,
    role: str = "",
    task_type: str = "",
    operator_constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "stage_id": stage_id,
        "stage_kind": stage_kind,
        "capability_capsule_id": capsule_id,
        "dispatch_mode": dispatch_mode,
        "role": role,
        "task_type": task_type,
        "reason": reason,
        "operator_constraints": dict(operator_constraints or {}),
    }


def build_capsule_plan_node(
    node: Dict[str, Any],
    *,
    request_type: str = "",
    lane_hint: str = "",
    registry_path: Optional[Path] = None,
) -> Dict[str, Any]:
    logical_operator = str(node.get("logical_operator") or "")
    base_plan = dict(node.get("capsule_plan") or {})
    if not base_plan:
        base_plan = default_capability_plan_for_logical_operator(
            logical_operator,
            request_type=request_type,
            lane_hint=lane_hint,
            node=node,
            registry_path=registry_path or CAPSULE_REGISTRY_PATH,
        )
    if not base_plan:
        return {
            "schema_version": "solar.capsule_plan_node.v1",
            "node_id": str(node.get("id") or ""),
            "logical_operator": logical_operator,
            "request_type": request_type,
            "lane_hint": lane_hint,
            "selected": False,
            "stages": [],
        }

    capsule_id = str(base_plan.get("capability_capsule_id") or "")
    manifest = _capsule_manifest(capsule_id, registry_path=registry_path)
    bindings = manifest.get("bindings", {})
    verification = manifest.get("verification", {})
    op_constraints = dict(base_plan.get("operator_constraints") or manifest.get("operator_compatibility") or {})
    task_type = str(base_plan.get("dispatch_task_type") or node.get("dispatch_task_type") or node.get("type") or "")
    role = logical_role_for_operator(logical_operator)

    stages: List[Dict[str, Any]] = []
    for index, guard_id in enumerate(bindings.get("required_guard_capsules", []) or [], start=1):
        guard_manifest = _capsule_manifest(str(guard_id), registry_path=registry_path)
        stages.append(
            _make_stage(
                stage_id=f"{node.get('id')}:guard:{index}",
                stage_kind="guard",
                capsule_id=str(guard_id),
                dispatch_mode="attached",
                reason="required_guard_capsules",
                role=role,
                task_type=task_type,
                operator_constraints=guard_manifest.get("operator_compatibility", {}),
            )
        )

    for index, resource_id in enumerate(bindings.get("required_resource_capsules", []) or [], start=1):
        resource_manifest = _capsule_manifest(str(resource_id), registry_path=registry_path)
        stages.append(
            _make_stage(
                stage_id=f"{node.get('id')}:resource:{index}",
                stage_kind="resource",
                capsule_id=str(resource_id),
                dispatch_mode="attached",
                reason="required_resource_capsules",
                role=role,
                task_type=task_type,
                operator_constraints=resource_manifest.get("operator_compatibility", {}),
            )
        )

    stages.append(
        _make_stage(
            stage_id=f"{node.get('id')}:capability",
            stage_kind="capability",
            capsule_id=capsule_id,
            dispatch_mode="execute",
            reason=str(base_plan.get("selection_mode") or "logical_operator_default"),
            role=role,
            task_type=task_type,
            operator_constraints=op_constraints,
        )
    )

    preferred_verifiers = list((verification.get("external_verifier") or {}).get("preferred_capsules", []) or [])
    if bool((verification.get("external_verifier") or {}).get("required")):
        for index, verifier_id in enumerate(preferred_verifiers, start=1):
            if str(verifier_id) == capsule_id:
                continue
            verifier_manifest = _capsule_manifest(str(verifier_id), registry_path=registry_path)
            verifier_kind = str(verifier_manifest.get("capsule_kind") or "capability")
            dispatch_mode = "execute" if verifier_kind == "capability" else "attached"
            verifier_role = logical_role_for_operator("Verifier") if dispatch_mode == "execute" else role
            verifier_task_type = "verification" if dispatch_mode == "execute" else task_type
            stages.append(
                _make_stage(
                    stage_id=f"{node.get('id')}:verifier:{index}",
                    stage_kind="verifier",
                    capsule_id=str(verifier_id),
                    dispatch_mode=dispatch_mode,
                    reason="external_verifier.required",
                    role=verifier_role,
                    task_type=verifier_task_type,
                    operator_constraints=verifier_manifest.get("operator_compatibility", {}),
                )
            )

    return {
        "schema_version": "solar.capsule_plan_node.v1",
        "node_id": str(node.get("id") or ""),
        "logical_operator": logical_operator,
        "request_type": request_type,
        "lane_hint": lane_hint,
        "goal": str(node.get("goal") or ""),
        "selected": True,
        "capability_capsule_id": capsule_id,
        "dispatch_task_type": task_type,
        "role": role,
        "required_guard_capsules": list(bindings.get("required_guard_capsules", []) or []),
        "required_resource_capsules": list(bindings.get("required_resource_capsules", []) or []),
        "selected_skills": list(base_plan.get("selected_skills") or bindings.get("skills", {}).get("required", []) or []),
        "stages": stages,
    }


def build_capsule_plan_ir(
    task_graph: Dict[str, Any],
    *,
    request_type: str = "",
    lane_hint: str = "",
    registry_path: Optional[Path] = None,
) -> Dict[str, Any]:
    nodes = [
        build_capsule_plan_node(
            dict(node),
            request_type=request_type,
            lane_hint=lane_hint,
            registry_path=registry_path,
        )
        for node in task_graph.get("nodes", []) or []
    ]
    return {
        "schema_version": "solar.capsule_plan_ir.v1",
        "sprint_id": task_graph.get("sprint_id", "N/A"),
        "request_type": request_type,
        "lane_hint": lane_hint,
        "dag_variant": task_graph.get("dag_variant"),
        "nodes": nodes,
    }


def _is_dispatchable_runtime(operator_id: str) -> bool:
    try:
        from operator_runtime import get_operator_runtime_state
    except Exception:
        return True
    return get_operator_runtime_state(operator_id) == "idle"


def enumerate_physical_candidates(
    *,
    role: str,
    task_type: str = "",
    logical_operator: str = "",
    operator_constraints: Optional[Dict[str, Any]] = None,
    prefer_operator: str = "",
    require_dispatchable: bool = False,
    operators_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    registry = _load_json(operators_path or PHYSICAL_OPERATORS_PATH)
    operators = registry.get("operators", {}) or {}
    constraints = dict(operator_constraints or {})
    preferred_ops = set(constraints.get("preferred", []) or [])
    forbidden_ops = set(constraints.get("forbidden", []) or [])
    default_profile = str(constraints.get("default_operator_profile") or "")
    candidates: List[Dict[str, Any]] = []

    for op_id, spec in operators.items():
        if prefer_operator and op_id != prefer_operator:
            continue
        if op_id in forbidden_ops:
            continue
        enabled = bool(spec.get("enabled", False))
        available = bool(spec.get("available", False))
        if not enabled or not available:
            continue
        if require_dispatchable and not _is_dispatchable_runtime(op_id):
            continue
        roles = [str(r).lower() for r in spec.get("roles", [spec.get("role", "")])]
        if role and role.lower() not in roles:
            continue

        priority = 0
        kind = str(spec.get("launch_cmd_kind", "") or spec.get("backend", ""))
        if "print_once" in kind or "print" in kind:
            priority += 10
        elif "command" in kind:
            priority += 5
        else:
            priority += 1

        task_classes = [str(t).lower() for t in spec.get("task_classes", [])]
        if task_type and any(task_type.lower() in tc for tc in task_classes):
            priority += 3
        preferred_for = [str(item).lower() for item in spec.get("preferred_for", [])]
        if logical_operator and logical_operator.lower() in preferred_for:
            priority += 2
        if role.lower() in preferred_for:
            priority += 2
        if preferred_ops and op_id in preferred_ops:
            priority += 20
        if default_profile and (op_id == default_profile or str(spec.get("profile", "")) == default_profile):
            priority += 8
        candidates.append(
            {
                "operator_id": op_id,
                "priority": priority,
                "role": role,
                "task_type": task_type,
                "profile": spec.get("profile"),
                "model": spec.get("model"),
                "preferred_for": spec.get("preferred_for", []),
            }
        )

    candidates.sort(key=lambda item: (-int(item["priority"]), str(item["operator_id"])))
    return candidates


def build_physical_plan_for_capsule_node(
    capsule_plan_node: Dict[str, Any],
    *,
    prefer_operator: str = "",
    require_dispatchable: bool = False,
    operators_path: Optional[Path] = None,
) -> Dict[str, Any]:
    execute_stage = next((stage for stage in capsule_plan_node.get("stages", []) if stage.get("stage_kind") == "capability"), None)
    verifier_stages = [
        stage for stage in capsule_plan_node.get("stages", [])
        if stage.get("stage_kind") == "verifier" and stage.get("dispatch_mode") == "execute"
    ]
    attached_stages = [
        stage for stage in capsule_plan_node.get("stages", [])
        if stage.get("dispatch_mode") != "execute"
    ]

    selected_operator_id = ""
    execution_candidates: List[Dict[str, Any]] = []
    if execute_stage:
        execution_candidates = enumerate_physical_candidates(
            role=str(execute_stage.get("role") or capsule_plan_node.get("role") or ""),
            task_type=str(execute_stage.get("task_type") or capsule_plan_node.get("dispatch_task_type") or ""),
            logical_operator=str(capsule_plan_node.get("logical_operator") or ""),
            operator_constraints=dict(execute_stage.get("operator_constraints") or {}),
            prefer_operator=prefer_operator,
            require_dispatchable=require_dispatchable,
            operators_path=operators_path,
        )
        if execution_candidates:
            selected_operator_id = str(execution_candidates[0]["operator_id"])

    verifier_plans = []
    for stage in verifier_stages:
        candidates = enumerate_physical_candidates(
            role=str(stage.get("role") or "evaluator"),
            task_type=str(stage.get("task_type") or "verification"),
            logical_operator="Verifier",
            operator_constraints=dict(stage.get("operator_constraints") or {}),
            require_dispatchable=require_dispatchable,
            operators_path=operators_path,
        )
        verifier_plans.append(
            {
                "stage_id": stage.get("stage_id"),
                "capability_capsule_id": stage.get("capability_capsule_id"),
                "candidates": candidates,
                "selected_operator_id": str(candidates[0]["operator_id"]) if candidates else "",
            }
        )

    return {
        "schema_version": "solar.physical_plan_node.v1",
        "node_id": capsule_plan_node.get("node_id"),
        "logical_operator": capsule_plan_node.get("logical_operator"),
        "capability_capsule_id": capsule_plan_node.get("capability_capsule_id"),
        "dispatch_task_type": capsule_plan_node.get("dispatch_task_type"),
        "selected_operator_id": selected_operator_id,
        "execution_candidates": execution_candidates,
        "attached_capsules": attached_stages,
        "verifier_plans": verifier_plans,
    }


def compile_execution_plan_for_node(
    node: Dict[str, Any],
    *,
    request_type: str = "",
    lane_hint: str = "",
    prefer_operator: str = "",
    registry_path: Optional[Path] = None,
    require_dispatchable: bool = False,
    operators_path: Optional[Path] = None,
) -> Dict[str, Any]:
    capsule_plan = build_capsule_plan_node(
        node,
        request_type=request_type,
        lane_hint=lane_hint,
        registry_path=registry_path,
    )
    physical_plan = build_physical_plan_for_capsule_node(
        capsule_plan,
        prefer_operator=prefer_operator,
        require_dispatchable=require_dispatchable,
        operators_path=operators_path,
    )
    return {
        "logical_plan_node": {
            "node_id": node.get("id"),
            "logical_operator": node.get("logical_operator"),
            "goal": node.get("goal"),
            "depends_on": list(node.get("depends_on", []) or []),
        },
        "capsule_plan": capsule_plan,
        "physical_plan": physical_plan,
    }
