"""Build conference signal artifacts for DeepDive insight mode.

This module does not scrape or hard-code CAIS facts. It takes caller-provided,
evidence-backed signal records, validates them with the N3 schemas, writes the
canonical artifacts, and fails closed when required inputs are missing.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any

from .schemas import validate_cais_signal_pack, write_cais_signal_packs


INSIGHT_AMMUNITION_GAP_KINDS = (
    "missing_cais_paper_signals",
    "missing_solar_absorption",
    "missing_prediction_drivers",
    "missing_counter_scenarios",
    "missing_operator_design",
    "missing_figure_spec",
    "missing_visible_citation",
)


def _record_to_dict(record: Any) -> dict[str, Any]:
    if is_dataclass(record):
        return asdict(record)
    if isinstance(record, dict):
        return dict(record)
    raise TypeError(f"expected dict/dataclass record, got {type(record).__name__}")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def fail_closed_result(
    builder: str,
    output_dir: str | Path,
    *,
    missing_inputs: list[str],
    gap_kinds: list[str],
    artifact_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a shared fail-closed sidecar shape for N4 builders."""
    known = set(INSIGHT_AMMUNITION_GAP_KINDS)
    normalized_gaps = [gap for gap in gap_kinds if gap in known]
    return {
        "ok": False,
        "builder": builder,
        "output_dir": str(Path(output_dir).expanduser()),
        "missing_inputs": missing_inputs,
        "gap_kinds": normalized_gaps,
        "artifact_paths": artifact_paths or {},
        "reason": "required_inputs_missing",
    }


def build_conference_signal_artifacts(
    output_dir: str | Path,
    signal_packs: list[dict[str, Any] | Any],
    *,
    profile_id: str = "cais-agent-insight",
) -> dict[str, Any]:
    """Write `conference_signal_map.json` and `cais_paper_signal_packs.jsonl`.

    The caller is responsible for collecting/extracting facts. This builder only
    validates and normalizes records into the artifact contract.
    """
    root = Path(output_dir).expanduser()
    if not signal_packs:
        return fail_closed_result(
            "ConferenceSignalExtractor",
            root,
            missing_inputs=["signal_packs"],
            gap_kinds=["missing_cais_paper_signals"],
            artifact_paths={
                "conference_signal_map": "conference_signal_map.json",
                "cais_paper_signal_packs": "cais_paper_signal_packs.jsonl",
            },
        )

    records = [_record_to_dict(item) for item in signal_packs]
    issues: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        result = validate_cais_signal_pack(record, artifact_path="cais_paper_signal_packs.jsonl")
        if not result.ok:
            issues.extend(issue.to_dict() if hasattr(issue, "to_dict") else asdict(issue) for issue in result.issues)
            issues[-1]["record_index"] = index
    if issues:
        return {
            "ok": False,
            "builder": "ConferenceSignalExtractor",
            "output_dir": str(root),
            "missing_inputs": [],
            "gap_kinds": ["missing_cais_paper_signals"],
            "artifact_paths": {
                "conference_signal_map": "conference_signal_map.json",
                "cais_paper_signal_packs": "cais_paper_signal_packs.jsonl",
            },
            "reason": "signal_pack_validation_failed",
            "issues": issues,
        }

    signal_map = {
        "profile_id": profile_id,
        "signal_count": len(records),
        "signals": [
            {
                "signal_id": record.get("signal_id"),
                "title": (record.get("source") or {}).get("title"),
                "source_type": (record.get("source") or {}).get("type"),
                "technical_challenge": record.get("technical_challenge"),
                "operator_count": len((record.get("solar_absorption") or {}).get("new_operators") or []),
                "gate_count": len((record.get("solar_absorption") or {}).get("new_gates") or []),
            }
            for record in records
        ],
        "gap_kinds": [],
        "artifact_paths": {
            "conference_signal_map": "conference_signal_map.json",
            "cais_paper_signal_packs": "cais_paper_signal_packs.jsonl",
        },
    }
    signal_map_path = _write_json(root / "conference_signal_map.json", signal_map)
    packs_path = write_cais_signal_packs(records, root / "cais_paper_signal_packs.jsonl")
    return {
        "ok": True,
        "builder": "ConferenceSignalExtractor",
        "artifact_paths": {
            "conference_signal_map": str(signal_map_path),
            "cais_paper_signal_packs": str(packs_path),
        },
        "signal_count": len(records),
        "gap_kinds": [],
    }


def detect_insight_ammunition_gaps(output_dir: str | Path) -> dict[str, Any]:
    """Detect report-level insight ammunition gaps from expected artifacts."""
    root = Path(output_dir).expanduser()
    checks = {
        "missing_cais_paper_signals": root / "cais_paper_signal_packs.jsonl",
        "missing_solar_absorption": root / "paper_to_solar_absorption_map.json",
        "missing_prediction_drivers": root / "prediction_packets.jsonl",
        "missing_counter_scenarios": root / "prediction_packets.jsonl",
        "missing_operator_design": root / "solar_operator_roadmap.json",
        "missing_figure_spec": root / "figures.json",
        "missing_visible_citation": root / "appendix_evidence_matrix.html",
    }
    gaps = [kind for kind, path in checks.items() if not path.exists()]
    return {
        "ok": not gaps,
        "output_dir": str(root),
        "gap_kinds": gaps,
        "known_gap_kinds": list(INSIGHT_AMMUNITION_GAP_KINDS),
    }
