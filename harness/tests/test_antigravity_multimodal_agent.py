from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_DIR / "tools"))

import antigravity_multimodal_agent as agy


def test_antigravity_timeout_output_refuses_success_handoff(tmp_path, monkeypatch, capsys):
    dispatch = tmp_path / "dispatch.md"
    dispatch.write_text("## Goal\nDo work\n## Acceptance\n- pass\n", encoding="utf-8")
    handoff = tmp_path / "handoff.md"
    monkeypatch.setenv("SOLAR_MULTI_TASK_DISPATCH_FILE", str(dispatch))
    monkeypatch.setenv("TASK_DIR", str(tmp_path))
    monkeypatch.setenv("HANDOFF", str(handoff))
    monkeypatch.setenv("AGY_BIN", "agy")

    def fake_run(cmd, text=True, capture_output=True, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="Error: timed out waiting for response\n", stderr="")

    monkeypatch.setattr(agy.subprocess, "run", fake_run)

    monkeypatch.setattr(agy.sys, "argv", ["antigravity_multimodal_agent.py"])

    assert agy.main() == 65
    assert not handoff.exists()
    assert "refusing success handoff" in capsys.readouterr().err


def test_antigravity_success_writes_handoff(tmp_path, monkeypatch):
    dispatch = tmp_path / "dispatch.md"
    dispatch.write_text("## Goal\nDo work\n## Acceptance\n- pass\n", encoding="utf-8")
    handoff = tmp_path / "handoff.md"
    monkeypatch.setenv("SOLAR_MULTI_TASK_DISPATCH_FILE", str(dispatch))
    monkeypatch.setenv("TASK_DIR", str(tmp_path))
    monkeypatch.setenv("HANDOFF", str(handoff))
    monkeypatch.setenv("AGY_BIN", "agy")

    def fake_run(cmd, text=True, capture_output=True, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="## completed\nDone\n## verified\nChecked\n", stderr="")

    monkeypatch.setattr(agy.subprocess, "run", fake_run)

    monkeypatch.setattr(agy.sys, "argv", ["antigravity_multimodal_agent.py"])

    assert agy.main() == 0
    assert "Done" in handoff.read_text(encoding="utf-8")
