#!/usr/bin/env python3
"""Tests for explicit APO plan compilation stages."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import apo_plan_compiler as apo


def test_build_capsule_plan_node_inserts_guard_resource_and_verifier():
    node = {
        "id": "S2",
        "goal": "Implement the approved scope.",
        "logical_operator": "ImplementationWorker",
        "depends_on": ["S1"],
        "type": "implementation",
        "capability_native": True,
        "capability_capsule_id": "cap.requirement-compiler-implementation",
        "dispatch_task_type": "implementation",
        "capsule_plan": {
            "capability_native": True,
            "capability_capsule_id": "cap.requirement-compiler-implementation",
            "dispatch_task_type": "implementation",
            "logical_operator": "ImplementationWorker",
            "required_guard_capsules": ["guard.secret-leak-guard"],
            "required_resource_capsules": ["resource.repo-workspace"],
            "selected_skills": ["skill.multi-file-implementation"],
            "operator_constraints": {
                "preferred": ["mini-claude-sonnet-builder"],
                "forbidden": [],
                "default_operator_profile": "mini-claude-sonnet-builder",
            },
        },
    }
    plan = apo.build_capsule_plan_node(
        node,
        request_type="implementation",
        lane_hint="delivery",
        registry_path=ROOT / "config" / "capability-capsules.registry.yaml",
    )
    assert [stage["stage_kind"] for stage in plan["stages"]] == [
        "guard",
        "resource",
        "capability",
        "verifier",
    ]
    assert plan["stages"][-1]["capability_capsule_id"] == "cap.requirement-compiler-verification"
    assert "artifact.task_graph_node" in plan["artifact_types"]["consumes"]
    assert "artifact.patch_diff" in plan["artifact_types"]["produces"]
    assert "repo.worktree" in plan["effect_union"]["write"]
    kinds = {item["kind"] for item in plan["proof_obligations"]}
    assert "self_check" in kinds
    assert "pass_condition" in kinds
    assert "external_verifier" in kinds


def test_build_physical_plan_for_capsule_node_prefers_capsule_operator():
    capsule_plan_node = {
        "node_id": "S2",
        "logical_operator": "ImplementationWorker",
        "capability_capsule_id": "cap.requirement-compiler-implementation",
        "dispatch_task_type": "implementation",
        "role": "builder",
        "stages": [
            {
                "stage_id": "S2:capability",
                "stage_kind": "capability",
                "capability_capsule_id": "cap.requirement-compiler-implementation",
                "dispatch_mode": "execute",
                "role": "builder",
                "task_type": "implementation",
                "operator_constraints": {
                    "preferred": ["mini-claude-sonnet-builder"],
                    "forbidden": [],
                    "default_operator_profile": "mini-claude-sonnet-builder",
                },
            }
        ],
    }
    plan = apo.build_physical_plan_for_capsule_node(
        capsule_plan_node,
        require_dispatchable=False,
        operators_path=ROOT / "config" / "physical-operators.json",
    )
    assert plan["selected_operator_id"] == "mini-claude-sonnet-builder"
    assert plan["execution_candidates"][0]["operator_id"] == "mini-claude-sonnet-builder"


def test_build_capsule_plan_ir_aggregates_effects_artifacts_and_proofs():
    task_graph = {
        "sprint_id": "sprint-apo-types",
        "nodes": [
            {
                "id": "S1",
                "goal": "Design plan",
                "logical_operator": "DeepArchitect",
                "type": "planning",
            },
            {
                "id": "S2",
                "goal": "Implement scope",
                "logical_operator": "ImplementationWorker",
                "type": "implementation",
            },
        ],
    }
    plan_ir = apo.build_capsule_plan_ir(
        task_graph,
        request_type="implementation",
        lane_hint="delivery",
        registry_path=ROOT / "config" / "capability-capsules.registry.yaml",
    )
    assert plan_ir["schema_version"] == "solar.capsule_plan_ir.v1"
    assert "artifact.requirement_ir" in plan_ir["artifact_types"]["consumes"]
    assert "artifact.handoff_md" in plan_ir["artifact_types"]["produces"]
    assert "repo.read" in plan_ir["effect_union"]["read"]
    assert "artifacts.handoff" in plan_ir["effect_union"]["write"]
    assert any(item["kind"] == "external_verifier" for item in plan_ir["proof_obligations"])


def test_build_physical_plan_inherits_type_effect_and_proof_metadata():
    node = {
        "id": "S2",
        "goal": "Implement scope",
        "logical_operator": "ImplementationWorker",
        "type": "implementation",
        "capability_native": True,
        "capability_capsule_id": "cap.requirement-compiler-implementation",
    }
    compiled = apo.compile_execution_plan_for_node(
        node,
        request_type="implementation",
        registry_path=ROOT / "config" / "capability-capsules.registry.yaml",
        operators_path=ROOT / "config" / "physical-operators.json",
    )
    physical = compiled["physical_plan"]
    assert physical["artifact_types"]["produces"]
    assert "repo.worktree" in physical["effect_union"]["write"]
    assert any(item["kind"] == "postcondition" for item in physical["proof_obligations"])


def test_rewrite_adapter_stage_for_missing_required_inputs():
    stages = [
        {
            "stage_id": "S9:capability",
            "stage_kind": "capability",
            "capability_capsule_id": "cap.synthetic",
            "dispatch_mode": "execute",
            "role": "builder",
            "task_type": "implementation",
            "reason": "synthetic",
            "operator_constraints": {},
            "artifact_types": {
                "required_inputs": ["artifact.unavailable_input"],
                "optional_inputs": [],
                "required_outputs": ["artifact.synthetic_output"],
                "optional_outputs": [],
                "consumes": ["artifact.unavailable_input"],
                "produces": ["artifact.synthetic_output"],
            },
            "effect_profile": {key: [] for key in apo.EFFECT_KEYS},
            "proof_obligations": [],
        }
    ]
    rewritten = apo._rewrite_adapter_stages(  # type: ignore[attr-defined]
        stages,
        node={"id": "S9", "goal": "Synthetic", "logical_operator": "ImplementationWorker", "type": "implementation"},
        request_type="implementation",
        adapter_registry_path=ROOT / "config" / "artifact-adapter-capsules.registry.yaml",
    )
    assert [stage["stage_kind"] for stage in rewritten] == ["adapter", "capability"]
    assert rewritten[0]["capability_capsule_id"] == "adapter.artifact-type-bridge"
    assert rewritten[0]["adapter_rule"]["missing_required_inputs"] == ["artifact.unavailable_input"]


def test_rewrite_adapter_stage_selects_registry_capsule_for_type_pair():
    stages = [
        {
            "stage_id": "S10:capability",
            "stage_kind": "capability",
            "capability_capsule_id": "cap.synthetic",
            "dispatch_mode": "execute",
            "role": "planner",
            "task_type": "planning",
            "reason": "synthetic",
            "operator_constraints": {},
            "artifact_types": {
                "required_inputs": ["artifact.design_md"],
                "optional_inputs": [],
                "required_outputs": ["artifact.synthetic_output"],
                "optional_outputs": [],
                "consumes": ["artifact.design_md"],
                "produces": ["artifact.synthetic_output"],
            },
            "effect_profile": {key: [] for key in apo.EFFECT_KEYS},
            "proof_obligations": [],
        }
    ]
    rewritten = apo._rewrite_adapter_stages(  # type: ignore[attr-defined]
        stages,
        node={"id": "S10", "goal": "Synthetic", "logical_operator": "DeepArchitect", "type": "planning"},
        request_type="planning",
        adapter_registry_path=ROOT / "config" / "artifact-adapter-capsules.registry.yaml",
    )
    assert [stage["stage_kind"] for stage in rewritten] == ["adapter", "capability"]
    assert rewritten[0]["capability_capsule_id"] == "adapter.requirement-ir-to-design-brief"
    assert rewritten[0]["artifact_types"]["produces"] == ["artifact.design_md"]
    assert rewritten[0]["adapter_rule"]["registry_match"]["target_artifacts"] == ["artifact.design_md"]
