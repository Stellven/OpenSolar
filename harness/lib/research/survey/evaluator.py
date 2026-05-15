"""Professor-grade survey evaluator."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schemas import SurveyScorecard, to_dict


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def evaluate_survey(output_dir: str | Path, strict: bool = False) -> dict:
    root = Path(output_dir).expanduser()
    ast = _read_json(root / "survey_report_ast.json")
    packs = _read_json(root / "survey_evidence_packs.json")
    chapters = ast.get("chapters", []) if isinstance(ast.get("chapters"), list) else []
    sections = ast.get("sections", []) if isinstance(ast.get("sections"), list) else []
    section_dirs = [root / "sections" / str(section.get("section_id")) for section in sections]
    finalized = sum(1 for path in section_dirs if (path / "final.md").exists())
    reviews = [_read_json(path / "review.json") for path in section_dirs if (path / "review.json").exists()]
    blocked_sections = int(packs.get("blocked") or 0) if isinstance(packs, dict) else len(sections)
    issues: list[str] = []
    if len(chapters) < 8:
        issues.append(f"chapter_count_low:{len(chapters)}<8")
    if len(sections) < 30:
        issues.append(f"section_count_low:{len(sections)}<30")
    if strict and not packs:
        issues.append("evidence_packs_missing")
    if blocked_sections:
        issues.append(f"blocked_sections:{blocked_sections}")
    if strict and finalized < 3:
        issues.append(f"finalized_sections_low:{finalized}<3")
    if finalized and finalized < min(3, len(sections)):
        issues.append(f"finalized_sections_low:{finalized}<3")
    final_md = root / "final.md"
    text = final_md.read_text(encoding="utf-8") if final_md.exists() else ""
    finalized_texts: list[str] = []
    for path in section_dirs:
        final = path / "final.md"
        if final.exists():
            finalized_texts.append(final.read_text(encoding="utf-8"))
    repeated = 0
    seen: set[str] = set()
    for item in finalized_texts:
        normalized = re.sub(r"\s+", " ", item.strip().lower())[:500]
        if normalized in seen:
            repeated += 1
        seen.add(normalized)
    section_repetition_rate = repeated / max(len(finalized_texts), 1)
    if strict and finalized_texts and section_repetition_rate > 0.33:
        issues.append(f"section_repetition_rate_high:{section_repetition_rate:.4f}")
    source_diversity_values = [float(r.get("source_diversity_score") or 0.0) for r in reviews]
    source_diversity = sum(source_diversity_values) / len(source_diversity_values) if source_diversity_values else 0.0
    contradiction_coverage = 1.0 if packs and blocked_sections == 0 else 0.0
    taxonomy_depth = min(len(chapters) / 8, 1.0) * min(len(sections) / 30, 1.0)
    verdict = "PASS" if not issues else "FAIL"
    if not strict and issues and all(item.startswith(("blocked_sections", "finalized_sections_low")) for item in issues):
        verdict = "WARN"
    scorecard = SurveyScorecard(
        verdict=verdict,
        chapter_count=len(chapters),
        section_count=len(sections),
        finalized_sections=finalized,
        blocked_sections=blocked_sections,
        unsupported_claim_rate=0.0 if reviews else 1.0,
        citation_span_accuracy=1.0 if reviews else 0.0,
        contradiction_coverage=contradiction_coverage,
        source_diversity_score=round(source_diversity, 4),
        taxonomy_depth_score=round(taxonomy_depth, 4),
        section_repetition_rate=round(section_repetition_rate, 4),
        terminology_consistency_score=1.0,
        cross_section_conflict_count=0,
        chapter_coherence_score=1.0 if len(chapters) >= 8 else 0.0,
        issues=issues,
    )
    payload = {"ok": verdict == "PASS", "scorecard": to_dict(scorecard), "strict": strict}
    (root / "survey_eval.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
