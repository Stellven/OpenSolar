#!/usr/bin/env python3
"""ruflo_adapter.py — safe read-only Ruflo integration status.

The adapter vendors ruvnet/ruflo and exposes inventory/status to Solar-Harness
without running `ruflo init`, registering MCP, or writing Claude Code hooks.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


HOME = Path.home()
HARNESS = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
RUFLO_DIR = Path(os.environ.get("RUFLO_SOURCE_DIR", HARNESS / "vendor" / "ruflo"))
RUFLO_REPO = "https://github.com/ruvnet/ruflo.git"


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 10) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except Exception as exc:
        return 99, f"{type(exc).__name__}: {exc}"


def _git(args: list[str]) -> str:
    if not RUFLO_DIR.exists():
        return ""
    code, out = _run(["git", *args], cwd=RUFLO_DIR, timeout=5)
    return out.splitlines()[0].strip() if code == 0 and out else ""


def _read_package() -> dict[str, Any]:
    path = RUFLO_DIR / "package.json"
    if not path.exists():
        return {"ok": False, "reason": "package.json missing"}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"ok": False, "reason": f"package.json invalid: {exc}"}
    return {
        "ok": True,
        "name": data.get("name"),
        "version": data.get("version"),
        "description": data.get("description"),
        "bin": data.get("bin", {}),
        "node_engine": (data.get("engines") or {}).get("node"),
    }


def _count_paths() -> dict[str, Any]:
    if RUFLO_DIR.exists():
        by_lower = {str(p).lower(): p for p in RUFLO_DIR.rglob("SKILL.md")}
        by_lower.update({str(p).lower(): p for p in RUFLO_DIR.rglob("skill.md")})
        skill_files = sorted(str(p) for p in by_lower.values())
    else:
        skill_files = []
    plugin_dirs = [p for p in (RUFLO_DIR / "plugins").iterdir() if p.is_dir()] if (RUFLO_DIR / "plugins").exists() else []
    agent_files = list((RUFLO_DIR / ".agents").rglob("*.md")) if (RUFLO_DIR / ".agents").exists() else []
    return {
        "skill_files": len(skill_files),
        "plugins": len(plugin_dirs),
        "agent_markdown_files": len(agent_files),
        "sample_skills": [str(Path(p).relative_to(RUFLO_DIR)) for p in skill_files[:20]],
        "sample_plugins": [p.name for p in plugin_dirs[:40]],
    }


def _case_collision_warnings() -> list[str]:
    warnings: list[str] = []
    code, out = _run(["git", "ls-files"], cwd=RUFLO_DIR, timeout=10)
    if code == 0:
        by_lower: dict[str, list[str]] = {}
        for line in out.splitlines():
            by_lower.setdefault(line.lower(), []).append(line)
        collisions = [paths for paths in by_lower.values() if len(paths) > 1]
        for paths in collisions[:20]:
            warnings.append("case-collision: " + " | ".join(paths))
    return warnings


def status() -> dict[str, Any]:
    exists = RUFLO_DIR.exists()
    pkg = _read_package() if exists else {"ok": False, "reason": "source missing"}
    counts = _count_paths() if exists else {"skill_files": 0, "plugins": 0, "agent_markdown_files": 0}
    warnings = _case_collision_warnings() if exists else []
    return {
        "ok": exists and bool(pkg.get("ok")),
        "integration_level": "basic_usable",
        "mode": "read_only_safe_vendor",
        "source": {
            "path": str(RUFLO_DIR),
            "repo": _git(["remote", "get-url", "origin"]),
            "commit": _git(["rev-parse", "--short", "HEAD"]),
            "exists": exists,
        },
        "package": pkg,
        "inventory": counts,
        "warnings": warnings,
        "blocked_actions": [
            "ruflo init is not run automatically because it writes .claude, hooks, MCP config and workspace files.",
            "MCP server registration is not enabled until a sandboxed command contract is added.",
        ],
    }


def vendor(update: bool = False) -> dict[str, Any]:
    RUFLO_DIR.parent.mkdir(parents=True, exist_ok=True)
    if RUFLO_DIR.exists():
        if update:
            code, out = _run(["git", "-C", str(RUFLO_DIR), "pull", "--ff-only"], timeout=120)
            return {"ok": code == 0, "action": "update", "output": out, "status": status()}
        return {"ok": True, "action": "noop", "status": status()}
    code, out = _run(["git", "clone", "--depth", "1", RUFLO_REPO, str(RUFLO_DIR)], timeout=300)
    return {"ok": code == 0, "action": "clone", "output": out, "status": status()}


def main() -> int:
    ap = argparse.ArgumentParser(prog="ruflo_adapter.py")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("vendor")
    p.add_argument("--json", action="store_true")
    p.add_argument("--update", action="store_true")
    args = ap.parse_args()

    if args.cmd == "vendor":
        data = vendor(update=args.update)
    else:
        data = status()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
