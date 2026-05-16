from __future__ import annotations

import json
import os
import sys

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.cli import main
from research.survey.auto_repair import run_auto_repair
from research.survey.evidence_pack import build_evidence_packs
from research.survey.planner import create_survey_plan, write_survey_plan
from research.survey.writing_loop import run_section_revision_loop


def _append_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _fixture(root):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, root)
    sources = [{"id": f"src_{i}", "source_type": t, "title": t} for i, t in enumerate(["paper", "official_doc", "code", "benchmark"])]
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % 4]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(48)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(48)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(48)]
    _append_jsonl(root / "sources.jsonl", sources)
    _append_jsonl(root / "evidence.jsonl", evidence)
    _append_jsonl(root / "claims.jsonl", claims)
    _append_jsonl(root / "claim_evidence.jsonl", links)
    build_evidence_packs(root, plan["report_ast"])
    return plan


def _break_section(root, section_id="ch01/sec01"):
    section_dir = root / "sections" / section_id
    section_dir.mkdir(parents=True, exist_ok=True)
    (section_dir / "final.md").write_text("# Broken\n\nNo tags.\n", encoding="utf-8")
    (section_dir / "review.json").write_text(json.dumps({
        "section_id": section_id,
        "verdict": "PASS",
        "unsupported_claim_rate": 0.0,
        "citation_span_accuracy": 1.0,
        "source_diversity_score": 1.0,
        "repetition_score": 0.0,
        "issues": [],
    }), encoding="utf-8")


def test_auto_repair_rewrites_failed_section(tmp_path):
    _fixture(tmp_path)
    _break_section(tmp_path)
    payload = run_auto_repair(tmp_path, max_passes=1, min_finalized=1, min_chars=100)
    assert payload["ok"] is True
    assert payload["reason"] == "repaired"
    assert payload["iterations"][0]["queue_count"] == 1
    assert payload["iterations"][0]["rewrite_run"]["passed"] == 1
    assert payload["blocked_issues"] == []
    assert (tmp_path / "sections" / "ch01" / "sec01" / "final.before_rewrite.md").exists()
    assert (tmp_path / "survey_auto_repair.json").exists()


def test_auto_repair_reports_already_passed(tmp_path):
    _fixture(tmp_path)
    run_section_revision_loop(tmp_path, "ch01/sec01", min_chars=100)
    payload = run_auto_repair(tmp_path, max_passes=1, min_finalized=1, min_chars=100)
    assert payload["ok"] is True
    assert payload["reason"] == "already_passed"
    assert payload["iterations"] == []


def test_auto_repair_waits_for_human_packet(tmp_path):
    _fixture(tmp_path)
    _break_section(tmp_path)
    payload = run_auto_repair(tmp_path, max_passes=1, min_finalized=1, min_chars=100, writer_backend="human-packet")
    assert payload["ok"] is False
    assert payload["reason"] == "waiting_for_writer"
    assert payload["waiting"] == 1
    assert payload["iterations"][0]["rewrite_run"]["results"][0]["expected_response"].endswith("human_responses/round_01.md")


def test_auto_repair_cli_allow_pending(tmp_path, capsys):
    _fixture(tmp_path)
    _break_section(tmp_path)
    rc = main([
        "survey-auto-repair",
        "--output-dir", str(tmp_path),
        "--min-finalized", "1",
        "--writer-backend", "human-packet",
        "--allow-pending",
        "--json",
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason"] == "waiting_for_writer"
    assert payload["waiting"] == 1
