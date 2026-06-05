"""Release-gate coverage for DeepDive Insight Runtime v2.

These tests exercise the public compiler/gate/scheduler modules used by the
runtime, not detached helper copies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from activation_proof import (
    BROKER_COVERAGE_FIELDS,
    build_activation_proof,
    validate_against_schema,
)
from graph_scheduler import parent_ready_check
from research.deepdive_requirement_compiler import (
    DeepDiveCompileOptions,
    compile_deepdive_brief,
    validate_deepdive_contract,
)
from research.survey.insight_gates import run_all_insight_gates


CAIS_BRIEF = (
    "DeepDive insight for CAIS 2026 accepted papers and Solar harness impact. "
    "Explain what the Agent papers imply for Solar operators, schemas, gates, "
    "runtime DAGs, and falsifiable roadmap decisions."
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _minimal_ast(title: str = "CAIS Agent Insight") -> dict[str, object]:
    return {
        "title": title,
        "chapters": [
            {"title": "Thesis-led CAIS signal map"},
            {"title": "Solar operator schema gate mapping"},
            {"title": "Prediction packet and watchlist"},
        ],
    }


def _write_golden_release_fixture(root: Path) -> None:
    contract = compile_deepdive_brief(
        CAIS_BRIEF,
        options=DeepDiveCompileOptions(profile="cais-agent-insight", source_channel="deepdive"),
    )
    _write_json(root / "deepdive_requirement_contract.json", contract)
    _write_json(root / "survey_report_ast.json", _minimal_ast())
    _write_json(
        root / "figures.json",
        {"figures": [{"id": f"figure-{idx}", "claim_id": f"claim-{idx}"} for idx in range(6)]},
    )
    _write_jsonl(
        root / "prediction_packets.jsonl",
        [
            {
                "id": f"prediction-{idx}",
                "drivers": ["agent benchmark pressure", "Solar runtime adoption"],
                "leading_indicators": ["schema PR count", "gate failure trend"],
                "counter_scenario": "CAIS agent methods remain lab-only.",
                "falsification_condition": "No operator or schema adoption within two releases.",
            }
            for idx in range(4)
        ],
    )
    citations = " ".join(f"[{idx}](https://example.org/cais/{idx})" for idx in range(1, 11))
    text = f"""
# CAIS Agent Insight

The central thesis of this DeepDive is that CAIS 2026 agent work should change
Solar runtime design now, not become a generic survey appendix. Dossier,
Do Agents Need to Plan Step-by-Step?, Open Agent Specification, TraceFix, and
AI Agents for Discovery in the Wild are treated as concrete signals.

Solar operator mapping: add a DeepDiveInsightThesisPlanner operator, a
CAISSignalPack operator, and a ChiefInsightEditor operator. Solar schema
mapping: CAISSignalPack, SolarAbsorptionMap, PredictionPacket,
SectionRenderCard, and FigureSpec. Solar gate mapping: GenericSurveyTOCGate,
MachineLabelLeakGate, CitationVisibilityGate, PredictionPacketGate,
VisualAuditGate, and UserQuestionFitnessGate.

What is the central thesis of this DeepDive? CAIS agent evidence should route
Solar toward stricter planning, trace repair, and artifact visibility. Which
concrete signals and evidence support, weaken, or complicate the thesis? The
five CAIS signals above support it, while lab-to-production transfer risk
complicates it. What actions, designs, experiments, roadmap items, schemas,
operators, or quality gates should follow when applicable? The listed operators,
schemas, and gates should be wired into the D10-D18 runtime.

What are the key technical, product, strategic, or ecosystem implications? The
technical implication is trace-aware planning; the product implication is a
visible release gate; the strategic implication is moving CAIS evidence into
Solar roadmap choices; the ecosystem implication is clearer operator/schema
contracts across agent tooling.

Prediction watch: drivers include stronger agent traces and Solar runtime
adoption; leading indicators include gate failures and schema PRs; falsification
requires no measurable adoption. Forecast sections expose driver, indicator,
counter-scenario, and falsification logic to readers.

<figure><img src="figures/figure-1.svg" alt="CAIS signal map"></figure>
<figure><img src="figures/figure-2.svg" alt="Solar absorption map"></figure>
<figure><img src="figures/figure-3.svg" alt="Agent challenge matrix"></figure>
<figure><img src="figures/figure-4.svg" alt="Runtime DAG"></figure>
<figure><img src="figures/figure-5.svg" alt="Prediction watchlist"></figure>
<figure><img src="figures/figure-6.svg" alt="Gate map"></figure>

Visible evidence: {citations}
"""
    (root / "final.html").write_text(text, encoding="utf-8")


def _write_failed_generic_fixture(root: Path) -> None:
    _write_json(
        root / "survey_report_ast.json",
        {
            "title": "Generic Agent Survey",
            "chapters": [
                {"title": "问题定义与研究边界"},
                {"title": "历史脉络与技术演进"},
                {"title": "核心架构范式"},
                {"title": "方法分类与代表系统"},
            ],
        },
    )
    (root / "final.md").write_text(
        "Generic CAIS survey with source_type official_doc, claim_id, and evidence_id labels.",
        encoding="utf-8",
    )


def test_cais_profile_compiler_exposes_release_runtime_contract() -> None:
    contract = compile_deepdive_brief(
        CAIS_BRIEF,
        options=DeepDiveCompileOptions(profile="cais-agent-insight", source_channel="deepdive"),
    )

    verdict = validate_deepdive_contract(contract)
    assert verdict["ok"], verdict
    assert contract["mode"] == "insight"
    assert contract["insight_profile"]["profile_id"] == "cais-agent-insight"
    assert "DD_INSIGHT" in contract["deepdive_dag"]["required_gates"]

    nodes = {node["id"]: node for node in contract["deepdive_dag"]["nodes"]}
    assert set(nodes) >= {f"D{idx}" for idx in range(10, 19)}
    assert nodes["D11"]["gate"] == "DD_INSIGHT"
    assert nodes["D11"]["evaluator_sidecar"] == "signal_coverage_eval.json"
    assert "prediction_packets.jsonl" in nodes["D14"]["artifact_paths"]
    assert "final.html" in nodes["D18"]["artifact_paths"]


def test_failed_cais_generic_survey_fixture_fails_negative_controls(tmp_path: Path) -> None:
    _write_failed_generic_fixture(tmp_path)

    results = run_all_insight_gates(tmp_path, json.loads((tmp_path / "survey_report_ast.json").read_text()))
    failed = {result["gate_id"] for result in results if not result["ok"]}
    failure_details = {result["gate_id"]: result for result in results if not result["ok"]}

    assert "generic_survey_toc" in failed
    assert "machine_label_leak" in failed
    assert "solar_actionability" in failed
    assert "cais_coverage" in failed
    assert "figure_required" in failed
    assert "citation_visibility" in failed
    assert "prediction_packet" in failed
    assert "official_doc" in failure_details["machine_label_leak"]["matched_patterns"]
    assert {"operator", "schema", "gate"} <= set(failure_details["solar_actionability"]["missing_fields"])
    assert failure_details["figure_required"]["missing_fields"] == ["figures:0<6"]
    assert failure_details["citation_visibility"]["missing_fields"] == ["visible_sources:0<10"]


def test_golden_mvp_fixture_passes_human_html_release_gates(tmp_path: Path) -> None:
    _write_golden_release_fixture(tmp_path)

    results = run_all_insight_gates(tmp_path, json.loads((tmp_path / "survey_report_ast.json").read_text()))
    failures = {result["gate_id"]: result for result in results if not result["ok"]}

    assert failures == {}
    final_html = (tmp_path / "final.html").read_text(encoding="utf-8")
    for forbidden in ("source_type", "claim_id", "evidence_id", "Execution Metrics"):
        assert forbidden not in final_html
    for required in ("operator", "schema", "gate", "Prediction", "<figure"):
        assert required in final_html


def test_parent_epic_release_gate_blocks_until_all_nodes_and_required_gates_pass() -> None:
    graph = {
        "sprint_id": "epic-release-check",
        "required_gates": ["G_IMPL", "G_S05_VERIFICATION_RELEASE_PASSED"],
        "nodes": [
            {"id": "S03_core_runtime", "status": "passed", "gate": "G_IMPL"},
            {"id": "S04_orchestration_ui", "status": "passed", "gate": "G_IMPL"},
            {"id": "S05_verification_release", "status": "reviewing", "gate": "G_IMPL"},
        ],
    }

    with_open_node = parent_ready_check(graph)
    assert with_open_node["ready"] is False
    assert with_open_node["open_nodes"] == ["S05_verification_release"]

    graph["nodes"][2]["status"] = "passed"
    missing_gate = parent_ready_check(graph)
    assert missing_gate["ready"] is False
    assert missing_gate["missing_gates"] == ["G_S05_VERIFICATION_RELEASE_PASSED"]

    graph["gate_results"] = {"G_S05_VERIFICATION_RELEASE_PASSED": {"status": "passed"}}
    releasable = parent_ready_check(graph)
    assert releasable["ready"] is True


def test_activation_proof_schema_is_reproducible_for_release_evidence() -> None:
    proof = build_activation_proof(
        "sprint-20260604-p0-p1-deepdive-insight-runtime-v2-请读取并执行需求文档-users-lisihao-s05-verification-release",
    )

    assert proof["ok"] is True
    assert proof["sprint_id"].endswith("s05-verification-release")
    assert set(BROKER_COVERAGE_FIELDS) <= set(proof["broker_coverage"])
    validation = validate_against_schema(proof["broker_coverage"])
    assert validation["ok"] is True
