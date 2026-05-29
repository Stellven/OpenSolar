#!/usr/bin/env python3
"""operatord — Solar Harness operator daemon CLI.

Launches a Solar operator process: resolves the operator config from the
physical-operators registry, loads the appropriate persona and evaluator
protocol, applies the tmux pane title, then emits a structured ready signal.

Usage
-----
    operatord run --operator <id> [options]
    operatord run --help
    operatord list
    operatord --help

Subcommands
-----------
run     Bootstrap one operator instance (persona load + pane title).
list    Print enabled operators from the registry.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
PERSONAS_DIR = HARNESS_DIR / "personas"
PHYSICAL_OPERATORS_PATH = Path(
    os.environ.get(
        "SOLAR_MULTI_TASK_OPERATORS",
        HARNESS_DIR / "config" / "physical-operators.json",
    )
)

# Insert lib directory so the shared persona resolver can be imported regardless
# of the working directory from which operatord is invoked.
_LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from operator_persona import (  # noqa: E402  (import after path setup)
    EVALUATOR_PROTOCOL_FILENAME,
    resolve_persona,
)

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def _load_registry() -> dict[str, Any]:
    if not PHYSICAL_OPERATORS_PATH.exists():
        return {"version": 1, "operators": {}}
    try:
        return json.loads(PHYSICAL_OPERATORS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        _die(f"Cannot read operator registry {PHYSICAL_OPERATORS_PATH}: {exc}")


def _get_operator(operator_id: str) -> dict[str, Any]:
    registry = _load_registry()
    operators = registry.get("operators", {})
    if operator_id not in operators:
        available = ", ".join(sorted(operators.keys())) or "(none)"
        _die(
            f"Operator '{operator_id}' not found in registry.\n"
            f"Available: {available}"
        )
    return dict(operators[operator_id])


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _die(msg: str) -> None:
    print(f"[operatord] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _info(msg: str) -> None:
    print(f"[operatord] {msg}")


# ---------------------------------------------------------------------------
# Daemon helpers
# ---------------------------------------------------------------------------


def _configured_launch_command(config: dict) -> str:
    surface = config.get("surface")
    if isinstance(surface, dict):
        launch_cmd = str(surface.get("launch_cmd") or "").strip()
        if launch_cmd:
            return launch_cmd
    return str(config.get("launch_cmd") or "").strip()


def _claude_model_arg(model: str) -> str:
    value = str(model or "sonnet").strip().lower()
    if "opus" in value:
        return "opus"
    if "sonnet" in value or value in {"claude", "anthropic"}:
        return "sonnet"
    return value or "sonnet"


def _dispatch_file_for_env(result_dir: Path, envelope: dict[str, Any]) -> Path | None:
    dispatch_text = str(envelope.get("dispatch_text") or "").strip()
    if dispatch_text:
        dispatch_file = result_dir / "dispatch.md"
        dispatch_file.write_text(dispatch_text, encoding="utf-8")
        return dispatch_file

    dispatch_file_value = str(envelope.get("dispatch_file") or "").strip()
    if not dispatch_file_value:
        return None

    dispatch_path = Path(dispatch_file_value).expanduser()
    if dispatch_path.exists():
        # Keep a local copy next to result.json for auditability while still
        # pointing the task at the canonical dispatch file.
        try:
            (result_dir / "dispatch.md").write_text(
                dispatch_path.read_text(encoding="utf-8", errors="replace"),
                encoding="utf-8",
            )
        except Exception:
            pass
        return dispatch_path
    return dispatch_path


def _materialize_envelope_context(result_dir: Path, envelope: dict) -> dict[str, str]:
    env: dict[str, str] = {}
    dispatch_file = _dispatch_file_for_env(result_dir, envelope)
    if dispatch_file is not None:
        env["SOLAR_MULTI_TASK_DISPATCH_FILE"] = str(dispatch_file)
        env["DISPATCH_FILE"] = str(dispatch_file)
    envelope_file = result_dir / "envelope.json"
    envelope_file.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    env["SOLAR_OPERATOR_ENVELOPE_JSON"] = str(envelope_file)
    handoff_path = str(envelope.get("handoff_path") or "").strip()
    if handoff_path:
        env["HANDOFF"] = handoff_path
    graph_path = str(envelope.get("graph_path") or "").strip()
    if graph_path:
        env["GRAPH"] = graph_path
    if str(envelope.get("node_id") or "").strip():
        env["NODE_ID"] = str(envelope["node_id"])
    if str(envelope.get("sprint_id") or "").strip():
        env["SID"] = str(envelope["sprint_id"])
    result_path = str(envelope.get("result_path") or "").strip()
    if result_path:
        env["RESULT_PATH"] = result_path
        env["PM_RESULT_PATH"] = result_path
    pm_context = str(envelope.get("pm_context") or "").strip()
    if pm_context:
        env["PM_CONTEXT"] = pm_context
    env["TASK_DIR"] = str(result_dir)
    env["OUTPUT_LOG"] = str(result_dir / "output.log")
    env["HARNESS_DIR"] = str(HARNESS_DIR)
    env["SPRINTS_DIR"] = str(HARNESS_DIR / "sprints")
    return env


def _claude_print_command(config: dict[str, Any]) -> list[str]:
    model = _claude_model_arg(str(config.get("model") or "sonnet"))
    empty_mcp = HARNESS_DIR / "config" / "empty-mcp.json"
    command = "\n".join([
        "export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1",
        "export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1",
        "export DISABLE_NON_ESSENTIAL_MODEL_CALLS=1",
        "export CLAUDE_CODE_MAX_OUTPUT_TOKENS=${CLAUDE_CODE_MAX_OUTPUT_TOKENS:-4096}",
        (
            "claude --dangerously-skip-permissions "
            "--permission-mode bypassPermissions "
            f"--model {shlex.quote(model)} "
            f"--add-dir {shlex.quote(str(HARNESS_DIR))} "
            f"--strict-mcp-config --mcp-config {shlex.quote(str(empty_mcp))} "
            '-p "$(cat "$DISPATCH_FILE")"'
        ),
    ])
    return ["bash", "-lc", command]


def _build_command(config: dict, envelope: dict) -> list[str]:
    """Return the shell command list to execute for this task.

    If the envelope carries an explicit ``command`` override, or if a command
    backend provides a configured launch command, operatord executes that
    command through a shell adapter. For any unsupported backend we still
    default to a safe echo so the daemon can be exercised without credentials
    in test/CI environments.
    """
    backend: str = str(config.get("backend", "local")).lower()

    # Explicit command in the envelope takes highest priority.
    cmd_val = envelope.get("command")
    if cmd_val:
        if isinstance(cmd_val, list):
            return [str(c) for c in cmd_val]
        return ["bash", "-lc", str(cmd_val)]

    launch_cmd = _configured_launch_command(config)
    if backend == "command" and launch_cmd:
        return ["bash", "-lc", launch_cmd]
    if backend == "command":
        configured_command = str(config.get("command") or "").strip()
        if configured_command:
            return ["bash", "-lc", configured_command]

    if backend == "claude-cli":
        return _claude_print_command(config)

    task_id: str = str(envelope.get("task_id", "unknown"))
    objective: str = str(envelope.get("objective", ""))[:120]

    if backend in ("local", "dummy", "echo"):
        return [
            "sh",
            "-c",
            (
                f"echo 'operatord: task={task_id}'; "
                f"echo 'objective={objective}'; "
                "sleep 0.05; "
                "echo 'operatord: completed'"
            ),
        ]

    # Real backends (claude-cli, agy, etc.) in non-interactive daemon context:
    # emit a safe placeholder so the daemon lifecycle can be validated without
    # actually spawning an AI process.
    return [
        "sh",
        "-c",
        (
            f"echo 'operatord: backend={backend} task={task_id}'; "
            "echo 'operatord: local-stub exit 0'; "
            "sleep 0.05"
        ),
    ]


def _is_pm_dispatch_task(envelope: dict[str, Any]) -> bool:
    task_id = str(envelope.get("task_id") or "").strip()
    result_path = str(envelope.get("result_path") or "").strip()
    return task_id.startswith("pm-") or result_path.endswith(".pm-result.md")


def _pm_result_path(envelope: dict[str, Any]) -> Path | None:
    value = str(envelope.get("result_path") or "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def _pm_dispatch_complete_command(task_id: str) -> list[str]:
    return [sys.executable, str(HARNESS_DIR / "tools" / "pm_dispatch.py"), "complete", "--task-id", task_id]


def _parse_utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Subcommand: daemon
# ---------------------------------------------------------------------------


def cmd_daemon(args: argparse.Namespace) -> int:
    """Run the operator as a persistent daemon (or process one task with --once)."""
    import signal
    import subprocess
    import time

    from operator_runtime import (  # noqa: E402
        acquire_operator_lease,
        get_operator_lease,
        get_operator_runtime_state,
        list_inbox_tasks,
        release_operator_lease,
        update_operator_lease_state,
        write_heartbeat,
        write_result,
        HARNESS_DIR as _RT_HARNESS_DIR,
        OPERATOR_RESULTS_DIR,
    )

    operator_id: str = args.operator
    once: bool = args.once
    poll_interval: float = args.poll_interval
    config = _get_operator(operator_id)

    if not config.get("enabled", False) and not args.force:
        _info(
            f"Operator '{operator_id}' is disabled. "
            "Pass --force to proceed anyway."
        )
        return 1

    resolved_persona: str = config.get("persona") or config.get("role", "")

    # ── Signal handling ───────────────────────────────────────────────────────
    _state: dict[str, Any] = {
        "drain": False,
        "current_state": "idle",
        "current_proc": None,
    }

    def _handle_signal(signum: int, frame: Any) -> None:
        _info(f"Signal {signum} received — transitioning to draining")
        _state["drain"] = True
        _state["current_state"] = "draining"
        write_heartbeat(
            operator_id,
            "draining",
            resolved_persona=resolved_persona,
        )

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _info(
        f"Daemon starting — operator_id={operator_id} "
        f"once={once} poll_interval={poll_interval}s"
    )
    write_heartbeat(operator_id, "idle", resolved_persona=resolved_persona)
    _state["current_state"] = "idle"

    processed: int = 0

    while True:
        # ── Drain check ───────────────────────────────────────────────────────
        if _state["drain"]:
            _info("Drain flag set — exiting daemon loop")
            write_heartbeat(operator_id, "idle", resolved_persona=resolved_persona)
            break

        # ── Heartbeat ─────────────────────────────────────────────────────────
        write_heartbeat(
            operator_id,
            _state["current_state"],
            resolved_persona=resolved_persona,
        )

        # ── Poll inbox ────────────────────────────────────────────────────────
        tasks = list_inbox_tasks(operator_id)

        if not tasks:
            if once:
                if processed > 0:
                    # Already processed the one task; exit normally.
                    break
                # Nothing yet — keep waiting.
            time.sleep(poll_interval)
            continue

        # ── Claim first available task ────────────────────────────────────────
        task_id, envelope, envelope_path = tasks[0]

        lease = get_operator_lease(operator_id)
        if lease is None or lease.get("task_id") != task_id:
            recovered_lease = None
            if lease is None:
                try:
                    recovered_lease = acquire_operator_lease(
                        operator_id=operator_id,
                        task_id=task_id,
                        sprint_id=str(envelope.get("sprint_id") or ""),
                        node_id=str(envelope.get("node_id") or ""),
                        ttl_seconds=int(envelope.get("lease_ttl_seconds") or 3600),
                        initial_state="leased",
                    )
                    lease = recovered_lease
                    _info(f"Recovered missing/expired lease for task {task_id}")
                except Exception as exc:
                    _info(f"Lease recovery failed for task {task_id}: {exc}")
            # Lease missing or for a different task; skip and wait.
            if lease is not None and lease.get("task_id") == task_id:
                pass
            else:
                _info(
                    f"No valid lease found for task {task_id} "
                    f"(current lease task: {lease.get('task_id') if lease else 'none'})"
                )
                time.sleep(poll_interval)
                continue

        if lease.get("state") not in ("leased",):
            _info(f"Task {task_id} lease state={lease.get('state')} — skipping")
            time.sleep(poll_interval)
            continue

        _info(f"Claiming task {task_id}")
        try:
            update_operator_lease_state(operator_id, "running")
        except RuntimeError as exc:
            _info(f"Cannot transition lease to running: {exc}")
            time.sleep(poll_interval)
            continue

        _state["current_state"] = "running"
        write_heartbeat(
            operator_id,
            "running",
            current_task_id=task_id,
            resolved_persona=resolved_persona,
        )

        # ── Execute ───────────────────────────────────────────────────────────
        sprint_id: str = str(envelope.get("sprint_id", ""))
        node_id: str = str(envelope.get("node_id", ""))
        started_at: str = _now_utc()
        result_status: str = "failed"
        exit_code: int = -1
        log_lines: list[str] = []

        result_dir = OPERATOR_RESULTS_DIR / operator_id / task_id
        result_dir.mkdir(parents=True, exist_ok=True)
        log_path = result_dir / "output.log"
        exec_env = os.environ.copy()
        exec_env.update(_materialize_envelope_context(result_dir, envelope))
        pm_result_path = _pm_result_path(envelope) if _is_pm_dispatch_task(envelope) else None
        if pm_result_path is not None:
            try:
                pm_result_path.parent.mkdir(parents=True, exist_ok=True)
                if pm_result_path.exists():
                    pm_result_path.unlink()
            except Exception as exc:
                _info(f"Unable to clear stale pm result {pm_result_path}: {exc}")

        cmd = _build_command(config, envelope)
        _info(f"Executing: {' '.join(shlex.quote(part) for part in cmd[:8])}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=exec_env,
            )
            _state["current_proc"] = proc

            with open(log_path, "w", encoding="utf-8") as log_f:
                assert proc.stdout is not None
                for line in proc.stdout:
                    from operator_runtime import scrub_secrets  # noqa: E402
                    scrubbed = scrub_secrets(line)
                    log_f.write(scrubbed)
                    log_lines.append(scrubbed.rstrip())

            proc.wait()
            exit_code = proc.returncode
            result_status = "completed" if exit_code == 0 else "failed"

        except Exception as exc:
            _info(f"Execution error: {exc}")
            log_lines.append(f"[ERROR] {exc}")
            result_status = "error"
        finally:
            _state["current_proc"] = None

        if _state["drain"]:
            # Signal arrived mid-execution; mark draining then tidy up.
            result_status = "draining"
            _state["current_state"] = "draining"

        finished_at: str = _now_utc()

        if result_status == "completed" and pm_result_path is not None:
            if not pm_result_path.exists():
                log_lines.append(f"[ERROR] missing pm_result: {pm_result_path}")
                result_status = "failed_missing_pm_result"
                exit_code = exit_code or 65
            else:
                try:
                    started_dt = _parse_utc(started_at)
                    result_dt = dt.datetime.fromtimestamp(
                        pm_result_path.stat().st_mtime,
                        tz=dt.timezone.utc,
                    )
                    if result_dt < started_dt:
                        log_lines.append(f"[ERROR] stale pm_result predates current run: {pm_result_path}")
                        result_status = "failed_stale_pm_result"
                        exit_code = exit_code or 66
                except Exception:
                    pass

        if result_status == "completed" and pm_result_path is not None:
            try:
                completed = subprocess.run(
                    _pm_dispatch_complete_command(task_id),
                    capture_output=True,
                    text=True,
                    env=exec_env,
                    timeout=30,
                )
                stdout = completed.stdout.strip()
                stderr = completed.stderr.strip()
                if stdout:
                    log_lines.append(stdout)
                if stderr:
                    log_lines.append(stderr)
                if completed.returncode != 0:
                    log_lines.append(
                        f"[WARN] pm_dispatch complete returned {completed.returncode} for {task_id}"
                    )
            except Exception as exc:
                log_lines.append(f"[WARN] pm_dispatch complete hook failed: {exc}")

        # ── Write result artifact ─────────────────────────────────────────────
        log_tail = "\n".join(log_lines[-50:])
        result_path = write_result(
            operator_id=operator_id,
            task_id=task_id,
            sprint_id=sprint_id,
            node_id=node_id,
            status=result_status,
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            log_tail=log_tail,
        )
        _info(f"Result written: {result_path}")

        # ── Cleanup ───────────────────────────────────────────────────────────
        try:
            envelope_path.unlink()
        except Exception:
            pass

        try:
            release_operator_lease(operator_id, reason=result_status)
        except Exception:
            pass

        processed += 1
        _state["current_state"] = "idle"
        write_heartbeat(operator_id, "idle", resolved_persona=resolved_persona)
        _info(f"Task {task_id} done: {result_status} (exit={exit_code})")

        if once:
            break

        if _state["drain"]:
            break

        time.sleep(poll_interval)

    write_heartbeat(operator_id, "idle", resolved_persona=resolved_persona)
    return 0


def _now_utc() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Subcommand: run
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    """Bootstrap an operator: load persona, apply pane title, emit ready."""
    # Lazy import to keep top-level clean
    try:
        from operator_naming import (  # type: ignore[import]
            canonical_operator_id,
            pane_title,
            apply_pane_title,
        )
    except ImportError:
        # Fallback if run from outside tools/ directory
        _tools_dir = Path(__file__).parent
        sys.path.insert(0, str(_tools_dir))
        from operator_naming import (  # type: ignore[import]
            canonical_operator_id,
            pane_title,
            apply_pane_title,
        )

    operator_id: str = args.operator
    config = _get_operator(operator_id)

    role: str = config.get("role", "builder")
    model: str = config.get("model", "")
    enabled: bool = config.get("enabled", False)

    # Warn but do not block on disabled operators (useful for testing)
    if not enabled and not args.force:
        _info(
            f"Operator '{operator_id}' is marked disabled "
            f"(reason: {config.get('disabled_reason', 'unknown')}). "
            "Pass --force to proceed anyway."
        )
        return 1

    # ── Canonical ID ─────────────────────────────────────────────────────────
    canon_id = canonical_operator_id(operator_id, config)
    _info(f"canonical_id  = {canon_id}")
    _info(f"role          = {role}")
    _info(f"model         = {model or '(unknown)'}")
    _info(f"display_name  = {config.get('display_name', operator_id)}")

    # ── Persona & evaluator protocol ──────────────────────────────────────────
    pr = None
    try:
        pr = resolve_persona(operator_id, config, PERSONAS_DIR)
    except RuntimeError as exc:
        _info(f"persona       = (not found: {exc})")

    if pr is not None:
        _info(f"persona       = {pr.persona_path}")
        if args.print_persona:
            print("\n" + "─" * 60)
            print(f"# Persona: {pr.persona_name}")
            print("─" * 60)
            print(pr.persona_text)
            print("─" * 60 + "\n")

        if pr.eval_protocol_loaded:
            _info(f"eval_protocol = {pr.eval_protocol_path}")
            if args.print_persona:
                print("\n" + "─" * 60)
                print("# Evaluator Verification Protocol")
                print("─" * 60)
                print(pr.eval_protocol_text)
                print("─" * 60 + "\n")
        elif pr.persona_name == "evaluator":
            _info(f"eval_protocol = (not found: {EVALUATOR_PROTOCOL_FILENAME})")

    # ── Pane title ────────────────────────────────────────────────────────────
    title = pane_title(
        operator_id=operator_id,
        role=role,
        config=config,
    )
    _info(f"pane_title    = {title}")
    pane_target = args.pane_id or os.environ.get("TMUX_PANE")
    apply_pane_title(title, pane_id=pane_target)

    # ── Ready signal ──────────────────────────────────────────────────────────
    ready: dict[str, Any] = {
        "status": "ready",
        "operator_id": operator_id,
        "canonical_id": canon_id,
        "role": role,
        "model": model,
        "persona_loaded": pr is not None,
        "eval_protocol_loaded": pr is not None and pr.eval_protocol_loaded,
        "pane_title": title,
    }
    if args.json:
        print(json.dumps(ready, indent=2))

    return 0


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    registry = _load_registry()
    operators = registry.get("operators", {})
    if not operators:
        _info("No operators registered.")
        return 0

    if args.json:
        print(json.dumps(operators, indent=2))
        return 0

    fmt = "  {:<42} {:<12} {:<14} {:<8}"
    print(fmt.format("ID", "ROLE", "VENDOR/BACKEND", "ENABLED"))
    print("  " + "-" * 80)
    for oid, cfg in sorted(operators.items()):
        print(
            fmt.format(
                oid[:42],
                str(cfg.get("role", "?"))[:12],
                str(cfg.get("backend", cfg.get("provider", "?")))[:14],
                "yes" if cfg.get("enabled") else "no",
            )
        )
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="operatord",
        description="Solar Harness operator daemon — bootstrap and manage operator instances.",
    )
    sub = parser.add_subparsers(dest="subcommand", metavar="<subcommand>")

    # ── run ──────────────────────────────────────────────────────────────────
    run_p = sub.add_parser(
        "run",
        help="Bootstrap an operator instance (load persona, apply pane title).",
        description=(
            "Bootstrap a Solar Harness operator: resolve config from the physical-operators "
            "registry, load the operator persona file, load the evaluator verification protocol "
            "when the role is 'evaluator', apply the tmux pane title, and emit a ready signal."
        ),
    )
    run_p.add_argument(
        "--operator",
        required=True,
        metavar="ID",
        help="Operator ID from physical-operators.json (e.g. mini-claude-sonnet-builder).",
    )
    run_p.add_argument(
        "--harness-dir",
        metavar="PATH",
        default=str(HARNESS_DIR),
        help=f"Path to the Solar Harness root directory (default: {HARNESS_DIR}).",
    )
    run_p.add_argument(
        "--pane-id",
        metavar="PANE",
        default=None,
        help="Explicit tmux pane target (e.g. %%3). Defaults to $TMUX_PANE.",
    )
    run_p.add_argument(
        "--force",
        action="store_true",
        help="Run even if the operator is disabled in the registry.",
    )
    run_p.add_argument(
        "--print-persona",
        action="store_true",
        help="Print the full persona and evaluator protocol text to stdout.",
    )
    run_p.add_argument(
        "--json",
        action="store_true",
        help="Emit the ready signal as JSON.",
    )

    # ── list ─────────────────────────────────────────────────────────────────
    list_p = sub.add_parser(
        "list",
        help="List operators registered in physical-operators.json.",
    )
    list_p.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON.",
    )

    # ── daemon ───────────────────────────────────────────────────────────────
    daemon_p = sub.add_parser(
        "daemon",
        help="Run the operator as a persistent daemon that polls its inbox.",
        description=(
            "Bootstrap the operator and enter a polling loop. "
            "When a task envelope appears in run/operator-inbox/<id>/, the daemon "
            "claims it, executes the backend command, writes result artifacts, "
            "and returns to idle. Use --once to process exactly one task then exit."
        ),
    )
    daemon_p.add_argument(
        "--operator",
        required=True,
        metavar="ID",
        help="Operator ID from physical-operators.json.",
    )
    daemon_p.add_argument(
        "--once",
        action="store_true",
        help="Process one task then exit (useful for testing and CI).",
    )
    daemon_p.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        metavar="SECS",
        help="Seconds between inbox polls (default: 1.0).",
    )
    daemon_p.add_argument(
        "--force",
        action="store_true",
        help="Run even if the operator is disabled in the registry.",
    )
    daemon_p.add_argument(
        "--harness-dir",
        metavar="PATH",
        default=str(HARNESS_DIR),
        help=f"Path to the Solar Harness root directory (default: {HARNESS_DIR}).",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Update HARNESS_DIR from --harness-dir if provided by run subcommand
    if hasattr(args, "harness_dir") and args.harness_dir:
        global HARNESS_DIR, PERSONAS_DIR, PHYSICAL_OPERATORS_PATH
        HARNESS_DIR = Path(args.harness_dir)
        PERSONAS_DIR = HARNESS_DIR / "personas"
        PHYSICAL_OPERATORS_PATH = Path(
            os.environ.get(
                "SOLAR_MULTI_TASK_OPERATORS",
                HARNESS_DIR / "config" / "physical-operators.json",
            )
        )

    if args.subcommand == "run":
        return cmd_run(args)
    elif args.subcommand == "list":
        return cmd_list(args)
    elif args.subcommand == "daemon":
        return cmd_daemon(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
