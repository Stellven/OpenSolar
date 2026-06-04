"""DeepDive-local requirement compiler.

This module intentionally does not import the PM requirement compiler.  It
copies a small set of concepts under DeepDive-specific names so long-horizon
research planning can benefit from requirement contracts without sharing route
state with normal PM / PRD work.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "solar.deepdive.requirement_contract.v1"
TRACE_SCHEMA_VERSION = "solar.deepdive.traceability.v1"

EXPLICIT_DEEPDIVE_PROFILES = {
    "deepdive",
    "deepdive_research",
    "deepresearch",
    "deep_research",
}


OPERATOR_MAPPING: list[dict[str, str]] = [
    {
        "pm_concept": "RawIntent capture",
        "deepdive_operator": "DeepDiveBriefCapture",
        "copy_policy": "copy_concept_rename",
        "boundary": "DeepDive-owned input contract; never writes raw_intent.json.",
    },
    {
        "pm_concept": "Requirement IR",
        "deepdive_operator": "DeepDiveResearchContract",
        "copy_policy": "copy_schema_shape_rename",
        "boundary": "Uses solar.deepdive.requirement_contract.v1, not solar.requirement_ir.v1.",
    },
    {
        "pm_concept": "Requirement item mapping",
        "deepdive_operator": "DeepDiveQuestionMapping",
        "copy_policy": "copy_algorithm_rename",
        "boundary": "Maps research questions to D* nodes only.",
    },
    {
        "pm_concept": "Research DAG skeleton",
        "deepdive_operator": "DeepDiveEvidenceDAG",
        "copy_policy": "copy_pattern_specialize",
        "boundary": "Uses dag_variant=deepdive_research; never returns standard/research PM DAG.",
    },
    {
        "pm_concept": "Coverage report",
        "deepdive_operator": "DeepDiveTraceabilityReport",
        "copy_policy": "copy_contract_rename",
        "boundary": "Checks research questions, evidence needs, claims, chapters, and verifier gates.",
    },
    {
        "pm_concept": "Acceptance verdict",
        "deepdive_operator": "DeepDiveCloseoutDecision",
        "copy_policy": "copy_gate_rename",
        "boundary": "Publishes DeepDive closeout only; does not affect PM sprint acceptance.",
    },
]


@dataclass(frozen=True)
class DeepDiveSourceRef:
    kind: str
    uri: str
    title: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "uri": self.uri,
            "title": self.title,
            "note": self.note,
        }


@dataclass(frozen=True)
class DeepDiveQuestion:
    id: str
    text: str
    evidence_need: str
    priority: str = "P1"

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "text": self.text,
            "evidence_need": self.evidence_need,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class DeepDiveCompileOptions:
    target_chars: int = 50000
    profile: str = "deepdive"
    source_channel: str = "deepdive"
    source_refs: list[DeepDiveSourceRef] = field(default_factory=list)


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def is_explicit_deepdive_request(
    text: str,
    *,
    profile: str | None = None,
    source_channel: str | None = None,
) -> bool:
    """Return true only for explicit DeepDive entrypoints.

    Generic words like "research", "调研", "论文", or "研究" are deliberately
    insufficient.  This prevents normal requirement analysis from entering the
    DeepDive compiler by accident.
    """

    candidates = {
        normalize_text(profile or "").lower(),
        normalize_text(source_channel or "").lower(),
    }
    if candidates & EXPLICIT_DEEPDIVE_PROFILES:
        return True
    normalized = normalize_text(text)
    lowered = normalized.lower()
    explicit_markers = (
        "deepdive",
        "deep dive",
        "deepresearch",
        "deep research",
        "深度研究",
        "深研",
        "深度调研报告",
    )
    return any(marker in lowered for marker in explicit_markers) or any(
        marker in normalized for marker in explicit_markers
    )


def stable_id(prefix: str, text: str) -> str:
    digest = hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def extract_research_questions(brief: str) -> list[DeepDiveQuestion]:
    normalized = normalize_text(brief)
    raw_lines = [line.strip(" -\t") for line in str(brief or "").splitlines() if line.strip()]
    question_lines = [
        line
        for line in raw_lines
        if line.endswith("?")
        or line.endswith("？")
        or re.match(r"^(why|how|what|when|where|是否|为什么|如何|哪些|什么)", line, re.I)
    ]
    if not question_lines and normalized:
        question_lines = [normalized[:240]]

    questions: list[DeepDiveQuestion] = []
    for index, text in enumerate(question_lines[:12], start=1):
        questions.append(
            DeepDiveQuestion(
                id=f"DQ-{index:03d}",
                text=normalize_text(text),
                evidence_need="primary sources, contrary evidence, claim-level citations",
                priority="P0" if index <= 3 else "P1",
            )
        )
    return questions


def build_deepdive_evidence_dag(questions: list[DeepDiveQuestion]) -> dict[str, Any]:
    question_ids = [question.id for question in questions]
    return {
        "dag_variant": "deepdive_research",
        "runtime_owner": "DeepDive",
        "required_gates": [
            "DD_SCOPE",
            "DD_SOURCE",
            "DD_EVIDENCE",
            "DD_SYNTHESIS",
            "DD_REVIEW",
            "DD_PUBLISH",
        ],
        "evidence_policy": {
            "ledger_required": True,
            "claim_citation_required": True,
            "counter_evidence_required": True,
            "unsupported_claim_guard": True,
            "normal_requirement_pipeline_import_allowed": False,
        },
        "nodes": [
            {
                "id": "D1",
                "gate": "DD_SCOPE",
                "logical_operator": "DeepDiveBriefCapture",
                "goal": "Freeze the DeepDive scope, questions, boundaries, and output contract.",
                "depends_on": [],
                "question_ids": question_ids,
                "acceptance": ["DeepDive scope contract is explicit and bounded."],
            },
            {
                "id": "D2",
                "gate": "DD_SOURCE",
                "logical_operator": "DeepDiveSourcePlanner",
                "goal": "Plan source acquisition across primary, secondary, code, benchmark, and dissenting evidence.",
                "depends_on": ["D1"],
                "question_ids": question_ids,
                "acceptance": ["Source matrix covers every research question."],
            },
            {
                "id": "D3",
                "gate": "DD_SOURCE",
                "logical_operator": "DeepDiveSourceCollector",
                "goal": "Collect sources and write an auditable source manifest.",
                "depends_on": ["D2"],
                "question_ids": question_ids,
                "acceptance": ["Source manifest and fetch status are recorded."],
            },
            {
                "id": "D4",
                "gate": "DD_EVIDENCE",
                "logical_operator": "DeepDiveClaimCompiler",
                "goal": "Compile claims, evidence atoms, methods, limitations, and confidence.",
                "depends_on": ["D3"],
                "question_ids": question_ids,
                "acceptance": ["Claim ledger binds claims to source evidence."],
            },
            {
                "id": "D5",
                "gate": "DD_EVIDENCE",
                "logical_operator": "DeepDiveContradictionScanner",
                "goal": "Find contradictions, weak evidence, missing sources, and overclaim risks.",
                "depends_on": ["D4"],
                "question_ids": question_ids,
                "acceptance": ["Contradiction and evidence-gap matrix is produced."],
            },
            {
                "id": "D6",
                "gate": "DD_SYNTHESIS",
                "logical_operator": "DeepDiveChapterPlanner",
                "goal": "Compile chapter jobs and per-chapter evidence requirements.",
                "depends_on": ["D4", "D5"],
                "question_ids": question_ids,
                "acceptance": ["Each chapter maps to questions and evidence requirements."],
            },
            {
                "id": "D7",
                "gate": "DD_SYNTHESIS",
                "logical_operator": "DeepDiveChiefEditor",
                "goal": "Synthesize the final DeepDive report from verified chapter outputs.",
                "depends_on": ["D6"],
                "question_ids": question_ids,
                "acceptance": ["Final report draft answers each research question with evidence."],
            },
            {
                "id": "D8",
                "gate": "DD_REVIEW",
                "logical_operator": "DeepDiveClaimVerifier",
                "goal": "Verify claim grounding, contradiction handling, and publication readiness.",
                "depends_on": ["D7"],
                "question_ids": question_ids,
                "acceptance": ["Verifier decision and repair requirements are recorded."],
            },
            {
                "id": "D9",
                "gate": "DD_PUBLISH",
                "logical_operator": "DeepDiveArtifactPublisher",
                "goal": "Publish final report, evidence map, traceability report, and closeout decision.",
                "depends_on": ["D8"],
                "question_ids": question_ids,
                "acceptance": ["DeepDive artifact package is complete."],
            },
        ],
    }


def build_traceability(contract: dict[str, Any]) -> dict[str, Any]:
    graph = contract["deepdive_dag"]
    nodes = graph["nodes"]
    items: list[dict[str, Any]] = []
    for question in contract["research_questions"]:
        mapped_nodes = [
            node["id"]
            for node in nodes
            if question["id"] in (node.get("question_ids") or [])
        ]
        items.append(
            {
                "question_id": question["id"],
                "mapped_nodes": mapped_nodes,
                "expected_artifacts": [
                    "source_manifest.json",
                    "claim_ledger.jsonl",
                    "contradiction_matrix.json",
                    "chapter_jobs.json",
                    "final_report.md",
                    "deepdive_closeout.json",
                ],
            }
        )
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "contract_id": contract["id"],
        "items": items,
    }


def compile_deepdive_brief(
    brief: str,
    *,
    options: DeepDiveCompileOptions | None = None,
    expansion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or DeepDiveCompileOptions()
    raw_normalized = normalize_text(brief)
    expanded_brief = ""
    if expansion and isinstance(expansion, dict):
        expanded_brief = normalize_text(str(expansion.get("expanded_brief") or ""))
    normalized = expanded_brief or raw_normalized
    if not normalized:
        raise ValueError("brief is required")

    questions = extract_research_questions(normalized)
    source_refs = [ref.to_dict() for ref in options.source_refs]
    contract = {
        "schema_version": SCHEMA_VERSION,
        "id": stable_id("ddc", normalized),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime_owner": "DeepDive",
        "compiler": {
            "name": "DeepDiveRequirementCompiler",
            "copy_policy": "copied_selected_requirement_pipeline_concepts_with_renamed_operators",
            "normal_requirement_pipeline_import_allowed": False,
        },
        "profile": options.profile,
        "source_channel": options.source_channel,
        "raw_brief": raw_normalized,
        "brief": normalized,
        "target_chars": options.target_chars,
        "research_questions": [question.to_dict() for question in questions],
        "source_refs": source_refs,
        "scope_boundaries": {
            "must_answer": [question.text for question in questions],
            "must_not_do": [
                "Do not dispatch normal PM requirement nodes.",
                "Do not write raw_intent.json or requirement_ir.json.",
                "Do not promote unsupported claims into final conclusions.",
            ],
        },
        "output_contract": {
            "reports": ["final_report.md", "final_report.html"],
            "evidence": ["source_manifest.json", "claim_ledger.jsonl", "evidence_map.json"],
            "quality": ["contradiction_matrix.json", "claim_verification.json", "deepdive_closeout.json"],
        },
        "operator_mapping": OPERATOR_MAPPING,
    }
    if expansion:
        contract["brief_expansion"] = {
            "schema_version": expansion.get("schema_version"),
            "operator": "DeepDiveBriefExpander",
            "status": expansion.get("status"),
            "attempted": bool(expansion.get("attempted")),
            "output_md_path": expansion.get("output_md_path", ""),
            "output_json_path": expansion.get("output_json_path", ""),
            "normal_requirement_pipeline_import_allowed": False,
        }
    contract["deepdive_dag"] = build_deepdive_evidence_dag(questions)
    contract["traceability"] = build_traceability(contract)
    return contract


def validate_deepdive_contract(contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid_deepdive_contract_schema")
    if contract.get("runtime_owner") != "DeepDive":
        errors.append("runtime_owner_not_deepdive")
    if "requirement_ir" in contract or contract.get("schema_version") == "solar.requirement_ir.v1":
        errors.append("normal_requirement_ir_leak")
    compiler = contract.get("compiler") if isinstance(contract.get("compiler"), dict) else {}
    if compiler.get("normal_requirement_pipeline_import_allowed") is not False:
        errors.append("normal_requirement_pipeline_import_not_disabled")
    graph = contract.get("deepdive_dag") if isinstance(contract.get("deepdive_dag"), dict) else {}
    if graph.get("dag_variant") != "deepdive_research":
        errors.append("invalid_deepdive_dag_variant")
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict)]
    if not nodes:
        errors.append("deepdive_nodes_missing")
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id.startswith("D"):
            errors.append(f"non_deepdive_node_id:{node_id or 'N/A'}")
        op = str(node.get("logical_operator") or "")
        if not op.startswith("DeepDive"):
            errors.append(f"non_deepdive_operator:{op or 'N/A'}")
    questions = contract.get("research_questions") if isinstance(contract.get("research_questions"), list) else []
    if not questions:
        errors.append("research_questions_missing")
    trace = contract.get("traceability") if isinstance(contract.get("traceability"), dict) else {}
    if trace.get("schema_version") != TRACE_SCHEMA_VERSION:
        errors.append("invalid_traceability_schema")
    for item in trace.get("items", []):
        if not item.get("mapped_nodes"):
            errors.append(f"question_unmapped:{item.get('question_id', 'N/A')}")
    if not contract.get("source_refs"):
        warnings.append("source_refs_empty")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "question_count": len(questions),
            "node_count": len(nodes),
            "mapping_count": len(contract.get("operator_mapping") or []),
        },
    }
