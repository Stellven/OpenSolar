"""Build Solar absorption artifacts from validated conference signals."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any

from .conference_signal_extractor import fail_closed_result
from .schemas import SolarAbsorptionMap, validate_insight_artifact_bundle, write_solar_absorption_map


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


def build_solar_absorption_artifacts(
    output_dir: str | Path,
    *,
    signal_packs: list[dict[str, Any] | Any],
    absorption_items: list[dict[str, Any] | Any],
) -> dict[str, Any]:
    """Write `paper_to_solar_absorption_map.json` and `solar_operator_roadmap.json`."""
    root = Path(output_dir).expanduser()
    missing = []
    if not signal_packs:
        missing.append("signal_packs")
    if not absorption_items:
        missing.append("absorption_items")
    if missing:
        return fail_closed_result(
            "PaperToSolarMapper",
            root,
            missing_inputs=missing,
            gap_kinds=["missing_solar_absorption", "missing_operator_design"],
            artifact_paths={
                "paper_to_solar_absorption_map": "paper_to_solar_absorption_map.json",
                "solar_operator_roadmap": "solar_operator_roadmap.json",
            },
        )

    absorption_map = SolarAbsorptionMap(
        absorption_items=[_record_to_dict(item) for item in absorption_items],
        artifact_path="paper_to_solar_absorption_map.json",
    )
    validation = validate_insight_artifact_bundle(
        signal_packs=signal_packs,
        absorption_map=absorption_map,
        prediction_packets=[],
        section_cards=[],
        figure_specs=[],
        artifact_paths={"paper_to_solar_absorption_map": "paper_to_solar_absorption_map.json"},
    )
    if not validation.ok:
        return {
            "ok": False,
            "builder": "PaperToSolarMapper",
            "output_dir": str(root),
            "missing_inputs": [],
            "gap_kinds": ["missing_solar_absorption"],
            "artifact_paths": {"paper_to_solar_absorption_map": "paper_to_solar_absorption_map.json"},
            "reason": "absorption_validation_failed",
            "issues": validation.to_dict()["issues"],
        }

    map_path = write_solar_absorption_map(absorption_map, root / "paper_to_solar_absorption_map.json")
    normalized_items = [_record_to_dict(item) for item in absorption_map.absorption_items]
    roadmap = {
        "roadmap_items": [
            {
                "priority": item.get("priority"),
                "cais_signal": item.get("cais_signal"),
                "operators": item.get("operators") or [],
                "schemas": item.get("schemas") or [],
                "gates": item.get("gates") or [],
                "solar_design": item.get("solar_design"),
            }
            for item in normalized_items
        ],
        "priority_counts": _priority_counts(normalized_items),
        "artifact_paths": {
            "paper_to_solar_absorption_map": "paper_to_solar_absorption_map.json",
            "solar_operator_roadmap": "solar_operator_roadmap.json",
        },
    }
    roadmap_path = _write_json(root / "solar_operator_roadmap.json", roadmap)
    return {
        "ok": True,
        "builder": "PaperToSolarMapper",
        "artifact_paths": {
            "paper_to_solar_absorption_map": str(map_path),
            "solar_operator_roadmap": str(roadmap_path),
        },
        "absorption_item_count": len(absorption_map.absorption_items),
        "gap_kinds": [],
    }


def _priority_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        priority = str(item.get("priority") or "")
        counts[priority] = counts.get(priority, 0) + 1
    return counts
