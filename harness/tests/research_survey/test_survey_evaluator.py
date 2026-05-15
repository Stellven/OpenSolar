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


def test_strict_eval_fails_five_section_brief(tmp_path):
    ast = {
        "title": "brief",
        "chapters": [{"chapter_id": "ch1", "title": "Brief"}],
        "sections": [{"section_id": f"ch1/sec{i}", "chapter_id": "ch1", "title": f"S{i}"} for i in range(5)],
    }
    (tmp_path / "survey_report_ast.json").write_text(json.dumps(ast), encoding="utf-8")
    (tmp_path / "survey_evidence_packs.json").write_text(json.dumps({"blocked": 0}), encoding="utf-8")
    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is False
    assert "chapter_count_low:1<8" in result["scorecard"]["issues"]
    assert "section_count_low:5<30" in result["scorecard"]["issues"]


def test_strict_eval_passes_controlled_strong_fixture(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = [{"id": f"src_{i}", "source_type": t, "title": t} for i, t in enumerate(["paper", "official_doc", "code", "benchmark"])]
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % 4]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(40)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(40)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    for section in plan["report_ast"]["sections"][:3]:
        compile_section(tmp_path, section["section_id"])
    compile_survey(tmp_path)
    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is True
    assert result["scorecard"]["chapter_count"] >= 8
    assert result["scorecard"]["section_count"] >= 30
