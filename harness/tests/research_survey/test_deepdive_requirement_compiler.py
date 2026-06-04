from __future__ import annotations

import inspect
import os
import sys


_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research import deepdive_requirement_compiler as compiler
from research import deepdive_brief_expander as expander


def test_generic_research_words_do_not_trigger_deepdive():
    assert not compiler.is_explicit_deepdive_request("帮我调研一下 agent memory 的论文")
    assert not compiler.is_explicit_deepdive_request("做一个研究综述，看看 benchmark comparison")
    assert not compiler.is_explicit_deepdive_request("分析这篇 paper 是否值得关注")


def test_explicit_profile_or_marker_triggers_deepdive():
    assert compiler.is_explicit_deepdive_request("分析 agent infra", profile="deepdive")
    assert compiler.is_explicit_deepdive_request("分析 agent infra", source_channel="deepdive")
    assert compiler.is_explicit_deepdive_request("做一个 DeepDive：agent infra 未来路线")
    assert compiler.is_explicit_deepdive_request("做一个深度研究：agent infra 未来路线")


def test_compile_deepdive_brief_uses_separate_schema_and_nodes():
    contract = compiler.compile_deepdive_brief(
        """
        DeepDive: Agent runtime 是否正在成为 AI infra 的核心层？
        为什么现在发生？
        哪些反证会推翻这个判断？
        """
    )
    validation = compiler.validate_deepdive_contract(contract)

    assert validation["ok"], validation
    assert contract["schema_version"] == compiler.SCHEMA_VERSION
    assert contract["schema_version"] != "solar.requirement_ir.v1"
    assert "requirement_ir" not in contract
    assert contract["runtime_owner"] == "DeepDive"
    assert contract["deepdive_dag"]["dag_variant"] == "deepdive_research"
    assert all(node["id"].startswith("D") for node in contract["deepdive_dag"]["nodes"])
    assert all(
        node["logical_operator"].startswith("DeepDive")
        for node in contract["deepdive_dag"]["nodes"]
    )
    assert all(item["mapped_nodes"] for item in contract["traceability"]["items"])


def test_deepdive_brief_expander_writes_separate_artifacts(tmp_path):
    payload = expander.expand_deepdive_brief("DeepDive: agent runtime 趋势是什么？", tmp_path)

    assert payload["schema_version"] == expander.SCHEMA_VERSION
    assert payload["operator"] == "DeepDiveBriefExpander"
    assert payload["normal_requirement_pipeline_import_allowed"] is False
    assert (tmp_path / "deepdive_brief_expansion.json").exists()
    assert (tmp_path / "deepdive_brief_expansion.md").exists()
    assert not (tmp_path / "raw_intent.json").exists()
    assert not (tmp_path / "requirement_ir.json").exists()


def test_deepdive_contract_records_expansion_without_normal_schema(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "SOLAR_DEEPDIVE_BRIEF_EXPANDER_CMD",
        f"{sys.executable} -c \"print('## 扩展研究 brief\\\\n\\\\n为什么 Agent runtime 会成为基础设施？')\"",
    )
    expansion = expander.expand_deepdive_brief("DeepDive: Agent runtime", tmp_path)
    contract = compiler.compile_deepdive_brief("DeepDive: Agent runtime", expansion=expansion)
    validation = compiler.validate_deepdive_contract(contract)

    assert validation["ok"], validation
    assert contract["brief"].startswith("## 扩展研究 brief")
    assert contract["raw_brief"] == "DeepDive: Agent runtime"
    assert contract["brief_expansion"]["operator"] == "DeepDiveBriefExpander"
    assert contract["brief_expansion"]["normal_requirement_pipeline_import_allowed"] is False
    assert contract["schema_version"] != "solar.requirement_ir.v1"


def test_deepdive_compiler_has_no_runtime_import_from_pm_router():
    source = inspect.getsource(compiler)

    assert "codex_pm_router" not in source
    assert "from requirement_coverage" not in source
    assert "solar.requirement_ir.v1" not in [
        compiler.SCHEMA_VERSION,
        compiler.TRACE_SCHEMA_VERSION,
    ]


def test_operator_mapping_documents_copy_policy():
    mapping = compiler.OPERATOR_MAPPING

    assert mapping
    assert {item["deepdive_operator"] for item in mapping} >= {
        "DeepDiveBriefCapture",
        "DeepDiveResearchContract",
        "DeepDiveEvidenceDAG",
        "DeepDiveTraceabilityReport",
        "DeepDiveCloseoutDecision",
    }
    assert all(item["copy_policy"] for item in mapping)
    assert all("boundary" in item for item in mapping)
