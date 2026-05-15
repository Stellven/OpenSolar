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


def assess_survey_quality(output_dir: str | Path, ast: dict | None = None, packs: dict | None = None) -> dict[str, Any]:
    root = Path(output_dir).expanduser()
    ast = ast or _read_json(root / "survey_report_ast.json")
    packs = packs or _read_json(root / "survey_evidence_packs.json")
    chapters = ast.get("chapters", []) if isinstance(ast.get("chapters"), list) else []
    sections = ast.get("sections", []) if isinstance(ast.get("sections"), list) else []
    sources = _read_jsonl(root / "sources.jsonl")
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

    payload = {
        "ok": taxonomy["ok"] and contradiction_matrix["ok"],
        "taxonomy": taxonomy,
        "contradiction_matrix": contradiction_matrix,
    }
    (root / "survey_taxonomy.json").write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "survey_contradiction_matrix.json").write_text(json.dumps(contradiction_matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
