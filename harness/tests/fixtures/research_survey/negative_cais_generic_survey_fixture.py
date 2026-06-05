"""Negative CAIS generic survey fixture.

This fixture represents a FAILED CAIS 2026 Agent insight report that exhibits
all the symptoms described in the requirement doc §2.2:
- Generic survey TOC leaked into conference insight task
- Machine labels in human output
- Low action mapping
- Missing figures
- Weak citation visibility
- Template repetition
- No prediction packets
- Missing user question answers

Used by tests to verify that the insight gates correctly reject this output.
"""

from __future__ import annotations

import json
from pathlib import Path


def create_negative_cais_generic_survey_fixture(output_dir: Path) -> dict:
    """Create a negative CAIS generic survey fixture and return its AST."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generic survey TOC that should be rejected (req 9.1)
    chapters = [
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
    ]

    sections = [
        {"section_id": "ch1/sec1", "chapter_id": "ch1", "title": "研究问题与术语边界"},
        {"section_id": "ch2/sec1", "chapter_id": "ch2", "title": "历史脉络概述"},
    ]

    ast = {
        "title": "深度报告：CAIS 2026 Agent 发展、技术挑战与 Solar 路线",
        "planner_mode": "conference_insight",
        "chapters": chapters,
        "sections": sections,
    }

    (output_dir / "survey_report_ast.json").write_text(
        json.dumps(ast, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Survey plan with insight mode
    (output_dir / "survey_plan.json").write_text(
        json.dumps({"planner_mode": "conference_insight"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Evidence packs
    (output_dir / "survey_evidence_packs.json").write_text(
        json.dumps({"blocked": 0, "packs": []}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Human final with all the bad patterns:
    # - Machine labels (official_doc, claim_id, evidence_id, source_type)
    # - Template repetition
    # - Low action mapping (no Solar operator/schema/gate language)
    # - No figures
    # - Very few visible citations
    (output_dir / "human_final.md").write_text(
        """# CAIS 2026 Agent Survey

## 问题定义与研究边界
研究问题与术语边界。official_doc 和 paper 需要区分。claim_id=e1。source_type=paper。
evidence_id=ev1。estimated_from_report_artifacts 数据来源。

## 核心架构范式
研究问题与术语边界。机制可行性不等于工程可控性。
研究问题与术语边界。机制可行性不等于工程可控性。
研究问题与术语边界。机制可行性不等于工程可控性。

## 方法分类与代表系统
研究问题与术语边界。关键机制与设计空间。
证据链与代表工作。工程取舍与评价标准。
风险与争议。未解问题。

## 历史脉络与技术演进
历史脉络概述。研究问题与术语边界。
研究问题与术语边界。机制可行性不等于工程可控性。

## 评估方法与基准体系
Execution Metrics 显示评估需要改进。official_doc 和 source_type 标签需要清理。

## 工程实现与部署约束
研究问题与术语边界。工程取舍与评价标准。
关键机制与设计空间。证据链与代表工作。

## 风险、安全与可解释性
风险与争议。机制可行性不等于工程可控性。
研究问题与术语边界。未解问题。

## 产业生态与开源实现
研究问题与术语边界。关键机制与设计空间。
工程取舍与评价标准。证据链与代表工作。

[1] https://example.com/only-ref
""",
        encoding="utf-8",
    )

    # Contract with must-answer questions that the report does NOT answer
    contract = {
        "profile": "cais-agent-insight",
        "brief": "分析 CAIS 2026 Agent 技术信号",
        "scope_boundaries": {
            "must_answer": [
                "CAIS 2026 释放了什么 Agent 技术信号？",
                "当前 Agent 的重大技术挑战是什么？",
                "Solar 应该吸收成哪些 operator/schema/gate/runtime？",
                "未来 24-36 个月 Agent 系统会怎么演进？",
            ]
        },
    }
    (output_dir / "deepdive_requirement_contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # No prediction packets file (deliberately missing)
    # No figures.json (deliberately missing)

    return ast
