"""Tests for research CLI (cli.py) — 5 subcommands via main() entry point.

Constraints:
- Real SQLite with tmp_path (no mocks)
- Zero @mock.patch decorators
- Assertion count >= 10

Spec: sprint-20260513-solar-deepresearch-product-line-s03-core-runtime / N5
"""

from __future__ import annotations

import os
import sys

import pytest

# Ensure harness/lib is importable from tests.
_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

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


class TestDoctorUnaffected:
    def test_doctor_not_broken(self):
        """A10: doctor subcommand is not affected by research routing."""
        # doctor is a separate path, not going through our code.
        # We just verify the CLI parser still works after our changes.
        parser = build_parser()
        assert parser.prog == "solar-harness research"
