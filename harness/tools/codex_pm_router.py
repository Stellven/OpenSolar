#!/usr/bin/env python3
"""Codex PM Router for three request classes.

Compiles a user request into a structured PM intake package that can feed
Codex-side skill workflows and downstream solar-harness PRD/contract/DAG
generation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SHORT_IMPL = "short_impl"
FULL_SPEC = "full_spec"
RESEARCH = "research"


def _normalized_text(text: str) -> str:
    return " ".join(text.strip().split())


def classify_request_type(text: str, papers: list[str] | None = None) -> str:
    papers = papers or []
    normalized = _normalized_text(text)
    lowered = normalized.lower()
    if papers:
        return RESEARCH
    if re.search(r"\b(arxiv|doi|paper|research|study|iclr|neurips|mlsys)\b", lowered):
        return RESEARCH
    if re.search(r"(论文|调研|研究|综述|文献|citation|evidence)", normalized):
        return RESEARCH

    full_spec_markers = [
        "architecture", "runtime", "system", "platform", "compatibility",
        "rollout", "migration", "refactor", "dag scheduler", "multi-step",
        "phased", "设计", "架构", "系统", "改造", "迁移", "兼容", "规划",
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
    lane_hint = choose_lane_hint(request_type, text)
    output_mode = choose_output_mode(request_type)
    priority = choose_priority(text, request_type)
    task_graph = build_task_graph_skeleton(request_type, lane_hint)
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
    }


def _markdown_summary(payload: dict[str, Any]) -> str:
    intake = payload["pm_intake"]
    graph = payload["task_graph_skeleton"]
    lines = [
        "# Codex PM Router Output",
        "",
        f"- request_type: `{intake['request_type']}`",
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
    parser = argparse.ArgumentParser(description="Compile a request into Codex PM intake artifacts.")
    parser.add_argument("--text", help="Inline request text.")
    parser.add_argument("--input-file", help="Read request text from file.")
    parser.add_argument("--paper", action="append", default=[], help="Paper title, link, or identifier.")
    parser.add_argument("--log", action="append", default=[], help="Relevant log or error artifact path.")
    parser.add_argument("--repo-context", action="append", default=[], help="Repo path or context hint.")
    parser.add_argument("--sprint-id", default="", help="Existing sprint id if continuing work.")
    parser.add_argument("--target-system", default="solar-harness", choices=["solar-harness", "codex"], help="Downstream target system.")
    parser.add_argument("--format", default="json", choices=["json", "markdown"], help="Output format.")
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

    if args.format == "markdown":
        sys.stdout.write(_markdown_summary(payload))
    else:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
