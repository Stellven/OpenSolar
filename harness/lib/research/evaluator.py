"""Deterministic quality gate for DeepResearch artifacts.

This is intentionally model-free. The model evaluator can still write the
human-readable judgement, but it must not PASS a DeepResearch node unless this
gate can read the research_eval/report_ast/final artifacts and they satisfy the
minimum evidence/citation constraints.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_MAX_UNSUPPORTED_RATE = 0.05
DEFAULT_MIN_CITATION_ACCURACY = 0.95


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _resolve_path(raw: Any, base_dir: Path) -> Path:
    raw_text = str(raw or "").strip()
    if not raw_text:
        return base_dir / "__missing_research_artifact__"
    path = Path(raw_text).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path


def _section_count(report_ast: dict[str, Any]) -> int:
    chapters = report_ast.get("chapters") or []
    if not isinstance(chapters, list):
        return 0
    return sum(len(ch.get("sections") or []) for ch in chapters if isinstance(ch, dict))


def _first_number(data: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = data.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def evaluate_artifacts(
    eval_json: str | Path,
    report_ast: str | Path | None = None,
    final_md: str | Path | None = None,
    bibliography: str | Path | None = None,
    max_unsupported_rate: float = DEFAULT_MAX_UNSUPPORTED_RATE,
    min_citation_accuracy: float = DEFAULT_MIN_CITATION_ACCURACY,
) -> dict[str, Any]:
    """Evaluate one DeepResearch artifact set and return a PASS/FAIL payload."""
    eval_path = Path(eval_json).expanduser()
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}

    if not eval_path.exists():
        return {
            "ok": False,
            "verdict": "FAIL",
            "errors": [f"research_eval_json_missing:{eval_path}"],
            "warnings": [],
            "metrics": metrics,
            "artifacts": {"eval_json": str(eval_path)},
        }

    eval_data = _read_json(eval_path)
    base_dir = eval_path.parent
    output_dir = _resolve_path(eval_data.get("output_dir"), base_dir) if eval_data.get("output_dir") else base_dir
    final_path = (
        Path(final_md).expanduser()
        if final_md
        else (_resolve_path(eval_data.get("final_md"), output_dir) if eval_data.get("final_md") else output_dir / "final.md")
    )
    report_ast_path = Path(report_ast).expanduser() if report_ast else output_dir / "report_ast.json"
    bibliography_path = Path(bibliography).expanduser() if bibliography else output_dir / "final.bibliography.json"

    source_count = int(eval_data.get("source_count") or 0)
    evidence_count = int(eval_data.get("evidence_count") or 0)
    claim_count = int(eval_data.get("claim_count") or 0)
    section_count = int(eval_data.get("section_count") or 0)
    unsupported_rate = _first_number(eval_data, "unsupported_rate", "unsupported_claim_rate")
    citation_accuracy = _first_number(eval_data, "citation_accuracy", "citation_span_accuracy")
    eval_status = str(eval_data.get("status") or "unknown").lower()

    metrics.update({
        "source_count": source_count,
        "evidence_count": evidence_count,
        "claim_count": claim_count,
        "section_count": section_count,
        "unsupported_rate": unsupported_rate,
        "citation_accuracy": citation_accuracy,
        "eval_status": eval_status,
    })

    if eval_status not in {"passed", "pass", "ok"}:
        errors.append(f"research_eval_status_not_passed:{eval_status}")
    if source_count <= 0:
        errors.append("source_count_zero")
    if evidence_count <= 0:
        errors.append("evidence_count_zero")
    if claim_count <= 0:
        errors.append("claim_count_zero")
    if section_count <= 0:
        errors.append("section_count_zero")
    if unsupported_rate > max_unsupported_rate:
        errors.append(f"unsupported_rate_too_high:{unsupported_rate:.4f}>{max_unsupported_rate:.4f}")
    if citation_accuracy < min_citation_accuracy:
        errors.append(f"citation_accuracy_too_low:{citation_accuracy:.4f}<{min_citation_accuracy:.4f}")

    report_ast_data = _read_json(report_ast_path)
    ast_sections = _section_count(report_ast_data)
    metrics["report_ast_sections"] = ast_sections
    if not report_ast_path.exists():
        errors.append(f"report_ast_missing:{report_ast_path}")
    elif ast_sections <= 0:
        errors.append("report_ast_has_no_sections")

    if not final_path.exists():
        errors.append(f"final_md_missing:{final_path}")
        final_text = ""
    else:
        final_text = final_path.read_text(encoding="utf-8", errors="replace")
        if not final_text.strip():
            errors.append("final_md_empty")
        if not re.search(r"\[cite:ev_[A-Za-z0-9_-]+", final_text):
            errors.append("final_md_missing_evidence_citations")

    if not bibliography_path.exists():
        warnings.append(f"bibliography_missing:{bibliography_path}")

    artifacts = {
        "eval_json": str(eval_path),
        "output_dir": str(output_dir),
        "report_ast": str(report_ast_path),
        "final_md": str(final_path),
        "bibliography": str(bibliography_path),
    }
    exists = {name: bool(path and Path(path).exists()) for name, path in artifacts.items()}
    verdict = "FAIL" if errors else "PASS"
    return {
        "ok": verdict == "PASS",
        "verdict": verdict,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
        "artifacts": artifacts,
        "artifact_exists": exists,
        "policy": {
            "max_unsupported_rate": max_unsupported_rate,
            "min_citation_accuracy": min_citation_accuracy,
        },
    }
