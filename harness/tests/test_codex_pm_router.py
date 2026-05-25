#!/usr/bin/env python3
"""Tests for codex_pm_router capability plan emission."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = ROOT / "tools" / "codex_pm_router.py"


def _load_router():
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
