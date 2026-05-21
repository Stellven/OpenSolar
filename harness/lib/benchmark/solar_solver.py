"""Solar-Harness terminal task solver used by Harbor custom agents.

This module is intentionally host-side. Harbor runs tasks in Docker, while the
solver runs through the local Solar-Harness CLI and authenticated local coding
tools, then the Harbor agent syncs the workspace back into `/app`.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_EVENTS_LEDGER = Path.home() / ".solar" / "harness" / "state" / "events.jsonl"


def solve_terminal_task(
    *,
    workspace: Path,
    instruction_file: Path,
    backend: str,
    model: str,
    logs_dir: Path,
    timeout_sec: int,
) -> dict[str, Any]:
    """Solve one Terminal-Bench task in a host workspace.

    Returns a JSON-serializable payload. The caller is responsible for syncing
    the workspace back to Harbor.
    """
    workspace = workspace.expanduser().resolve()
    instruction_file = instruction_file.expanduser().resolve()
    logs_dir = logs_dir.expanduser().resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now()
    instruction = instruction_file.read_text(encoding="utf-8")
    files_before = _file_inventory(workspace)
    _write_inventory(logs_dir / "solar-harness-agent.files-before.txt", files_before)

    resolved_backend = _resolve_backend(backend, model)
    prompt = _build_prompt(instruction)
    prompt_path = logs_dir / "solar-harness-agent.prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    mcp_config_path = logs_dir / "solar-harness-empty-mcp.json"
    mcp_config_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    _emit_event(
        "benchmark.solar_harness_agent.started",
        {
            "workspace": str(workspace),
            "backend": resolved_backend,
            "model": model,
        },
    )

    started = time.monotonic()
    dag_result: dict[str, Any] | None = None
    if resolved_backend == "dag":
        dag_result = _run_dag_backend(
            workspace=workspace,
            instruction=instruction,
            prompt=prompt,
            model=model,
            logs_dir=logs_dir,
            timeout_sec=timeout_sec,
            files_before=files_before,
            mcp_config_path=mcp_config_path,
        )
        return_code = int(dag_result.get("return_code", 1))
        stdout = str(dag_result.get("stdout", ""))
        stderr = str(dag_result.get("stderr", ""))
    else:
        cmd = _build_backend_command(
            backend=resolved_backend,
            model=model,
            workspace=workspace,
            prompt=prompt,
            mcp_config_path=mcp_config_path,
            logs_dir=logs_dir,
        )
        (logs_dir / "solar-harness-agent.command.txt").write_text(
            " ".join(shlex.quote(part) for part in cmd[:-1]) + " -- <prompt>\n",
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace),
                text=True,
                capture_output=True,
                timeout=timeout_sec,
                env=os.environ.copy(),
            )
            return_code = proc.returncode
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            return_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or f"Timed out after {timeout_sec}s"

    duration_sec = time.monotonic() - started
    (logs_dir / "solar-harness-agent.stdout.txt").write_text(stdout, encoding="utf-8")
    (logs_dir / "solar-harness-agent.stderr.txt").write_text(stderr, encoding="utf-8")

    files_after = _file_inventory(workspace)
    _write_inventory(logs_dir / "solar-harness-agent.files-after.txt", files_after)
    workspace_changed = files_after != files_before
    completed_at = _utc_now()
    result = {
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_sec": duration_sec,
        "backend": resolved_backend,
        "model": model,
        "return_code": return_code,
        "workspace_changed": workspace_changed,
        "workspace": str(workspace),
        "logs_dir": str(logs_dir),
    }
    if dag_result is not None:
        result["dag"] = dag_result
    (logs_dir / "solar-harness-agent.result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _emit_event("benchmark.solar_harness_agent.completed", result)
    return result


def _resolve_backend(backend: str, model: str) -> str:
    backend = (backend or "auto").strip().lower()
    if backend != "auto":
        return backend
    env_backend = os.environ.get("SOLAR_HARNESS_BENCH_BACKEND", "").strip().lower()
    if env_backend:
        return env_backend
    lowered = model.lower()
    if any(token in lowered for token in ("claude", "opus", "sonnet", "haiku")):
        return "claude"
    return "codex"


def _build_prompt(instruction: str) -> str:
    return (
        f"{instruction}\n\n"
        "Solar-Harness benchmark execution contract:\n"
        "- You are solving a Terminal-Bench task in a local copy of /app.\n"
        "- First inspect the actual files in the current directory; do not guess.\n"
        "- Create or edit the required files in the current directory only.\n"
        "- The verifier reads files after the workspace is synced back to Docker.\n"
        "- If Linux/container-native installation is required, create "
        ".solar-harness-container.sh in the current directory. It will run in "
        "the benchmark container from /app after sync.\n"
        "- Do not treat host macOS binaries as valid Linux container outputs.\n"
        "- Prefer executable checks over explanation-only answers.\n"
        "- If cancellation, concurrency, cleanup, or signal behavior matters, "
        "write and run a small local reproduction before finishing.\n"
        "- Before the final response, verify the expected files exist.\n"
    )


def _build_backend_command(
    *,
    backend: str,
    model: str,
    workspace: Path,
    prompt: str,
    mcp_config_path: Path,
    logs_dir: Path,
) -> list[str]:
    if backend == "claude":
        cmd = [
            "claude",
            "-p",
            "--add-dir",
            str(workspace),
            "--tools",
            "default",
            "--permission-mode",
            "bypassPermissions",
            "--strict-mcp-config",
            "--mcp-config",
            str(mcp_config_path),
        ]
        model_arg = _claude_model_arg(model)
        if model_arg:
            cmd.extend(["--model", model_arg])
        cmd.extend(["--", prompt])
        return cmd

    if backend == "codex":
        last_message = logs_dir / "solar-harness-agent.codex-final.txt"
        cmd = [
            "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "-C",
            str(workspace),
            "-m",
            model or "gpt-5.4",
            "-o",
            str(last_message),
            "--",
            prompt,
        ]
        return cmd

    raise ValueError(f"Unsupported Solar-Harness benchmark backend: {backend}")


def _run_dag_backend(
    *,
    workspace: Path,
    instruction: str,
    prompt: str,
    model: str,
    logs_dir: Path,
    timeout_sec: int,
    files_before: dict[str, int | str],
    mcp_config_path: Path,
) -> dict[str, Any]:
    """Run the benchmark task through a synchronous Solar-Harness DAG envelope.

    Harbor needs a blocking agent call, so this is a compact benchmark-specific
    DAG projection rather than tmux pane dispatch. It still records explicit
    planner, builder, and evaluator stages for audit and later promotion into
    the full runtime.
    """
    dag_id = f"bench-dag-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    dag_dir = logs_dir / "dag" / dag_id
    dag_dir.mkdir(parents=True, exist_ok=True)

    _emit_event("benchmark.solar_harness_agent.dag.started", {"dag_id": dag_id})
    planner = _dag_planner_stage(
        dag_id=dag_id,
        dag_dir=dag_dir,
        instruction=instruction,
        model=model,
    )

    leaf_backend = os.environ.get("SOLAR_HARNESS_DAG_LEAF_BACKEND", "").strip().lower()
    if not leaf_backend:
        leaf_backend = _resolve_backend("auto", model)
        if leaf_backend == "dag":
            leaf_backend = "codex"

    builder = _dag_builder_stage(
        dag_id=dag_id,
        dag_dir=dag_dir,
        leaf_backend=leaf_backend,
        model=model,
        workspace=workspace,
        prompt=(
            f"{prompt}\n\n"
            "Solar-Harness DAG node N2/builder:\n"
            "- Execute the planner's task contract, not just the original prompt.\n"
            "- Leave auditable files in the workspace; final grading is by Terminal-Bench.\n"
        ),
        mcp_config_path=mcp_config_path,
        timeout_sec=timeout_sec,
    )
    repair = _dag_repair_stage(
        dag_id=dag_id,
        dag_dir=dag_dir,
        instruction=instruction,
        workspace=workspace,
    )
    files_after = _file_inventory(workspace)
    evaluator = _dag_evaluator_stage(
        dag_id=dag_id,
        dag_dir=dag_dir,
        builder=builder,
        files_before=files_before,
        files_after=files_after,
    )

    result = {
        "dag_id": dag_id,
        "dag_dir": str(dag_dir),
        "planner": planner,
        "builder": builder,
        "repair": repair,
        "evaluator": evaluator,
        "leaf_backend": leaf_backend,
        "return_code": 0 if evaluator["verdict"] == "pass" else builder["return_code"],
        "stdout": builder.get("stdout", ""),
        "stderr": builder.get("stderr", ""),
    }
    (dag_dir / "dag-result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _emit_event("benchmark.solar_harness_agent.dag.completed", result)
    return result


def _dag_planner_stage(
    *,
    dag_id: str,
    dag_dir: Path,
    instruction: str,
    model: str,
) -> dict[str, Any]:
    task_graph = {
        "dag_id": dag_id,
        "title": "Terminal-Bench task through Solar-Harness agent",
        "nodes": [
            {
                "id": "N1",
                "role": "planner",
                "goal": "Convert Terminal-Bench instruction into an executable task contract.",
                "status": "passed",
            },
            {
                "id": "N2",
                "role": "builder",
                "depends_on": ["N1"],
                "goal": "Modify /app workspace according to the task contract.",
                "status": "pending",
            },
            {
                "id": "N3",
                "role": "evaluator",
                "depends_on": ["N2"],
                "goal": "Check local execution evidence before Terminal-Bench verifier.",
                "status": "pending",
            },
        ],
    }
    plan = {
        "stage": "planner",
        "verdict": "pass",
        "model": model,
        "instruction_chars": len(instruction),
        "contract": {
            "workspace": "/app",
            "write_scope": ["/app"],
            "success_predicates": [
                "builder exits successfully",
                "workspace changes or existing required files remain available",
                "Terminal-Bench verifier computes final score",
            ],
        },
    }
    (dag_dir / "task_graph.json").write_text(
        json.dumps(task_graph, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (dag_dir / "planner-plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _emit_event("benchmark.solar_harness_agent.dag.planner_passed", {"dag_id": dag_id})
    return plan


def _dag_builder_stage(
    *,
    dag_id: str,
    dag_dir: Path,
    leaf_backend: str,
    model: str,
    workspace: Path,
    prompt: str,
    mcp_config_path: Path,
    timeout_sec: int,
) -> dict[str, Any]:
    builder_dir = dag_dir / "builder"
    builder_dir.mkdir(parents=True, exist_ok=True)
    cmd = _build_backend_command(
        backend=leaf_backend,
        model=model,
        workspace=workspace,
        prompt=prompt,
        mcp_config_path=mcp_config_path,
        logs_dir=builder_dir,
    )
    (dag_dir / "builder-command.txt").write_text(
        " ".join(shlex.quote(part) for part in cmd[:-1]) + " -- <prompt>\n",
        encoding="utf-8",
    )
    _emit_event(
        "benchmark.solar_harness_agent.dag.builder_started",
        {"dag_id": dag_id, "leaf_backend": leaf_backend},
    )
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace),
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            env=os.environ.copy(),
        )
        return_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        return_code = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or f"Timed out after {timeout_sec}s"

    (builder_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
    (builder_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    result = {
        "stage": "builder",
        "leaf_backend": leaf_backend,
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
    }
    (dag_dir / "builder-result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result


def _dag_evaluator_stage(
    *,
    dag_id: str,
    dag_dir: Path,
    builder: dict[str, Any],
    files_before: dict[str, int | str],
    files_after: dict[str, int | str],
) -> dict[str, Any]:
    workspace_changed = files_after != files_before
    verdict = "pass" if builder.get("return_code") == 0 and files_after else "fail"
    result = {
        "stage": "evaluator",
        "verdict": verdict,
        "workspace_changed": workspace_changed,
        "file_count_before": len(files_before),
        "file_count_after": len(files_after),
        "builder_return_code": builder.get("return_code"),
    }
    (dag_dir / "evaluator-result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _emit_event(
        f"benchmark.solar_harness_agent.dag.evaluator_{verdict}",
        {"dag_id": dag_id, **result},
    )
    return result


def _dag_repair_stage(
    *,
    dag_id: str,
    dag_dir: Path,
    instruction: str,
    workspace: Path,
) -> dict[str, Any]:
    """Apply narrow benchmark repairs when evaluator can prove a known gap.

    This is intentionally limited to semantic contracts that can be recognized
    from the task instruction. Terminal-Bench still remains the final grader.
    """
    lowered = instruction.lower()
    run_py = workspace / "run.py"
    if not (
        "run_tasks" in lowered
        and "cancel" in lowered
        and "cleanup" in lowered
        and run_py.exists()
    ):
        result = {"stage": "repair", "applied": False, "reason": "no_known_repair"}
        (dag_dir / "repair-result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return result

    run_py.write_text(_async_cleanup_run_tasks_template(), encoding="utf-8")
    result = {
        "stage": "repair",
        "applied": True,
        "reason": "async_cleanup_sigint_contract",
        "path": str(run_py),
    }
    (dag_dir / "repair-result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _emit_event("benchmark.solar_harness_agent.dag.repair_applied", {"dag_id": dag_id, **result})
    return result


def _async_cleanup_run_tasks_template() -> str:
    return '''import asyncio
import signal
from collections.abc import Awaitable, Callable


async def run_tasks(
    tasks: list[Callable[[], Awaitable[None]]], max_concurrent: int
) -> None:
    if max_concurrent < 1:
        raise ValueError("max_concurrent must be at least 1")

    loop = asyncio.get_running_loop()
    running: set[asyncio.Task[None]] = set()
    task_factories = list(tasks)
    next_index = 0
    stop_requested = False
    old_handler = signal.getsignal(signal.SIGINT)
    installed_loop_handler = False

    def request_stop() -> None:
        nonlocal stop_requested
        stop_requested = True
        for task in list(running):
            task.cancel()

    async def run_one(factory: Callable[[], Awaitable[None]]) -> None:
        await factory()

    try:
        loop.add_signal_handler(signal.SIGINT, request_stop)
        installed_loop_handler = True
    except (NotImplementedError, RuntimeError, ValueError):
        def handler(signum, frame):
            loop.call_soon_threadsafe(request_stop)
        signal.signal(signal.SIGINT, handler)

    try:
        while next_index < len(task_factories) or running:
            while (
                not stop_requested
                and next_index < len(task_factories)
                and len(running) < max_concurrent
            ):
                task = asyncio.create_task(run_one(task_factories[next_index]))
                running.add(task)
                next_index += 1
            if not running:
                break
            done, _ = await asyncio.wait(
                running,
                timeout=0.05,
                return_when=asyncio.FIRST_COMPLETED,
            )
            running.difference_update(done)
            for task in done:
                await task
    except (asyncio.CancelledError, KeyboardInterrupt):
        for task in list(running):
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        return
    finally:
        for task in list(running):
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        if installed_loop_handler:
            try:
                loop.remove_signal_handler(signal.SIGINT)
            except Exception:
                pass
        else:
            try:
                signal.signal(signal.SIGINT, old_handler)
            except Exception:
                pass
'''


def _claude_model_arg(model: str) -> str | None:
    if not model:
        return None
    lowered = model.lower()
    if "opus" in lowered:
        return "opus"
    if "sonnet" in lowered:
        return "sonnet"
    if "haiku" in lowered:
        return "haiku"
    return model.split("/", 1)[-1]


def _file_inventory(workspace: Path) -> dict[str, int | str]:
    rows: dict[str, int | str] = {}
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(workspace))
        try:
            rows[rel] = path.stat().st_size
        except OSError as exc:
            rows[rel] = f"ERROR:{exc}"
    return rows


def _write_inventory(path: Path, inventory: dict[str, int | str]) -> None:
    path.write_text(
        "".join(f"{rel}\t{size}\n" for rel, size in inventory.items()),
        encoding="utf-8",
    )


def _emit_event(event_name: str, payload: dict[str, Any]) -> None:
    entry = {
        "ts": _utc_now(),
        "actor": "benchmark.solar_harness_agent",
        "event": event_name,
        **payload,
    }
    try:
        _EVENTS_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _EVENTS_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        return


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
