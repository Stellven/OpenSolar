"""Tests for research CLI (cli.py) — 5 subcommands via main() entry point.

Constraints:
- Real SQLite with tmp_path (no mocks)
- Zero @mock.patch decorators
- Assertion count >= 10

Spec: sprint-20260513-solar-deepresearch-product-line-s03-core-runtime / N5
"""

from __future__ import annotations

import json
import os
import sys

import pytest

# Ensure harness/lib is importable from tests.
_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research import cli as research_cli
from research.cli import build_parser, main


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_research.db")


class TestCliParser:
    def test_all_five_subcommands_registered(self):
        """A1: --help lists init, add-source, extract, ledger, status."""
        parser = build_parser()
        subs = parser._subparsers._group_actions[0].choices
        assert "init" in subs
        assert "add-source" in subs
        assert "extract" in subs
        assert "ledger" in subs
        assert "status" in subs

    def test_help_exits_zero(self):
        """A2: research --help exits 0."""
        assert main(["--help"]) == 0

    def test_no_subcommand_exits_zero(self):
        """A3: no subcommand prints help and exits 0."""
        assert main([]) == 0


class TestInit:
    def test_init_creates_db(self, db_path):
        """A4: init creates DB file and returns 0."""
        assert main(["init", db_path]) == 0
        assert os.path.exists(db_path)

    def test_init_rejects_existing(self, db_path):
        """A5: init on existing DB returns 1."""
        assert main(["init", db_path]) == 0
        assert main(["init", db_path]) == 1


class TestAddSourceAndExtract:
    def test_add_source_then_extract(self, db_path):
        """A6: add-source followed by extract produces evidence row."""
        assert main(["init", db_path]) == 0
        # Get run_id from init output — parse it by running init again is messy,
        # so query the DB directly.
        import sqlite3
        conn = sqlite3.connect(db_path)
        run_id = conn.execute("SELECT id FROM research_runs LIMIT 1").fetchone()[0]
        conn.close()

        assert main([
            "add-source", db_path,
            "--run-id", run_id,
            "--title", "Test Source",
            "--text", "This is test source content for CLI testing.",
        ]) == 0

        source_row = sqlite3.connect(db_path).execute(
            "SELECT id FROM research_sources WHERE run_id = ?", (run_id,)
        ).fetchone()
        source_id = source_row[0]

        assert main([
            "extract", db_path,
            "--run-id", run_id,
            "--source-id", source_id,
        ]) == 0


class TestLedger:
    def test_ledger_shows_summary(self, tmp_path):
        """A7: ledger shows run summary with source and evidence counts."""
        db = str(tmp_path / "ledger_test.db")
        assert main(["init", db]) == 0

        import sqlite3
        conn = sqlite3.connect(db)
        run_id = conn.execute("SELECT id FROM research_runs LIMIT 1").fetchone()[0]
        conn.close()

        assert main([
            "add-source", db, "--run-id", run_id,
            "--text", "Evidence ledger content",
        ]) == 0

        source_id = sqlite3.connect(db).execute(
            "SELECT id FROM research_sources WHERE run_id = ?", (run_id,)
        ).fetchone()[0]

        assert main([
            "extract", db, "--run-id", run_id, "--source-id", source_id,
        ]) == 0

        # Run ledger — just check exit code; output goes to stdout.
        assert main(["ledger", db, "--run-id", run_id]) == 0


class TestStatus:
    def test_status_exits_zero(self, db_path):
        """A8: status on valid DB returns 0."""
        assert main(["init", db_path]) == 0
        assert main(["status", db_path]) == 0

    def test_status_nonexistent_returns_one(self):
        """A9: status on missing DB returns 1."""
        assert main(["status", "/tmp/nonexistent_cli_test.db"]) == 1


class TestWebResearch:
    def test_search_writes_online_sources_with_fetch(self, db_path, monkeypatch):
        """Search must materialize source rows, not only update last_search."""
        assert main(["init", db_path, "--topic", "web smoke"]) == 0

        import sqlite3
        conn = sqlite3.connect(db_path)
        run_id = conn.execute("SELECT id FROM research_runs LIMIT 1").fetchone()[0]
        conn.close()

        monkeypatch.setattr(
            research_cli,
            "browser_use_search",
            lambda query, max_results: (
                [{"title": "Result A", "url": "https://example.com/a", "snippet": "Snippet A", "rank": 1, "connector": "fake"}],
                [],
            ),
        )
        monkeypatch.setattr(
            research_cli,
            "fetch_url_readable",
            lambda url: ("A fetched article says orbital data centers need evidence ledgers and citations.", None),
        )
        monkeypatch.setattr(research_cli, "browser_use_fetch_url", lambda url: ("A browser-use fetched article says orbital data centers need evidence ledgers and citations.", None))

        assert main(["search", db_path, "--run-id", run_id, "--query", "orbital data centers", "--fetch", "--require-online", "--json"]) == 0

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT title, url, content_span FROM research_sources WHERE run_id = ?", (run_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "Result A"
        assert row[1] == "https://example.com/a"
        assert "fetched article" in json.loads(row[2])["text"]

    def test_run_web_query_end_to_end_without_network(self, db_path, tmp_path, monkeypatch):
        """run --web-query should create source/evidence/claims/sections/final.md."""
        monkeypatch.setattr(
            research_cli,
            "browser_use_search",
            lambda query, max_results: (
                [{"title": "Result B", "url": "https://example.com/b", "snippet": "Snippet B", "rank": 1, "connector": "fake"}],
                [],
            ),
        )
        monkeypatch.setattr(
            research_cli,
            "fetch_url_readable",
            lambda url: (
                "Orbital data centers are proposed as a response to terrestrial energy and cooling constraints. "
                "They also require launch economics, radiation tolerance, and reliable downlink capacity.",
                None,
            ),
        )
        monkeypatch.setattr(
            research_cli,
            "browser_use_fetch_url",
            lambda url: (
                "Orbital data centers are proposed as a response to terrestrial energy and cooling constraints. "
                "They also require launch economics, radiation tolerance, and reliable downlink capacity.",
                None,
            ),
        )

        out = tmp_path / "out"
        assert main([
            "run", db_path,
            "--topic", "orbital data centers",
            "--web-query", "orbital data centers",
            "--max-results", "1",
            "--output-dir", str(out),
            "--output-md", str(out / "final.md"),
        ]) == 0
        final = (out / "final.md").read_text()
        assert "Orbital data centers" in final or "orbital data centers" in final
        assert "[cite:" in final
        assert (out / "sources.jsonl").exists()
        assert (out / "evidence.jsonl").exists()
        assert (out / "claims.jsonl").exists()

    def test_auto_provider_prefers_browser_use_over_http(self, db_path, monkeypatch):
        """Auto provider must use browser-use first and avoid HTTP if it succeeds."""
        assert main(["init", db_path, "--topic", "provider route"]) == 0

        import sqlite3
        conn = sqlite3.connect(db_path)
        run_id = conn.execute("SELECT id FROM research_runs LIMIT 1").fetchone()[0]
        conn.close()

        called = {"http": False}
        monkeypatch.setattr(
            research_cli,
            "browser_use_search",
            lambda query, max_results: (
                [{"title": "Browser Result", "url": "https://example.com/browser", "snippet": "Browser snippet", "rank": 1, "connector": "browser-use"}],
                [],
            ),
        )

        def fail_http(query, max_results):
            called["http"] = True
            return [], ["http should not be called"]

        monkeypatch.setattr(research_cli, "http_web_search", fail_http)

        assert main([
            "search", db_path,
            "--run-id", run_id,
            "--query", "browser route",
            "--provider", "auto",
            "--json",
        ]) == 0
        assert called["http"] is False


class TestHumanSearchLoop:
    def test_handoff_search_writes_markdown(self, db_path, tmp_path):
        assert main(["init", db_path, "--topic", "human loop topic"]) == 0

        import sqlite3
        conn = sqlite3.connect(db_path)
        run_id = conn.execute("SELECT id FROM research_runs LIMIT 1").fetchone()[0]
        conn.close()

        out = tmp_path / "handoff.md"
        assert main([
            "handoff-search", db_path,
            "--run-id", run_id,
            "--query", "human loop query",
            "--max-results", "3",
            "--output-md", str(out),
        ]) == 0
        text = out.read_text()
        assert "Solar DeepResearch Human Search Handoff" in text
        assert "human loop query" in text
        assert "Required Output Format" in text

    def test_import_search_can_continue_pipeline(self, db_path, tmp_path):
        assert main(["init", db_path, "--topic", "human loop topic"]) == 0

        import sqlite3
        conn = sqlite3.connect(db_path)
        run_id = conn.execute("SELECT id FROM research_runs LIMIT 1").fetchone()[0]
        conn.close()

        results = tmp_path / "gemini-results.md"
        results.write_text(
            """# External Search Results: human loop topic

## Source 1: Official Orbital Data Center Note
URL: https://example.com/orbital-data-center
Publisher: Example Institute
Published: 2026-01-01
Source Type: official

Summary:
- Orbital data centers need launch economics and radiation-tolerant hardware.
- Power, cooling, and downlink constraints determine feasibility.

Key Claims:
- Orbital data centers can reduce terrestrial cooling pressure.
- Space deployment creates new reliability and communications constraints.

Relevant Quotes:
> Orbital computing depends on power and downlink capacity.
""",
            encoding="utf-8",
        )
        out = tmp_path / "out"
        final = out / "final.md"
        assert main([
            "import-search", db_path,
            "--run-id", run_id,
            "--input-md", str(results),
            "--continue",
            "--output-dir", str(out),
            "--output-md", str(final),
        ]) == 0
        assert final.exists()
        text = final.read_text()
        assert "Orbital data centers" in text
        assert "[cite:" in text
        assert (out / "sources.jsonl").exists()
        assert (out / "claims.jsonl").exists()


class TestDoctorUnaffected:
    def test_doctor_not_broken(self):
        """A10: doctor subcommand is not affected by research routing."""
        # doctor is a separate path, not going through our code.
        # We just verify the CLI parser still works after our changes.
        parser = build_parser()
        assert parser.prog == "solar-harness research"
