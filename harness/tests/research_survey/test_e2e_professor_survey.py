from __future__ import annotations

import json
import os
import sys

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.survey.evaluator import evaluate_survey
from research.survey.evidence_pack import build_evidence_packs
from research.survey.planner import create_survey_plan, write_survey_plan
from research.survey.section_compiler import compile_section, compile_survey


def _append_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_e2e_professor_survey_smoke(tmp_path):
    plan = create_survey_plan("隐空间推理技术架构和演进方向", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    assert len(plan["report_ast"]["chapters"]) >= 8
    assert len(plan["report_ast"]["sections"]) >= 30

    weak = build_evidence_packs(tmp_path, plan["report_ast"])
    assert weak["blocked"] == len(plan["report_ast"]["sections"])
    assert evaluate_survey(tmp_path, strict=True)["ok"] is False

    sources = [{"id": f"src_{i}", "source_type": t, "title": t} for i, t in enumerate(["paper", "official_doc", "code", "benchmark"])]
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % 4]["id"], "content": "latent reasoning architecture evaluation deployment survey"} for i in range(48)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence and deployment boundaries"} for i in range(48)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(48)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)

    strong = build_evidence_packs(tmp_path, plan["report_ast"])
    assert strong["ready"] >= 30
    for section in plan["report_ast"]["sections"][:3]:
        assert compile_section(tmp_path, section["section_id"])["ok"] is True
    assert compile_survey(tmp_path)["ok"] is True
    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is True
    assert result["scorecard"]["finalized_sections"] == 3
