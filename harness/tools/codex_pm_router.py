#!/usr/bin/env python3
"""Codex PM Router for three request classes.

Compiles a user request into a structured PM intake package that can feed
Codex-side skill workflows and downstream solar-harness PRD/contract/DAG
generation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

HARNESS_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = HARNESS_ROOT / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from requirement_coverage import (
    build_acceptance_verdict,
    build_coverage_report,
    build_requirement_trace,
    enrich_task_graph_defaults,
)

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


SHORT_IMPL = "short_impl"
FULL_SPEC = "full_spec"
RESEARCH = "research"
CLASS_TO_CANONICAL = {
    SHORT_IMPL: "implementation",
    FULL_SPEC: "full_prd",
    RESEARCH: "research",
}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _yaml_text(data: Any) -> str:
    if yaml is not None:
        return yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
    return json.dumps(data, ensure_ascii=False, indent=2)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write_yaml(path: Path, payload: Any) -> None:
    _write_text(path, _yaml_text(payload))


def _safe_title(text: str) -> str:
    line = next((line.strip() for line in text.splitlines() if line.strip()), "").strip(" -:#")
    return line[:80] or "Untitled Request"


def _derive_confidence(request_type: str, text: str, papers: list[str]) -> float:
    normalized = _normalized_text(text)
    if request_type == SHORT_IMPL:
        return 0.86 if len(normalized) < 200 else 0.79
    if request_type == RESEARCH:
        return 0.9 if papers else 0.72
    if re.search(r"(metric|指标|success|acceptance|scope|non-goal)", normalized, re.I):
        return 0.84
    return 0.73


def _derive_assumptions(request_type: str, lane_hint: str) -> list[str]:
    assumptions = [
        "PM 产物需要兼容 solar-harness 现有 PM -> Planner -> Builder 主链。",
        "Markdown PRD / contract 是编译视图，不是唯一事实源。",
    ]
    if request_type == SHORT_IMPL:
        assumptions.append("短实现类请求默认优先最小改动和 verifier gate。")
    if request_type == FULL_SPEC:
        assumptions.append("完整需求默认先保证正确性、可验证性和风险前置。")
    if request_type == RESEARCH:
        assumptions.append("研究类请求默认要求 evidence ledger 和 verifier gate。")
    if lane_hint == "strategy":
        assumptions.append("涉及架构/迁移/兼容时默认进入 strategy lane。")
    return assumptions


def _derive_open_questions(request_type: str, text: str, papers: list[str]) -> list[str]:
    questions: list[str] = []
    if ("优化 DAG" in text or "optimize dag" in text.lower()) and "wall-clock" not in text.lower():
        questions.append("DAG 优化优先级是否应默认按 正确性 > 可验证性 > 风险前置 > 并行度 > wall-clock 时间 排序？")
    if request_type == FULL_SPEC and not re.search(r"(metric|指标|success|acceptance)", text, re.I):
        questions.append("当前请求缺少显式 success metric，需在 PRD 中补齐。")
    if request_type == RESEARCH and not papers:
        questions.append("研究类请求尚未附具体 paper inventory，后续需要补充来源证据。")
    if "人工审批" in text and "全自动" in text:
        questions.append("全自动执行与 destructive 操作人工审批存在冲突，需要明确优先级。")
    return questions


def _derive_risk_register(request_type: str) -> list[dict[str, str]]:
    risks = [
        {
            "id": "R1",
            "level": "medium",
            "title": "PRD / contract / DAG 多份产物漂移",
            "mitigation": "用 Requirement IR 做唯一事实源，所有视图从 IR 编译。",
        },
        {
            "id": "R2",
            "level": "medium",
            "title": "原始需求直接派给 Builder 导致执行发散",
            "mitigation": "强制走 product-brief / planner handoff，不允许 raw request 直派 builder。",
        },
    ]
    if request_type == RESEARCH:
        risks.append(
            {
                "id": "R3",
                "level": "high",
                "title": "研究结论缺证据链就进入实现",
                "mitigation": "Research mode 强制 evidence ledger 和 review gate。",
            }
        )
    else:
        risks.append(
            {
                "id": "R3",
                "level": "medium",
                "title": "验收标准没有映射到验证步骤",
                "mitigation": "编译期做 acceptance coverage 检查，缺失时阻断派单。",
            }
        )
    return risks


def _default_acceptance(request_type: str) -> list[str]:
    if request_type == SHORT_IMPL:
        return [
            "目标变更在声明范围内完成。",
            "至少一条测试/执行证据被记录。",
            "存在独立 verifier 决策。",
        ]
    if request_type == RESEARCH:
        return [
            "paper/source inventory 完整可追溯。",
            "claim -> evidence -> implication 映射完整。",
            "研究结论具备 adoption/rejection criteria。",
        ]
    return [
        "PRD、contract、TaskDAG 互相对齐。",
        "实施、验证、兼容/发布路径均已显式表达。",
        "每条验收标准都能追溯到验证或 gate。",
    ]


def _default_non_goals(request_type: str) -> list[str]:
    if request_type == SHORT_IMPL:
        return [
            "不做无关架构重写。",
            "不默认引入新的生产依赖。",
        ]
    if request_type == RESEARCH:
        return [
            "不把论文总结直接当作实现结论。",
            "不在缺证据时进入生产实现。",
        ]
    return [
        "不在首批交付中做完整四区 PM pane 重构。",
        "不绕过 planner 直接进入 builder。",
    ]


def _default_stop_rules(request_type: str) -> list[str]:
    rules = [
        "缺少可验证 acceptance 不得标记为完成。",
        "缺少 verifier 决策不得进入 DONE。",
    ]
    if request_type == RESEARCH:
        rules.append("缺少 evidence ledger 或 critique gate 时不得推进到 adoption。")
    return rules


def _node_enrichment(request_type: str, node: dict[str, Any]) -> dict[str, Any]:
    owner = "subagent" if request_type == RESEARCH and node["logical_operator"] in {"ResearchScout", "ResearchSynthesizer", "ArtifactCurator"} else ("solar-harness" if node["logical_operator"] in {"Verifier", "Critic"} else "codex")
    node_type_map = {
        "DeepArchitect": "design",
        "ImplementationWorker": "implementation",
        "TestRunner": "test",
        "Verifier": "review",
        "Critic": "review",
        "ResearchScout": "research",
        "ResearchSynthesizer": "research",
        "ArtifactCurator": "release",
    }
    validation_target = {
        "S1": "patch.diff",
        "S2": "test_report.md",
        "S3": "review_decision.yaml",
        "S4": "review_decision.yaml",
        "S5": "rollout_notes.md",
        "R1": "source_manifest.json",
        "R2": "claims.jsonl",
        "R3": "contradictions.jsonl",
        "R4": "synthesis.md",
        "R5": "critique.md",
        "R6": "final_prd_implications.md",
    }.get(node["id"], "artifact.md")
    enriched = dict(node)
    enriched.setdefault("type", node_type_map.get(node["logical_operator"], "spec"))
    enriched.setdefault("owner", owner)
    enriched.setdefault("inputs", ["requirement_ir.json"] if not node.get("depends_on") else ["upstream_artifact"])
    enriched.setdefault("outputs", [validation_target])
    enriched.setdefault("validation", [{"kind": "artifact", "target": validation_target, "required": True}])
    enriched.setdefault("risk", "high" if node["logical_operator"] in {"Verifier", "Critic"} else ("medium" if request_type != SHORT_IMPL else "low"))
    enriched.setdefault("uncertainty", 0.2 if request_type == SHORT_IMPL else (0.45 if request_type == FULL_SPEC else 0.55))
    enriched.setdefault("parallelizable", request_type != SHORT_IMPL and node["logical_operator"] not in {"Verifier", "Critic"})
    enriched.setdefault("approval_gate", node["logical_operator"] in {"Verifier", "Critic"})
    return enriched


def _build_requirement_items(
    normalized_goal: str,
    acceptance: list[str],
    priority: str,
) -> list[dict[str, Any]]:
    items = [
        {
            "id": "REQ-000",
            "source_text": normalized_goal,
            "success_criteria": [normalized_goal],
            "verification_method": "task_graph_closeout",
            "priority": priority,
        }
    ]
    for index, item in enumerate(acceptance, start=1):
        items.append(
            {
                "id": f"REQ-{index:03d}",
                "source_text": item,
                "success_criteria": [item],
                "verification_method": "acceptance_evidence",
                "priority": priority,
            }
        )
    return items


def _apply_requirement_mapping(
    graph: dict[str, Any],
    requirements: list[dict[str, Any]],
    request_type: str,
) -> dict[str, Any]:
    mapped = dict(graph)
    nodes = [dict(node) for node in mapped.get("nodes") or []]
    goal_req = requirements[:1]
    acceptance_reqs = requirements[1:] or requirements[:1]
    all_req_ids = [item["id"] for item in requirements]
    goal_req_ids = [item["id"] for item in goal_req]
    acceptance_req_ids = [item["id"] for item in acceptance_reqs]

    root_ops = {"DeepArchitect", "ResearchScout"}
    terminal_ops = {"Verifier", "Critic", "ArtifactCurator"}
    execution_ops = {"ImplementationWorker", "TestRunner", "ResearchSynthesizer"}

    for node in nodes:
        op = str(node.get("logical_operator") or "")
        if op in root_ops:
            node["requirement_ids"] = all_req_ids
        elif op in execution_ops:
            node["requirement_ids"] = acceptance_req_ids
        elif op in terminal_ops:
            node["requirement_ids"] = all_req_ids
        else:
            node["requirement_ids"] = goal_req_ids
        if request_type == RESEARCH and op == "ResearchScout" and not node.get("depends_on"):
            node["requirement_ids"] = goal_req_ids
    mapped["nodes"] = nodes
    return mapped


def _make_prd_view(
    request_type: str,
    normalized_goal: str,
    source_inputs: dict[str, Any],
    acceptance: list[str],
    non_goals: list[str],
    open_questions: list[str],
    risks: list[dict[str, str]],
) -> dict[str, Any]:
    if request_type == "implementation":
        sections = [
            {"title": "Goal", "body": normalized_goal},
            {"title": "Context", "body": "相关上下文: " + ", ".join(source_inputs["repo_context"] + source_inputs["logs"]) if source_inputs["repo_context"] or source_inputs["logs"] else "基于当前请求直接定位到局部改动范围。"},
            {"title": "Scope", "body": f"- {normalized_goal}"},
            {"title": "Non-goals", "body": "\n".join(f"- {item}" for item in non_goals)},
            {"title": "Acceptance Criteria", "body": "\n".join(f"- {item}" for item in acceptance)},
            {"title": "Validation", "body": "- 运行测试或 smoke check\n- 记录 diff / 风险 / 验证证据"},
            {"title": "Rollback", "body": "如验证失败，回退到变更前状态并保留失败证据。"},
        ]
        return {"variant": "short", "sections": sections}
    if request_type == "research":
        sections = [
            {"title": "Research Question", "body": normalized_goal},
            {"title": "Paper Inventory", "body": "\n".join(f"- {paper}" for paper in source_inputs["papers"]) or "- 待补充来源"},
            {"title": "Claim Extraction", "body": "对每篇论文提取核心 claim、方法、benchmark、限制条件。"},
            {"title": "Evidence Map", "body": "每个 engineering implication 都必须绑定 source + evidence + confidence。"},
            {"title": "Relevance to Our System", "body": "输出对 Codex / solar-harness / PM pane 的工程含义。"},
            {"title": "Design Candidates", "body": "基于证据链生成候选设计方案，并明确 pros / cons。"},
            {"title": "Experiment Plan", "body": "定义 baseline、metric、threshold 和失败退出条件。"},
            {"title": "Build Plan", "body": "只有通过 eval gate 的研究结论才能进入实现 DAG。"},
            {"title": "Adoption Criteria", "body": "\n".join(f"- {item}" for item in acceptance)},
            {"title": "Rejection Criteria", "body": "\n".join(f"- [{risk['level']}] {risk['title']} -> {risk['mitigation']}" for risk in risks)},
        ]
        return {"variant": "research", "sections": sections}
    sections = [
        {"title": "1. Problem", "body": normalized_goal},
        {"title": "2. Users / Stakeholders", "body": "- PM\n- Planner\n- Builder\n- Evaluator"},
        {"title": "3. Goals / Non-goals", "body": "Goals:\n- " + normalized_goal + "\n\nNon-goals:\n" + "\n".join(f"- {item}" for item in non_goals)},
        {"title": "4. User Scenarios", "body": "用户输入需求后，需要被结构化、合约化、任务图化，然后再派给执行链路。"},
        {"title": "5. Functional Requirements", "body": "\n".join(f"- {item}" for item in acceptance)},
        {"title": "6. Non-functional Requirements", "body": "- 可验证\n- 可追溯\n- 与现有 PM -> Planner -> Builder 主链兼容"},
        {"title": "7. UX / Interaction Model", "body": "首批仅提供编译结果视图与 handoff bar，不重做完整 UI。"},
        {"title": "8. Data Model", "body": "Requirement IR 为唯一事实源，PRD/contract/DAG/handoff 均从 IR 派生。"},
        {"title": "9. Acceptance Criteria", "body": "\n".join(f"- {item}" for item in acceptance)},
        {"title": "10. Risks / Open Questions", "body": "\n".join(f"- [{risk['level']}] {risk['title']} -> {risk['mitigation']}" for risk in risks) + "\n\nOpen Questions:\n" + ("\n".join(f"- {item}" for item in open_questions) if open_questions else "- N/A")},
        {"title": "11. Release Plan", "body": "先交付后端编译底座，再逐步扩展 PM pane UI 与 eval loop。"},
    ]
    return {"variant": "standard", "sections": sections}


def _build_contracts(
    classification: str,
    normalized_goal: str,
    acceptance: list[str],
    non_goals: list[str],
    stop_rules: list[str],
    request_text: str,
    papers: list[str],
) -> dict[str, Any]:
    product = {
        "enabled": True,
        "goal": normalized_goal,
        "success_metrics": acceptance,
        "non_goals": non_goals,
        "acceptance": acceptance,
        "stop_rules": stop_rules,
    }
    interface = {
        "enabled": True,
        "name": "RequirementCompilerAdapters",
        "version": "1.0",
        "inputs": ["RequirementIR"],
        "outputs": ["ProductBrief", "ContractsBundle", "TaskDAG", "HandoffPackage"],
        "invariants": [
            "Requirement IR is the only source of truth.",
            "DAG nodes[*].id must be unique.",
            "Every acceptance criterion maps to at least one validation step.",
        ],
        "errors": [
            {"code": "CYCLE_DETECTED", "action": "split dependencies or ask for clarification"},
            {"code": "ACCEPTANCE_COVERAGE_MISSING", "action": "add validation before dispatch"},
        ],
    }
    agent_execution = {
        "enabled": True,
        "task_scope": CLASS_TO_CANONICAL[classification],
        "allowed_paths": ["apps/pm-pane/**", "packages/requirement-ir/**", "harness/**"],
        "forbidden_paths": ["infra/prod/**", ".env*", "secrets/**"],
        "commands": {
            "test": ["pnpm test", "pnpm lint"],
            "inspect": ["rg", "python3", "pytest"],
        },
        "approval_required_when": [
            "new production dependency",
            "database migration",
            "network access",
            "touching auth or billing",
        ],
        "stop_conditions": stop_rules,
    }
    research = {
        "enabled": classification == RESEARCH,
        "hypothesis": normalized_goal,
        "source_papers": papers,
        "experiments": [
            {
                "name": "dag_quality_eval",
                "dataset": "golden_cases.jsonl",
                "metric": ["cycle_rate", "acceptance_coverage", "human_edit_distance"],
            }
        ] if classification == RESEARCH else [],
        "adoption_threshold": {
            "cycle_rate": "< 2%",
            "acceptance_coverage": "> 95%",
            "human_edit_reduction": "> 25%",
        } if classification == RESEARCH else {},
        "rejection_criteria": [
            "No evidence ledger available",
            "No verifier/critique gate",
        ] if classification == RESEARCH else [],
    }
    return {
        "product": product,
        "interface": interface,
        "agent_execution": agent_execution,
        "research": research,
        "bundle": {
            "schema_version": "solar.contract_bundle.v1",
            "request_type": CLASS_TO_CANONICAL[classification],
            "source_of_truth": "requirement_ir.json",
            "contracts": {
                "product": product,
                "interface": interface,
                "agent_execution": agent_execution,
                "research": research,
            },
            "request_excerpt": request_text[:240],
        },
    }


def _render_prd_markdown(title: str, prd_view: dict[str, Any]) -> str:
    lines = [f"# {title}", ""]
    for section in prd_view["sections"]:
        lines.append(f"## {section['title']}")
        lines.append(section["body"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_contract_markdown(title: str, contracts: dict[str, Any]) -> str:
    product = contracts["product"]
    interface = contracts["interface"]
    agent = contracts["agent_execution"]
    research = contracts["research"]
    lines = [
        f"# Compiled Contract — {title}",
        "",
        "## Canonical Sources",
        "",
        "- `requirement_ir.json` is the source of truth.",
        "- `contracts/*.yaml` are canonical structured contracts.",
        "- `.contract.md` is a compiled human-readable view.",
        "",
        "## Product Contract",
        "",
        f"- goal: {product['goal']}",
        "- success_metrics:",
        *[f"  - {item}" for item in product["success_metrics"]],
        "- non_goals:",
        *[f"  - {item}" for item in product["non_goals"]],
        "",
        "## Interface Contract",
        "",
        f"- name: {interface['name']}",
        f"- version: {interface['version']}",
        "- invariants:",
        *[f"  - {item}" for item in interface["invariants"]],
        "",
        "## Agent Execution Contract",
        "",
        "- allowed_paths:",
        *[f"  - {item}" for item in agent["allowed_paths"]],
        "- forbidden_paths:",
        *[f"  - {item}" for item in agent["forbidden_paths"]],
        "- approval_required_when:",
        *[f"  - {item}" for item in agent["approval_required_when"]],
        "- stop_conditions:",
        *[f"  - {item}" for item in agent["stop_conditions"]],
    ]
    if research.get("enabled"):
        lines.extend(
            [
                "",
                "## Research Contract",
                "",
                f"- hypothesis: {research['hypothesis']}",
                "- source_papers:",
                *[f"  - {item}" for item in research["source_papers"]],
                "- rejection_criteria:",
                *[f"  - {item}" for item in research["rejection_criteria"]],
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_handoff_markdown(
    title: str,
    target: str,
    goal: str,
    artifacts: list[str],
    acceptance: list[str],
    constraints: list[str],
) -> str:
    lines = [
        f"# {target} Handoff — {title}",
        "",
        "## Goal",
        "",
        goal,
        "",
        "## Read First",
        "",
        *[f"- {item}" for item in artifacts],
        "",
        "## Constraints",
        "",
        *[f"- {item}" for item in constraints],
        "",
        "## Acceptance",
        "",
        *[f"- {item}" for item in acceptance],
        "",
    ]
    return "\n".join(lines)


def _render_product_brief_markdown(brief: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Product Brief — {brief['title']}",
            "",
            f"**Source**: {brief['source']}",
            f"**Priority**: {brief['priority']}",
            f"**Lane**: {brief['lane_hint']}",
            f"**Handoff To**: {brief['handoff_to']}",
            "",
            "## Intent",
            "",
            brief["intent"],
            "",
            "## Problem",
            "",
            brief["problem"],
            "",
            "## Acceptance Criteria",
            "",
            *[f"- {item}" for item in brief["acceptance"]],
            "",
            "## Non-Goals",
            "",
            *[f"- {item}" for item in brief["non_goals"]],
            "",
            "## Stop Rules",
            "",
            *[f"- {item}" for item in brief["stop_rules"]],
            "",
            "## Context / Notes",
            "",
            brief.get("notes", "N/A"),
            "",
        ]
    )


def emit_requirement_package(
    payload: dict[str, Any],
    *,
    workspace_root: Path,
    sprint_root: Path | None = None,
    sprint_id: str = "",
) -> dict[str, str]:
    workspace_root = Path(workspace_root)
    pm_dir = workspace_root / ".pm"
    contracts_dir = pm_dir / "contracts"
    handoff_dir = pm_dir / "handoff"
    evals_dir = pm_dir / "evals"
    artifacts = payload["compiled_artifacts"]
    requirement_ir = payload["requirement_ir"]
    _write_json(pm_dir / "intake.json", payload["pm_intake"])
    _write_json(pm_dir / "requirement_ir.json", requirement_ir)
    _write_json(pm_dir / "requirement_trace.json", artifacts["requirement_trace"])
    _write_json(pm_dir / "coverage_report.json", artifacts["coverage_report"])
    _write_json(pm_dir / "acceptance_verdict.json", artifacts["acceptance_verdict"])
    _write_text(pm_dir / "prd.md", artifacts["prd_markdown"])
    _write_yaml(pm_dir / "Contracts.yaml", artifacts["contracts_bundle"])
    _write_yaml(contracts_dir / "product.yaml", artifacts["contract_files"]["product"])
    _write_yaml(contracts_dir / "interface.yaml", artifacts["contract_files"]["interface"])
    _write_yaml(contracts_dir / "agent_execution.yaml", artifacts["contract_files"]["agent_execution"])
    _write_yaml(contracts_dir / "research.yaml", artifacts["contract_files"]["research"])
    _write_json(pm_dir / "task_dag.json", artifacts["task_dag"])
    _write_text(handoff_dir / "codex_handoff.md", artifacts["handoff_markdown"]["codex"])
    _write_text(handoff_dir / "solar_harness_handoff.md", artifacts["handoff_markdown"]["solar_harness"])
    _write_text(evals_dir / "golden_cases.jsonl", "\n".join(json.dumps(case, ensure_ascii=False) for case in artifacts["eval_seed_cases"]) + "\n")

    emitted = {
        "pm_dir": str(pm_dir),
        "requirement_ir": str(pm_dir / "requirement_ir.json"),
        "requirement_trace": str(pm_dir / "requirement_trace.json"),
        "coverage_report": str(pm_dir / "coverage_report.json"),
        "acceptance_verdict": str(pm_dir / "acceptance_verdict.json"),
        "prd": str(pm_dir / "prd.md"),
        "contracts_bundle": str(pm_dir / "Contracts.yaml"),
        "task_dag": str(pm_dir / "task_dag.json"),
        "codex_handoff": str(handoff_dir / "codex_handoff.md"),
        "solar_harness_handoff": str(handoff_dir / "solar_harness_handoff.md"),
    }
    if sprint_root and sprint_id:
        sprint_root = Path(sprint_root)
        _write_text(sprint_root / f"{sprint_id}.prd.md", artifacts["prd_markdown"])
        _write_text(sprint_root / f"{sprint_id}.contract.md", artifacts["contract_markdown"])
        _write_json(sprint_root / f"{sprint_id}.task_graph.json", artifacts["task_dag"])
        _write_text(sprint_root / f"{sprint_id}.product-brief.md", artifacts["product_brief_markdown"])
        _write_text(sprint_root / f"{sprint_id}.handoff.md", artifacts["handoff_markdown"]["solar_harness"])
        _write_json(sprint_root / f"{sprint_id}.requirement_ir.json", requirement_ir)
        _write_json(sprint_root / f"{sprint_id}.requirement_trace.json", artifacts["requirement_trace"])
        _write_json(sprint_root / f"{sprint_id}.coverage_report.json", artifacts["coverage_report"])
        _write_json(sprint_root / f"{sprint_id}.acceptance_verdict.json", artifacts["acceptance_verdict"])
        _write_yaml(sprint_root / f"{sprint_id}.Contracts.yaml", artifacts["contracts_bundle"])
        emitted.update(
            {
                "sprint_prd": str(sprint_root / f"{sprint_id}.prd.md"),
                "sprint_contract": str(sprint_root / f"{sprint_id}.contract.md"),
                "sprint_task_graph": str(sprint_root / f"{sprint_id}.task_graph.json"),
                "sprint_requirement_trace": str(sprint_root / f"{sprint_id}.requirement_trace.json"),
                "sprint_coverage_report": str(sprint_root / f"{sprint_id}.coverage_report.json"),
                "sprint_acceptance_verdict": str(sprint_root / f"{sprint_id}.acceptance_verdict.json"),
                "sprint_product_brief": str(sprint_root / f"{sprint_id}.product-brief.md"),
                "sprint_handoff": str(sprint_root / f"{sprint_id}.handoff.md"),
            }
        )
    return emitted


def _normalized_text(text: str) -> str:
    return " ".join(text.strip().split())


def classify_request_type(text: str, papers: list[str] | None = None) -> str:
    papers = papers or []
    normalized = _normalized_text(text)
    lowered = normalized.lower()
    if papers:
        return RESEARCH
    if re.search(r"\b(arxiv|doi|paper|study|literature|survey|iclr|neurips|mlsys|benchmark comparison)\b", lowered):
        return RESEARCH
    if re.search(r"(论文|调研|研究|综述|文献|citation)", normalized):
        return RESEARCH

    full_spec_markers = [
        "architecture", "runtime", "system", "platform", "compatibility",
        "rollout", "migration", "refactor", "dag scheduler", "multi-step",
        "phased", "requirement compiler", "requirement ir", "task dag",
        "contract", "handoff", "设计", "架构", "系统", "改造", "迁移", "兼容", "规划",
        "需求编译器", "需求中间表示", "任务图",
    ]
    if any(marker in lowered for marker in full_spec_markers) or any(marker in normalized for marker in full_spec_markers):
        return FULL_SPEC

    short_markers = [
        "fix", "bug", "add", "change", "rename", "check", "trace",
        "修", "改", "查", "看", "补", "加一个", "改一下", "检查",
    ]
    line_count = len([line for line in text.splitlines() if line.strip()])
    if (
        len(normalized) <= 280
        or line_count <= 3
        or any(marker in lowered for marker in short_markers)
        or any(marker in normalized for marker in short_markers)
    ):
        return SHORT_IMPL
    return FULL_SPEC


def choose_lane_hint(request_type: str, text: str) -> str:
    lowered = text.lower()
    if request_type == RESEARCH:
        return "strategy"
    if request_type == FULL_SPEC and re.search(r"(architecture|refactor|runtime|system|platform|schema|dag)", lowered):
        return "strategy"
    return "delivery"


def choose_priority(text: str, request_type: str) -> str:
    lowered = text.lower()
    if re.search(r"(p0|urgent|blocker|broken|crash|failure|security|sev0)", lowered):
        return "P0"
    if request_type == RESEARCH:
        return "P1"
    if request_type == SHORT_IMPL:
        return "P1" if re.search(r"(bug|fix|repair|修|排查|debug)", lowered) else "P2"
    return "P1"


def choose_output_mode(request_type: str) -> dict[str, str]:
    if request_type == SHORT_IMPL:
        return {"prd": "short", "contract": "short", "dag": "short"}
    if request_type == RESEARCH:
        return {"prd": "research", "contract": "research", "dag": "research"}
    return {"prd": "standard", "contract": "standard", "dag": "standard"}


def choose_acceptance_profile(request_type: str) -> str:
    if request_type == SHORT_IMPL:
        return "execution_evidence"
    if request_type == RESEARCH:
        return "evidence_synthesis"
    return "phased_delivery"


def _short_task_graph() -> dict[str, Any]:
    return {
        "dag_variant": "short",
        "required_gates": ["G_IMPL", "G_TEST", "G_REVIEW"],
        "nodes": [
            {
                "id": "S1",
                "goal": "Implement the requested targeted change.",
                "logical_operator": "ImplementationWorker",
                "depends_on": [],
                "acceptance": ["Patch or config change produced within declared scope."],
                "verifier_required": True,
                "estimated_cost": 1,
            },
            {
                "id": "S2",
                "goal": "Run tests or collect execution evidence for the change.",
                "logical_operator": "TestRunner",
                "depends_on": ["S1"],
                "acceptance": ["Test report or execution evidence captured."],
                "estimated_cost": 1,
            },
            {
                "id": "S3",
                "goal": "Review implementation and evidence before closeout.",
                "logical_operator": "Verifier",
                "depends_on": ["S2"],
                "acceptance": ["Independent verifier decision recorded."],
                "estimated_cost": 1,
            },
        ],
    }


def _standard_task_graph(strategy_lane: bool) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [
        {
            "id": "S1",
            "goal": "Lock implementation approach, constraints, and file boundaries.",
            "logical_operator": "DeepArchitect",
            "depends_on": [],
            "acceptance": ["Implementation path and constraints are explicit."],
            "estimated_cost": 2,
        },
        {
            "id": "S2",
            "goal": "Implement the approved scope.",
            "logical_operator": "ImplementationWorker",
            "depends_on": ["S1"],
            "acceptance": ["Patch is produced within declared write scope."],
            "estimated_cost": 3,
        },
        {
            "id": "S3",
            "goal": "Run verification commands and collect execution evidence.",
            "logical_operator": "TestRunner",
            "depends_on": ["S2"],
            "acceptance": ["Verification evidence is attached."],
            "estimated_cost": 2,
        },
        {
            "id": "S4",
            "goal": "Perform independent review and closeout decision.",
            "logical_operator": "Verifier",
            "depends_on": ["S3"],
            "acceptance": ["Verifier decision is machine-readable."],
            "estimated_cost": 2,
        },
    ]
    if strategy_lane:
        nodes.append(
            {
                "id": "S5",
                "goal": "Check migration, compatibility, or rollout implications.",
                "logical_operator": "Critic",
                "depends_on": ["S4"],
                "acceptance": ["Compatibility or rollout notes are explicit."],
                "estimated_cost": 2,
            }
        )
    return {
        "dag_variant": "standard",
        "required_gates": ["G_PLAN", "G_IMPL", "G_VERIFY", "G_REVIEW"],
        "nodes": nodes,
    }


def _research_task_graph() -> dict[str, Any]:
    return {
        "dag_variant": "research",
        "research_mode": True,
        "evidence_policy": {
            "ledger_required": True,
            "unsupported_claim_guard": True,
            "citation_required": True,
        },
        "required_gates": ["G_SOURCE", "G_EVIDENCE", "G_SYNTHESIS", "G_REVIEW"],
        "nodes": [
            {
                "id": "R1",
                "goal": "Ingest papers, links, and source metadata into the research run.",
                "logical_operator": "ResearchScout",
                "depends_on": [],
                "acceptance": ["Source manifest is recorded."],
                "estimated_cost": 1,
            },
            {
                "id": "R2",
                "goal": "Extract claims, findings, and relevant technical levers.",
                "logical_operator": "ResearchScout",
                "depends_on": ["R1"],
                "acceptance": ["Claims ledger is produced."],
                "estimated_cost": 2,
            },
            {
                "id": "R3",
                "goal": "Scan contradictions, gaps, and unsupported assumptions.",
                "logical_operator": "Critic",
                "depends_on": ["R2"],
                "acceptance": ["Contradictions or gaps are enumerated."],
                "estimated_cost": 2,
            },
            {
                "id": "R4",
                "goal": "Synthesize the research into actionable insights.",
                "logical_operator": "ResearchSynthesizer",
                "depends_on": ["R2", "R3"],
                "acceptance": ["Synthesis report is drafted."],
                "estimated_cost": 3,
            },
            {
                "id": "R5",
                "goal": "Perform independent critique and evidence verification.",
                "logical_operator": "Verifier",
                "depends_on": ["R4"],
                "acceptance": ["Critique and verifier decision are recorded."],
                "estimated_cost": 2,
            },
            {
                "id": "R6",
                "goal": "Translate research findings into PRD/DAG implications.",
                "logical_operator": "ArtifactCurator",
                "depends_on": ["R5"],
                "acceptance": ["Final implications document is produced."],
                "estimated_cost": 1,
            },
        ],
    }


def build_task_graph_skeleton(request_type: str, lane_hint: str) -> dict[str, Any]:
    if request_type == SHORT_IMPL:
        return _short_task_graph()
    if request_type == RESEARCH:
        return _research_task_graph()
    return _standard_task_graph(strategy_lane=lane_hint == "strategy")


def build_pm_intake(
    text: str,
    *,
    papers: list[str] | None = None,
    logs: list[str] | None = None,
    repo_context: list[str] | None = None,
    sprint_id: str = "",
    target_system: str = "solar-harness",
) -> dict[str, Any]:
    papers = papers or []
    logs = logs or []
    repo_context = repo_context or []
    request_type = classify_request_type(text, papers)
    canonical_request_type = CLASS_TO_CANONICAL[request_type]
    lane_hint = choose_lane_hint(request_type, text)
    output_mode = choose_output_mode(request_type)
    priority = choose_priority(text, request_type)
    task_graph = build_task_graph_skeleton(request_type, lane_hint)
    task_graph["nodes"] = [_node_enrichment(request_type, node) for node in task_graph["nodes"]]
    normalized_goal = _normalized_text(text)[:400]
    title = _safe_title(text)
    acceptance = _default_acceptance(request_type)
    non_goals = _default_non_goals(request_type)
    stop_rules = _default_stop_rules(request_type)
    open_questions = _derive_open_questions(request_type, text, papers)
    risk_register = _derive_risk_register(request_type)
    requirements = _build_requirement_items(normalized_goal, acceptance, priority)
    source_inputs = {
        "raw_request": text,
        "papers": papers,
        "logs": logs,
        "repo_context": repo_context,
    }
    prd_view = _make_prd_view(
        canonical_request_type,
        normalized_goal,
        source_inputs,
        acceptance,
        non_goals,
        open_questions,
        risk_register,
    )
    contracts = _build_contracts(
        request_type,
        normalized_goal,
        acceptance,
        non_goals,
        stop_rules,
        text,
        papers,
    )
    requirement_ir = {
        "schema_version": "solar.requirement_ir.v1",
        "id": f"req-{uuid.uuid4().hex[:12]}",
        "request_type": canonical_request_type,
        "priority": priority,
        "lane_hint": lane_hint,
        "source_inputs": source_inputs,
        "user_intent": normalized_goal,
        "normalized_goal": normalized_goal,
        "assumptions": _derive_assumptions(request_type, lane_hint),
        "open_questions": open_questions,
        "risk_register": risk_register,
        "requirements": requirements,
        "scheduling": {
            "queue_class": "requirements_compile",
            "global_priority_boost": 1000,
            "lane_hint": lane_hint,
        },
        "confidence": _derive_confidence(request_type, text, papers),
        "prd_view": prd_view,
        "contracts": {
            "product": contracts["product"],
            "interface": contracts["interface"],
            "agent_execution": contracts["agent_execution"],
            "research": contracts["research"],
        },
        "dag_view": task_graph,
        "handoff_view": {
            "codex": {
                "target": "Codex",
                "artifacts": [
                    ".pm/requirement_ir.json",
                    ".pm/prd.md",
                    ".pm/Contracts.yaml",
                    ".pm/task_dag.json",
                ],
            },
            "solar_harness": {
                "target": "solar-harness",
                "artifacts": [
                    ".pm/requirement_ir.json",
                    ".pm/prd.md",
                    ".pm/Contracts.yaml",
                    ".pm/task_dag.json",
                    ".pm/handoff/solar_harness_handoff.md",
                ],
            },
        },
        "evidence_policy": task_graph.get("evidence_policy", {}),
    }
    task_graph = _apply_requirement_mapping(task_graph, requirements, request_type)
    task_graph = enrich_task_graph_defaults(task_graph, requirement_ir, sprint_id=sprint_id or "N/A")
    requirement_ir["dag_view"] = task_graph
    product_brief = {
        "title": title,
        "source": "codex-pm-router",
        "intent": normalized_goal,
        "problem": normalized_goal,
        "priority": priority,
        "lane_hint": lane_hint,
        "acceptance": acceptance,
        "non_goals": non_goals,
        "stop_rules": stop_rules,
        "handoff_to": "planner",
        "request_type": request_type,
        "template_variant": output_mode["prd"],
        "pm_intake": {
            "request_type": request_type,
            "intent_summary": _normalized_text(text)[:240],
            "source_inputs": {
                "papers": papers,
                "logs": logs,
                "repo_context": repo_context,
            },
            "output_mode": output_mode,
        },
        "requirement_ir_ref": ".pm/requirement_ir.json",
        "notes": "Requirement Compiler produced canonical IR, compiled contracts, and a task DAG proposal.",
    }
    prd_markdown = _render_prd_markdown(title, prd_view)
    contract_markdown = _render_contract_markdown(title, contracts)
    codex_handoff_md = _render_handoff_markdown(
        title,
        "Codex",
        _normalized_text(text)[:400],
        [".pm/requirement_ir.json", ".pm/prd.md", ".pm/Contracts.yaml", ".pm/task_dag.json"],
        acceptance,
        [
            "Treat requirement_ir.json and contracts/*.yaml as canonical sources.",
            "Use requirement_trace/coverage_report as completion evidence, not intuition.",
            "Do not bypass planner before builder dispatch.",
        ],
    )
    solar_handoff_md = _render_handoff_markdown(
        title,
        "solar-harness",
        "Read compiled PRD / contract / task graph proposal, then produce planner artifacts without skipping governance.",
        [".pm/requirement_ir.json", ".pm/prd.md", ".pm/Contracts.yaml", ".pm/task_dag.json", ".pm/handoff/solar_harness_handoff.md"],
        [
            "Planner produces design.md and plan.md.",
            "Planner may refine task_graph.json but must preserve compiled governance constraints and explicit requirement_ids mapping.",
            "No direct builder dispatch from raw request.",
        ],
        [
            "IR is source of truth.",
            "Markdown PRD / contract are compiled views.",
        ],
    )
    product_brief_markdown = _render_product_brief_markdown(product_brief)
    requirement_trace = build_requirement_trace(requirement_ir, task_graph)
    coverage_report = build_coverage_report(requirement_trace, task_graph)
    acceptance_verdict = build_acceptance_verdict(
        requirement_ir,
        task_graph,
        coverage_report,
        requested_verdict="pass",
    )
    return {
        "pm_intake": {
            "request_type": request_type,
            "intent_summary": _normalized_text(text)[:240],
            "source_inputs": {
                "papers": papers,
                "logs": logs,
                "repo_context": repo_context,
            },
            "output_mode": output_mode,
        },
        "classification": request_type,
        "canonical_request_type": canonical_request_type,
        "prd_variant": output_mode["prd"],
        "contract_variant": output_mode["contract"],
        "dag_variant": output_mode["dag"],
        "lane_hint": lane_hint,
        "priority": priority,
        "acceptance_profile": choose_acceptance_profile(request_type),
        "target_system": target_system,
        "handoff_package": {
            "sprint_id": sprint_id or "N/A",
            "artifacts": [
                "product-brief.md",
                "contract.md",
                "plan.md",
                "task_graph.json",
            ],
            "research_artifacts": [
                "source_manifest.json",
                "claims.jsonl",
                "contradictions.jsonl",
                "evidence_ledger.json",
                "synthesis.md",
                "critique.md",
            ] if request_type == RESEARCH else [],
        },
        "task_graph_skeleton": task_graph,
        "requirement_ir": requirement_ir,
        "compiled_artifacts": {
            "prd_markdown": prd_markdown,
            "contracts_bundle": contracts["bundle"],
            "contract_markdown": contract_markdown,
            "task_dag": task_graph,
            "requirement_trace": requirement_trace,
            "coverage_report": coverage_report,
            "acceptance_verdict": acceptance_verdict,
            "product_brief": product_brief,
            "product_brief_markdown": product_brief_markdown,
            "handoff_markdown": {
                "codex": codex_handoff_md,
                "solar_harness": solar_handoff_md,
            },
            "contract_files": {
                "product": contracts["product"],
                "interface": contracts["interface"],
                "agent_execution": contracts["agent_execution"],
                "research": contracts["research"],
            },
            "eval_seed_cases": [
                {
                    "case_id": f"golden-{requirement_ir['id']}",
                    "request_type": request_type,
                    "goal": _normalized_text(text)[:400],
                    "expected_dag_variant": task_graph["dag_variant"],
                    "expected_template_variant": output_mode["prd"],
                }
            ],
        },
    }


def _markdown_summary(payload: dict[str, Any]) -> str:
    intake = payload["pm_intake"]
    graph = payload["task_graph_skeleton"]
    lines = [
        "# Codex PM Router Output",
        "",
        f"- request_type: `{intake['request_type']}`",
        f"- canonical_request_type: `{payload['canonical_request_type']}`",
        f"- prd_variant: `{payload['prd_variant']}`",
        f"- contract_variant: `{payload['contract_variant']}`",
        f"- dag_variant: `{payload['dag_variant']}`",
        f"- lane_hint: `{payload['lane_hint']}`",
        f"- priority: `{payload['priority']}`",
        f"- acceptance_profile: `{payload['acceptance_profile']}`",
        "",
        "## Task Graph Skeleton",
        "",
    ]
    for node in graph["nodes"]:
        lines.append(
            f"- `{node['id']}` `{node['logical_operator']}` -> {node['goal']}"
        )
    return "\n".join(lines) + "\n"


def _read_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")
    raw = sys.stdin.read()
    if raw.strip():
        return raw
    raise SystemExit("Provide --text, --input-file, or stdin.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a request into Requirement IR and PM intake artifacts.")
    parser.add_argument("--text", help="Inline request text.")
    parser.add_argument("--input-file", help="Read request text from file.")
    parser.add_argument("--paper", action="append", default=[], help="Paper title, link, or identifier.")
    parser.add_argument("--log", action="append", default=[], help="Relevant log or error artifact path.")
    parser.add_argument("--repo-context", action="append", default=[], help="Repo path or context hint.")
    parser.add_argument("--sprint-id", default="", help="Existing sprint id if continuing work.")
    parser.add_argument("--target-system", default="solar-harness", choices=["solar-harness", "codex"], help="Downstream target system.")
    parser.add_argument("--format", default="json", choices=["json", "markdown"], help="Output format.")
    parser.add_argument("--emit-dir", default="", help="Workspace root where .pm/ artifacts should be emitted.")
    parser.add_argument("--emit-sprint-root", default="", help="Optional sprint directory for compiled sprint artifacts.")
    args = parser.parse_args()

    text = _read_text(args)
    payload = build_pm_intake(
        text,
        papers=args.paper,
        logs=args.log,
        repo_context=args.repo_context,
        sprint_id=args.sprint_id,
        target_system=args.target_system,
    )
    if args.emit_dir:
        emit_requirement_package(
            payload,
            workspace_root=Path(args.emit_dir),
            sprint_root=Path(args.emit_sprint_root) if args.emit_sprint_root else None,
            sprint_id=args.sprint_id,
        )

    if args.format == "markdown":
        sys.stdout.write(_markdown_summary(payload))
    else:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
