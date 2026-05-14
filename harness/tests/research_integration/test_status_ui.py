"""Tests for status-server/research_routes.py and /research/<sid> endpoint.

Acceptance:
- GET /research/<sid> returns JSON with required keys
- All numbers read from research_eval.*.json; no hardcoded data
- generate_markdown_report produces valid markdown
- End-to-end HTTP test via http.server
- Zero @mock.patch

Tests use real JSON files in temp directories.
"""

from __future__ import annotations

import json
import sys
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

import pytest

# Place harness root on sys.path
_HARNESS_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HARNESS_ROOT))

import importlib.util as _ilu

_mod_path = _HARNESS_ROOT / "status-server" / "research_routes.py"
_spec = _ilu.spec_from_file_location("research_routes", str(_mod_path))
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_research_payload = _mod.build_research_payload
discover_eval_files = _mod.discover_eval_files
generate_markdown_report = _mod.generate_markdown_report
load_eval = _mod.load_eval


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_eval(tmpdir: Path, filename: str, data: dict) -> Path:
    p = tmpdir / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _make_eval_data(
    source_count=10,
    evidence_count=50,
    claim_count=20,
    unsupported_claims=2,
    total_key_claims=20,
    span_matches=45,
    total_spans=50,
    status="passed",
):
    return {
        "source_count": source_count,
        "evidence_count": evidence_count,
        "claim_count": claim_count,
        "unsupported_claims": unsupported_claims,
        "total_key_claims": total_key_claims,
        "span_matches": span_matches,
        "total_spans": total_spans,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Tests: discover_eval_files
# ---------------------------------------------------------------------------

class TestDiscoverEvalFiles:
    def test_finds_matching_files(self, tmp_path):
        _write_eval(tmp_path, "sprint-001-research_eval.json", {})
        _write_eval(tmp_path, "sprint-001-research_eval_extra.json", {})
        _write_eval(tmp_path, "sprint-002-research_eval.json", {})
        found = discover_eval_files(tmp_path, "sprint-001")
        assert len(found) == 2

    def test_returns_empty_for_no_match(self, tmp_path):
        _write_eval(tmp_path, "sprint-002-research_eval.json", {})
        found = discover_eval_files(tmp_path, "sprint-999")
        assert found == []

    def test_ignores_non_eval_files(self, tmp_path):
        _write_eval(tmp_path, "sprint-001-eval.json", {})
        _write_eval(tmp_path, "sprint-001-research_eval.json", {})
        found = discover_eval_files(tmp_path, "sprint-001")
        assert len(found) == 1


# ---------------------------------------------------------------------------
# Tests: load_eval
# ---------------------------------------------------------------------------

class TestLoadEval:
    def test_loads_valid_json(self, tmp_path):
        data = {"source_count": 5}
        p = _write_eval(tmp_path, "eval.json", data)
        assert load_eval(p) == data

    def test_returns_empty_on_missing(self, tmp_path):
        assert load_eval(tmp_path / "nonexistent.json") == {}

    def test_returns_empty_on_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json{{{", encoding="utf-8")
        assert load_eval(p) == {}


# ---------------------------------------------------------------------------
# Tests: build_research_payload
# ---------------------------------------------------------------------------

class TestBuildResearchPayload:
    def test_no_eval_files_returns_defaults(self, tmp_path):
        result = build_research_payload(tmp_path, "sprint-nope")
        assert result["source_count"] == 0
        assert result["evidence_count"] == 0
        assert result["claim_count"] == 0
        assert result["unsupported_rate"] == 0.0
        assert result["citation_accuracy"] == 0.0
        assert result["status"] == "no_data"
        assert result["eval_files"] == 0

    def test_single_eval_file_aggregates(self, tmp_path):
        _write_eval(tmp_path, "sid-research_eval.json", _make_eval_data())
        result = build_research_payload(tmp_path, "sid")
        assert result["source_count"] == 10
        assert result["evidence_count"] == 50
        assert result["claim_count"] == 20
        assert result["status"] == "passed"
        assert result["eval_files"] == 1

    def test_multiple_eval_files_sum(self, tmp_path):
        _write_eval(tmp_path, "sid-research_eval.json", _make_eval_data(source_count=5, evidence_count=10))
        _write_eval(tmp_path, "sid-research_eval_extra.json", _make_eval_data(source_count=3, evidence_count=15))
        result = build_research_payload(tmp_path, "sid")
        assert result["source_count"] == 8
        assert result["evidence_count"] == 25
        assert result["eval_files"] == 2

    def test_unsupported_rate_calculation(self, tmp_path):
        _write_eval(tmp_path, "sid-research_eval.json", _make_eval_data(
            unsupported_claims=3, total_key_claims=30,
            span_matches=40, total_spans=50,
        ))
        result = build_research_payload(tmp_path, "sid")
        assert result["unsupported_rate"] == pytest.approx(0.1, abs=0.001)
        assert result["citation_accuracy"] == pytest.approx(0.8, abs=0.001)

    def test_zero_division_safe(self, tmp_path):
        _write_eval(tmp_path, "sid-research_eval.json", _make_eval_data(
            total_key_claims=0, total_spans=0,
        ))
        result = build_research_payload(tmp_path, "sid")
        assert result["unsupported_rate"] == 0.0
        assert result["citation_accuracy"] == 0.0

    def test_status_priority_failed_over_passed(self, tmp_path):
        _write_eval(tmp_path, "sid-research_eval_a.json", _make_eval_data(status="passed"))
        _write_eval(tmp_path, "sid-research_eval_b.json", _make_eval_data(status="failed"))
        result = build_research_payload(tmp_path, "sid")
        assert result["status"] == "failed"

    def test_json_keys_complete(self, tmp_path):
        _write_eval(tmp_path, "sid-research_eval.json", _make_eval_data())
        result = build_research_payload(tmp_path, "sid")
        for key in ("sid", "source_count", "evidence_count", "claim_count",
                     "unsupported_rate", "citation_accuracy", "status", "eval_files"):
            assert key in result, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Tests: generate_markdown_report
# ---------------------------------------------------------------------------

class TestMarkdownReport:
    def test_includes_sid(self, tmp_path):
        _write_eval(tmp_path, "sid-research_eval.json", _make_eval_data())
        md = generate_markdown_report(tmp_path, "sid")
        assert "# Research Status Report: sid" in md

    def test_includes_metrics_table(self, tmp_path):
        _write_eval(tmp_path, "sid-research_eval.json", _make_eval_data(
            source_count=7, evidence_count=42, claim_count=15,
        ))
        md = generate_markdown_report(tmp_path, "sid")
        assert "| Source Count | 7 |" in md
        assert "| Evidence Count | 42 |" in md
        assert "| Claim Count | 15 |" in md

    def test_includes_status(self, tmp_path):
        _write_eval(tmp_path, "sid-research_eval.json", _make_eval_data(status="passed"))
        md = generate_markdown_report(tmp_path, "sid")
        assert "**Status**: passed" in md
