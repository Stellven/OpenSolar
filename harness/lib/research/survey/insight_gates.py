"""Insight-mode quality gates for DeepDive reports.

Each gate inspects an artifact directory and returns a structured result dict
with: gate_id, ok, artifact_path, failed_requirement_ids, matched_patterns or
missing_fields, and remediation_hint.

Gates are designed to be composed: a report must pass *all* gates to be
publishable in insight mode.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Generic survey TOC patterns (req 9.1)
# ---------------------------------------------------------------------------
GENERIC_SURVEY_TOC_PATTERNS: list[str] = [
    "问题定义与研究边界",
    "历史脉络与技术演进",
    "核心架构范式",
    "方法分类与代表系统",
    "评估方法与基准体系",
    "工程实现与部署约束",
    "风险、安全与可解释性",
    "产业生态与开源实现",
]

# ---------------------------------------------------------------------------
# Template repetition patterns (req 9.2)
# ---------------------------------------------------------------------------
TEMPLATE_REPETITION_PATTERNS: list[str] = [
    "研究问题与术语边界",
    "关键机制与设计空间",
    "证据链与代表工作",
    "工程取舍与评价标准",
    "风险与争议",
    "未解问题",
    "机制可行性不等于工程可控性",
]

# ---------------------------------------------------------------------------
# Machine label leak patterns (req 9.3)
# ---------------------------------------------------------------------------
MACHINE_LABEL_PATTERNS: dict[str, str] = {
    "official_doc": r"\bofficial_doc\b",
    "claim_id": r"\bclaim_id\b",
    "evidence_id": r"\bevidence_id\b",
    "source_type": r"\bsource_type\b",
    "execution_metrics": r"\bExecution Metrics\b",
    "estimated_from_report_artifacts": r"\bestimated_from_report_artifacts\b",
}

# ---------------------------------------------------------------------------
# CAIS coverage required signals (req 9.5)
# ---------------------------------------------------------------------------
CAIS_REQUIRED_SIGNALS: list[str] = [
    "Dossier",
    "Do Agents Need to Plan Step-by-Step?",
    "Open Agent Specification",
    "TraceFix",
    "AI Agents for Discovery in the Wild",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _visible_text(root: Path) -> str:
    """Return concatenated human-visible output text."""
    parts: list[str] = []
    for name in ("chief_editor_final.md", "human_final.md", "final.html", "final.md"):
        p = root / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8", errors="ignore"))
    return "\n\n".join(parts)


def _chapter_titles(ast: dict) -> list[str]:
    chapters = ast.get("chapters", [])
    if not isinstance(chapters, list):
        return []
    return [str(ch.get("title", "")) for ch in chapters if isinstance(ch, dict)]


def _gate_result(
    gate_id: str,
    ok: bool,
    artifact_path: str,
    failed_requirement_ids: list[str] | None = None,
    matched_patterns: list[str] | None = None,
    missing_fields: list[str] | None = None,
    remediation_hint: str = "",
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "ok": ok,
        "artifact_path": artifact_path,
        "failed_requirement_ids": failed_requirement_ids or [],
        "matched_patterns": matched_patterns or [],
        "missing_fields": missing_fields or [],
        "remediation_hint": remediation_hint,
    }


# ---------------------------------------------------------------------------
# Gate implementations
# ---------------------------------------------------------------------------

def run_generic_survey_toc_gate(root: Path, ast: dict) -> dict[str, Any]:
    """Req 9.1 — reject reports whose chapter titles match generic survey TOC."""
    titles = _chapter_titles(ast)
    matched = [t for t in titles if t in GENERIC_SURVEY_TOC_PATTERNS]
    ok = len(matched) < 4
    failed = []
    if not ok:
        failed.append("RG-01")
        failed.append("REQ-9.1")
    return _gate_result(
        gate_id="generic_survey_toc",
        ok=ok,
        artifact_path=str(root / "survey_report_ast.json"),
        failed_requirement_ids=failed,
        matched_patterns=matched,
        remediation_hint=(
            "Replace generic survey chapter titles (e.g. '历史脉络与技术演进') "
            "with thesis-led titles tied to the central argument. "
            "See req §9.1 for the full banned list."
        ),
    )


def run_template_repetition_gate(root: Path, ast: dict) -> dict[str, Any]:
    """Req 9.2 — reject reports with excessive repeated template headings."""
    text = _visible_text(root)
    matched_counts: dict[str, int] = {}
    for pattern in TEMPLATE_REPETITION_PATTERNS:
        count = len(re.findall(re.escape(pattern), text, flags=re.I))
        if count > 2:
            matched_counts[pattern] = count
    ok = not matched_counts
    failed = []
    if not ok:
        failed.append("RG-01")
        failed.append("REQ-9.2")
    return _gate_result(
        gate_id="template_repetition",
        ok=ok,
        artifact_path=str(root / "final.md"),
        failed_requirement_ids=failed,
        matched_patterns=list(matched_counts.keys()),
        remediation_hint=(
            "Reduce repetition of template headings/slogans like "
            "'机制可行性不等于工程可控性'. Each should appear at most 2 times. "
            "See req §9.2 for the full banned list."
        ),
    )


def run_machine_label_leak_gate(root: Path, ast: dict) -> dict[str, Any]:
    """Req 9.3 — reject human-visible output containing machine labels."""
    text = _visible_text(root)
    leaks: dict[str, int] = {}
    for label, pattern in MACHINE_LABEL_PATTERNS.items():
        count = len(re.findall(pattern, text, flags=re.I))
        if count:
            leaks[label] = count
    ok = not leaks
    failed = []
    if not ok:
        failed.append("RG-04")
        failed.append("REQ-9.3")
    return _gate_result(
        gate_id="machine_label_leak",
        ok=ok,
        artifact_path=str(root / "final.md"),
        failed_requirement_ids=failed,
        matched_patterns=list(leaks.keys()),
        remediation_hint=(
            "Remove machine labels (official_doc, claim_id, evidence_id, source_type, "
            "Execution Metrics, estimated_from_report_artifacts) from human-visible output. "
            "These are only allowed in final_machine.md, audit_dossier.json, "
            "and appendix_evidence_matrix.html."
        ),
    )


def run_solar_actionability_gate(root: Path, ast: dict) -> dict[str, Any]:
    """Req 9.4 — every major chapter needs Solar absorption mapping."""
    text = _visible_text(root)
    lowered = text.lower()
    solar_terms = {
        "operator": len(re.findall(r"\boperator\b|算子", lowered)),
        "schema": len(re.findall(r"\bschema\b|数据结构", lowered)),
        "gate": len(re.findall(r"\bgate\b|质量门|门禁", lowered)),
    }
    hit_groups = [label for label, count in solar_terms.items() if count > 0]
    missing = [label for label, count in solar_terms.items() if count == 0]
    min_hit_groups = 3
    ok = len(hit_groups) >= min_hit_groups
    failed = []
    if not ok:
        failed.append("RG-05")
        failed.append("REQ-9.4")
    return _gate_result(
        gate_id="solar_actionability",
        ok=ok,
        artifact_path=str(root / "final.md"),
        failed_requirement_ids=failed,
        missing_fields=missing,
        remediation_hint=(
            "Add Solar absorption mapping per chapter: propose at least one "
            "operator, schema, or gate for each major section. "
            f"Current hits: operator={solar_terms['operator']}, "
            f"schema={solar_terms['schema']}, gate={solar_terms['gate']}. "
            "Need at least 3 of these categories present."
        ),
    )


def run_cais_coverage_gate(root: Path, ast: dict) -> dict[str, Any]:
    """Req 9.5 — verify named CAIS paper signals are present and processed."""
    text = _visible_text(root)
    lowered = text.lower()
    found: list[str] = []
    missing: list[str] = []
    for signal in CAIS_REQUIRED_SIGNALS:
        if signal.lower() in lowered:
            found.append(signal)
        else:
            missing.append(signal)
    ok = len(missing) == 0
    failed = []
    if not ok:
        failed.append("RG-05")
        failed.append("REQ-9.5")
    return _gate_result(
        gate_id="cais_coverage",
        ok=ok,
        artifact_path=str(root / "final.md"),
        failed_requirement_ids=failed,
        matched_patterns=found,
        missing_fields=missing,
        remediation_hint=(
            "Include all required CAIS paper signals in the report: "
            f"missing {missing}. Each named paper must be mentioned "
            "with a challenge extraction and Solar mapping, not just cited once."
        ),
    )


def run_figure_required_gate(root: Path, ast: dict) -> dict[str, Any]:
    """Req 9.6 — MVP requires minimum 6 claim-linked figures."""
    figures_json = _read_json(root / "figures.json")
    json_figures = (
        figures_json
        if isinstance(figures_json, list)
        else figures_json.get("figures", [])
        if isinstance(figures_json, dict)
        else []
    )
    svg_files = list((root / "figures").glob("*.svg")) if (root / "figures").exists() else []
    text = _visible_text(root)
    html_mentions = len(re.findall(r"<figure\b|class=[\"'][^\"']*figure|\.svg", text, flags=re.I))
    figure_count = len(svg_files) + len(json_figures if isinstance(json_figures, list) else []) + html_mentions
    min_figures = 6
    ok = figure_count >= min_figures
    missing: list[str] = []
    if not ok:
        missing.append(f"figures:{figure_count}<{min_figures}")
    failed = []
    if not ok:
        failed.append("RG-06")
        failed.append("REQ-9.6")
    return _gate_result(
        gate_id="figure_required",
        ok=ok,
        artifact_path=str(root / "figures.json"),
        failed_requirement_ids=failed,
        missing_fields=missing,
        remediation_hint=(
            f"Add at least {min_figures} claim-linked figures (found {figure_count}). "
            "Required figure types: conference_signal_map, agent_challenge_matrix, "
            "solar_absorption_architecture, roadmap. "
            "Place SVGs in figures/ or reference them in figures.json."
        ),
    )


def run_citation_visibility_gate(root: Path, ast: dict) -> dict[str, Any]:
    """Req 9.7 — require visible citations, not just bottom footnotes."""
    text = _visible_text(root)
    urls = set(re.findall(r"https?://[^\s)>\"]+", text))
    markdown_links = set(re.findall(r"\[[^\]]+\]\((https?://[^)]+)\)", text))
    footnote_refs = set(re.findall(r"\[\^\d+\]|\[[0-9]{1,3}\]", text))
    visible_count = len(urls | markdown_links) + len(footnote_refs)
    min_visible = 10
    ok = visible_count >= min_visible
    missing: list[str] = []
    if not ok:
        missing.append(f"visible_sources:{visible_count}<{min_visible}")
    failed = []
    if not ok:
        failed.append("RG-04")
        failed.append("REQ-9.7")
    return _gate_result(
        gate_id="citation_visibility",
        ok=ok,
        artifact_path=str(root / "final.md"),
        failed_requirement_ids=failed,
        missing_fields=missing,
        remediation_hint=(
            f"Increase visible citations to at least {min_visible} "
            f"(found {visible_count}). Major sections need at least 2 visible "
            "citations or evidence callouts. Bottom-only footnotes are insufficient."
        ),
    )


def run_prediction_packet_gate(root: Path, ast: dict) -> dict[str, Any]:
    """Req 9.8 — require at least 4 prediction packets with complete fields."""
    packets_path = root / "prediction_packets.jsonl"
    packets = _read_jsonl(packets_path)
    required_fields = ["drivers", "leading_indicators", "counter_scenario", "falsification_condition"]
    min_packets = 4
    complete_packets = 0
    incomplete: list[str] = []
    for idx, packet in enumerate(packets):
        missing = [f for f in required_fields if not packet.get(f)]
        if not missing:
            complete_packets += 1
        else:
            incomplete.append(f"packet_{idx}:missing_{','.join(missing)}")

    text = _visible_text(root)
    lowered = text.lower()
    forecast_patterns = {
        "future": r"未来|预测|forecast|watch",
        "driver": r"driver|驱动",
        "indicator": r"indicator|领先指标|观察指标",
        "falsification": r"falsification|证伪|推翻|失效",
    }
    text_signal = any(re.search(p, lowered) for p in forecast_patterns.values())

    ok = complete_packets >= min_packets and text_signal
    missing_fields: list[str] = []
    if complete_packets < min_packets:
        missing_fields.append(f"complete_packets:{complete_packets}<{min_packets}")
    if incomplete:
        missing_fields.extend(incomplete[:5])
    failed = []
    if not ok:
        failed.append("RG-06")
        failed.append("REQ-9.8")
    return _gate_result(
        gate_id="prediction_packet",
        ok=ok,
        artifact_path=str(packets_path),
        failed_requirement_ids=failed,
        missing_fields=missing_fields,
        remediation_hint=(
            f"Provide at least {min_packets} prediction packets with drivers, "
            "leading indicators, counter scenarios, and falsification conditions. "
            f"Found {complete_packets} complete packets. "
            "Prediction content must also appear in the visible report text."
        ),
    )


def run_user_question_fitness_gate(root: Path, ast: dict) -> dict[str, Any]:
    """Req 9.9 — final output must answer all must-answer questions."""
    contract = _read_json(root / "deepdive_requirement_contract.json")
    text = _visible_text(root)
    lowered = text.lower()

    questions: list[str] = []
    scope = contract.get("scope_boundaries", {}) if isinstance(contract.get("scope_boundaries"), dict) else {}
    for item in scope.get("must_answer", []):
        if str(item).strip():
            questions.append(str(item))
    for item in contract.get("research_questions", []) if isinstance(contract.get("research_questions"), list) else []:
        if isinstance(item, dict) and str(item.get("text", "")).strip():
            questions.append(str(item["text"]))

    if not questions and ast.get("title"):
        questions.append(str(ast.get("title")))

    uncovered: list[str] = []
    for question in questions:
        tokens = _extract_question_tokens(question)
        if not tokens:
            continue
        hits = sum(1 for token in tokens if token.lower() in lowered)
        threshold = max(1, min(3, len(tokens) // 2))
        if hits < threshold:
            uncovered.append(question)

    ok = not uncovered
    failed = []
    if not ok:
        failed.append("RG-01")
        failed.append("REQ-9.9")
    return _gate_result(
        gate_id="user_question_fitness",
        ok=ok,
        artifact_path=str(root / "deepdive_requirement_contract.json"),
        failed_requirement_ids=failed,
        missing_fields=uncovered,
        remediation_hint=(
            "The report does not explicitly answer these required questions: "
            f"{uncovered}. Each must-answer question needs a dedicated section "
            "with a clear, thesis-backed response."
        ),
    )


def _extract_question_tokens(question: str) -> set[str]:
    COMMON = {
        "what", "which", "with", "this", "that", "should", "when", "where",
        "how", "why", "deepdive", "insight", "report", "分析", "报告",
        "洞察", "什么", "哪些", "如何", "为什么",
    }
    text = question.lower()
    english = {t for t in re.findall(r"[a-z][a-z0-9_-]{3,}", text) if t not in COMMON}
    chinese = {t for t in re.findall(r"[一-鿿]{2,}", text) if t not in COMMON}
    return english | chinese


# ---------------------------------------------------------------------------
# Runner: execute all gates and return list of results
# ---------------------------------------------------------------------------

INSIGHT_GATE_FUNCTIONS = [
    ("generic_survey_toc", run_generic_survey_toc_gate),
    ("template_repetition", run_template_repetition_gate),
    ("machine_label_leak", run_machine_label_leak_gate),
    ("solar_actionability", run_solar_actionability_gate),
    ("cais_coverage", run_cais_coverage_gate),
    ("figure_required", run_figure_required_gate),
    ("citation_visibility", run_citation_visibility_gate),
    ("prediction_packet", run_prediction_packet_gate),
    ("user_question_fitness", run_user_question_fitness_gate),
]


def run_all_insight_gates(root: Path, ast: dict) -> list[dict[str, Any]]:
    """Execute all 9 insight gates and return their results."""
    results: list[dict[str, Any]] = []
    for _gate_name, gate_fn in INSIGHT_GATE_FUNCTIONS:
        results.append(gate_fn(root, ast))
    return results
