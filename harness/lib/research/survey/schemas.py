"""Dataclasses for professor-grade DeepResearch surveys."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "solar.research.survey.v1"


@dataclass
class SurveyRun:
    run_id: str
    brief: str
    target_chars: int = 50000
    audience: str = "technical"
    domain: str = "ai"
    status: str = "planned"
    schema_version: str = SCHEMA_VERSION


@dataclass
class SurveyQuestion:
    question_id: str
    text: str
    parent_id: str | None = None
    depth: int = 0
    required_source_types: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


@dataclass
class SourceMatrix:
    section_id: str
    required_source_types: list[str]
    recommended_source_types: list[str]
    min_sources: int
    min_evidence: int
    contradiction_required: bool = True
    schema_version: str = SCHEMA_VERSION


@dataclass
class ChapterSpec:
    chapter_id: str
    title: str
    order: int
    target_chars: int
    objective: str
    schema_version: str = SCHEMA_VERSION


@dataclass
class SectionSpec:
    section_id: str
    chapter_id: str
    title: str
    order: int
    target_chars: int
    research_question: str
    required_source_types: list[str]
    min_evidence: int
    min_claims: int
    schema_version: str = SCHEMA_VERSION


@dataclass
class SurveyReportAST:
    ast_id: str
    run_id: str
    title: str
    target_chars: int
    chapters: list[ChapterSpec]
    sections: list[SectionSpec]
    status: str = "planned"
    schema_version: str = SCHEMA_VERSION


@dataclass
class EvidencePack:
    pack_id: str
    section_id: str
    evidence_ids: list[str]
    claim_ids: list[str]
    source_ids: list[str]
    source_types: list[str]
    contradiction_slots: list[str]
    status: str
    blockers: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


@dataclass
class SectionReview:
    section_id: str
    verdict: str
    unsupported_claim_rate: float
    citation_span_accuracy: float
    source_diversity_score: float
    repetition_score: float
    issues: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


@dataclass
class SectionRevisionTrace:
    section_id: str
    round_index: int
    verdict: str
    changed: bool
    issues_before: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


@dataclass
class SurveyScorecard:
    verdict: str
    chapter_count: int
    section_count: int
    finalized_sections: int
    blocked_sections: int
    unsupported_claim_rate: float
    citation_span_accuracy: float
    contradiction_coverage: float
    source_diversity_score: float
    taxonomy_depth_score: float
    section_repetition_rate: float
    terminology_consistency_score: float
    cross_section_conflict_count: int
    chapter_coherence_score: float
    issues: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value
