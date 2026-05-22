#!/usr/bin/env python3
"""Command backend adapter for Antigravity multimodal/image tasks."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


IMAGE_RE = re.compile(r"(?P<path>(?:/[^\\s`'\"<>]+|~[^\\s`'\"<>]+)\\.(?:png|jpe?g|webp))", re.I)


def image_paths(text: str) -> list[Path]:
    paths: list[Path] = []
    explicit = os.environ.get("SOLAR_MULTIMODAL_IMAGE", "")
    for item in explicit.split(":"):
        if item.strip():
            paths.append(Path(item).expanduser())
    for match in IMAGE_RE.finditer(text):
        paths.append(Path(match.group("path")).expanduser())
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen and path.exists():
            seen.add(key)
            result.append(path)
    return result


def main() -> int:
    dispatch_file = Path(os.environ.get("SOLAR_MULTI_TASK_DISPATCH_FILE", "")).expanduser()
    if not dispatch_file.exists():
        print("ERROR: SOLAR_MULTI_TASK_DISPATCH_FILE missing", file=sys.stderr)
        return 2

    dispatch = dispatch_file.read_text(encoding="utf-8", errors="replace")
    images = image_paths(dispatch)
    add_dirs = sorted({str(path.parent) for path in images})
    agy = os.environ.get("AGY_BIN", "/Users/lisihao/.local/bin/agy")
    timeout = os.environ.get("AGY_PRINT_TIMEOUT", "10m")

    prompt = "\n".join([
        "You are running as a Solar multimodal/image physical operator.",
        "Read the dispatch below, inspect referenced image files if present, and complete only the requested node.",
        "Do not print secrets. If you cannot inspect an image, state IMAGE_UNSUPPORTED and explain the blocker.",
        "",
        "Referenced image files:",
        "\n".join(f"- {path}" for path in images) if images else "- N/A",
        "",
        dispatch,
    ])

    cmd = [agy, "--dangerously-skip-permissions", "--print-timeout", timeout]
    for directory in add_dirs:
        cmd.extend(["--add-dir", directory])
    cmd.extend(["--print", prompt])
    print("[solar-harness agy-multimodal] cmd=" + " ".join(shlex.quote(part) for part in cmd[:-1]) + " <prompt>")
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
