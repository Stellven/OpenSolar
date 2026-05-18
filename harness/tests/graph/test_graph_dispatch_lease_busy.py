"""Regression tests for graph dispatcher lease busy classification."""

from __future__ import annotations

import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import graph_node_dispatcher as gnd  # noqa: E402


def _ts(delta_seconds: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=delta_seconds)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_expired_lease_does_not_make_pane_busy(monkeypatch) -> None:
    monkeypatch.setattr(gnd, "read_lease", lambda pane: {"expires_at": _ts(-60)})
    assert gnd._pane_has_active_lease("solar-harness-lab:0.0") is False


def test_active_lease_makes_pane_busy(monkeypatch) -> None:
    monkeypatch.setattr(gnd, "read_lease", lambda pane: {"expires_at": _ts(60)})
    assert gnd._pane_has_active_lease("solar-harness-lab:0.0") is True


def test_default_claude_try_prompt_is_not_prompt_residue() -> None:
    tail = '────────────────\n❯\u00a0Try "how do I log an error?"\n────────────────\n'
    assert gnd.PANE_PROMPT_RESIDUE_RE.search(tail) is None


def test_non_default_prompt_text_is_prompt_residue() -> None:
    tail = "────────────────\n❯\u00a0继续执行下一个 dispatch 文件\n────────────────\n"
    assert gnd.PANE_PROMPT_RESIDUE_RE.search(tail)


def test_worker_discovery_ignores_expired_lease(monkeypatch) -> None:
    monkeypatch.setattr(
        gnd.subprocess,
        "check_output",
        lambda *a, **kw: b"solar-harness-lab:0.0\tbuilder-glm\n",
    )
    monkeypatch.setattr(gnd, "read_lease", lambda pane: {"expires_at": _ts(-60)})
    monkeypatch.setattr(gnd, "_clear_stale_prompt_residue", lambda pane: False)
    monkeypatch.setattr(gnd, "_pane_unavailable_reason", lambda pane: "")
    monkeypatch.setattr(gnd, "_pane_tui_busy", lambda pane: False)
    monkeypatch.setattr(gnd, "_pane_health", lambda pane: {})

    workers = gnd._discover_workers(dry_run=False)

    assert len(workers) == 1
    assert workers[0]["pane"] == "solar-harness-lab:0.0"
    assert workers[0]["busy"] is False


def test_worker_discovery_marks_shell_prompt_residue_as_runtime_not_running(monkeypatch) -> None:
    monkeypatch.setattr(
        gnd.subprocess,
        "check_output",
        lambda *a, **kw: b"solar-harness-lab:0.3\tBuilder 4 | \xe7\x8a\xb6\xe6\x80\x81:idle/no active sprint\n",
    )
    monkeypatch.setattr(gnd, "read_lease", lambda pane: None)
    monkeypatch.setattr(gnd, "_clear_stale_prompt_residue", lambda pane: False)
    monkeypatch.setattr(gnd, "_pane_current_command", lambda pane: "bash")
    monkeypatch.setattr(
        gnd,
        "_pane_tail",
        lambda pane, lines=80: "✻ Baked for 4m 16s\n❯\u00a0继续执行下一个 dispatch 文件\n",
    )
    monkeypatch.setattr(gnd, "_pane_health", lambda pane: {})

    workers = gnd._discover_workers(dry_run=False)

    assert len(workers) == 1
    assert workers[0]["busy"] is True
    assert workers[0]["unavailable_reason"] == "worker_runtime_not_running"


def test_evaluator_discovery_ignores_expired_lease(monkeypatch) -> None:
    monkeypatch.setattr(gnd, "SESSION", "solar-harness")
    monkeypatch.setattr(gnd, "_pane_exists", lambda pane: True)
    monkeypatch.setattr(gnd, "read_lease", lambda pane: {"expires_at": _ts(-60)})
    monkeypatch.setattr(gnd, "_pane_unavailable_reason", lambda pane: "")
    monkeypatch.setattr(gnd, "_pane_tui_busy", lambda pane: False)

    evaluators = gnd._discover_evaluators(dry_run=False)

    assert len(evaluators) == 1
    assert evaluators[0]["pane"] == "solar-harness:0.3"
    assert evaluators[0]["busy"] is False


def test_clear_stale_prompt_residue_uses_ctrl_c_fallback(monkeypatch) -> None:
    prompt_residue = "✻ Baked for 4m 16s\n────────────────\n❯\u00a0继续执行下一个 dispatch 文件\n────────────────\n"
    idle_prompt = "────────────────\n❯\u00a0\n────────────────\n"
    tails = [prompt_residue, prompt_residue, prompt_residue, idle_prompt]
    sent: list[tuple[str, ...]] = []

    def fake_tail(pane: str, lines: int = 80) -> str:
        return tails.pop(0) if tails else idle_prompt

    def fake_run(cmd, **kwargs):
        sent.append(tuple(cmd[-(len(cmd) - cmd.index("send-keys") - 3):]))

    monkeypatch.setattr(gnd, "_pane_tail", fake_tail)
    monkeypatch.setattr(gnd.subprocess, "run", fake_run)
    monkeypatch.setattr(gnd.time, "sleep", lambda seconds: None)

    assert gnd._clear_stale_prompt_residue("solar-harness-lab:0.3") is True
    assert ("C-a", "C-k") in sent
    assert ("C-u",) in sent
    assert ("C-c",) in sent
