"""Dataclasses for professor-grade DeepResearch surveys."""

# S03 N1 extensions appended below per S02 architecture specs (markdown, frozen):
#   - source-quality-arch.md         -> SourceQualityDistribution, StuffingAlert
#   - argument-density-arch.md       -> ArgumentDensityProfile, NotApplicableEntry, DimensionIndicator
#   - contradiction-matrix-arch.md   -> ContradictionMatrix, ClaimEvidenceLink
#   - exploration-arch.md            -> EliminationRecord, ExplorationDirection, ExplorationRunResult
#   - gate-report-arch.md            -> GateReport, GateVerdict
# Existing 12 dataclasses above the to_dict() helper remain untouched (append-only).

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

from ..schemas import FigureSpec, write_json_artifact, write_jsonl_artifact

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
    suggested_figure_type: str = ""
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
class SectionPromptPacket:
    section_id: str
    round_index: int
    writer_backend: str
    role: str
    task: str
    constraints: list[str]
    output_contract: list[str]
    artifact_paths: dict[str, str]
    schema_version: str = SCHEMA_VERSION


@dataclass
class ChapterEditorialReview:
    chapter_id: str
    verdict: str
    finalized_sections: int
    missing_sections: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
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


# =============================================================================
# S03 N1 schema extensions (APPEND ONLY)
# Each dataclass below mirrors the field table from the cited S02 arch spec.
# =============================================================================


@dataclass
class StuffingAlert:
    """Per source-quality-arch.md §1 nested table (embedded in SourceQualityDistribution).

    Promoted to a top-level dataclass so it can be round-tripped and reused by
    downstream gates without re-declaring the shape.
    """

    domain: str
    count: int
    source_ids: list[str]
    confidence: str = "medium"  # high / medium / low (per FM-4)
    schema_version: str = SCHEMA_VERSION


@dataclass
class SourceQualityDistribution:
    """Per source-quality-arch.md §1 field table (7 fields + taxonomy_version)."""

    section_id: str
    source_type_counts: dict[str, int]
    primary_ratio: float
    stuffing_alerts: list[StuffingAlert]
    canonical_coverage: dict[str, bool]
    verdict: str  # pass / warning / fail
    verdict_reasons: list[str]
    taxonomy_version: str = ""  # FM-5 traceability
    schema_version: str = SCHEMA_VERSION


@dataclass
class NotApplicableEntry:
    """Per argument-density-arch.md §1 sub-type table."""

    dimension: str  # one of the 5 DimensionName values
    reason: str  # non-empty (AC2.2 from S01 O2)
    schema_version: str = SCHEMA_VERSION


@dataclass
class DimensionIndicator:
    """Per argument-density-arch.md §1 sub-type table."""

    dimension: str
    span_text: str
    confidence: str  # high / medium / low
    schema_version: str = SCHEMA_VERSION


@dataclass
class ArgumentDensityProfile:
    """Per argument-density-arch.md §1 field table (per-section density profile)."""

    section_id: str
    dimension_coverages: dict[str, str]  # DimensionName -> CoverageStatus
    density_score: float
    detected_indicators: list[DimensionIndicator]
    not_applicable_entries: list[NotApplicableEntry] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


@dataclass
class ClaimEvidenceLink:
    """Per contradiction-matrix-arch.md §2 sub-schema table."""

    evidence_id: str
    source_id: str
    source_type: str  # paper / code / official / benchmark / web-generic
    relation_strength: str  # strong / moderate / weak
    schema_version: str = SCHEMA_VERSION


@dataclass
class ContradictionMatrix:
    """Per contradiction-matrix-arch.md §2 field table (one row per unique claim)."""

    claim_id: str
    claim_text: str
    supporting_evidence: list[ClaimEvidenceLink]
    contradicting_evidence: list[ClaimEvidenceLink]
    uncertain_evidence: list[ClaimEvidenceLink]
    chapter_ids: list[str]
    synthesis_referenced: bool
    schema_version: str = SCHEMA_VERSION


@dataclass
class EliminationRecord:
    """Per exploration-arch.md §3 field table (one entry per elimination event)."""

    direction_id: str
    direction_name: str
    score: float
    kill_reason: str  # must be non-empty
    evidence_refs: list[str]  # must be non-empty
    decision_ts: str  # ISO 8601 UTC, set at elimination moment
    direction_query: str = ""
    candidate_count: int = 0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


@dataclass
class ExplorationDirection:
    """Per exploration-arch.md §4 field table (lifecycle: active -> eliminated|selected)."""

    direction_id: str
    direction_name: str
    query: str
    status: str  # active / eliminated / selected
    source_matrix: SourceMatrix | None = None
    elimination_record: EliminationRecord | None = None
    schema_version: str = SCHEMA_VERSION


@dataclass
class ExplorationRunResult:
    """Per exploration-arch.md §6 output schema (exploration_run return type)."""

    run_id: str
    selected_directions: list[ExplorationDirection]
    eliminated_directions: list[ExplorationDirection]
    elimination_log_path: str
    source_matrix_consumed: SourceMatrix | None = None
    schema_version: str = SCHEMA_VERSION


@dataclass
class GateVerdict:
    """Per gate-report-arch.md §2 common contract (one per gate plugin output)."""

    gate_id: str
    verdict: str  # pass / warn / fail / not_applicable
    evidence_refs: list[str]
    report_section: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


@dataclass
class GateReport:
    """Per gate-report-arch.md §2 top-level field table (aggregation artifact).

    `scorecard_ref` references the frozen SurveyScorecard output via path +
    verdict snapshot rather than duplicating its fields (no rewrite of
    evaluate_survey signature, per S02 gate-report-arch §8).
    """

    report_id: str
    run_metadata: dict[str, Any]
    gate_verdicts: dict[str, GateVerdict]
    artifact_paths: dict[str, str]
    scorecard_ref: dict[str, Any]
    schema_version: str = SCHEMA_VERSION


# =============================================================================
# S03 N3 insight runtime artifact schemas and writer/validator helpers
# =============================================================================

INSIGHT_SCHEMA_VERSION = "solar.research.survey.insight.v1"


def _record_to_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return value
    raise TypeError(f"expected dataclass or dict, got {type(value).__name__}")


def _path_is_safe_relative(path_value: str) -> bool:
    path = Path(path_value)
    return bool(path_value) and not path.is_absolute() and ".." not in path.parts


@dataclass
class ArtifactValidationIssue:
    schema_name: str
    code: str
    message: str
    field_path: str = ""
    artifact_path: str = ""
    requirement_id: str = ""
    remediation: str = ""


@dataclass
class ArtifactValidationResult:
    ok: bool
    issues: list[ArtifactValidationIssue] = field(default_factory=list)
    artifact_paths: dict[str, str] = field(default_factory=dict)
    schema_version: str = INSIGHT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)


@dataclass
class CAISSourceRef:
    type: str
    title: str
    track: str = ""
    url: str = ""
    schema_version: str = INSIGHT_SCHEMA_VERSION


@dataclass
class SolarAbsorption:
    design_thesis: str
    new_schema: list[str] = field(default_factory=list)
    new_operators: list[str] = field(default_factory=list)
    new_gates: list[str] = field(default_factory=list)
    schema_version: str = INSIGHT_SCHEMA_VERSION


@dataclass
class Forecast:
    claim: str
    confidence: float
    leading_indicators: list[str]
    falsification_condition: str
    schema_version: str = INSIGHT_SCHEMA_VERSION


@dataclass
class CAISSignalPack:
    signal_id: str
    source: CAISSourceRef
    raw_signal: str
    technical_challenge: str
    agent_development_implication: str
    solar_absorption: SolarAbsorption
    forecast: Forecast
    artifact_path: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    schema_version: str = INSIGHT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        issues = validate_cais_signal_pack(self).issues
        if issues:
            raise ValueError(_format_issue(issues[0]))


@dataclass
class SolarAbsorptionItem:
    cais_signal: str
    solar_problem: str
    solar_design: str
    operators: list[str]
    schemas: list[str]
    gates: list[str]
    priority: str
    evidence_ids: list[str] = field(default_factory=list)
    schema_version: str = INSIGHT_SCHEMA_VERSION


@dataclass
class SolarAbsorptionMap:
    absorption_items: list[SolarAbsorptionItem]
    artifact_path: str = ""
    schema_version: str = INSIGHT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        issues = validate_solar_absorption_map(self).issues
        if issues:
            raise ValueError(_format_issue(issues[0]))


@dataclass
class PredictionPacket:
    prediction_id: str
    claim: str
    time_horizon: str
    confidence: float
    drivers: list[str]
    counter_scenario: str
    leading_indicators: list[str]
    falsification_condition: str
    signal_refs: list[str] = field(default_factory=list)
    artifact_path: str = ""
    schema_version: str = INSIGHT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        issues = validate_prediction_packet(self).issues
        if issues:
            raise ValueError(_format_issue(issues[0]))


@dataclass
class SectionRenderCard:
    section_id: str
    title: str
    title_claim_type: str
    body_blocks: list[dict[str, Any]]
    figure: FigureSpec | dict[str, Any]
    evidence_callouts: list[dict[str, Any]]
    takeaways: list[str]
    citations: list[dict[str, Any]]
    solar_absorption: list[str]
    prediction_packet_refs: list[str]
    artifact_path: str = ""
    schema_version: str = INSIGHT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        issues = validate_section_render_card(self).issues
        if issues:
            raise ValueError(_format_issue(issues[0]))


def _format_issue(issue: ArtifactValidationIssue) -> str:
    location = f" at {issue.field_path}" if issue.field_path else ""
    return f"{issue.schema_name}.{issue.code}{location}: {issue.message}"


def _issue(
    issues: list[ArtifactValidationIssue],
    schema_name: str,
    code: str,
    message: str,
    field_path: str,
    artifact_path: str = "",
    requirement_id: str = "",
    remediation: str = "",
) -> None:
    issues.append(
        ArtifactValidationIssue(
            schema_name=schema_name,
            code=code,
            message=message,
            field_path=field_path,
            artifact_path=artifact_path,
            requirement_id=requirement_id,
            remediation=remediation,
        )
    )


def _require_text(issues: list[ArtifactValidationIssue], schema_name: str, data: dict[str, Any], field_path: str, artifact_path: str) -> None:
    if not isinstance(data.get(field_path), str) or not data.get(field_path, "").strip():
        _issue(issues, schema_name, "required_text", f"{field_path} must be a non-empty string", field_path, artifact_path, remediation="Provide the missing insight field from evidence-backed extraction.")


def _require_list(issues: list[ArtifactValidationIssue], schema_name: str, data: dict[str, Any], field_path: str, artifact_path: str) -> None:
    if not isinstance(data.get(field_path), list) or not data.get(field_path):
        _issue(issues, schema_name, "required_list", f"{field_path} must be a non-empty list", field_path, artifact_path, remediation="Provide at least one referenced item.")


def _require_confidence(issues: list[ArtifactValidationIssue], schema_name: str, data: dict[str, Any], field_path: str, artifact_path: str) -> None:
    value = data.get(field_path)
    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
        _issue(issues, schema_name, "confidence_range", f"{field_path} must be between 0 and 1", field_path, artifact_path, remediation="Use calibrated numeric confidence in [0, 1].")


def _validate_artifact_path(issues: list[ArtifactValidationIssue], schema_name: str, data: dict[str, Any], artifact_path: str) -> None:
    path_value = data.get("artifact_path") or artifact_path
    if path_value and not _path_is_safe_relative(str(path_value)):
        _issue(issues, schema_name, "unsafe_artifact_path", "artifact_path must be a safe relative path", "artifact_path", str(path_value), remediation="Store only workspace-relative artifact paths.")


def validate_cais_signal_pack(value: CAISSignalPack | dict[str, Any], artifact_path: str = "") -> ArtifactValidationResult:
    schema_name = "CAISSignalPack"
    data = _record_to_dict(value)
    issues: list[ArtifactValidationIssue] = []
    _validate_artifact_path(issues, schema_name, data, artifact_path)
    for key in ("signal_id", "raw_signal", "technical_challenge", "agent_development_implication"):
        _require_text(issues, schema_name, data, key, artifact_path)
    source = data.get("source")
    if not isinstance(source, dict):
        _issue(issues, schema_name, "required_object", "source must be an object", "source", artifact_path)
    else:
        for key in ("type", "title"):
            _require_text(issues, schema_name, source, key, artifact_path)
    absorption = data.get("solar_absorption")
    if not isinstance(absorption, dict):
        _issue(issues, schema_name, "required_object", "solar_absorption must be an object", "solar_absorption", artifact_path)
    else:
        _require_text(issues, schema_name, absorption, "design_thesis", artifact_path)
        for key in ("new_schema", "new_operators", "new_gates"):
            _require_list(issues, schema_name, absorption, key, artifact_path)
    forecast = data.get("forecast")
    if not isinstance(forecast, dict):
        _issue(issues, schema_name, "required_object", "forecast must be an object", "forecast", artifact_path)
    else:
        _require_text(issues, schema_name, forecast, "claim", artifact_path)
        _require_confidence(issues, schema_name, forecast, "confidence", artifact_path)
        _require_list(issues, schema_name, forecast, "leading_indicators", artifact_path)
        _require_text(issues, schema_name, forecast, "falsification_condition", artifact_path)
    return ArtifactValidationResult(ok=not issues, issues=issues, artifact_paths={"cais_signal_pack": artifact_path} if artifact_path else {})


def validate_solar_absorption_map(value: SolarAbsorptionMap | dict[str, Any], artifact_path: str = "") -> ArtifactValidationResult:
    schema_name = "SolarAbsorptionMap"
    data = _record_to_dict(value)
    issues: list[ArtifactValidationIssue] = []
    _validate_artifact_path(issues, schema_name, data, artifact_path)
    items = data.get("absorption_items")
    if not isinstance(items, list) or not items:
        _issue(issues, schema_name, "required_list", "absorption_items must be a non-empty list", "absorption_items", artifact_path)
    else:
        for index, item in enumerate(items):
            if is_dataclass(item):
                item = asdict(item)
            if not isinstance(item, dict):
                _issue(issues, schema_name, "required_object", "absorption item must be an object", f"absorption_items[{index}]", artifact_path)
                continue
            prefix = f"absorption_items[{index}]"
            for key in ("cais_signal", "solar_problem", "solar_design", "priority"):
                _require_text(issues, schema_name, item, key, artifact_path)
            for key in ("operators", "schemas", "gates"):
                _require_list(issues, schema_name, item, key, artifact_path)
            if item.get("priority") not in {"P0", "P1", "P2"}:
                _issue(issues, schema_name, "priority_enum", "priority must be P0, P1, or P2", f"{prefix}.priority", artifact_path)
    return ArtifactValidationResult(ok=not issues, issues=issues, artifact_paths={"solar_absorption_map": artifact_path} if artifact_path else {})


def validate_prediction_packet(value: PredictionPacket | dict[str, Any], artifact_path: str = "") -> ArtifactValidationResult:
    schema_name = "PredictionPacket"
    data = _record_to_dict(value)
    issues: list[ArtifactValidationIssue] = []
    _validate_artifact_path(issues, schema_name, data, artifact_path)
    for key in ("prediction_id", "claim", "time_horizon", "counter_scenario", "falsification_condition"):
        _require_text(issues, schema_name, data, key, artifact_path)
    for key in ("drivers", "leading_indicators"):
        _require_list(issues, schema_name, data, key, artifact_path)
    _require_confidence(issues, schema_name, data, "confidence", artifact_path)
    return ArtifactValidationResult(ok=not issues, issues=issues, artifact_paths={"prediction_packets": artifact_path} if artifact_path else {})


def validate_section_render_card(value: SectionRenderCard | dict[str, Any], artifact_path: str = "") -> ArtifactValidationResult:
    schema_name = "SectionRenderCard"
    data = _record_to_dict(value)
    issues: list[ArtifactValidationIssue] = []
    _validate_artifact_path(issues, schema_name, data, artifact_path)
    for key in ("section_id", "title", "title_claim_type"):
        _require_text(issues, schema_name, data, key, artifact_path)
    for key in ("body_blocks", "evidence_callouts", "takeaways", "citations", "solar_absorption", "prediction_packet_refs"):
        _require_list(issues, schema_name, data, key, artifact_path)
    figure = data.get("figure")
    if not isinstance(figure, dict):
        _issue(issues, schema_name, "required_object", "figure must be a FigureSpec-compatible object", "figure", artifact_path)
    else:
        for key in ("figure_id", "title", "figure_type", "grounding_ids"):
            if key == "grounding_ids":
                _require_list(issues, schema_name, figure, key, artifact_path)
            else:
                _require_text(issues, schema_name, figure, key, artifact_path)
    return ArtifactValidationResult(ok=not issues, issues=issues, artifact_paths={"section_render_card": artifact_path} if artifact_path else {})


def validate_figure_spec(value: FigureSpec | dict[str, Any], artifact_path: str = "") -> ArtifactValidationResult:
    schema_name = "FigureSpec"
    issues: list[ArtifactValidationIssue] = []
    try:
        FigureSpec(**value) if isinstance(value, dict) else value.__post_init__()
    except ValueError as exc:
        _issue(issues, schema_name, "invalid_figure_spec", str(exc), "figure", artifact_path, remediation="Emit a grounded FigureSpec with supported figure_type and evidence/claim grounding ids.")
    return ArtifactValidationResult(ok=not issues, issues=issues, artifact_paths={"figure_spec": artifact_path} if artifact_path else {})


def validate_insight_artifact_bundle(
    *,
    signal_packs: list[CAISSignalPack | dict[str, Any]],
    absorption_map: SolarAbsorptionMap | dict[str, Any],
    prediction_packets: list[PredictionPacket | dict[str, Any]],
    section_cards: list[SectionRenderCard | dict[str, Any]],
    figure_specs: list[FigureSpec | dict[str, Any]],
    artifact_paths: dict[str, str] | None = None,
) -> ArtifactValidationResult:
    """Validate required fields, artifact paths, and cross-references across N3 artifacts."""
    artifact_paths = artifact_paths or {}
    issues: list[ArtifactValidationIssue] = []
    for name, path in artifact_paths.items():
        if not _path_is_safe_relative(path):
            _issue(issues, "InsightArtifactBundle", "unsafe_artifact_path", f"{name} must be a safe relative path", f"artifact_paths.{name}", path)

    signal_ids = {_record_to_dict(item).get("signal_id") for item in signal_packs}
    prediction_ids = {_record_to_dict(item).get("prediction_id") for item in prediction_packets}
    figure_ids = {_record_to_dict(item).get("figure_id") for item in figure_specs}

    for item in signal_packs:
        issues.extend(validate_cais_signal_pack(item).issues)
    issues.extend(validate_solar_absorption_map(absorption_map).issues)
    for item in prediction_packets:
        packet = _record_to_dict(item)
        issues.extend(validate_prediction_packet(packet).issues)
        for ref in packet.get("signal_refs", []):
            if ref not in signal_ids:
                _issue(issues, "PredictionPacket", "missing_signal_ref", f"signal ref {ref!r} does not match a CAISSignalPack.signal_id", "signal_refs", remediation="Reference an emitted signal_id.")
    for item in section_cards:
        card = _record_to_dict(item)
        issues.extend(validate_section_render_card(card).issues)
        figure_id = (card.get("figure") or {}).get("figure_id") if isinstance(card.get("figure"), dict) else ""
        if figure_id and figure_id not in figure_ids:
            _issue(issues, "SectionRenderCard", "missing_figure_ref", f"figure {figure_id!r} is not present in FigureSpec artifacts", "figure.figure_id", remediation="Emit the referenced FigureSpec artifact.")
        for ref in card.get("prediction_packet_refs", []):
            if ref not in prediction_ids:
                _issue(issues, "SectionRenderCard", "missing_prediction_ref", f"prediction ref {ref!r} is not present in PredictionPacket artifacts", "prediction_packet_refs", remediation="Reference an emitted prediction_id.")
    for item in figure_specs:
        issues.extend(validate_figure_spec(item).issues)

    absorption = _record_to_dict(absorption_map)
    for item in absorption.get("absorption_items", []):
        item_dict = _record_to_dict(item)
        if item_dict.get("cais_signal") not in signal_ids:
            _issue(issues, "SolarAbsorptionMap", "missing_signal_ref", f"cais_signal {item_dict.get('cais_signal')!r} does not match a CAISSignalPack.signal_id", "absorption_items[].cais_signal", remediation="Map each absorption item to an emitted signal_id.")

    return ArtifactValidationResult(ok=not issues, issues=issues, artifact_paths=artifact_paths)


def write_cais_signal_packs(records: list[CAISSignalPack | dict[str, Any]], path: str | Path) -> Path:
    for record in records:
        result = validate_cais_signal_pack(record)
        if not result.ok:
            raise ValueError(_format_issue(result.issues[0]))
    return write_jsonl_artifact([_record_to_dict(record) for record in records], path)


def write_solar_absorption_map(record: SolarAbsorptionMap | dict[str, Any], path: str | Path) -> Path:
    result = validate_solar_absorption_map(record)
    if not result.ok:
        raise ValueError(_format_issue(result.issues[0]))
    return write_json_artifact(_record_to_dict(record), path)


def write_prediction_packets(records: list[PredictionPacket | dict[str, Any]], path: str | Path) -> Path:
    for record in records:
        result = validate_prediction_packet(record)
        if not result.ok:
            raise ValueError(_format_issue(result.issues[0]))
    return write_jsonl_artifact([_record_to_dict(record) for record in records], path)


def write_section_render_card(record: SectionRenderCard | dict[str, Any], path: str | Path) -> Path:
    result = validate_section_render_card(record)
    if not result.ok:
        raise ValueError(_format_issue(result.issues[0]))
    return write_json_artifact(_record_to_dict(record), path)
