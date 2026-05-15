"""Compile survey sections from specs and evidence packs."""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import SectionReview, to_dict
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


def compile_survey(output_dir: str | Path) -> dict:
    root = Path(output_dir).expanduser()
    ast = _read_json(root / "survey_report_ast.json")
    lines = [f"# {ast.get('title', 'Professor-Grade Survey')}", ""]
    finalized = 0
    for chapter in ast.get("chapters", []):
        lines.extend([f"## {chapter.get('title')}", ""])
        chapter_dir = root / "chapters" / str(chapter.get("chapter_id"))
        chapter_dir.mkdir(parents=True, exist_ok=True)
        chapter_lines = [f"# {chapter.get('title')}", ""]
        for section in ast.get("sections", []):
            if section.get("chapter_id") != chapter.get("chapter_id"):
                continue
            final = root / "sections" / str(section.get("section_id")) / "final.md"
            if final.exists():
                text = final.read_text(encoding="utf-8")
                lines.extend([text, ""])
                chapter_lines.extend([text, ""])
                finalized += 1
            else:
                lines.extend([f"### {section.get('title')}", "", "Status: pending final section.", ""])
        (chapter_dir / "synthesis.md").write_text("\n".join(chapter_lines), encoding="utf-8")
        (chapter_dir / "review.json").write_text(json.dumps({"verdict": "PASS" if chapter_lines else "PENDING"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    final_path = root / "final.md"
    final_path.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "final_md": str(final_path), "finalized_sections": finalized, "total_sections": len(ast.get("sections", []))}
