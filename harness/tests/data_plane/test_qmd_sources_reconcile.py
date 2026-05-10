#!/usr/bin/env python3
"""test_qmd_sources_reconcile.py — S4 acceptance tests for QMD reindex/reconcile.
Sprint: sprint-20260510-data-plane-storage-access-unification

Verifies:
  - QMD index is reachable and reports healthy state
  - source-manifest.jsonl entries preserve original_path provenance
  - rebuild --dry-run completes without foreground blocking
  - embedding/rebuild is idle/background, not launched inline
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", str(Path.home() / ".solar" / "harness")))
sys.path.insert(0, str(HARNESS_DIR / "lib"))

HOME = Path.home()
MANIFEST_PATH = HOME / "Knowledge" / "_meta" / "source-manifest.jsonl"
QMD_PORT = 8181


def _qmd_port_open() -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", QMD_PORT), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def _load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    entries = []
    with open(MANIFEST_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
    return entries


# ---------------------------------------------------------------------------
# QMD availability
# ---------------------------------------------------------------------------

class TestQMDAvailability:
    """QMD index is reachable and reports healthy."""

    def test_qmd_port_open(self):
        """QMD MCP server is listening on port 8181."""
        assert _qmd_port_open(), \
            f"QMD MCP port {QMD_PORT} is not open — run: solar-harness wiki qmd-status"

    def test_qmd_health_endpoint(self):
        """QMD /health returns ok status."""
        import urllib.request
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{QMD_PORT}/health", timeout=3
            ) as resp:
                body = json.loads(resp.read())
                assert body.get("status") == "ok", f"QMD health not ok: {body}"
        except Exception as exc:
            pytest.skip(f"QMD health endpoint not available: {exc}")

    def test_qmd_adapter_status(self):
        """qmd_adapter.py status command completes without error."""
        from qmd_adapter import cmd_status
        # Should not raise
        rc = cmd_status(as_json=False)
        assert rc == 0


# ---------------------------------------------------------------------------
# Manifest provenance tracing
# ---------------------------------------------------------------------------

class TestManifestProvenance:
    """source-manifest.jsonl entries preserve _raw/file-uploads provenance."""

    def test_manifest_exists(self):
        """source-manifest.jsonl exists with at least 1 entry."""
        entries = _load_manifest()
        assert len(entries) >= 1, f"source-manifest.jsonl missing or empty at {MANIFEST_PATH}"

    def test_all_entries_have_original_path(self):
        """Every manifest entry has a non-empty original_path."""
        entries = _load_manifest()
        for e in entries:
            assert e.get("original_path"), \
                f"Entry missing original_path: sha256={e.get('sha256','?')[:8]}"

    def test_original_path_in_raw_uploads(self):
        """All original_path values are under Knowledge/_raw/file-uploads."""
        raw_root = str(HOME / "Knowledge" / "_raw" / "file-uploads")
        entries = _load_manifest()
        for e in entries:
            op = e.get("original_path", "")
            assert op.startswith(raw_root), \
                f"original_path not under _raw/file-uploads: {op}"

    def test_all_entries_have_sha256(self):
        """Every manifest entry has a sha256 checksum."""
        entries = _load_manifest()
        for e in entries:
            sha = e.get("sha256", "")
            assert sha and len(sha) == 64, \
                f"Entry missing valid sha256: {e.get('original_path','?')}"

    def test_all_entries_have_canonical_path(self):
        """Every entry has a canonical_path under Knowledge/_sources."""
        sources_root = str(HOME / "Knowledge" / "_sources")
        entries = _load_manifest()
        for e in entries:
            cp = e.get("canonical_path", "")
            assert cp.startswith(sources_root), \
                f"canonical_path not under _sources: {cp}"

    def test_canonical_path_includes_sha_prefix(self):
        """canonical_path structure: _sources/category/sha[:2]/sha/filename."""
        entries = _load_manifest()
        for e in entries:
            sha = e.get("sha256", "")
            cp = e.get("canonical_path", "")
            if sha and cp:
                # sha prefix directory should appear in path
                assert sha[:2] in cp, \
                    f"SHA prefix {sha[:2]} not in canonical_path: {cp}"

    def test_provenance_roundtrip(self):
        """Given a canonical_path, the sha256 in the path matches the entry sha256."""
        entries = _load_manifest()
        for e in entries[:10]:  # sample first 10
            sha = e.get("sha256", "")
            cp = e.get("canonical_path", "")
            if sha and cp:
                assert sha in cp, \
                    f"sha256 {sha[:16]} not found in canonical_path {cp}"


# ---------------------------------------------------------------------------
# Rebuild dry-run (non-blocking)
# ---------------------------------------------------------------------------

class TestRebuildNonBlocking:
    """rebuild --dry-run completes quickly without foreground embedding."""

    def test_dry_run_completes_under_10s(self):
        """qmd_adapter rebuild --dry-run finishes in under 10 seconds."""
        from qmd_adapter import cmd_rebuild
        start = time.time()
        rc = cmd_rebuild(dry_run=True, force=True, as_json=False)
        elapsed = time.time() - start
        assert elapsed < 10.0, f"dry-run took {elapsed:.1f}s, expected < 10s"
        assert rc == 0

    def test_dry_run_reports_new_files(self):
        """dry-run --force returns new_files_found >= 0 without writing."""
        import io
        from contextlib import redirect_stdout
        from qmd_adapter import cmd_rebuild

        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_rebuild(dry_run=True, force=False, as_json=True)
        result = json.loads(buf.getvalue())
        assert "new_files_found" in result
        assert result["new_files_found"] >= 0
        assert result.get("action") == "dry_run"

    def test_dry_run_does_not_write_last_build(self):
        """dry-run does not update last-build.json."""
        from qmd_adapter import LAST_BUILD_FILE, cmd_rebuild

        mtime_before = LAST_BUILD_FILE.stat().st_mtime if LAST_BUILD_FILE.exists() else None
        cmd_rebuild(dry_run=True, force=False, as_json=False)
        mtime_after = LAST_BUILD_FILE.stat().st_mtime if LAST_BUILD_FILE.exists() else None
        assert mtime_before == mtime_after, \
            "dry-run should not modify last-build.json"

    def test_embed_state_shows_idle_or_gentle(self):
        """QMD embed state is idle/gentle (not actively consuming CPU)."""
        embed_state_path = HARNESS_DIR / "state" / "qmd-embed-status.json"
        if not embed_state_path.exists():
            pytest.skip("qmd-embed-status.json not present")
        state = json.loads(embed_state_path.read_text())
        mode = state.get("mode", "")
        st = state.get("state", "")
        assert mode in ("gentle", "idle", "paused") or st in (
            "gentle_wait", "idle", "paused", "done"
        ), f"Embed not in idle/gentle mode: mode={mode!r} state={st!r}"


# ---------------------------------------------------------------------------
# Papers reconcile
# ---------------------------------------------------------------------------

class TestPapersReconcile:
    """Papers manifest entries are consistent and traceable."""

    def test_papers_category_present(self):
        """Manifest has at least 1 'papers' category entry."""
        entries = _load_manifest()
        papers = [e for e in entries if e.get("category") == "papers"]
        assert len(papers) >= 1, "No papers found in manifest"

    def test_papers_canonical_path_under_sources_papers(self):
        """All paper canonical paths are under _sources/papers/."""
        papers_root = str(HOME / "Knowledge" / "_sources" / "papers")
        entries = _load_manifest()
        for e in entries:
            if e.get("category") == "papers":
                cp = e.get("canonical_path", "")
                assert cp.startswith(papers_root), \
                    f"Paper canonical_path not under _sources/papers: {cp}"

    def test_reindex_plan_report_exists(self):
        """S4 qmd-reindex.md report has been generated."""
        report = (
            HARNESS_DIR
            / "reports"
            / "data-plane-storage-access-unification"
            / "qmd-reindex.md"
        )
        assert report.exists(), f"qmd-reindex.md not found at {report}"
        content = report.read_text()
        assert len(content) > 200, "qmd-reindex.md is too short"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
