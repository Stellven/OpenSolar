#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import runtime_doctor  # noqa: E402


def test_state_surface_drift_detects_terminal_evidence_nonterminal_status(tmp_path, monkeypatch) -> None:
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    monkeypatch.setattr(runtime_doctor, "SPRINTS_DIR", str(sprints))

    sid = "sprint-drifted"
    (sprints / f"{sid}.status.json").write_text(json.dumps({
        "sprint_id": sid,
        "status": "active",
        "phase": "planning_complete",
        "stage": "planning_complete",
    }), encoding="utf-8")
    (sprints / f"{sid}.handoff.md").write_text("# handoff\n", encoding="utf-8")
    (sprints / f"{sid}.eval.md").write_text("# eval\n", encoding="utf-8")

    report = runtime_doctor._check_state_surface_drift(sid)  # noqa: SLF001 - targeted doctor coverage

    assert report["ok"] is False
    assert report["warn"] is True
    assert "terminal_evidence_nonterminal_status" in report["issues"]
    assert report["details"]["artifact_evidence"] == {"handoff": True, "eval": True}
