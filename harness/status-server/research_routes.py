"""Research status route module for Solar Harness status-server.

Provides /research/<sid> endpoint that reads from research_eval.*.json files
and displays source_count, evidence_count, claim_count, unsupported_rate,
citation_accuracy, and overall status. No hardcoded fake data.

Usage:
    from status_server.research_routes import build_research_payload, generate_markdown_report
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Any

HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", str(Path.home() / ".solar" / "harness")))
SPRINTS_DIR = HARNESS_DIR / "sprints"


def discover_eval_files(sprints_dir: Path | str, sid: str) -> list[Path]:
    """Find research_eval.*.json files matching the given sprint ID prefix."""
    sprints_dir = Path(sprints_dir)
    pattern = str(sprints_dir / f"{sid}*research_eval*.json")
    return sorted(Path(p) for p in glob.glob(pattern))


def load_eval(path: Path) -> dict[str, Any]:
    """Load a single research_eval JSON file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_research_payload(sprints_dir: Path | str | None, sid: str) -> dict[str, Any]:
    """Build JSON payload for GET /research/<sid>.

    Reads from research_eval.*.json files. Returns zeroed defaults if no files found.
    """
    sprints_dir = Path(sprints_dir) if sprints_dir else SPRINTS_DIR
    eval_files = discover_eval_files(sprints_dir, sid)

    total_sources = 0
    total_evidence = 0
    total_claims = 0
    total_unsupported = 0
    total_key_claims = 0
    total_span_matches = 0
    total_spans = 0
    overall_status = "no_data"
    eval_count = len(eval_files)

    for ef in eval_files:
        data = load_eval(ef)
        total_sources += data.get("source_count", 0)
        total_evidence += data.get("evidence_count", 0)
        total_claims += data.get("claim_count", 0)
        total_unsupported += data.get("unsupported_claims", 0)
        total_key_claims += data.get("total_key_claims", 0)
        total_span_matches += data.get("span_matches", 0)
        total_spans += data.get("total_spans", 0)

        status = data.get("status", "")
        if status == "failed":
            overall_status = "failed"
        elif status == "running" and overall_status != "failed":
            overall_status = "running"
        elif status == "passed" and overall_status not in ("failed", "running"):
            overall_status = "passed"
        elif status == "partial" and overall_status not in ("failed", "running", "passed"):
            overall_status = "partial"

    if eval_count > 0 and overall_status == "no_data":
        overall_status = "data_loaded"

    unsupported_rate = round(total_unsupported / total_key_claims, 4) if total_key_claims > 0 else 0.0
    citation_accuracy = round(total_span_matches / total_spans, 4) if total_spans > 0 else 0.0

    return {
        "sid": sid,
        "source_count": total_sources,
        "evidence_count": total_evidence,
        "claim_count": total_claims,
        "unsupported_rate": unsupported_rate,
        "citation_accuracy": citation_accuracy,
        "status": overall_status,
        "eval_files": eval_count,
    }


def generate_markdown_report(sprints_dir: Path | str | None, sid: str) -> str:
    """Generate markdown report for activation-proof --research <sid>."""
    data = build_research_payload(sprints_dir, sid)
    lines = [
        f"# Research Status Report: {sid}",
        "",
        f"**Status**: {data['status']}",
        f"**Eval Files**: {data['eval_files']}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Source Count | {data['source_count']} |",
        f"| Evidence Count | {data['evidence_count']} |",
        f"| Claim Count | {data['claim_count']} |",
        f"| Unsupported Rate | {data['unsupported_rate']:.2%} |",
        f"| Citation Accuracy | {data['citation_accuracy']:.2%} |",
        "",
    ]
    return "\n".join(lines)
