"""Tests for deterministic DeepResearch artifact evaluator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HARNESS_LIB = Path(__file__).resolve().parents[2] / "lib"
if str(_HARNESS_LIB) not in sys.path:
    sys.path.insert(0, str(_HARNESS_LIB))

from research.evaluator import evaluate_artifacts  # noqa: E402


def _write_good_artifacts(root: Path, **eval_overrides) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "final.md").write_text("# Final\n\nSupported claim [cite:ev_abcdef1234567890]\n", encoding="utf-8")
    (root / "report_ast.json").write_text(
        json.dumps({"chapters": [{"sections": [{"section_id": "ch1/sec1"}]}]}),
        encoding="utf-8",
    )
    (root / "final.bibliography.json").write_text("[]", encoding="utf-8")
    payload = {
        "run_id": "run-good",
        "source_count": 1,
        "evidence_count": 1,
        "claim_count": 1,
        "section_count": 1,
        "unsupported_rate": 0.0,
        "citation_accuracy": 1.0,
        "status": "passed",
        "output_dir": str(root),
        "final_md": str(root / "final.md"),
    }
    payload.update(eval_overrides)
    path = root / "run-good-research_eval.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_evaluate_artifacts_passes_complete_artifact_set(tmp_path):
    eval_json = _write_good_artifacts(tmp_path)

    result = evaluate_artifacts(eval_json)

    assert result["ok"] is True
    assert result["verdict"] == "PASS"
    assert result["metrics"]["report_ast_sections"] == 1
    assert result["artifact_exists"]["final_md"] is True


def test_evaluate_artifacts_accepts_smoke_metric_aliases_and_named_evidence_ids(tmp_path):
    eval_json = _write_good_artifacts(
        tmp_path,
        unsupported_rate=None,
        citation_accuracy=None,
        unsupported_claim_rate=0.0,
        citation_span_accuracy=1.0,
    )
    (tmp_path / "final.md").write_text("# Final\n\nSupported claim [cite:ev_vaswani_self_attention]\n", encoding="utf-8")

    result = evaluate_artifacts(eval_json)

    assert result["ok"] is True
    assert result["metrics"]["unsupported_rate"] == 0.0
    assert result["metrics"]["citation_accuracy"] == 1.0


def test_evaluate_artifacts_fails_missing_claims(tmp_path):
    eval_json = _write_good_artifacts(tmp_path, claim_count=0, citation_accuracy=0.0)

    result = evaluate_artifacts(eval_json)

    assert result["ok"] is False
    assert result["verdict"] == "FAIL"
    assert "claim_count_zero" in result["errors"]
    assert any(err.startswith("citation_accuracy_too_low") for err in result["errors"])


def test_evaluate_artifacts_fails_final_without_citations(tmp_path):
    eval_json = _write_good_artifacts(tmp_path)
    (tmp_path / "final.md").write_text("# Final\n\nNo citation marker.\n", encoding="utf-8")

    result = evaluate_artifacts(eval_json)

    assert result["ok"] is False
    assert "final_md_missing_evidence_citations" in result["errors"]


def test_evaluate_artifacts_fails_metadata_noise(tmp_path):
    eval_json = _write_good_artifacts(tmp_path)
    (tmp_path / "final.md").write_text(
        "# Final\n\n"
        "Title: A\nURL: https://example.com/a\nPublisher: X\nPublished: 2025\n"
        "Supported claim [cite:ev_abcdef1234567890]\n",
        encoding="utf-8",
    )

    result = evaluate_artifacts(eval_json)

    assert result["ok"] is False
    assert any(err.startswith("final_md_metadata_noise") for err in result["errors"])


def test_evaluate_artifacts_requires_expert_synthesis_gate(tmp_path):
    eval_json = _write_good_artifacts(tmp_path)
    expert = tmp_path / "expert_synthesis.md"
    expert.write_text(
        "# Expert\n\n"
        "## Insight Scorecard\n\n"
        "| Dimension | Score | Rationale |\n"
        "|---|---:|---|\n"
        "| Source strength | 4/5 | paper sources |\n"
        "| Architecture abstraction | 4/5 | taxonomy |\n"
        "| Auditability | 4/5 | projection |\n\n"
        "## Architecture Taxonomy\n\n"
        "Taxonomy table.\n\n"
        "## Source Strength\n\n"
        "Source strength is high.\n\n"
        "## Design Tradeoffs\n\n"
        "Tradeoff: deployability vs. purity.\n\n"
        "## Contradictions and Uncertainty\n\n"
        "Uncertainty remains around faithfulness.\n\n"
        "## Implementation Roadmap\n\n"
        "- **P0:** baseline.\n"
        "- **P1:** runtime.\n"
        "- **P2:** scale.\n"
        + ("Evidence text.\n" * 120),
        encoding="utf-8",
    )

    result = evaluate_artifacts(eval_json, expert_md=expert, require_expert=True)

    assert result["ok"] is True
    assert result["metrics"]["expert_has_taxonomy"] is True
    assert result["metrics"]["expert_roadmap_mentions"] >= 3
    assert result["metrics"]["expert_has_source_strength"] is True
    assert result["metrics"]["expert_has_contradiction_uncertainty"] is True
    assert result["metrics"]["expert_insight_scorecard_rows"] == 3
