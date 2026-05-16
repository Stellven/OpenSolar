"""Survey taxonomy and contradiction quality assessment."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _required_types_from_source_matrix(root: Path) -> set[str]:
    data = _read_json(root / "survey_source_matrix.json")
    rows = data if isinstance(data, list) else data.get("source_matrix", [])
    required: set[str] = set()
    if not isinstance(rows, list):
        return required
    for row in rows:
        if not isinstance(row, dict):
            continue
        for item in row.get("required_source_types", []):
            if item:
                required.add(str(item))
    return required


def _chapter_axis(chapter_title: str) -> str:
    text = str(chapter_title or "")
    rules = [
        ("definition", r"定义|边界|术语"),
        ("history", r"历史|演进|脉络"),
        ("evaluation", r"评估|基准|评价"),
        ("contradiction", r"争议|反证|失败"),
        ("architecture", r"架构|范式|系统"),
        ("method_taxonomy", r"分类|方法|代表系统"),
        ("engineering", r"工程|部署|实现"),
        ("risk", r"风险|安全|可解释"),
        ("ecosystem", r"产业|生态|开源"),
        ("roadmap", r"未来|路线图|开放问题"),
    ]
    for axis, pattern in rules:
        if re.search(pattern, text):
            return axis
    return "other"


def _extract_tags(text: str, tag: str) -> set[str]:
    return {item.strip() for item in re.findall(rf"\[{re.escape(tag)}:([^\]]+)\]", text or "") if item.strip()}


def _evidence_text(row: dict[str, Any]) -> str:
    return str(row.get("content") or row.get("span_text") or row.get("clean_markdown") or row.get("text") or row.get("title") or "")


def _tokens(text: str) -> set[str]:
    ascii_words = {part.lower() for part in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text or "")}
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", text or "")
    cjk_bigrams: set[str] = set()
    for chunk in cjk:
        cjk_bigrams.update(chunk[idx:idx + 2] for idx in range(max(len(chunk) - 1, 0)))
    return ascii_words | cjk_bigrams


def _grounding_checks(text: str, evidence_tags: set[str], evidence_by_id: dict[str, str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for line_no, line in enumerate((text or "").splitlines(), start=1):
        tags = _extract_tags(line, "evidence")
        if not tags:
            continue
        context_tokens = _tokens(line)
        for evidence_id in sorted(tags):
            evidence_tokens = _tokens(evidence_by_id.get(evidence_id, ""))
            if not evidence_tokens:
                checks.append({
                    "evidence_id": evidence_id,
                    "line": line_no,
                    "ok": False,
                    "reason": "evidence_span_text_missing",
                    "overlap": [],
                })
                continue
            overlap = sorted(context_tokens & evidence_tokens)
            checks.append({
                "evidence_id": evidence_id,
                "line": line_no,
                "ok": bool(overlap),
                "reason": "" if overlap else "citation_context_not_grounded",
                "overlap": overlap[:12],
            })
    return checks


def _grounding_failures_for_evidence(evidence_tags: set[str], checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for evidence_id in sorted(evidence_tags):
        related = [item for item in checks if item.get("evidence_id") == evidence_id]
        if any(item.get("ok") for item in related):
            continue
        failures.append({
            "evidence_id": evidence_id,
            "ok": False,
            "reason": related[0].get("reason") if related else "citation_context_missing",
            "lines": [item.get("line") for item in related if item.get("line")],
        })
    return failures


def _section_factual_audit(
    root: Path,
    sections: list[dict[str, Any]],
    pack_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_by_id = {
        str(row.get("id") or row.get("evidence_id")): _evidence_text(row)
        for row in evidence_rows
        if str(row.get("id") or row.get("evidence_id") or "")
    }
    audited = 0
    passed = 0
    grounded = 0
    missing_final: list[str] = []
    section_results: list[dict[str, Any]] = []
    for section in sections:
        section_id = str(section.get("section_id") or "")
        if not section_id:
            continue
        final_path = root / "sections" / section_id / "final.md"
        pack = next((row for row in pack_rows if str(row.get("section_id") or "") == section_id), {})
        allowed_claims = {str(item) for item in pack.get("claim_ids", []) if str(item)}
        allowed_evidence = {str(item) for item in pack.get("evidence_ids", []) if str(item)}
        if not final_path.exists():
            missing_final.append(section_id)
            continue
        audited += 1
        text = final_path.read_text(encoding="utf-8", errors="ignore")
        claim_tags = _extract_tags(text, "claim")
        evidence_tags = _extract_tags(text, "evidence")
        unknown_claims = sorted(claim_tags - allowed_claims)
        unknown_evidence = sorted(evidence_tags - allowed_evidence)
        missing_claim_tags = not bool(claim_tags)
        missing_evidence_tags = not bool(evidence_tags)
        grounding_checks = _grounding_checks(text, evidence_tags, evidence_by_id)
        grounding_failures = _grounding_failures_for_evidence(evidence_tags, grounding_checks)
        grounding_ok = bool(grounding_checks) and not grounding_failures
        ok = not unknown_claims and not unknown_evidence and not missing_claim_tags and not missing_evidence_tags and grounding_ok
        if ok:
            passed += 1
        if grounding_ok:
            grounded += 1
        section_results.append({
            "section_id": section_id,
            "ok": ok,
            "claim_tags": sorted(claim_tags),
            "evidence_tags": sorted(evidence_tags),
            "unknown_claim_ids": unknown_claims,
            "unknown_evidence_ids": unknown_evidence,
            "missing_claim_tags": missing_claim_tags,
            "missing_evidence_tags": missing_evidence_tags,
            "grounding_ok": grounding_ok,
            "grounding_failures": grounding_failures[:20],
        })
    accuracy = round(passed / max(audited, 1), 4)
    grounding_accuracy = round(grounded / max(audited, 1), 4)
    return {
        "ok": accuracy >= 0.95,
        "section_factual_accuracy": accuracy,
        "section_grounding_accuracy": grounding_accuracy,
        "audited_sections": audited,
        "passed_sections": passed,
        "grounded_sections": grounded,
        "missing_final_sections": missing_final[:50],
        "failed_sections": [item for item in section_results if not item.get("ok")][:50],
    }


def _build_section_scorecard(
    root: Path,
    sections: list[dict[str, Any]],
    pack_rows: list[dict[str, Any]],
    section_factual_audit: dict[str, Any],
) -> dict[str, Any]:
    failed_by_id = {
        str(item.get("section_id") or ""): item
        for item in section_factual_audit.get("failed_sections", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for section in sections:
        section_id = str(section.get("section_id") or "")
        if not section_id:
            continue
        final_path = root / "sections" / section_id / "final.md"
        review = _read_json(root / "sections" / section_id / "review.json")
        pack = next((row for row in pack_rows if str(row.get("section_id") or "") == section_id), {})
        issues: list[dict[str, Any]] = []
        pending = False
        if not final_path.exists():
            pending = True
        failed = failed_by_id.get(section_id, {})
        if failed.get("unknown_claim_ids"):
            issues.append({"severity": "P0", "code": "unknown_claim_ids", "detail": failed.get("unknown_claim_ids")})
        if failed.get("unknown_evidence_ids"):
            issues.append({"severity": "P0", "code": "unknown_evidence_ids", "detail": failed.get("unknown_evidence_ids")})
        if failed.get("missing_claim_tags"):
            issues.append({"severity": "P0", "code": "missing_claim_tags", "detail": True})
        if failed.get("missing_evidence_tags"):
            issues.append({"severity": "P0", "code": "missing_evidence_tags", "detail": True})
        if failed.get("grounding_failures"):
            issues.append({"severity": "P0", "code": "grounding_failures", "detail": failed.get("grounding_failures")})
        if pack.get("status") != "ready":
            issues.append({"severity": "P0", "code": "evidence_pack_not_ready", "detail": pack.get("blockers", [])})
        for issue in review.get("issues", []) if isinstance(review.get("issues"), list) else []:
            code = str(issue)
            severity = "P1" if re.search(r"contradiction|evaluation|source_diversity", code, re.I) else "P2"
            issues.append({"severity": severity, "code": code.split(":", 1)[0], "detail": code})
        if final_path.exists():
            text = final_path.read_text(encoding="utf-8", errors="ignore")
            headings = len(re.findall(r"^##\s+", text, flags=re.M))
            if headings < 6:
                issues.append({"severity": "P1", "code": "section_structure_shallow", "detail": f"{headings}<6"})
            paragraphs = [re.sub(r"\s+", " ", p.strip().lower()) for p in text.split("\n\n") if p.strip()]
            repetition = 1.0 - (len(set(paragraphs)) / max(len(paragraphs), 1))
            if repetition > 0.20:
                issues.append({"severity": "P2", "code": "section_repetition_high", "detail": round(repetition, 4)})
        severity_weight = {"P0": 100, "P1": 25, "P2": 5}
        risk_score = sum(severity_weight.get(str(item.get("severity")), 1) for item in issues)
        rows.append({
            "section_id": section_id,
            "status": "pending" if pending else "pass" if not issues else "needs_rewrite",
            "risk_score": risk_score,
            "p0_count": sum(1 for item in issues if item.get("severity") == "P0"),
            "p1_count": sum(1 for item in issues if item.get("severity") == "P1"),
            "p2_count": sum(1 for item in issues if item.get("severity") == "P2"),
            "issues": issues,
            "rewrite_recommended": (not pending) and risk_score >= 25,
        })
    rows.sort(key=lambda item: (-int(item.get("risk_score") or 0), str(item.get("section_id") or "")))
    return {
        "ok": not any(item.get("p0_count") for item in rows),
        "section_count": len(rows),
        "needs_rewrite_count": sum(1 for item in rows if item.get("rewrite_recommended")),
        "top_issues": rows[:20],
    }


def _build_final_quality(root: Path, ast: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
    final_path = root / "final.md"
    final_text = final_path.read_text(encoding="utf-8", errors="ignore") if final_path.exists() else ""
    target_chars = int(ast.get("target_chars") or sum(int(section.get("target_chars") or 0) for section in sections) or 0)
    finalized_lengths: list[int] = []
    missing_sections: list[str] = []
    for section in sections:
        section_id = str(section.get("section_id") or "")
        if not section_id:
            continue
        path = root / "sections" / section_id / "final.md"
        if not path.exists():
            missing_sections.append(section_id)
            continue
        finalized_lengths.append(len(path.read_text(encoding="utf-8", errors="ignore")))
    final_char_count = len(final_text)
    finalized_count = len(finalized_lengths)
    avg_section_chars = round(sum(finalized_lengths) / max(finalized_count, 1), 2)
    pending_placeholder_count = len(re.findall(r"Status:\s*pending final section\.", final_text))
    heading_count = len(re.findall(r"^#{2,4}\s+", final_text, flags=re.M))
    claim_tag_count = len(re.findall(r"\[claim:[^\]]+\]", final_text))
    evidence_tag_count = len(re.findall(r"\[evidence:[^\]]+\]", final_text))
    chars_k = max(final_char_count / 1000.0, 1.0)
    claim_tag_density = round(claim_tag_count / chars_k, 4)
    evidence_tag_density = round(evidence_tag_count / chars_k, 4)
    paragraphs = []
    for item in final_text.split("\n\n"):
        cleaned = re.sub(r"\[[a-z]+:[^\]]+\]", "", item.strip().lower())
        cleaned = re.sub(r"^#+\s+", "", cleaned, flags=re.M)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) >= 80:
            paragraphs.append(cleaned)
    repetition_rate = round(1.0 - (len(set(paragraphs)) / max(len(paragraphs), 1)), 4)
    per_section_target = target_chars / max(len(sections), 1) if target_chars else 0
    min_final_chars = int(target_chars * 0.60) if target_chars else 0
    min_avg_section_chars = int(max(min(per_section_target * 0.45, 1200), 500)) if per_section_target else 500
    min_heading_count = max(finalized_count * 5, 1) if finalized_count else 0
    issues: list[str] = []
    if target_chars and final_char_count < min_final_chars:
        issues.append(f"final_char_count_low:{final_char_count}<{min_final_chars}")
    if finalized_count and avg_section_chars < min_avg_section_chars:
        issues.append(f"avg_section_chars_low:{avg_section_chars:.2f}<{min_avg_section_chars}")
    if pending_placeholder_count:
        issues.append(f"pending_placeholder_count:{pending_placeholder_count}")
    if finalized_count and heading_count < min_heading_count:
        issues.append(f"final_heading_count_low:{heading_count}<{min_heading_count}")
    if finalized_count and claim_tag_density < 0.80:
        issues.append(f"claim_tag_density_low:{claim_tag_density:.4f}<0.8000")
    if finalized_count and evidence_tag_density < 0.80:
        issues.append(f"evidence_tag_density_low:{evidence_tag_density:.4f}<0.8000")
    if repetition_rate > 0.99:
        issues.append(f"final_repetition_rate_high:{repetition_rate:.4f}>0.9900")
    return {
        "ok": not issues,
        "final_md": str(final_path),
        "target_chars": target_chars,
        "final_char_count": final_char_count,
        "min_final_chars": min_final_chars,
        "finalized_sections": finalized_count,
        "total_sections": len(sections),
        "missing_sections": missing_sections[:50],
        "avg_section_chars": avg_section_chars,
        "min_avg_section_chars": min_avg_section_chars,
        "pending_placeholder_count": pending_placeholder_count,
        "heading_count": heading_count,
        "min_heading_count": min_heading_count,
        "claim_tag_count": claim_tag_count,
        "evidence_tag_count": evidence_tag_count,
        "claim_tag_density_per_1k_chars": claim_tag_density,
        "evidence_tag_density_per_1k_chars": evidence_tag_density,
        "repetition_rate": repetition_rate,
        "issues": issues,
    }


def assess_survey_quality(output_dir: str | Path, ast: dict | None = None, packs: dict | None = None) -> dict[str, Any]:
    root = Path(output_dir).expanduser()
    ast = ast or _read_json(root / "survey_report_ast.json")
    packs = packs or _read_json(root / "survey_evidence_packs.json")
    chapters = ast.get("chapters", []) if isinstance(ast.get("chapters"), list) else []
    sections = ast.get("sections", []) if isinstance(ast.get("sections"), list) else []
    sources = _read_jsonl(root / "sources.jsonl")
    evidence_rows = _read_jsonl(root / "evidence.jsonl")
    source_types = {str(row.get("source_type") or "") for row in sources if row.get("source_type")}
    required_source_types = _required_types_from_source_matrix(root)
    chapter_axes = sorted({_chapter_axis(str(row.get("title") or "")) for row in chapters if isinstance(row, dict)})
    method_axis_present = "method_taxonomy" in chapter_axes or "architecture" in chapter_axes
    evaluation_axis_present = "evaluation" in chapter_axes
    contradiction_axis_present = "contradiction" in chapter_axes
    taxonomy_depth_score = round(
        min(len(chapter_axes) / 8, 1.0)
        * min(max(len(required_source_types), len(source_types)) / 4, 1.0)
        * (1.0 if method_axis_present and evaluation_axis_present else 0.5),
        4,
    )
    taxonomy = {
        "ok": taxonomy_depth_score >= 0.75,
        "taxonomy_depth_score": taxonomy_depth_score,
        "chapter_axes": chapter_axes,
        "required_source_types": sorted(required_source_types),
        "observed_source_types": sorted(source_types),
        "method_axis_present": method_axis_present,
        "evaluation_axis_present": evaluation_axis_present,
        "contradiction_axis_present": contradiction_axis_present,
    }

    pack_rows = packs.get("packs", []) if isinstance(packs.get("packs"), list) else []
    required_contradictions = len(sections)
    covered = 0
    missing: list[str] = []
    for section in sections:
        section_id = str(section.get("section_id") or "")
        pack = next((row for row in pack_rows if str(row.get("section_id") or "") == section_id), {})
        slots = [slot for slot in pack.get("contradiction_slots", []) if str(slot).strip()]
        if slots:
            covered += 1
        elif section_id:
            missing.append(section_id)
    contradiction_coverage = round(covered / max(required_contradictions, 1), 4)
    contradiction_matrix = {
        "ok": contradiction_coverage >= 0.80,
        "contradiction_coverage": contradiction_coverage,
        "required_sections": required_contradictions,
        "covered_sections": covered,
        "missing_section_ids": missing[:50],
        "contradiction_axis_present": contradiction_axis_present,
    }
    section_factual_audit = _section_factual_audit(root, sections, pack_rows, evidence_rows)
    section_scorecard = _build_section_scorecard(root, sections, pack_rows, section_factual_audit)
    final_quality = _build_final_quality(root, ast, sections)

    payload = {
        "ok": taxonomy["ok"] and contradiction_matrix["ok"] and section_factual_audit["ok"] and section_scorecard["ok"] and final_quality["ok"],
        "taxonomy": taxonomy,
        "contradiction_matrix": contradiction_matrix,
        "section_factual_audit": section_factual_audit,
        "section_scorecard": section_scorecard,
        "final_quality": final_quality,
    }
    (root / "survey_taxonomy.json").write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "survey_contradiction_matrix.json").write_text(json.dumps(contradiction_matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "survey_section_factual_audit.json").write_text(json.dumps(section_factual_audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "survey_section_scorecard.json").write_text(json.dumps(section_scorecard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "survey_final_quality.json").write_text(json.dumps(final_quality, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
