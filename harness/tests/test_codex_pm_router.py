#!/usr/bin/env python3
"""Tests for codex_pm_router capability plan emission."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = ROOT / "tools" / "codex_pm_router.py"


def _load_router():
    for module_name in ("codex_pm_router", "capability_capsules", "requirement_coverage", "apo_plan_compiler"):
        sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location("codex_pm_router", ROUTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_pm_intake_emits_capsule_plan_for_standard_request():
    router = _load_router()
    payload = router.build_pm_intake(
        "Build a requirement compiler that produces PRD, contracts, and task graphs.",
        sprint_id="sprint-test",
        target_system="solar-harness",
    )
    nodes = payload["compiled_artifacts"]["task_dag"]["nodes"]
    by_id = {node["id"]: node for node in nodes}
    assert by_id["S1"]["capability_capsule_id"] == "cap.requirement-compiler-planner"
    assert by_id["S2"]["capability_capsule_id"] == "cap.requirement-compiler-implementation"
    assert by_id["S4"]["capability_capsule_id"] == "cap.requirement-compiler-verification"
    assert by_id["S2"]["capsule_plan"]["required_resource_capsules"] == ["resource.repo-workspace"]


def test_build_pm_intake_emits_capsule_plan_for_research_request():
    router = _load_router()
    payload = router.build_pm_intake(
        "Read these papers and synthesize research implications for the planner.",
        papers=["paper-a"],
        sprint_id="sprint-test",
        target_system="solar-harness",
    )
    nodes = payload["compiled_artifacts"]["task_dag"]["nodes"]
    by_id = {node["id"]: node for node in nodes}
    assert by_id["R1"]["capability_capsule_id"] == "cap.requirement-research-scout"
    assert by_id["R4"]["capability_capsule_id"] == "cap.requirement-research-synthesizer"
    assert by_id["R5"]["capability_capsule_id"] == "cap.requirement-compiler-verification"


def test_browser_agent_operator_request_is_standard_implementation_not_research():
    router = _load_router()
    text = """
    增加 Browser Agent 物理执行算子，用 browser 自动化调用 ChatGPT Deep Research
    和 Gemini Deep Research。需要接入 operator runtime、registry、schema、
    logical_operator、async submit/poll/collect、quota fallback 和 bridge observability。
    """
    payload = router.build_pm_intake(text, sprint_id="sprint-test", target_system="solar-harness")
    assert payload["classification"] == router.FULL_SPEC
    assert payload["dag_variant"] == "standard"
    node_ids = [node["id"] for node in payload["compiled_artifacts"]["task_dag"]["nodes"]]
    assert node_ids[:4] == ["S1", "S2", "S3", "S4"]


def test_convergence_request_uses_parallel_spec_dag():
    router = _load_router()
    payload = router.build_pm_intake(
        "把 GitHub Hotspot Radar 收口成统一 convergence package，补 architecture、contract、traceability 和 rollout。",
        sprint_id="sprint-test",
        target_system="solar-harness",
    )
    nodes = payload["compiled_artifacts"]["task_dag"]["nodes"]
    by_id = {node["id"]: node for node in nodes}
    assert payload["classification"] == router.FULL_SPEC
    assert payload["dag_variant"] == "parallel_spec"
    assert payload["compiled_artifacts"]["task_dag"]["dag_variant"] == "parallel_spec"
    assert by_id["S2"]["depends_on"] == ["S1"]
    assert by_id["S3"]["depends_on"] == ["S1"]
    assert by_id["S4"]["depends_on"] == ["S1"]
    assert by_id["S5"]["depends_on"] == ["S2", "S3", "S4"]
    assert by_id["S1"]["gate"] == "G_PLAN"
    assert by_id["S2"]["gate"] == "G_IMPL"
    assert by_id["S3"]["gate"] == "G_IMPL"
    assert by_id["S4"]["gate"] == "G_VERIFY"
    assert by_id["S5"]["gate"] == "G_REVIEW"


def test_productization_request_uses_parallel_spec_dag():
    router = _load_router()
    payload = router.build_pm_intake(
        "继续做 skill-to-capsule operator 产品化，输出蓝图、追踪矩阵和最终收口。",
        sprint_id="sprint-test",
        target_system="solar-harness",
    )
    nodes = payload["compiled_artifacts"]["task_dag"]["nodes"]
    by_id = {node["id"]: node for node in nodes}
    assert payload["dag_variant"] == "parallel_spec"
    assert by_id["S4"]["logical_operator"] == "ArtifactCurator"
    assert by_id["S5"]["logical_operator"] == "Verifier"


def test_plain_paper_research_request_still_uses_research_dag():
    router = _load_router()
    payload = router.build_pm_intake(
        "调研这些论文并输出证据链和技术洞察。",
        papers=["paper-a"],
        sprint_id="sprint-test",
        target_system="solar-harness",
    )
    assert payload["classification"] == router.RESEARCH
    assert payload["dag_variant"] == "research"


def test_code_understanding_request_rewrites_standard_graph_goals():
    router = _load_router()
    payload = router.build_pm_intake(
        "为这个仓库生成 knowledge graph、architecture map 和 onboarding artifacts。",
        repo_context=["/Users/lisihao/Solar"],
        sprint_id="sprint-test",
        target_system="solar-harness",
    )
    nodes = payload["compiled_artifacts"]["task_dag"]["nodes"]
    by_id = {node["id"]: node for node in nodes}
    assert payload["dag_variant"] == "standard"
    assert by_id["S1"]["type"] == "code-understanding"
    assert "knowledge-graph" in by_id["S1"]["signals"]
    assert "knowledge graph" in by_id["S2"]["goal"].lower()
    assert by_id["S2"]["outputs"] == ["knowledge-graph.json", "meta.json", "chunk-manifest.json", "resume-state.json"]
    assert by_id["S1"]["gate"] == "G_PLAN"
    assert by_id["S2"]["gate"] == "G_IMPL"
    assert by_id["S3"]["gate"] == "G_VERIFY"
    assert by_id["S4"]["gate"] == "G_REVIEW"
    assert by_id["S5"]["gate"] == "G_REVIEW"


def test_code_understanding_request_rewrites_research_graph_goals():
    router = _load_router()
    payload = router.build_pm_intake(
        "结合仓库和这些论文，输出代码库理解、architecture map、onboarding 和 knowledge graph。",
        papers=["paper-a"],
        repo_context=["/Users/lisihao/Solar"],
        sprint_id="sprint-test",
        target_system="solar-harness",
    )
    nodes = payload["compiled_artifacts"]["task_dag"]["nodes"]
    by_id = {node["id"]: node for node in nodes}
    assert payload["dag_variant"] == "research"
    assert "knowledge graph" in by_id["R1"]["goal"].lower()
    assert "architecture map" in by_id["R2"]["goal"].lower()
    assert "onboarding" in by_id["R4"]["goal"].lower()
    assert by_id["R1"]["gate"] == "G_SOURCE"
    assert by_id["R2"]["gate"] == "G_EVIDENCE"
    assert by_id["R3"]["gate"] == "G_EVIDENCE"
    assert by_id["R4"]["gate"] == "G_SYNTHESIS"
    assert by_id["R5"]["gate"] == "G_REVIEW"
    assert by_id["R6"]["gate"] == "G_REVIEW"


def test_solar_handoff_view_uses_sprint_root_artifacts_for_sprint_packages():
    router = _load_router()
    payload = router.build_pm_intake(
        "为 GitHub Hotspot Radar 收口 requirement package 和 handoff。",
        sprint_id="sprint-test",
        target_system="solar-harness",
    )
    handoff_view = payload["requirement_ir"]["handoff_view"]
    assert handoff_view["codex"]["artifacts"] == [
        "sprint-test.requirement_ir.json",
        "sprint-test.prd.md",
        "sprint-test.Contracts.yaml",
        "sprint-test.task_graph.json",
    ]
    assert handoff_view["solar_harness"]["artifacts"] == [
        "sprint-test.requirement_ir.json",
        "sprint-test.prd.md",
        "sprint-test.Contracts.yaml",
        "sprint-test.task_graph.json",
        "sprint-test.handoff.md",
    ]
    solar_handoff = payload["compiled_artifacts"]["handoff_markdown"]["solar_harness"]
    assert "sprint-test.requirement_ir.json" in solar_handoff
    assert ".pm/requirement_ir.json" not in solar_handoff


def test_build_pm_intake_sanitizes_rawintent_consumer_payload():
    router = _load_router()
    consumer_text = """# RawIntent Consumer Request - codex bridge consumer smoke

## Source

- intent_id: intent-20260525-153733-d0bbf8d0af
- channel: codex_bridge
- actor: codex
- device: mac_mini
- thread_ref: N/A

## Rewritten Objective

让 Codex bridge 捕获 RawIntent 并自动编译成 sprint package。

## Problem

--- 
title: codex bridge consumer smoke
---
Codex bridge should capture RawIntent and auto consume into sprint package.

## Constraints

- All execution must enter Solar-Harness through RawIntent.

## Acceptance

- RawIntent, rewritten_intent, requirement_ir, and requirement_trace artifacts are persisted.

## Raw User Intent

[entrypoint_metadata]
sprint_id: N/A
node_id: N/A
role: pm

[raw_request]
Codex bridge should capture RawIntent and auto consume into sprint package.
"""
    payload = router.build_pm_intake(consumer_text, sprint_id="sprint-test", target_system="solar-harness")
    requirement_ir = payload["requirement_ir"]
    prd = payload["compiled_artifacts"]["prd_markdown"]
    assert "## Source" not in requirement_ir["normalized_goal"]
    assert "thread_ref:" not in requirement_ir["normalized_goal"]
    assert requirement_ir["normalized_goal"] == "让 Codex bridge 捕获 RawIntent 并自动编译成 sprint package。"
    assert requirement_ir["problem_statement"] == "Codex bridge should capture RawIntent and auto consume into sprint package."
    assert "RawIntent Consumer Request" not in prd


def test_build_pm_intake_prefers_enhanced_requirement_design_section():
    router = _load_router()
    consumer_text = """# RawIntent Consumer Request - research implementation

## Rewritten Objective

把研究类需求编译成 sprint package。

## Problem

用户想做研究实现链路，但原始文本很短。

## Enhanced Requirement Design

# 需求概述

需要把研究实现类需求先走章节化增强，再进入 requirement compiler，输出更完整的 IR、PRD、contract 和 task_graph。

## 功能需求

- 必须支持显式启动词 `研究实现`
- 必须保留 raw user intent provenance

## Raw User Intent

研究实现 一个需求编译链路。
"""
    payload = router.build_pm_intake(consumer_text, sprint_id="sprint-test", target_system="solar-harness")
    requirement_ir = payload["requirement_ir"]
    assert "章节化增强" in requirement_ir["normalized_goal"]
    assert requirement_ir["user_intent"] == "研究实现 一个需求编译链路。"
    assert requirement_ir["source_inputs"]["enhanced_requirement_sections"][0]["heading"] == "需求概述"
    assert requirement_ir["source_inputs"]["compile_segments"][0]["kind"] == "enhanced_requirement_section"
    assert requirement_ir["source_inputs"]["compile_segments"][0]["semantic_label"] == "architecture_and_scope"


def test_build_pm_intake_maps_enhanced_requirement_sections_to_dag_semantics():
    router = _load_router()
    consumer_text = """# RawIntent Consumer Request - section semantic mapping

## Rewritten Objective

把研究实现需求编译成更细粒度的 DAG 提示。

## Problem

用户需要按章节语义把需求拆进不同 node family。

## Enhanced Requirement Design

# 需求概述

需要把增强需求的章节语义映射到 requirement compiler DAG。

## 功能需求

- 生成 GPTRequirementWriter 增强需求
- 把章节喂给 requirement compiler

## 非功能需求

- 保持 provenance
- 保持可验证

## 风险与约束

- 不能破坏现有 DAG 主骨架

## 验收标准

- ImplementationWorker / Verifier 能看到章节语义提示

## Raw User Intent

研究实现 一个章节语义到 DAG 模板的链路。
"""
    payload = router.build_pm_intake(consumer_text, sprint_id="sprint-test", target_system="solar-harness")
    requirement_ir = payload["requirement_ir"]
    semantic_hints = requirement_ir["source_inputs"]["enhanced_requirement_semantic_hints"]
    assert [item["node_family"] for item in semantic_hints[:4]] == [
        "design",
        "implementation",
        "quality",
        "risk_review",
    ]
    compile_segments = requirement_ir["source_inputs"]["compile_segments"]
    assert compile_segments[1]["semantic_label"] == "functional_requirements"
    assert compile_segments[2]["node_family"] == "quality"
    assert compile_segments[3]["node_family"] == "risk_review"
    by_id = {node["id"]: node for node in payload["compiled_artifacts"]["task_dag"]["nodes"]}
    assert "implementation" in by_id["S2"]["semantic_focus"]
    assert any(item["heading"] == "功能需求" for item in by_id["S2"]["section_semantic_hints"])
    assert "implementation-plan.md" in by_id["S2"]["outputs"]
    assert "section-functional-requirements" in by_id["S2"]["signals"]
    assert any(item["target"] == "implementation-plan.md" for item in by_id["S2"]["validation"])
    assert "quality" in by_id["S3"]["semantic_focus"]
    assert "quality-checklist.md" in by_id["S3"]["outputs"]
    assert any(item["target"] == "quality-checklist.md" for item in by_id["S3"]["validation"])
    assert "verification" in by_id["S4"]["semantic_focus"]
    assert any(item["heading"] == "验收标准" for item in by_id["S4"]["section_semantic_hints"])
    assert "acceptance-matrix.json" in by_id["S4"]["outputs"]
    assert "acceptance-traceability" in by_id["S4"]["signals"]
    assert any(item["target"] == "acceptance-matrix.json" for item in by_id["S4"]["validation"])
    assert "risk_review" in by_id["S1"]["semantic_focus"]
    assert "risk-register.md" in by_id["S1"]["outputs"]
    assert any(item["target"] == "risk-register.md" for item in by_id["S1"]["validation"])
    assert "verification" in by_id["S4"]["semantic_template_overrides"]["applied"]
    assert requirement_ir["section_semantic_plan"]["section_count"] == 5


def test_build_pm_intake_upgrades_standard_dag_when_semantic_families_are_heavy():
    router = _load_router()
    consumer_text = """# RawIntent Consumer Request - semantic dag upgrade

## Rewritten Objective

把研究实现需求编译成更宽的并行交付 DAG。

## Problem

需求同时包含接口、风险、非功能和验收章节，标准串行 DAG 太窄。

## Enhanced Requirement Design

# 需求概述

这是一条研究实现链路，需要在进入实现前把接口、风险和验证分支准备好。

## 接口与数据契约

- 定义 IR 输入输出边界
- 声明 contract 和 schema 兼容要求

## 风险与约束

- 不能破坏现有 requirement compiler 主链
- 不能丢失 raw provenance

## 非功能需求

- 需要可验证
- 需要回归证据

## 验收标准

- 必须有 acceptance matrix
- 必须有 closeout decision

## 功能需求

- 最终把增强需求编译进 DAG 和 PRD

## Raw User Intent

研究实现 一个语义驱动 DAG 升级链路。
"""
    payload = router.build_pm_intake(consumer_text, sprint_id="sprint-test", target_system="solar-harness")
    requirement_ir = payload["requirement_ir"]
    dag = payload["compiled_artifacts"]["task_dag"]
    by_id = {node["id"]: node for node in dag["nodes"]}
    assert payload["classification"] == router.FULL_SPEC
    assert payload["dag_variant"] == "parallel_delivery"
    assert dag["semantic_upgrade"]["enabled"] is True
    assert dag["semantic_upgrade"]["mode"] == "section_family_parallel_delivery"
    assert dag["quality_gates"]["parallelism"]["min_ready_width"] == 3
    source_nodes = [node["id"] for node in dag["nodes"] if not node["depends_on"]]
    assert source_nodes == ["S1", "S2", "S3"]
    assert by_id["S4"]["depends_on"] == ["S1", "S2", "S3"]
    assert "interface_contract" in by_id["S1"]["semantic_focus"]
    assert "risk_review" in by_id["S2"]["semantic_focus"]
    assert "verification" in by_id["S3"]["semantic_focus"]
    assert "quality" in by_id["S3"]["semantic_focus"]
    assert "implementation" in by_id["S4"]["semantic_focus"]
    assert "acceptance-matrix.json" in by_id["S5"]["outputs"]
    assert requirement_ir["dag_view"]["semantic_upgrade"]["trigger_families"] == [
        "interface_contract",
        "quality",
        "risk_review",
        "verification",
    ]


def test_validate_compiled_package_rejects_raw_metadata_pollution():
    router = _load_router()
    payload = router.build_pm_intake("正常需求：补齐 requirement compiler 的 closeout gate。", sprint_id="sprint-test")
    payload["requirement_ir"]["normalized_goal"] = "# RawIntent Consumer Request - ## Source intent_id: test"
    result = router.validate_compiled_package(payload)
    assert result["ok"] is False
    assert "raw_metadata_pollution_detected" in result["errors"]


def test_codex_pm_router_cli_defaults_to_rawintent(tmp_path):
    env = dict(os.environ)
    env["SOLAR_HARNESS_DIR"] = str(ROOT)
    env["HARNESS_DIR"] = str(ROOT)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    env["SOLAR_INTENT_CONSUMER_WORKSPACE_ROOT"] = str(tmp_path / "workspace")

    proc = subprocess.run(
        [
            sys.executable,
            str(ROUTER_PATH),
            "--text",
            "把 codex_pm_router 入口接到 RawIntent 主链。",
            "--format",
            "json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "rawintent"
    results = payload["consumer"]["results"]
    assert results and results[0]["status"] == "consumed"
