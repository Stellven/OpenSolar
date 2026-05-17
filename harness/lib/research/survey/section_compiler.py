"""Compile survey sections from specs and evidence packs."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schemas import ChapterEditorialReview, SectionReview, to_dict
from .writing_loop import run_section_revision_loop


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def compile_section(output_dir: str | Path, section_id: str, finalize: bool = True) -> dict:
    root = Path(output_dir).expanduser()
    section_dir = root / "sections" / section_id
    spec = _read_json(section_dir / "section.spec.json")
    pack = _read_json(section_dir / "evidence_pack.json")
    section_dir.mkdir(parents=True, exist_ok=True)
    if not spec:
        return {"ok": False, "section_id": section_id, "reason": "section_spec_missing"}
    if not pack:
        return {"ok": False, "section_id": section_id, "reason": "evidence_pack_missing"}
    if pack.get("status") != "ready":
        review = SectionReview(
            section_id=section_id,
            verdict="BLOCKED",
            unsupported_claim_rate=1.0,
            citation_span_accuracy=0.0,
            source_diversity_score=0.0,
            repetition_score=0.0,
            issues=list(pack.get("blockers") or ["evidence_pack_blocked"]),
        )
        (section_dir / "review.json").write_text(json.dumps(to_dict(review), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"ok": False, "section_id": section_id, "reason": "evidence_pack_blocked", "review": to_dict(review)}
    return run_section_revision_loop(output_dir, section_id, finalize=finalize)


def _extract_tags(text: str, tag: str) -> list[str]:
    return [item.strip() for item in re.findall(rf"\[{re.escape(tag)}:([^\]]+)\]", text or "") if item.strip()]


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


def _source_type_counts(root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in _read_jsonl(root / "sources.jsonl"):
        source_type = str(row.get("source_type") or "unknown")
        counts[source_type] = counts.get(source_type, 0) + 1
    return counts


def _section_final(root: Path, section_id: str) -> str:
    path = root / "sections" / section_id / "final.md"
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _build_contribution_matrix(root: Path, ast: dict) -> dict:
    rows = []
    for section in ast.get("sections", []):
        section_id = str(section.get("section_id") or "")
        text = _section_final(root, section_id)
        claims = sorted(set(_extract_tags(text, "claim")))
        evidence = sorted(set(_extract_tags(text, "evidence")))
        headings = [line.strip("# ").strip() for line in text.splitlines() if line.startswith("## ")]
        rows.append({
            "section_id": section_id,
            "chapter_id": str(section.get("chapter_id") or ""),
            "title": str(section.get("title") or section_id),
            "status": "finalized" if text else "pending",
            "claim_ids": claims,
            "evidence_ids": evidence,
            "claim_count": len(claims),
            "evidence_count": len(evidence),
            "has_architecture_synthesis": "Architecture Synthesis" in text,
            "has_comparative_positioning": "Comparative Positioning" in text,
            "has_evaluation_boundary": "Evaluation And Risk Boundary" in text,
            "has_limitations_failure_modes": "Limitations And Failure Modes" in text,
            "has_contradiction_slots": "Contradiction Slots" in text,
            "headings": headings[:20],
        })
    finalized = [row for row in rows if row["status"] == "finalized"]
    payload = {
        "ok": True,
        "section_count": len(rows),
        "finalized_sections": len(finalized),
        "pending_sections": len(rows) - len(finalized),
        "source_type_counts": _source_type_counts(root),
        "total_claim_tags": sum(row["claim_count"] for row in rows),
        "total_evidence_tags": sum(row["evidence_count"] for row in rows),
        "rows": rows,
    }
    (root / "survey_contribution_matrix.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _chapter_sections(ast: dict, chapter_id: str) -> list[dict]:
    return [
        section for section in ast.get("sections", [])
        if str(section.get("chapter_id") or "") == chapter_id
    ]


def _build_chapter_synthesis(root: Path, chapter: dict, sections: list[dict], matrix_rows: list[dict]) -> tuple[str, list[str]]:
    chapter_id = str(chapter.get("chapter_id") or "")
    title = str(chapter.get("title") or chapter_id)
    objective = str(chapter.get("objective") or "N/A")
    finalized_rows = [row for row in matrix_rows if row.get("chapter_id") == chapter_id and row.get("status") == "finalized"]
    missing = [str(section.get("section_id") or "") for section in sections if not _section_final(root, str(section.get("section_id") or ""))]
    claim_total = sum(int(row.get("claim_count") or 0) for row in finalized_rows)
    evidence_total = sum(int(row.get("evidence_count") or 0) for row in finalized_rows)
    coverage_bits = []
    for key, label in [
        ("has_architecture_synthesis", "architecture"),
        ("has_comparative_positioning", "comparison"),
        ("has_evaluation_boundary", "evaluation"),
        ("has_limitations_failure_modes", "limitations"),
        ("has_contradiction_slots", "contradiction"),
    ]:
        covered = sum(1 for row in finalized_rows if row.get(key))
        coverage_bits.append(f"{label}:{covered}/{max(len(finalized_rows), 1)}")
    primary_gap = "missing finalized section evidence" if missing else "cross-section claim alignment"
    section_titles = [str(row.get("title") or row.get("section_id") or "") for row in finalized_rows[:3]]
    section_focus = "; ".join(section_titles) if section_titles else "N/A"
    synthesis = [
        f"# {title}",
        "",
        "## Chapter Synthesis",
        "",
        f"{chapter_id} compiles {len(finalized_rows)}/{len(sections)} finalized sections for '{title}'. It carries {claim_total} claim tags and {evidence_total} evidence tags into the final report while preserving the chapter objective: {objective}.",
        "",
        "## Contribution Coverage",
        "",
        "- " + "\n- ".join(coverage_bits) if coverage_bits else "- N/A",
        "",
        "## Chapter-Level Open Problems",
        "",
        f"{chapter_id} preserves unresolved evidence gaps around {primary_gap}, contradiction slots from {len(finalized_rows)} finalized sections, and consistency risks across representative sections: {section_focus}. Chief-editor review for '{title}' should verify that this chapter objective remains bounded: {objective}.",
        "",
    ]
    return "\n".join(synthesis), missing


def _build_final_summary(root: Path, ast: dict, contribution: dict, chapter_reviews: list[dict]) -> dict:
    finalized = int(contribution.get("finalized_sections") or 0)
    total = int(contribution.get("section_count") or 0)
    source_counts = contribution.get("source_type_counts") if isinstance(contribution.get("source_type_counts"), dict) else {}
    source_summary = ", ".join(f"{key}={value}" for key, value in sorted(source_counts.items())) or "N/A"
    pending = int(contribution.get("pending_sections") or 0)
    review_issues = [issue for review in chapter_reviews for issue in review.get("issues", [])]
    payload = {
        "ok": True,
        "title": ast.get("title", "Professor-Grade Survey"),
        "executive_summary": [
            f"This survey compiles {finalized}/{total} finalized sections into a structured technical report.",
            f"The evidence base covers source types: {source_summary}.",
            "The report separates architecture synthesis, comparison, evaluation boundaries, limitations, contradictions, and open problems.",
        ],
        "technical_summary": [
            f"Claim tags: {contribution.get('total_claim_tags', 0)}.",
            f"Evidence tags: {contribution.get('total_evidence_tags', 0)}.",
            f"Pending sections: {pending}.",
            f"Chapter review issue count: {len(review_issues)}.",
        ],
        "roadmap": [
            "Use contribution gaps to drive section rewrites.",
            "Use chapter synthesis outputs for chief-editor coherence review.",
            "Use source/evidence ledgers to prevent unsupported expansion in final prose.",
        ],
    }
    (root / "survey_final_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def compile_survey(output_dir: str | Path) -> dict:
    root = Path(output_dir).expanduser()
    ast = _read_json(root / "survey_report_ast.json")
    contribution = _build_contribution_matrix(root, ast)
    matrix_rows = contribution.get("rows", []) if isinstance(contribution.get("rows"), list) else []
    chapter_reviews: list[dict] = []
    chapter_blocks: list[str] = []
    finalized = 0
    for chapter in ast.get("chapters", []):
        chapter_dir = root / "chapters" / str(chapter.get("chapter_id"))
        chapter_dir.mkdir(parents=True, exist_ok=True)
        sections = _chapter_sections(ast, str(chapter.get("chapter_id") or ""))
        chapter_synthesis, missing = _build_chapter_synthesis(root, chapter, sections, matrix_rows)
        chapter_lines = [chapter_synthesis, ""]
        block_lines = [f"## {chapter.get('title')}", "", chapter_synthesis, ""]
        for section in ast.get("sections", []):
            if section.get("chapter_id") != chapter.get("chapter_id"):
                continue
            final = root / "sections" / str(section.get("section_id")) / "final.md"
            if final.exists():
                text = final.read_text(encoding="utf-8")
                block_lines.extend([text, ""])
                chapter_lines.extend([text, ""])
                finalized += 1
            else:
                block_lines.extend([f"### {section.get('title')}", "", "Status: pending final section.", ""])
        chapter_section_ids = [
            str(section.get("section_id"))
            for section in ast.get("sections", [])
            if section.get("chapter_id") == chapter.get("chapter_id")
        ]
        issues = []
        if missing:
            issues.append(f"missing_sections:{len(missing)}")
        review = ChapterEditorialReview(
            chapter_id=str(chapter.get("chapter_id")),
            verdict="PASS" if not missing else "REVISE",
            finalized_sections=len(chapter_section_ids) - len(missing),
            missing_sections=missing,
            issues=issues,
        )
        chapter_reviews.append(to_dict(review))
        (chapter_dir / "synthesis.md").write_text("\n".join(chapter_lines), encoding="utf-8")
        (chapter_dir / "editorial_review.json").write_text(json.dumps(to_dict(review), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (chapter_dir / "review.json").write_text(json.dumps(to_dict(review), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        chapter_blocks.append("\n".join(block_lines))
    final_summary = _build_final_summary(root, ast, contribution, chapter_reviews)
    lines = [
        f"# {ast.get('title', 'Professor-Grade Survey')}",
        "",
        "## Executive Summary",
        "",
        *[f"- {item}" for item in final_summary["executive_summary"]],
        "",
        "## Technical Summary",
        "",
        *[f"- {item}" for item in final_summary["technical_summary"]],
        "",
        "## Contribution Matrix",
        "",
        "| Section | Claims | Evidence | Architecture | Comparison | Evaluation | Limitations | Contradictions |",
        "| --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in matrix_rows:
        lines.append(
            f"| {row.get('section_id')} | {row.get('claim_count')} | {row.get('evidence_count')} | "
            f"{'yes' if row.get('has_architecture_synthesis') else 'no'} | "
            f"{'yes' if row.get('has_comparative_positioning') else 'no'} | "
            f"{'yes' if row.get('has_evaluation_boundary') else 'no'} | "
            f"{'yes' if row.get('has_limitations_failure_modes') else 'no'} | "
            f"{'yes' if row.get('has_contradiction_slots') else 'no'} |"
        )
    lines.extend(["", "## Roadmap", ""])
    lines.extend(f"- {item}" for item in final_summary["roadmap"])
    lines.extend(["", *chapter_blocks])
    final_path = root / "final.md"
    final_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "ok": True,
        "final_md": str(final_path),
        "finalized_sections": finalized,
        "total_sections": len(ast.get("sections", [])),
        "contribution_matrix": str(root / "survey_contribution_matrix.json"),
        "final_summary": str(root / "survey_final_summary.json"),
    }
