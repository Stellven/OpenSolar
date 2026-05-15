from __future__ import annotations

import json
import os
import sys

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.survey.evidence_pack import build_evidence_packs
from research.survey.planner import create_survey_plan, write_survey_plan
from research.survey.section_compiler import compile_section, compile_survey


def _append_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _strong_fixture(root):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, root)
    sources = [{"id": f"src_{i}", "source_type": t, "title": t} for i, t in enumerate(["paper", "official_doc", "code", "benchmark"])]
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % 4]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(16)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(12)]
    links = [{"claim_id": f"cl_{i % 12}", "evidence_id": f"ev_{i}"} for i in range(16)]
    _append_jsonl(root / "sources.jsonl", sources)
    _append_jsonl(root / "evidence.jsonl", evidence)
    _append_jsonl(root / "claims.jsonl", claims)
    _append_jsonl(root / "claim_evidence.jsonl", links)
    build_evidence_packs(root, plan["report_ast"])
    return plan


def test_compile_section_refuses_blocked_pack(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    build_evidence_packs(tmp_path, plan["report_ast"])
    result = compile_section(tmp_path, "ch01/sec01")
    assert result["ok"] is False
    assert result["reason"] == "evidence_pack_blocked"


def test_compile_section_and_survey(tmp_path):
    _strong_fixture(tmp_path)
    result = compile_section(tmp_path, "ch01/sec01")
    assert result["ok"] is True
    assert (tmp_path / "sections" / "ch01" / "sec01" / "final.md").exists()
    compiled = compile_survey(tmp_path)
    assert compiled["ok"] is True
    assert (tmp_path / "final.md").exists()
