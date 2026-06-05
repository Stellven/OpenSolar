"""Compile typed claims and claim-evidence maps for insight mode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .conference_signal_extractor import fail_closed_result


ALLOWED_CLAIM_TYPES = {"factual", "interpretive", "predictive", "strategic"}


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records) + "\n", encoding="utf-8")
    return path


def compile_typed_claim_artifacts(output_dir: str | Path, claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Write `typed_claims.jsonl` and `claim_evidence_map.json`.

    Required input fields per claim: `claim_id`, `claim`, `claim_type`, and
    non-empty `evidence_ids`.
    """
    root = Path(output_dir).expanduser()
    if not claims:
        return fail_closed_result(
            "TypedClaimCompiler",
            root,
            missing_inputs=["claims"],
            gap_kinds=["missing_visible_citation"],
            artifact_paths={"typed_claims": "typed_claims.jsonl", "claim_evidence_map": "claim_evidence_map.json"},
        )

    normalized: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        claim_id = str(claim.get("claim_id") or claim.get("id") or "").strip()
        text = str(claim.get("claim") or claim.get("text") or "").strip()
        claim_type = str(claim.get("claim_type") or "").strip().lower()
        evidence_ids = claim.get("evidence_ids") if isinstance(claim.get("evidence_ids"), list) else []
        if not claim_id:
            issues.append({"record_index": index, "code": "missing_claim_id", "field_path": "claim_id"})
        if not text:
            issues.append({"record_index": index, "code": "missing_claim", "field_path": "claim"})
        if claim_type not in ALLOWED_CLAIM_TYPES:
            issues.append({"record_index": index, "code": "invalid_claim_type", "field_path": "claim_type"})
        if not evidence_ids:
            issues.append({"record_index": index, "code": "missing_evidence_ids", "field_path": "evidence_ids"})
        if issues and issues[-1].get("record_index") == index:
            continue
        normalized.append(
            {
                "claim_id": claim_id,
                "claim": text,
                "claim_type": claim_type,
                "evidence_ids": [str(item) for item in evidence_ids],
                "signal_refs": [str(item) for item in claim.get("signal_refs", []) if item],
                "section_refs": [str(item) for item in claim.get("section_refs", []) if item],
            }
        )

    if issues:
        return {
            "ok": False,
            "builder": "TypedClaimCompiler",
            "output_dir": str(root),
            "missing_inputs": [],
            "gap_kinds": ["missing_visible_citation"],
            "artifact_paths": {"typed_claims": "typed_claims.jsonl", "claim_evidence_map": "claim_evidence_map.json"},
            "reason": "typed_claim_validation_failed",
            "issues": issues,
        }

    typed_path = _write_jsonl(root / "typed_claims.jsonl", normalized)
    evidence_map = {
        "claim_count": len(normalized),
        "claims": [
            {
                "claim_id": item["claim_id"],
                "claim_type": item["claim_type"],
                "evidence_ids": item["evidence_ids"],
                "signal_refs": item["signal_refs"],
                "section_refs": item["section_refs"],
            }
            for item in normalized
        ],
    }
    map_path = _write_json(root / "claim_evidence_map.json", evidence_map)
    return {
        "ok": True,
        "builder": "TypedClaimCompiler",
        "artifact_paths": {"typed_claims": str(typed_path), "claim_evidence_map": str(map_path)},
        "claim_count": len(normalized),
        "gap_kinds": [],
    }
