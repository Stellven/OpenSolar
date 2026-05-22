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
import json
import os
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

EVALUATOR_PROTOCOL_FILENAME = "evaluator-verification-protocol.md"

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
# Persona / protocol loading
# ---------------------------------------------------------------------------


def _load_persona(role: str) -> tuple[Optional[Path], Optional[str]]:
    """Return (path, content) for the persona file matching *role*, or (None, None)."""
    candidate = PERSONAS_DIR / f"{role}.md"
    if candidate.exists():
        try:
            return candidate, candidate.read_text(encoding="utf-8")
        except Exception:
            pass
    return None, None


def _load_evaluator_protocol() -> tuple[Optional[Path], Optional[str]]:
    """Return (path, content) for the evaluator verification protocol."""
    path = PERSONAS_DIR / EVALUATOR_PROTOCOL_FILENAME
    if path.exists():
        try:
            return path, path.read_text(encoding="utf-8")
        except Exception:
            pass
    return None, None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _die(msg: str) -> None:
    print(f"[operatord] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _info(msg: str) -> None:
    print(f"[operatord] {msg}")


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

    # ── Persona ───────────────────────────────────────────────────────────────
    persona_path, persona_text = _load_persona(role)
    if persona_path:
        _info(f"persona       = {persona_path}")
        if args.print_persona:
            print("\n" + "─" * 60)
            print(f"# Persona: {role}")
            print("─" * 60)
            print(persona_text)
            print("─" * 60 + "\n")
    else:
        _info(f"persona       = (not found for role '{role}')")

    # ── Evaluator protocol ────────────────────────────────────────────────────
    eval_path: Optional[Path] = None
    if role == "evaluator":
        eval_path, eval_text = _load_evaluator_protocol()
        if eval_path:
            _info(f"eval_protocol = {eval_path}")
            if args.print_persona:
                print("\n" + "─" * 60)
                print("# Evaluator Verification Protocol")
                print("─" * 60)
                print(eval_text)
                print("─" * 60 + "\n")
        else:
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
        "persona_loaded": persona_path is not None,
        "eval_protocol_loaded": eval_path is not None,
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
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
