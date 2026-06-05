from __future__ import annotations

import json
import os
import sys

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.survey.conference_signal_extractor import (  # noqa: E402
    INSIGHT_AMMUNITION_GAP_KINDS,
    build_conference_signal_artifacts,
    detect_insight_ammunition_gaps,
)
from research.survey.prediction_packet_builder import build_prediction_packet_artifacts  # noqa: E402
from research.survey.solar_absorption_mapper import build_solar_absorption_artifacts  # noqa: E402
from research.survey.typed_claim_compiler import compile_typed_claim_artifacts  # noqa: E402


def _signal_pack(signal_id: str = "signal_trace_runtime") -> dict:
    return {
        "signal_id": signal_id,
        "source": {
            "type": "accepted_paper",
            "title": "Evidence-backed Agent Runtime Paper",
            "track": "Evaluation & Benchmarking",
            "url": "https://example.test/paper",
        },
        "raw_signal": "Agent systems need observable runtime traces.",
        "technical_challenge": "Runtime behavior is hard to verify across tools.",
        "agent_development_implication": "Agent development needs portable trace contracts.",
        "solar_absorption": {
            "design_thesis": "Solar should preserve agent runtime traces as first-class evidence.",
            "new_schema": ["RuntimeBehaviorTrace"],
            "new_operators": ["RuntimeTraceCollector"],
            "new_gates": ["runtime_trace_gate"],
        },
        "forecast": {
            "claim": "Trace-level evaluation will become a platform differentiator.",
            "confidence": 0.7,
            "leading_indicators": ["conference evaluation tracks"],
            "falsification_condition": "No trace-based benchmark emerges in the horizon.",
        },
        "artifact_path": "cais_paper_signal_packs.jsonl",
        "evidence_ids": ["ev_trace"],
    }


def _absorption_item(signal_id: str = "signal_trace_runtime") -> dict:
    return {
        "cais_signal": signal_id,
        "solar_problem": "Solar reports lack durable trace-backed action mapping.",
        "solar_design": "Introduce RuntimeTraceCollector and trace gates.",
        "operators": ["RuntimeTraceCollector"],
        "schemas": ["RuntimeBehaviorTrace"],
        "gates": ["runtime_trace_gate"],
        "priority": "P0",
        "evidence_ids": ["ev_trace"],
    }


def _prediction(signal_id: str = "signal_trace_runtime") -> dict:
    return {
        "prediction_id": "pred_trace_evals",
        "claim": "Trace-level agent evaluation will become a buying criterion.",
        "time_horizon": "24-36 months",
        "confidence": 0.68,
        "drivers": ["enterprise deployment risk"],
        "counter_scenario": "Model-only benchmark gains dominate procurement.",
        "leading_indicators": ["trace benchmark adoption"],
        "falsification_condition": "No trace benchmark or procurement requirement appears.",
        "signal_refs": [signal_id],
        "artifact_path": "prediction_packets.jsonl",
    }


def test_conference_signal_builder_writes_gate_ready_artifacts(tmp_path):
    result = build_conference_signal_artifacts(tmp_path, [_signal_pack()])

    assert result["ok"] is True
    signal_map = json.loads((tmp_path / "conference_signal_map.json").read_text(encoding="utf-8"))
    signal_pack = json.loads((tmp_path / "cais_paper_signal_packs.jsonl").read_text(encoding="utf-8").strip())
    assert signal_map["signal_count"] == 1
    assert signal_map["signals"][0]["signal_id"] == "signal_trace_runtime"
    assert signal_pack["technical_challenge"]


def test_absorption_builder_writes_map_and_roadmap(tmp_path):
    result = build_solar_absorption_artifacts(
        tmp_path,
        signal_packs=[_signal_pack()],
        absorption_items=[_absorption_item()],
    )

    assert result["ok"] is True
    absorption = json.loads((tmp_path / "paper_to_solar_absorption_map.json").read_text(encoding="utf-8"))
    roadmap = json.loads((tmp_path / "solar_operator_roadmap.json").read_text(encoding="utf-8"))
    assert absorption["absorption_items"][0]["cais_signal"] == "signal_trace_runtime"
    assert roadmap["roadmap_items"][0]["operators"] == ["RuntimeTraceCollector"]


def test_prediction_and_typed_claim_builders_write_required_artifacts(tmp_path):
    prediction_result = build_prediction_packet_artifacts(tmp_path, [_prediction()])
    claim_result = compile_typed_claim_artifacts(
        tmp_path,
        [
            {
                "claim_id": "claim_trace",
                "claim": "Trace evidence supports runtime verification.",
                "claim_type": "interpretive",
                "evidence_ids": ["ev_trace"],
                "signal_refs": ["signal_trace_runtime"],
            }
        ],
    )

    assert prediction_result["ok"] is True
    assert claim_result["ok"] is True
    prediction = json.loads((tmp_path / "prediction_packets.jsonl").read_text(encoding="utf-8").strip())
    claim_map = json.loads((tmp_path / "claim_evidence_map.json").read_text(encoding="utf-8"))
    assert prediction["falsification_condition"]
    assert claim_map["claims"][0]["evidence_ids"] == ["ev_trace"]


def test_builders_fail_closed_when_inputs_missing(tmp_path):
    results = [
        build_conference_signal_artifacts(tmp_path, []),
        build_solar_absorption_artifacts(tmp_path, signal_packs=[], absorption_items=[]),
        build_prediction_packet_artifacts(tmp_path, []),
        compile_typed_claim_artifacts(tmp_path, []),
    ]

    assert all(result["ok"] is False for result in results)
    assert all(result["reason"] == "required_inputs_missing" for result in results)
    assert any("missing_cais_paper_signals" in result["gap_kinds"] for result in results)
    assert any("missing_solar_absorption" in result["gap_kinds"] for result in results)
    assert set(INSIGHT_AMMUNITION_GAP_KINDS) >= {gap for result in results for gap in result["gap_kinds"]}


def test_detect_insight_ammunition_gap_kinds(tmp_path):
    result = detect_insight_ammunition_gaps(tmp_path)

    assert result["ok"] is False
    assert set(result["gap_kinds"]) == set(INSIGHT_AMMUNITION_GAP_KINDS)
