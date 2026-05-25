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

