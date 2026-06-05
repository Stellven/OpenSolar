from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.survey.planner import create_survey_plan, write_survey_plan


def test_planner_creates_professor_grade_shape(tmp_path):
    plan = create_survey_plan("隐空间推理技术架构和演进方向", target_chars=50000)
    assert len(plan["report_ast"]["chapters"]) >= 8
    assert len(plan["report_ast"]["sections"]) >= 30
    assert len(plan["source_matrix"]) == len(plan["report_ast"]["sections"])
    assert all(section["min_evidence"] >= 4 for section in plan["report_ast"]["sections"])

    files = write_survey_plan(plan, tmp_path)
    assert (tmp_path / "survey_plan.json").exists()
    assert (tmp_path / "survey_report_ast.json").exists()
    assert files["source_matrix"].endswith("survey_source_matrix.json")


def test_planner_uses_conference_insight_mode_for_conference_briefs():
    brief = (
        "通过洞察 CAIS 2026 学术会议，分析当前 Agent 应如何发展、重大技术挑战是什么、"
        "Solar 该如何吸收这些思想。要求形成 DeepDive 风格的结构化、证据化、章节化洞察报告。"
    )

    plan = create_survey_plan(brief, target_chars=50000)

    assert plan["planner_mode"] == "conference_insight"
    assert plan["report_ast"]["title"] == "深度报告：CAIS 2026 Agent 发展、技术挑战与 Solar 路线"

    first_chapter = plan["report_ast"]["chapters"][0]
    first_section = plan["report_ast"]["sections"][0]
    first_question = plan["questions"][0]

    assert first_chapter["title"] == "会议信号与中心论点"
    assert "accepted papers" in first_chapter["objective"]
    assert "avoid generic methodology talk" in first_chapter["objective"]
    assert "Professor-Grade Survey" not in plan["report_ast"]["title"]
    assert "议题迁移与关键变化" in [chapter["title"] for chapter in plan["report_ast"]["chapters"]]
    assert "会议在讨论什么问题" in first_section["title"]
    assert "conference tracks" in first_section["research_question"]
    assert any(section["title"].endswith("对 Solar 的启示") for section in plan["report_ast"]["sections"])
    assert "会议和论文信号" in first_question["text"]


def test_planner_uses_generic_insight_shape_for_deepdive_hint():
    plan = create_survey_plan(
        "## 扩展研究 brief\n\n为什么 Agent runtime 会成为基础设施？",
        target_chars=50000,
        planner_mode_hint="insight",
    )

    assert plan["planner_mode"] == "insight"
    assert plan["report_ast"]["title"].startswith("DeepDive 洞察报告")
    chapter_titles = [chapter["title"] for chapter in plan["report_ast"]["chapters"]]
    assert chapter_titles[:4] == [
        "核心判断与中心论点",
        "信号地图与证据强度",
        "关键变化、分歧与机会",
        "技术、产品与生态影响",
    ]
    assert "历史脉络与技术演进" not in chapter_titles
    first_section = plan["report_ast"]["sections"][0]
    assert "本节判断" in first_section["title"]
    assert "中心论点" in first_section["research_question"]
    assert first_section["suggested_figure_type"] == "insight_argument_map"
    figure_types = {section["suggested_figure_type"] for section in plan["report_ast"]["sections"]}
    assert "architecture_map" in figure_types
    assert "roadmap_timeline" in figure_types
    assert "risk_map" in figure_types


def test_planner_keeps_general_mode_for_non_conference_briefs():
    plan = create_survey_plan("隐空间推理技术架构和演进方向", target_chars=50000)

    assert plan["planner_mode"] == "general_survey"
    assert plan["report_ast"]["title"] == "Professor-Grade Survey: 隐空间推理技术架构和演进方向"
    assert plan["report_ast"]["chapters"][1]["title"] == "历史脉络与技术演进"


def test_survey_plan_cli_prepares_deepdive_entry_before_plan(tmp_path):
    root = Path(__file__).resolve().parents[2]
    script = root / "lib" / "research" / "cli.py"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "lib")
    env["SOLAR_DEEPDIVE_BRIEF_EXPANDER_CMD"] = (
        f"{sys.executable} -c \"print('## 扩展研究 brief\\\\n\\\\n为什么 Agent runtime 会成为基础设施？')\""
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "survey-plan",
            "--brief",
            "DeepDive: Agent runtime",
            "--output-dir",
            str(tmp_path),
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)

    assert payload["deepdive_entry"]["ok"] is True
    assert (tmp_path / "deepdive_brief_expansion.json").exists()
    assert (tmp_path / "deepdive_requirement_contract.json").exists()
    assert (tmp_path / "deepdive_traceability.json").exists()
    ast = json.loads((tmp_path / "survey_report_ast.json").read_text())
    assert ast["title"].startswith("DeepDive 洞察报告")
