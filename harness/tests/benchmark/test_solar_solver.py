"""Unit tests for the host-side Solar-Harness Terminal-Bench solver."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from harness.lib.benchmark import solar_solver


def test_dag_backend_records_graph_dispatch_dry_run(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    instruction_file = tmp_path / "instruction.txt"
    instruction_file.write_text("Create a result file.\n", encoding="utf-8")
    logs_dir = tmp_path / "logs"
    runtime_harness = tmp_path / "runtime-harness"
    (runtime_harness / "lib").mkdir(parents=True)

    monkeypatch.setenv("SOLAR_HARNESS_DAG_EXECUTOR", "graph-dispatch-dry-run")
    monkeypatch.setenv("SOLAR_HARNESS_DAG_LEAF_BACKEND", "codex")
    monkeypatch.setattr(solar_solver, "_runtime_harness_dir", lambda: runtime_harness)

    def fake_run(cmd, cwd, text, capture_output, timeout, env):
        joined = " ".join(str(part) for part in cmd)
        if "graph_node_dispatcher.py" in joined:
            graph_path = Path(cmd[cmd.index("--graph") + 1])
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            sid = graph["sprint_id"]
            dispatch_file = (
                graph_path.parent
                / "graph-dispatch-harness"
                / "sprints"
                / f"{sid}.N2-dispatch.md"
            )
            dispatch_file.parent.mkdir(parents=True, exist_ok=True)
            dispatch_file.write_text("dispatch dry-run\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"ok": True, "drain": {"processed": 1}}),
                stderr="",
            )
        (Path(cwd) / "result.txt").write_text("ok\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="builder ok\n", stderr="")

    monkeypatch.setattr(solar_solver.subprocess, "run", fake_run)

    result = solar_solver.solve_terminal_task(
        workspace=workspace,
        instruction_file=instruction_file,
        backend="dag",
        model="gpt-5.4",
        logs_dir=logs_dir,
        timeout_sec=30,
    )

    assert result["return_code"] == 0
    graph_dispatch = result["dag"]["graph_dispatch"]
    assert graph_dispatch["enabled"] is True
    assert graph_dispatch["mode"] == "graph-dispatch-dry-run"
    assert graph_dispatch["ok"] is True
    assert Path(graph_dispatch["dispatch_file"]).exists()
    assert (workspace / "result.txt").read_text(encoding="utf-8") == "ok\n"


def test_dag_backend_graph_dispatch_live_does_not_fallback_to_leaf(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    instruction_file = tmp_path / "instruction.txt"
    instruction_file.write_text("Create a result file through live dispatch.\n", encoding="utf-8")
    logs_dir = tmp_path / "logs"
    runtime_harness = tmp_path / "runtime-harness"
    (runtime_harness / "lib").mkdir(parents=True)

    monkeypatch.setenv("SOLAR_HARNESS_DAG_EXECUTOR", "graph-dispatch-live")
    monkeypatch.setenv("SOLAR_HARNESS_DAG_LEAF_BACKEND", "codex")
    monkeypatch.setenv("SOLAR_HARNESS_BENCH_LIVE_TIMEOUT_SEC", "2")
    monkeypatch.setenv("SOLAR_HARNESS_BENCH_LIVE_POLL_SEC", "0.25")
    monkeypatch.setattr(solar_solver, "_runtime_harness_dir", lambda: runtime_harness)

    def fake_run(cmd, cwd, text, capture_output, timeout, env):
        joined = " ".join(str(part) for part in cmd)
        assert "codex exec" not in joined, "live mode must not fallback to leaf codex"
        assert "claude -p" not in joined, "live mode must not fallback to leaf claude"
        if "graph_node_dispatcher.py" not in joined:
            raise AssertionError(f"unexpected subprocess in live mode: {joined}")
        assert env["SOLAR_GRAPH_DISPATCH_ASYNC_SUBMIT"] == "1"
        assert env["SOLAR_GRAPH_DISPATCH_RESTRICT_SESSION"] == "1"
        graph_path = Path(cmd[cmd.index("--graph") + 1])
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        sid = graph["sprint_id"]
        sprints_dir = graph_path.parent / "graph-dispatch-harness" / "sprints"
        sprints_dir.mkdir(parents=True, exist_ok=True)
        (sprints_dir / f"{sid}.N2-dispatch.md").write_text("dispatch live\n", encoding="utf-8")
        (sprints_dir / f"{sid}.N2-handoff.md").write_text("handoff live\n", encoding="utf-8")
        (workspace / "result.txt").write_text("ok\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"ok": True, "drain": {"processed": 1}}),
            stderr="",
        )

    monkeypatch.setattr(solar_solver.subprocess, "run", fake_run)

    result = solar_solver.solve_terminal_task(
        workspace=workspace,
        instruction_file=instruction_file,
        backend="dag",
        model="gpt-5.4",
        logs_dir=logs_dir,
        timeout_sec=30,
    )

    assert result["return_code"] == 0
    graph_dispatch = result["dag"]["graph_dispatch"]
    assert graph_dispatch["mode"] == "graph-dispatch-live"
    assert graph_dispatch["processed"] == 1
    assert graph_dispatch["live_completion"]["completed"] is True
    assert result["dag"]["builder"]["leaf_backend"] == "graph-dispatch-live"
    assert (workspace / "result.txt").read_text(encoding="utf-8") == "ok\n"


def test_dag_backend_graph_dispatch_live_accepts_durable_completion_after_send_failure(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    instruction_file = tmp_path / "instruction.txt"
    instruction_file.write_text("Create a result file through live dispatch.\n", encoding="utf-8")
    logs_dir = tmp_path / "logs"
    runtime_harness = tmp_path / "runtime-harness"
    (runtime_harness / "lib").mkdir(parents=True)

    monkeypatch.setenv("SOLAR_HARNESS_DAG_EXECUTOR", "graph-dispatch-live")
    monkeypatch.setenv("SOLAR_HARNESS_BENCH_LIVE_TIMEOUT_SEC", "2")
    monkeypatch.setenv("SOLAR_HARNESS_BENCH_LIVE_POLL_SEC", "0.25")
    monkeypatch.setattr(solar_solver, "_runtime_harness_dir", lambda: runtime_harness)

    def fake_run(cmd, cwd, text, capture_output, timeout, env):
        joined = " ".join(str(part) for part in cmd)
        assert "codex exec" not in joined
        assert env["SOLAR_GRAPH_DISPATCH_ASYNC_SUBMIT"] == "1"
        graph_path = Path(cmd[cmd.index("--graph") + 1])
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        sid = graph["sprint_id"]
        sprints_dir = graph_path.parent / "graph-dispatch-harness" / "sprints"
        sprints_dir.mkdir(parents=True, exist_ok=True)
        (sprints_dir / f"{sid}.N2-dispatch.md").write_text("dispatch live\n", encoding="utf-8")
        (sprints_dir / f"{sid}.N2-handoff.md").write_text("handoff live\n", encoding="utf-8")
        (workspace / "result.txt").write_text("ok\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            cmd,
            2,
            stdout=json.dumps(
                {
                    "ok": False,
                    "drain": {
                        "processed": 1,
                        "results": [{"ok": False, "reason": "send_failed"}],
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(solar_solver.subprocess, "run", fake_run)

    result = solar_solver.solve_terminal_task(
        workspace=workspace,
        instruction_file=instruction_file,
        backend="dag",
        model="gpt-5.4",
        logs_dir=logs_dir,
        timeout_sec=30,
    )

    graph_dispatch = result["dag"]["graph_dispatch"]
    assert result["return_code"] == 0
    assert graph_dispatch["ok"] is True
    assert graph_dispatch["dispatcher_ok"] is False
    assert graph_dispatch["live_completion"]["completed"] is True
    assert result["dag"]["builder"]["leaf_backend"] == "graph-dispatch-live"


def test_dag_backend_graph_dispatch_failure_blocks_leaf_fallback(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    instruction_file = tmp_path / "instruction.txt"
    instruction_file.write_text("Create a result file.\n", encoding="utf-8")
    logs_dir = tmp_path / "logs"
    runtime_harness = tmp_path / "runtime-harness"
    (runtime_harness / "lib").mkdir(parents=True)

    monkeypatch.setenv("SOLAR_HARNESS_DAG_EXECUTOR", "graph-dispatch-dry-run")
    monkeypatch.setenv("SOLAR_HARNESS_DAG_LEAF_BACKEND", "codex")
    monkeypatch.setattr(solar_solver, "_runtime_harness_dir", lambda: runtime_harness)

    def fake_run(cmd, cwd, text, capture_output, timeout, env):
        joined = " ".join(str(part) for part in cmd)
        assert "codex exec" not in joined, "failed graph-dispatch must not fallback to leaf codex"
        if "graph_node_dispatcher.py" not in joined:
            raise AssertionError(f"unexpected subprocess after graph-dispatch failure: {joined}")
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"ok": True, "drain": {"processed": 0}}),
            stderr="",
        )

    monkeypatch.setattr(solar_solver.subprocess, "run", fake_run)

    result = solar_solver.solve_terminal_task(
        workspace=workspace,
        instruction_file=instruction_file,
        backend="dag",
        model="gpt-5.4",
        logs_dir=logs_dir,
        timeout_sec=30,
    )

    assert result["return_code"] == 2
    assert result["dag"]["graph_dispatch"]["ok"] is False
    assert result["dag"]["builder"]["leaf_backend"] == "graph-dispatch"
    assert not (workspace / "result.txt").exists()
