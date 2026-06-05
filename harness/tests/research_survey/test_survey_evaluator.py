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
from research.survey.insight_gates import (
    run_all_insight_gates,
    run_generic_survey_toc_gate,
    run_template_repetition_gate,
    run_machine_label_leak_gate,
    run_solar_actionability_gate,
    run_cais_coverage_gate,
    run_figure_required_gate,
    run_citation_visibility_gate,
    run_prediction_packet_gate,
    run_user_question_fitness_gate,
)

_FIXTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")
if _FIXTURE_DIR not in sys.path:
    sys.path.insert(0, _FIXTURE_DIR)
from research_survey.negative_cais_generic_survey_fixture import (
    create_negative_cais_generic_survey_fixture,
)


def _append_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _strong_sources():
    return [
        {"id": "src_0", "source_type": "paper", "title": "Latent Reasoning Paper", "url": "https://arxiv.org/abs/2412.06769"},
        {"id": "src_1", "source_type": "paper", "title": "Continuous Thought Paper", "url": "https://openreview.net/forum?id=latent-reasoning"},
        {"id": "src_2", "source_type": "paper", "title": "Reasoning Survey Proceedings", "url": "https://doi.org/10.1145/latent-reasoning"},
        {"id": "src_3", "source_type": "paper", "title": "Neural Computation Journal Article", "url": "https://ieeexplore.ieee.org/document/123456"},
        {"id": "src_4", "source_type": "official_doc", "title": "Official Developer Docs", "url": "https://docs.example.edu/latent-reasoning"},
        {"id": "src_5", "source_type": "code", "title": "Latent Reasoning Repository", "url": "https://github.com/example/latent-reasoning"},
        {"id": "src_6", "source_type": "benchmark", "title": "Latent Reasoning Benchmark", "url": "https://paperswithcode.com/task/latent-reasoning"},
        {"id": "src_7", "source_type": "benchmark", "title": "Hugging Face Evaluation Dataset", "url": "https://huggingface.co/datasets/example/latent-reasoning"},
    ]


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


def test_conference_insight_eval_rejects_correct_but_generic_report(tmp_path):
    ast = {
        "title": "深度报告：CAIS 2026 Agent 发展、技术挑战与 Solar 路线",
        "planner_mode": "conference_insight",
        "chapters": [
            {"chapter_id": f"ch{i}", "title": title}
            for i, title in enumerate([
                "问题定义与研究边界",
                "历史脉络与技术演进",
                "核心架构范式",
                "方法分类与代表系统",
                "评估方法与基准体系",
                "工程实现与部署约束",
                "风险、安全与可解释性",
                "产业生态与开源实现",
            ], start=1)
        ],
        "sections": [{"section_id": "ch1/sec1", "chapter_id": "ch1", "title": "研究问题与术语边界"}],
    }
    (tmp_path / "survey_report_ast.json").write_text(json.dumps(ast), encoding="utf-8")
    (tmp_path / "survey_plan.json").write_text(json.dumps({"planner_mode": "conference_insight"}), encoding="utf-8")
    (tmp_path / "survey_evidence_packs.json").write_text(json.dumps({"blocked": 0, "packs": []}), encoding="utf-8")
    (tmp_path / "human_final.md").write_text(
        """
        # CAIS 2026 Survey

        ## 问题定义与研究边界
        研究问题与术语边界。official_doc 和 paper 需要区分。claim_id=e1。

        ## 核心架构范式
        研究问题与术语边界。机制可行性不等于工程可控性。
        研究问题与术语边界。机制可行性不等于工程可控性。
        研究问题与术语边界。机制可行性不等于工程可控性。
        """,
        encoding="utf-8",
    )

    result = evaluate_survey(tmp_path, strict=True)

    assert result["ok"] is False
    assert result["insight_quality"]["active"] is True
    issues = result["scorecard"]["issues"]
    assert any(issue.startswith("insight_generic_survey_toc_leak") for issue in issues)
    assert any(issue.startswith("insight_machine_label_leak") for issue in issues)
    assert any(issue.startswith("insight_action_mapping_low") for issue in issues)
    assert any(issue.startswith("insight_solar_absorption_low") for issue in issues)
    assert "insight_figure_required_missing" in issues


def test_insight_required_signals_are_profile_configured_not_default(tmp_path):
    ast = {
        "title": "DeepDive insight: AI coding agent 产品机会",
        "profile": "deepdive-insight",
        "chapters": [{"chapter_id": "ch1", "title": "核心判断"}],
        "sections": [{"section_id": "ch1/sec1", "chapter_id": "ch1", "title": "核心判断"}],
        "insight_profile": {"required_signals": ["Spec Runtime"]},
    }
    (tmp_path / "survey_report_ast.json").write_text(json.dumps(ast), encoding="utf-8")
    (tmp_path / "survey_evidence_packs.json").write_text(json.dumps({"blocked": 0, "packs": []}), encoding="utf-8")
    (tmp_path / "human_final.md").write_text(
        """
        # AI coding agent DeepDive

        ## 核心判断
        AI coding agent 的中心论点是产品竞争正在转向工作流闭环。
        行动建议是先做实验验证和产品路线图，配套架构设计、观察指标、风险与证伪条件。
        https://example.com/source
        https://example.com/source2
        https://example.com/source3
        https://example.com/source4
        https://example.com/source5
        <figure>路线图</figure>
        """,
        encoding="utf-8",
    )

    result = evaluate_survey(tmp_path, strict=True)

    assert result["insight_quality"]["active"] is True
    assert any(issue.startswith("insight_required_signal_missing:Spec Runtime") for issue in result["scorecard"]["issues"])
    assert not any("Dossier" in issue or "TraceFix" in issue for issue in result["scorecard"]["issues"])


def test_strict_eval_passes_controlled_strong_fixture(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
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
    assert result["coverage"]["source_type_count"] == 4
    assert result["coverage"]["claim_support_coverage"] == 1.0
    assert result["taxonomy"]["taxonomy_depth_score"] >= 0.75
    assert result["contradiction_matrix"]["contradiction_coverage"] >= 0.80
    assert result["section_factual_audit"]["section_factual_accuracy"] == 1.0
    assert result["section_factual_audit"]["section_grounding_accuracy"] == 1.0
    assert result["section_scorecard"]["ok"] is True
    assert result["section_scorecard"]["needs_rewrite_count"] == 0
    assert result["chief_editor_review"]["ok"] is True
    assert result["depth_profile"]["ok"] is True
    assert (tmp_path / "survey_chief_editor.json").exists()
    assert (tmp_path / "survey_depth_profile.json").exists()


def test_strict_eval_fails_when_claims_have_no_evidence_links(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(40)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", [])
    build_evidence_packs(tmp_path, plan["report_ast"])
    for section in plan["report_ast"]["sections"][:3]:
        compile_section(tmp_path, section["section_id"])
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is False
    assert "claim_support_coverage_low:0.0000<0.8000" in result["scorecard"]["issues"]


def test_strict_eval_fails_when_source_types_are_too_narrow(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = [{"id": "src_0", "source_type": "paper", "title": "paper", "url": "https://arxiv.org/abs/0000.00000"}]
    evidence = [{"id": f"ev_{i}", "source_id": "src_0", "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(40)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(40)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is False
    assert "source_type_count_low:1<4" in result["scorecard"]["issues"]


def test_strict_eval_fails_when_taxonomy_is_shallow(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    for chapter in plan["report_ast"]["chapters"]:
        chapter["title"] = "General Notes"
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
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
    assert result["ok"] is False
    assert any(item.startswith("taxonomy_depth_score_low:") for item in result["scorecard"]["issues"])


def test_strict_eval_fails_when_contradiction_slots_are_missing(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(40)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(40)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    packs = build_evidence_packs(tmp_path, plan["report_ast"])
    for pack in packs["packs"]:
        pack["contradiction_slots"] = []
        section_pack = tmp_path / "sections" / pack["section_id"] / "evidence_pack.json"
        section_pack.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (tmp_path / "survey_evidence_packs.json").write_text(json.dumps(packs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for section in plan["report_ast"]["sections"][:3]:
        compile_section(tmp_path, section["section_id"])
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is False
    assert "contradiction_coverage_low:0.0000<0.8000" in result["scorecard"]["issues"]


def test_strict_eval_fails_when_section_references_out_of_pack_claim(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(40)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(40)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    for section in plan["report_ast"]["sections"][:3]:
        compile_section(tmp_path, section["section_id"])
    bad_final = tmp_path / "sections" / plan["report_ast"]["sections"][0]["section_id"] / "final.md"
    bad_final.write_text(
        bad_final.read_text(encoding="utf-8") + "\n\nInvalid unsupported claim [claim:cl_not_in_pack] [evidence:ev_not_in_pack]\n",
        encoding="utf-8",
    )
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is False
    assert "section_factual_accuracy_low:0.6667<0.9500" in result["scorecard"]["issues"]
    failed = result["section_factual_audit"]["failed_sections"]
    assert failed[0]["unknown_claim_ids"] == ["cl_not_in_pack"]
    assert failed[0]["unknown_evidence_ids"] == ["ev_not_in_pack"]
    top = result["section_scorecard"]["top_issues"][0]
    assert top["section_id"] == plan["report_ast"]["sections"][0]["section_id"]
    assert top["p0_count"] >= 2
    assert top["rewrite_recommended"] is True


def test_strict_eval_fails_when_section_has_no_claim_or_evidence_tags(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(40)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(40)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    for section in plan["report_ast"]["sections"][:3]:
        compile_section(tmp_path, section["section_id"])
    bad_final = tmp_path / "sections" / plan["report_ast"]["sections"][0]["section_id"] / "final.md"
    bad_final.write_text("A polished section with no factual tags.\n", encoding="utf-8")
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is False
    failed = result["section_factual_audit"]["failed_sections"]
    assert failed[0]["missing_claim_tags"] is True
    assert failed[0]["missing_evidence_tags"] is True


def test_strict_eval_fails_when_evidence_tag_context_is_not_grounded(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(40)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(40)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    for section in plan["report_ast"]["sections"][:3]:
        compile_section(tmp_path, section["section_id"])
    section_id = plan["report_ast"]["sections"][0]["section_id"]
    pack = json.loads((tmp_path / "sections" / section_id / "evidence_pack.json").read_text(encoding="utf-8"))
    allowed_claim = pack["claim_ids"][0]
    allowed_evidence = pack["evidence_ids"][0]
    bad_final = tmp_path / "sections" / section_id / "final.md"
    bad_final.write_text(
        f"# Bad Section\n\n## Claim\n\nBanana ocean unrelated sentence [claim:{allowed_claim}] [evidence:{allowed_evidence}]\n",
        encoding="utf-8",
    )
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is False
    assert "section_grounding_accuracy_low:0.6667<0.9500" in result["scorecard"]["issues"]
    failed = result["section_factual_audit"]["failed_sections"]
    assert failed[0]["grounding_failures"][0]["reason"] == "citation_context_not_grounded"
    assert result["section_scorecard"]["top_issues"][0]["issues"][0]["severity"] == "P0"


def test_section_scorecard_ranks_rewrite_candidates(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(40)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(40)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(40)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    for section in plan["report_ast"]["sections"][:3]:
        compile_section(tmp_path, section["section_id"])
    first = plan["report_ast"]["sections"][0]["section_id"]
    second = plan["report_ast"]["sections"][1]["section_id"]
    (tmp_path / "sections" / first / "final.md").write_text("No tags here.\n", encoding="utf-8")
    review = tmp_path / "sections" / second / "review.json"
    data = json.loads(review.read_text(encoding="utf-8"))
    data["issues"] = ["section_structure_shallow:3<6"]
    review.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True)
    top = result["section_scorecard"]["top_issues"]
    assert top[0]["section_id"] == first
    assert top[0]["p0_count"] == 2
    assert top[0]["risk_score"] > top[1]["risk_score"]


def test_complete_professor_gate_rejects_tiny_tagged_sections(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(80)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(80)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(80)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    for section in plan["report_ast"]["sections"]:
        section_id = section["section_id"]
        pack = json.loads((tmp_path / "sections" / section_id / "evidence_pack.json").read_text(encoding="utf-8"))
        claim_id = pack["claim_ids"][0]
        evidence_id = pack["evidence_ids"][0]
        final = tmp_path / "sections" / section_id / "final.md"
        final.write_text(
            f"# Tiny\n\n## Claim\n\nlatent reasoning architecture evaluation deployment [claim:{claim_id}] [evidence:{evidence_id}]\n",
            encoding="utf-8",
        )
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True, require_complete=True)
    assert result["ok"] is False
    assert result["final_quality"]["ok"] is False
    assert any(item.startswith("final_char_count_low:") for item in result["scorecard"]["issues"])
    assert any(item.startswith("avg_section_chars_low:") for item in result["scorecard"]["issues"])


def test_strict_eval_fails_low_authority_web_heavy_sources(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = [
        {"id": f"src_{i}", "source_type": "web", "title": f"SEO blog {i}", "url": f"https://blog.example.com/latent-{i}"}
        for i in range(12)
    ]
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(80)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(80)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(80)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True)
    assert result["ok"] is False
    assert result["source_coverage"]["ok"] is False
    assert any(item.startswith("survey_missing_required_source_types:") for item in result["scorecard"]["issues"])
    assert any(item.startswith("low_value_source_ratio_high:") for item in result["scorecard"]["issues"])


def test_chief_editor_gate_flags_duplicate_complete_sections(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(80)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(80)]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(80)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    duplicate_body = "# Duplicate\n\n## Claim\n\nlatent reasoning architecture evaluation deployment [claim:{claim_id}] [evidence:{evidence_id}]\n"
    for section in plan["report_ast"]["sections"]:
        section_id = section["section_id"]
        pack = json.loads((tmp_path / "sections" / section_id / "evidence_pack.json").read_text(encoding="utf-8"))
        final = tmp_path / "sections" / section_id / "final.md"
        final.write_text(duplicate_body.format(claim_id=pack["claim_ids"][0], evidence_id=pack["evidence_ids"][0]), encoding="utf-8")
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True, require_complete=True)
    assert result["ok"] is False
    assert result["chief_editor_review"]["ok"] is False
    assert any(item.startswith("chief_editor_section_duplicate_rate_high:") for item in result["scorecard"]["issues"])


def test_final_quality_flags_repeated_long_sentences_across_complete_report(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [
        {
            "id": f"ev_{i}",
            "source_id": sources[i % len(sources)]["id"],
            "content": "latent reasoning architecture evaluation deployment hidden state planning explicit verbalization benchmark coverage implementation constraints",
        }
        for i in range(96)
    ]
    claims = [
        {
            "id": f"cl_{i}",
            "claim_text": f"latent reasoning architecture claim {i} requires evaluation evidence and implementation constraints",
        }
        for i in range(96)
    ]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(96)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    repeated = (
        "Latent reasoning architecture evaluation deployment requires a balanced analysis of hidden state planning, "
        "explicit verbalization, benchmark coverage, and implementation constraints."
    )
    for section in plan["report_ast"]["sections"]:
        section_id = section["section_id"]
        pack = json.loads((tmp_path / "sections" / section_id / "evidence_pack.json").read_text(encoding="utf-8"))
        claim_ids = pack["claim_ids"][:3]
        evidence_ids = pack["evidence_ids"][:4]
        final = tmp_path / "sections" / section_id / "final.md"
        final.write_text(
            f"# {section['title']}\n\n"
            "## Research Question\n\n"
            f"{section['research_question']}\n\n"
            "## Position\n\n"
            f"{repeated} [claim:{claim_ids[0]}] [evidence:{evidence_ids[0]}]\n\n"
            "## Claim Map\n\n"
            f"1. Section-specific claim for {section_id} [claim:{claim_ids[0]}] [evidence:{evidence_ids[0]}]\n"
            f"2. Section-specific implementation constraint {section_id} [claim:{claim_ids[1]}] [evidence:{evidence_ids[1]}]\n"
            f"3. Section-specific evaluation boundary {section_id} [claim:{claim_ids[2]}] [evidence:{evidence_ids[2]}]\n\n"
            "## Evidence Map\n\n"
            f"- Evidence for architecture evaluation deployment {section_id} [evidence:{evidence_ids[0]}]\n"
            f"- Evidence for hidden state planning {section_id} [evidence:{evidence_ids[1]}]\n"
            f"- Evidence for benchmark coverage {section_id} [evidence:{evidence_ids[2]}]\n"
            f"- Evidence for implementation constraints {section_id} [evidence:{evidence_ids[3]}]\n\n"
            "## Source Map\n\n"
            "The section uses paper, official, code, and benchmark sources.\n\n"
            "## Architecture Synthesis\n\n"
            f"{repeated} This unique section {section_id} ties the repeated frame to a local architectural decision. "
            "The analysis expands the design axis, runtime implications, and evaluation constraints with grounded evidence.\n\n"
            "## Comparative Positioning\n\n"
            f"Compared with token-only chain-of-thought, section {section_id} separates latent search, explicit narration, and benchmark-facing outputs.\n\n"
            "## Evaluation And Risk Boundary\n\n"
            f"Evaluation for {section_id} must separate benchmark gains, hidden-state opacity, and reproducibility constraints. [claim:{claim_ids[1]}] [evidence:{evidence_ids[1]}]\n\n"
            "## Limitations And Failure Modes\n\n"
            f"Failure modes for {section_id} include hidden-state drift, unverifiable reasoning traces, and benchmark overfitting. [claim:{claim_ids[2]}] [evidence:{evidence_ids[2]}]\n\n"
            "## Contradiction Slots\n\n"
            f"Contradiction slot for {section_id}: latent compression can improve compute efficiency while reducing interpretability. [evidence:{evidence_ids[3]}]\n\n"
            "## Open Problems\n\n"
            f"Open problems for {section_id} include controllable latent planning, robust evaluation, and reproducible implementation contracts.\n",
            encoding="utf-8",
        )
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True, require_complete=True)
    assert result["ok"] is False
    assert result["final_quality"]["ok"] is False
    assert result["final_quality"]["max_duplicate_long_sentence_count"] >= 8
    assert any(item.startswith("final_duplicate_sentence_count_high:") for item in result["scorecard"]["issues"])


def test_depth_profile_rejects_long_but_shallow_complete_survey(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    sources = _strong_sources()
    evidence = [
        {
            "id": f"ev_{i}",
            "source_id": sources[i % len(sources)]["id"],
            "content": "latent reasoning architecture evaluation deployment evidence supports source-specific claims",
        }
        for i in range(96)
    ]
    claims = [
        {
            "id": f"cl_{i}",
            "claim_text": "latent reasoning architecture evaluation deployment requires evidence",
        }
        for i in range(96)
    ]
    links = [{"claim_id": f"cl_{i}", "evidence_id": f"ev_{i}"} for i in range(96)]
    _append_jsonl(tmp_path / "sources.jsonl", sources)
    _append_jsonl(tmp_path / "evidence.jsonl", evidence)
    _append_jsonl(tmp_path / "claims.jsonl", claims)
    _append_jsonl(tmp_path / "claim_evidence.jsonl", links)
    build_evidence_packs(tmp_path, plan["report_ast"])
    for section in plan["report_ast"]["sections"]:
        section_id = section["section_id"]
        pack = json.loads((tmp_path / "sections" / section_id / "evidence_pack.json").read_text(encoding="utf-8"))
        claim_ids = pack["claim_ids"][:3]
        evidence_ids = pack["evidence_ids"][:4]
        def shallow_sentence(label: str, idx: int) -> str:
            return (
                f"latent reasoning architecture evaluation deployment evidence section {section_id} "
                f"uses source-specific wording for {label} detail {idx} while still remaining shallow."
            )

        def shallow_block(label: str, count: int) -> str:
            return " ".join(shallow_sentence(label, idx) for idx in range(1, count + 1))

        final = tmp_path / "sections" / section_id / "final.md"
        final.write_text(
            f"# {section['title']}\n\n"
            "## Research Question\n\n"
            f"{section['research_question']}\n\n"
            "## Position\n\n"
            f"{shallow_block('position', 4)} [claim:{claim_ids[0]}] [evidence:{evidence_ids[0]}]\n\n"
            "## Claim Map\n\n"
            f"1. {shallow_sentence('claim', 1)} [claim:{claim_ids[0]}] [evidence:{evidence_ids[0]}]\n"
            f"2. {shallow_sentence('claim', 2)} [claim:{claim_ids[1]}] [evidence:{evidence_ids[1]}]\n"
            f"3. {shallow_sentence('claim', 3)} [claim:{claim_ids[2]}] [evidence:{evidence_ids[2]}]\n\n"
            "## Evidence Map\n\n"
            f"- {shallow_sentence('evidence', 1)} [evidence:{evidence_ids[0]}]\n"
            f"- {shallow_sentence('evidence', 2)} [evidence:{evidence_ids[1]}]\n"
            f"- {shallow_sentence('evidence', 3)} [evidence:{evidence_ids[2]}]\n"
            f"- {shallow_sentence('evidence', 4)} [evidence:{evidence_ids[3]}]\n\n"
            "## Source Map\n\n"
            f"Source families for {section_id} are listed as paper, official, code, and benchmark evidence without additional synthesis claims.\n\n"
            "## Architecture Synthesis\n\n"
            f"{shallow_block('architecture', 3)} [claim:{claim_ids[0]}] [evidence:{evidence_ids[0]}]\n\n"
            "## Comparative Positioning\n\n"
            f"{shallow_block('comparison', 3)} [claim:{claim_ids[1]}] [evidence:{evidence_ids[1]}]\n\n"
            "## Evaluation And Risk Boundary\n\n"
            f"{shallow_block('evaluation', 3)} [claim:{claim_ids[2]}] [evidence:{evidence_ids[2]}]\n\n"
            "## Limitations And Failure Modes\n\n"
            f"{shallow_block('limitations', 3)} [claim:{claim_ids[2]}] [evidence:{evidence_ids[2]}]\n\n"
            "## Contradiction Slots\n\n"
            f"{shallow_block('contradiction', 2)} [evidence:{evidence_ids[3]}]\n\n"
            "## Open Problems\n\n"
            f"{shallow_block('open-problems', 2)}\n",
            encoding="utf-8",
        )
    compile_survey(tmp_path)

    result = evaluate_survey(tmp_path, strict=True, require_complete=True)
    assert result["ok"] is False
    assert result["depth_profile"]["ok"] is False
    assert result["final_quality"]["ok"] is True
    assert any(item.startswith("depth_academic_marker_variety_low:") for item in result["scorecard"]["issues"])
    assert any(item.startswith("depth_terminology_variant_count_low:") for item in result["scorecard"]["issues"])


# ---------------------------------------------------------------------------
# N2 Insight Gates Tests
# ---------------------------------------------------------------------------


def test_insight_gates_reject_negative_cais_generic_survey_fixture(tmp_path):
    """The negative CAIS generic survey fixture must fail multiple gates."""
    ast = create_negative_cais_generic_survey_fixture(tmp_path)
    results = run_all_insight_gates(tmp_path, ast)

    assert len(results) == 9
    by_id = {r["gate_id"]: r for r in results}

    # Generic survey TOC must fail (all 8 generic titles present)
    toc = by_id["generic_survey_toc"]
    assert toc["ok"] is False
    assert len(toc["matched_patterns"]) >= 4
    assert "REQ-9.1" in toc["failed_requirement_ids"]
    assert toc["remediation_hint"]

    # Machine label leak must fail
    leak = by_id["machine_label_leak"]
    assert leak["ok"] is False
    assert "official_doc" in leak["matched_patterns"]
    assert "claim_id" in leak["matched_patterns"]
    assert "evidence_id" in leak["matched_patterns"]
    assert "REQ-9.3" in leak["failed_requirement_ids"]

    # Template repetition must fail
    template = by_id["template_repetition"]
    assert template["ok"] is False
    assert any("研究问题与术语边界" in p for p in template["matched_patterns"])
    assert "REQ-9.2" in template["failed_requirement_ids"]

    # Solar actionability must fail (no operator/schema/gate in text)
    action = by_id["solar_actionability"]
    assert action["ok"] is False
    assert "REQ-9.4" in action["failed_requirement_ids"]

    # Figure required must fail (no figures)
    fig = by_id["figure_required"]
    assert fig["ok"] is False
    assert "REQ-9.6" in fig["failed_requirement_ids"]

    # Citation visibility must fail (only 1 URL)
    cite = by_id["citation_visibility"]
    assert cite["ok"] is False
    assert "REQ-9.7" in cite["failed_requirement_ids"]

    # Prediction packet must fail (no packets file)
    pred = by_id["prediction_packet"]
    assert pred["ok"] is False
    assert "REQ-9.8" in pred["failed_requirement_ids"]

    # User question fitness must fail
    fitness = by_id["user_question_fitness"]
    assert fitness["ok"] is False
    assert "REQ-9.9" in fitness["failed_requirement_ids"]


def test_insight_gates_integrated_in_evaluate_survey_negative_fixture(tmp_path):
    """evaluate_survey with strict=True must propagate insight gate failures."""
    ast = create_negative_cais_generic_survey_fixture(tmp_path)
    result = evaluate_survey(tmp_path, strict=True)

    assert result["ok"] is False
    assert result["insight_quality"]["active"] is True
    assert len(result.get("insight_gates", [])) == 9

    issues = result["scorecard"]["issues"]

    # Must have generic survey TOC leak
    assert any("insight_gate:generic_survey_toc" in issue for issue in issues)

    # Must have machine label leak
    assert any("insight_gate:machine_label_leak" in issue for issue in issues)

    # Must have figure missing
    assert any("insight_gate:figure_required" in issue for issue in issues)

    # Must have action mapping low
    assert any("insight_gate:solar_actionability" in issue for issue in issues)


def test_each_gate_result_has_required_fields(tmp_path):
    """Each gate result must include gate_id, ok, artifact_path, failed_requirement_ids,
    matched_patterns or missing_fields, and remediation_hint."""
    ast = create_negative_cais_generic_survey_fixture(tmp_path)
    results = run_all_insight_gates(tmp_path, ast)

    for gate in results:
        assert "gate_id" in gate, f"Missing gate_id in {gate}"
        assert "ok" in gate, f"Missing ok in gate {gate['gate_id']}"
        assert isinstance(gate["ok"], bool), f"ok must be bool in gate {gate['gate_id']}"
        assert "artifact_path" in gate, f"Missing artifact_path in gate {gate['gate_id']}"
        assert "failed_requirement_ids" in gate, f"Missing failed_requirement_ids in gate {gate['gate_id']}"
        assert isinstance(gate["failed_requirement_ids"], list), f"failed_requirement_ids must be list"
        assert "remediation_hint" in gate, f"Missing remediation_hint in gate {gate['gate_id']}"
        assert isinstance(gate["remediation_hint"], str), f"remediation_hint must be str"
        assert "matched_patterns" in gate or "missing_fields" in gate


def test_generic_survey_toc_gate_passes_with_thesis_titles(tmp_path):
    """A report with thesis-led titles should pass the TOC gate."""
    ast = {
        "chapters": [
            {"chapter_id": "ch1", "title": "Agent 正在从模型应用变成可验证执行系统"},
            {"chapter_id": "ch2", "title": "CAIS 会议信号: compound system 工程阶段"},
            {"chapter_id": "ch3", "title": "Dossier: branching search 需要 Persistent Research Ledger"},
        ],
        "sections": [],
    }
    (tmp_path / "survey_report_ast.json").write_text(json.dumps(ast), encoding="utf-8")
    result = run_generic_survey_toc_gate(tmp_path, ast)
    assert result["ok"] is True
    assert result["matched_patterns"] == []


def test_machine_label_leak_gate_passes_clean_output(tmp_path):
    """Clean human output should pass the machine label leak gate."""
    ast = {"chapters": [], "sections": []}
    (tmp_path / "human_final.md").write_text(
        "# Clean Report\n\nThis is a clean report with no machine labels.\n",
        encoding="utf-8",
    )
    result = run_machine_label_leak_gate(tmp_path, ast)
    assert result["ok"] is True
    assert result["matched_patterns"] == []


def test_cais_coverage_gate_passes_with_all_signals(tmp_path):
    """Report mentioning all required CAIS signals should pass."""
    ast = {"chapters": [], "sections": []}
    (tmp_path / "human_final.md").write_text(
        "# CAIS Report\n\n"
        "Dossier reveals deep research challenges. "
        "Do Agents Need to Plan Step-by-Step? is a key question. "
        "Open Agent Specification provides a standard. "
        "TraceFix enables protocol verification. "
        "AI Agents for Discovery in the Wild shows real-world deployment.\n",
        encoding="utf-8",
    )
    result = run_cais_coverage_gate(tmp_path, ast)
    assert result["ok"] is True
    assert result["missing_fields"] == []


def test_prediction_packet_gate_passes_with_complete_packets(tmp_path):
    """Report with 4 complete prediction packets should pass."""
    ast = {"chapters": [], "sections": []}
    packets = [
        {
            "claim": "Agent systems will converge on verified execution",
            "drivers": "formal verification tooling maturity",
            "leading_indicators": ["adoption of runtime verification"],
            "counter_scenario": "verification overhead slows adoption",
            "falsification_condition": "no major framework adopts verification by 2028",
        }
        for _ in range(4)
    ]
    (tmp_path / "prediction_packets.jsonl").write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in packets) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "human_final.md").write_text(
        "# Report\n\n未来预测：Agent 将走向可验证执行。驱动因素是形式化验证工具成熟。"
        "领先指标是主要框架采纳运行时验证。证伪条件是到 2028 年没有主流框架采纳。\n",
        encoding="utf-8",
    )
    result = run_prediction_packet_gate(tmp_path, ast)
    assert result["ok"] is True


def test_user_question_fitness_gate_passes_when_questions_answered(tmp_path):
    """Report answering all must-answer questions should pass."""
    ast = {"chapters": [], "sections": [], "title": "CAIS 2026 Agent"}
    (tmp_path / "human_final.md").write_text(
        "# Report\n\n"
        "CAIS 2026 释放了 Agent 技术信号包括 Dossier 和 TraceFix。"
        "当前 Agent 重大技术挑战是规划步进验证。"
        "Solar 应该吸收 BranchingResearchPlanner 作为 operator。"
        "未来 24-36 个月 Agent 系统将走向可验证执行 runtime。\n",
        encoding="utf-8",
    )
    contract = {
        "scope_boundaries": {
            "must_answer": [
                "CAIS 2026 释放了什么 Agent 技术信号？",
                "当前 Agent 的重大技术挑战是什么？",
                "Solar 应该吸收成哪些 operator？",
                "未来 Agent 系统会怎么演进？",
            ]
        }
    }
    (tmp_path / "deepdive_requirement_contract.json").write_text(
        json.dumps(contract, ensure_ascii=False), encoding="utf-8"
    )
    result = run_user_question_fitness_gate(tmp_path, ast)
    assert result["ok"] is True
