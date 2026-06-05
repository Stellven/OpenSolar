from __future__ import annotations

import json
import os
import sys

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.survey import schemas


def test_survey_dataclasses_have_schema_version():
    classes = [
        schemas.SurveyRun,
        schemas.SurveyQuestion,
        schemas.SourceMatrix,
        schemas.SurveyReportAST,
        schemas.ChapterSpec,
        schemas.SectionSpec,
        schemas.EvidencePack,
        schemas.SectionReview,
        schemas.SurveyScorecard,
    ]
    for cls in classes:
        assert "schema_version" in cls.__dataclass_fields__, cls.__name__


def test_to_dict_serializes_nested_dataclasses():
    chapter = schemas.ChapterSpec("ch01", "Intro", 1, 1000, "objective")
    section = schemas.SectionSpec("ch01/sec01", "ch01", "Section", 1, 500, "question", ["paper"], 2, 1)
    ast = schemas.SurveyReportAST("ast", "run", "Title", 50000, [chapter], [section])
    payload = schemas.to_dict(ast)
    assert payload["schema_version"] == schemas.SCHEMA_VERSION
    assert payload["chapters"][0]["chapter_id"] == "ch01"
    assert payload["sections"][0]["section_id"] == "ch01/sec01"


def _signal_pack(signal_id: str = "signal_compound_systems") -> schemas.CAISSignalPack:
    return schemas.CAISSignalPack(
        signal_id=signal_id,
        source=schemas.CAISSourceRef(type="accepted_paper", title="Evidence-backed paper"),
        raw_signal="Agents require system-level evaluation.",
        technical_challenge="Runtime behavior must be observable across tools.",
        agent_development_implication="Agent stacks need explicit contracts.",
        solar_absorption=schemas.SolarAbsorption(
            design_thesis="Represent agent behavior as portable runtime traces.",
            new_schema=["AgentRuntimeTrace"],
            new_operators=["RuntimeTraceCollector"],
            new_gates=["runtime_trace_gate"],
        ),
        forecast=schemas.Forecast(
            claim="Trace portability becomes a selection criterion.",
            confidence=0.7,
            leading_indicators=["conference benchmark tracks"],
            falsification_condition="No evaluation venues adopt trace-based review.",
        ),
        artifact_path="cais_paper_signal_packs.jsonl",
        evidence_ids=["ev_signal"],
    )


def _absorption_map(signal_id: str = "signal_compound_systems") -> schemas.SolarAbsorptionMap:
    return schemas.SolarAbsorptionMap(
        absorption_items=[
            schemas.SolarAbsorptionItem(
                cais_signal=signal_id,
                solar_problem="Current runtime lacks durable behavior traces.",
                solar_design="Add trace collection and replay gates.",
                operators=["RuntimeTraceCollector"],
                schemas=["AgentRuntimeTrace"],
                gates=["runtime_trace_gate"],
                priority="P0",
                evidence_ids=["ev_signal"],
            )
        ],
        artifact_path="paper_to_solar_absorption_map.json",
    )


def _prediction(prediction_id: str = "pred_trace_portability") -> schemas.PredictionPacket:
    return schemas.PredictionPacket(
        prediction_id=prediction_id,
        claim="Trace-portable agents will be easier to certify.",
        time_horizon="24-36 months",
        confidence=0.64,
        drivers=["evaluation pressure"],
        counter_scenario="Model-only benchmark gains dominate evaluation.",
        leading_indicators=["new trace benchmark"],
        falsification_condition="No trace benchmark appears in the target window.",
        signal_refs=["signal_compound_systems"],
        artifact_path="prediction_packets.jsonl",
    )


def _figure() -> schemas.FigureSpec:
    return schemas.FigureSpec(
        figure_id="fig_trace_runtime",
        title="Trace Runtime",
        figure_type="architecture_diagram",
        grounding_ids=["ev_signal"],
        spec_data={"nodes": [{"id": "trace", "grounding_id": "ev_signal"}]},
        artifact_path="assets/figures/fig_trace_runtime.svg",
    )


def _section_card() -> schemas.SectionRenderCard:
    figure = _figure()
    return schemas.SectionRenderCard(
        section_id="sec_trace",
        title="Agent evaluation shifts toward runtime traces",
        title_claim_type="thesis",
        body_blocks=[{"type": "paragraph", "text": "Evidence-backed synthesis."}],
        figure=figure,
        evidence_callouts=[{"evidence_id": "ev_signal", "summary": "Conference signal"}],
        takeaways=["Solar should validate runtime traces."],
        citations=[{"evidence_id": "ev_signal", "marker": "[cite:ev_signal]"}],
        solar_absorption=["runtime_trace_gate"],
        prediction_packet_refs=["pred_trace_portability"],
        artifact_path="section_render_cards/sec_trace.json",
    )


def test_insight_artifact_bundle_validates_required_fields_paths_and_cross_refs():
    result = schemas.validate_insight_artifact_bundle(
        signal_packs=[_signal_pack()],
        absorption_map=_absorption_map(),
        prediction_packets=[_prediction()],
        section_cards=[_section_card()],
        figure_specs=[_figure()],
        artifact_paths={
            "conference_signal_map": "conference_signal_map.json",
            "prediction_packets": "prediction_packets.jsonl",
            "section_card": "section_render_cards/sec_trace.json",
        },
    )
    assert result.ok is True
    assert result.issues == []


def test_insight_artifact_bundle_reports_consumable_cross_ref_errors():
    result = schemas.validate_insight_artifact_bundle(
        signal_packs=[_signal_pack()],
        absorption_map=_absorption_map(signal_id="missing_signal"),
        prediction_packets=[_prediction()],
        section_cards=[_section_card()],
        figure_specs=[],
        artifact_paths={"bad": "../escape.json"},
    )
    assert result.ok is False
    issue_payload = result.to_dict()["issues"]
    codes = {issue["code"] for issue in issue_payload}
    assert "unsafe_artifact_path" in codes
    assert "missing_signal_ref" in codes
    assert "missing_figure_ref" in codes
    assert all("schema_name" in issue and "remediation" in issue for issue in issue_payload)


def test_prediction_packet_rejects_missing_required_fields():
    result = schemas.validate_prediction_packet(
        {
            "prediction_id": "pred_x",
            "claim": "x",
            "time_horizon": "12 months",
            "confidence": 1.5,
            "drivers": [],
            "counter_scenario": "",
            "leading_indicators": ["indicator"],
            "falsification_condition": "condition",
        }
    )
    assert result.ok is False
    codes = {issue.code for issue in result.issues}
    assert {"confidence_range", "required_list", "required_text"} <= codes


def test_insight_writers_emit_deterministic_json_and_jsonl(tmp_path):
    signal_path = tmp_path / "cais_paper_signal_packs.jsonl"
    map_path = tmp_path / "paper_to_solar_absorption_map.json"
    packet_path = tmp_path / "prediction_packets.jsonl"
    card_path = tmp_path / "section_render_cards" / "sec_trace.json"

    schemas.write_cais_signal_packs([_signal_pack()], signal_path)
    schemas.write_solar_absorption_map(_absorption_map(), map_path)
    schemas.write_prediction_packets([_prediction()], packet_path)
    schemas.write_section_render_card(_section_card(), card_path)

    signal_line = json.loads(signal_path.read_text(encoding="utf-8").strip())
    map_payload = json.loads(map_path.read_text(encoding="utf-8"))
    packet_line = json.loads(packet_path.read_text(encoding="utf-8").strip())
    card_payload = json.loads(card_path.read_text(encoding="utf-8"))

    assert signal_line["signal_id"] == "signal_compound_systems"
    assert map_payload["absorption_items"][0]["cais_signal"] == "signal_compound_systems"
    assert packet_line["prediction_id"] == "pred_trace_portability"
    assert card_payload["figure"]["figure_id"] == "fig_trace_runtime"
    assert map_path.read_text(encoding="utf-8").endswith("\n")
