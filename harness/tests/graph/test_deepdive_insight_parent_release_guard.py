"""Parent-release guard checks for DeepDive Insight Runtime v2 S05."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from activation_proof import build_activation_proof, validate_against_schema
from graph_scheduler import parent_ready_check


SPRINT_ID = (
    "sprint-20260604-p0-p1-deepdive-insight-runtime-v2-"
    "请读取并执行需求文档-users-lisihao-s05-verification-release"
)


def _parent_epic_graph(s05_status: str = "reviewing") -> dict[str, object]:
    return {
        "sprint_id": "epic-20260604-p0-p1-deepdive-insight-runtime-v2",
        "required_gates": [
            "G_S03_CORE_RUNTIME_READY",
            "G_S04_ORCHESTRATION_UI_READY",
            "G_S05_VERIFICATION_RELEASE_READY",
            "G_S05_EVALUATOR_ACCEPTED",
        ],
        "gate_results": {
            "G_S03_CORE_RUNTIME_READY": {"status": "passed"},
            "G_S04_ORCHESTRATION_UI_READY": {"status": "passed"},
        },
        "nodes": [
            {
                "id": "S03_core_runtime",
                "status": "passed",
                "gate": "G_S03_CORE_RUNTIME_READY",
            },
            {
                "id": "S04_orchestration_ui",
                "status": "passed",
                "gate": "G_S04_ORCHESTRATION_UI_READY",
            },
            {
                "id": "S05_verification_release",
                "status": s05_status,
                "gate": "G_S05_VERIFICATION_RELEASE_READY",
            },
        ],
    }


def test_parent_epic_cannot_close_while_s05_is_not_passed() -> None:
    verdict = parent_ready_check(_parent_epic_graph(s05_status="reviewing"))

    assert verdict["ok"] is True
    assert verdict["ready"] is False
    assert verdict["open_nodes"] == ["S05_verification_release"]
    assert verdict["missing_gates"] == [
        "G_S05_VERIFICATION_RELEASE_READY",
        "G_S05_EVALUATOR_ACCEPTED",
    ]


def test_parent_epic_cannot_close_without_s05_required_gate() -> None:
    verdict = parent_ready_check(_parent_epic_graph(s05_status="passed"))

    assert verdict["ok"] is True
    assert verdict["ready"] is False
    assert verdict["open_nodes"] == []
    assert verdict["missing_gates"] == ["G_S05_EVALUATOR_ACCEPTED"]


def test_parent_epic_can_close_only_after_s05_gate_passes() -> None:
    graph = _parent_epic_graph(s05_status="passed")
    graph["gate_results"]["G_S05_VERIFICATION_RELEASE_READY"] = {"status": "passed"}  # type: ignore[index]
    graph["gate_results"]["G_S05_EVALUATOR_ACCEPTED"] = {"status": "passed"}  # type: ignore[index]

    verdict = parent_ready_check(graph)

    assert verdict["ok"] is True
    assert verdict["ready"] is True
    assert verdict["open_nodes"] == []
    assert verdict["missing_gates"] == []


def test_activation_proof_schema_validation_remains_reproducible() -> None:
    proof = build_activation_proof(SPRINT_ID)

    assert proof["ok"] is True
    assert proof["sprint_id"] == SPRINT_ID
    assert validate_against_schema(proof["broker_coverage"])["ok"] is True
