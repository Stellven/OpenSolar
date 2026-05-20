#!/usr/bin/env python3
"""Gemini CLI/SDK adapter for Solar Harness background workers."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _model_alias(value: str) -> str:
    raw = (value or "gemini").strip().lower()
    aliases = {
        "gemini": "gemini-2.5-pro",
        "gemini-pro": "gemini-2.5-pro",
        "gemini-2.5": "gemini-2.5-pro",
        "gemini-flash": "gemini-2.5-flash",
        "flash": "gemini-2.5-flash",
    }
    return aliases.get(raw, value)


def _sdk_available() -> tuple[bool, str]:
    try:
        import google.genai  # type: ignore  # noqa: F401

        return True, "google.genai"
    except Exception as exc:
        return False, f"google.genai:{type(exc).__name__}"


def doctor() -> dict[str, Any]:
    gemini = shutil.which("gemini")
    sdk_ok, sdk_detail = _sdk_available()
    return {
        "ok": bool(gemini) or sdk_ok,
        "cli": {
            "ok": bool(gemini),
            "path": gemini or "",
        },
        "sdk": {
            "ok": sdk_ok,
            "detail": sdk_detail,
        },
        "auth_hints": {
            "cli": "Gemini CLI subscription/session is used by `gemini` itself.",
            "sdk": "Set GOOGLE_API_KEY or use Application Default Credentials before selecting gemini-sdk.",
        },
    }


def run_cli(prompt: str, model: str, approval_mode: str, output_format: str) -> int:
    gemini = shutil.which("gemini")
    if not gemini:
        print("ERROR: gemini CLI not found", file=sys.stderr)
        return 127
    cmd = [
        gemini,
        "--model",
        _model_alias(model),
        "--approval-mode",
        approval_mode or "auto_edit",
        "--output-format",
        output_format or "text",
        "--prompt",
        prompt,
    ]
    return subprocess.call(cmd)


def run_sdk(prompt: str, model: str) -> int:
    try:
        from google import genai  # type: ignore
    except Exception as exc:
        print(f"ERROR: google-genai SDK not available: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 127
    try:
        client = genai.Client()
        result = client.models.generate_content(model=_model_alias(model), contents=prompt)
        text = getattr(result, "text", None)
        if text:
            print(text)
        else:
            print(result)
        return 0
    except Exception as exc:
        print(f"ERROR: gemini SDK call failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gemini_adapter.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    run = sub.add_parser("run")
    run.add_argument("--backend", choices=["cli", "sdk"], default="cli")
    run.add_argument("--model", default="gemini")
    run.add_argument("--prompt-file", required=True)
    run.add_argument("--approval-mode", default="auto_edit")
    run.add_argument("--output-format", default="text")
    args = parser.parse_args(argv)

    if args.cmd == "doctor":
        print(json.dumps(doctor(), ensure_ascii=False, indent=2))
        return 0 if doctor().get("ok") else 1

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if args.backend == "sdk":
        return run_sdk(prompt, args.model)
    return run_cli(prompt, args.model, args.approval_mode, args.output_format)


if __name__ == "__main__":
    raise SystemExit(main())
