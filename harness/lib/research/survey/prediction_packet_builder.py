"""Build prediction packet artifacts for insight mode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .conference_signal_extractor import fail_closed_result
from .schemas import validate_prediction_packet, write_prediction_packets


def build_prediction_packet_artifacts(output_dir: str | Path, packets: list[dict[str, Any] | Any]) -> dict[str, Any]:
    """Write `prediction_packets.jsonl` after validating falsifiable forecasts."""
    root = Path(output_dir).expanduser()
    if not packets:
        return fail_closed_result(
            "PredictionPacketBuilder",
            root,
            missing_inputs=["prediction_packets"],
            gap_kinds=["missing_prediction_drivers", "missing_counter_scenarios"],
            artifact_paths={"prediction_packets": "prediction_packets.jsonl"},
        )

    issues: list[dict[str, Any]] = []
    for index, packet in enumerate(packets):
        result = validate_prediction_packet(packet, artifact_path="prediction_packets.jsonl")
        if not result.ok:
            for issue in result.to_dict()["issues"]:
                issue["record_index"] = index
                issues.append(issue)
    if issues:
        return {
            "ok": False,
            "builder": "PredictionPacketBuilder",
            "output_dir": str(root),
            "missing_inputs": [],
            "gap_kinds": ["missing_prediction_drivers", "missing_counter_scenarios"],
            "artifact_paths": {"prediction_packets": "prediction_packets.jsonl"},
            "reason": "prediction_packet_validation_failed",
            "issues": issues,
        }

    packet_path = write_prediction_packets(packets, root / "prediction_packets.jsonl")
    return {
        "ok": True,
        "builder": "PredictionPacketBuilder",
        "artifact_paths": {"prediction_packets": str(packet_path)},
        "prediction_packet_count": len(packets),
        "gap_kinds": [],
    }
