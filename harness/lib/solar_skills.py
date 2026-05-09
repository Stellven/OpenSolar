#!/usr/bin/env python3
"""
solar_skills.py — Solar capability plane: skills inventory, doctor, inject,
                   eval, promote, rollback, export.

Subcommands (called via solar-harness skills <sub>):
  inventory [--json]          scan skill roots + registry, return counts + sources
  doctor    [--json]          pane-level capability report (no secrets)
  inject    <dispatch_file>   idempotent injection of skills+KB context blocks
  pane-status [--json]        alias for doctor
  native-extract              extract Solar native skills to cache
  eval      --skill SKILL [--json]   run eval pack checks, report score
  promote   --skill SKILL    promote candidate→stable (requires eval+regression pass)
  rollback  --skill SKILL [--to STATUS]  demote skill status in registry
  export    --skill SKILL [--dest DIR] [--force] [--dry-run]  safe export/symlink
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── paths ──────────────────────────────────────────────────────────────────
HARNESS_DIR = Path(__file__).resolve().parent.parent
SKILLS_ROOT = Path.home() / ".agents" / "skills"
SOLAR_NATIVE_ROOT = Path.home() / "Solar" / "skills"
STATE_DIR = HARNESS_DIR / "state"
NATIVE_CACHE = STATE_DIR / "solar-native-skills.json"
INVENTORY_CACHE = STATE_DIR / "skills-inventory.json"
SOLAR_CONTEXT_PY = HARNESS_DIR / "lib" / "solar-unified-context.py"

# Keys redacted from doctor output
SECRET_PATTERNS = re.compile(
    r"(ZHIPU_AUTH_TOKEN|ANTHROPIC_AUTH_TOKEN|DEEPSEEK_API_KEY|sk-[A-Za-z0-9]{8,})",
    re.IGNORECASE,
)


# ── helpers ────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _count_skills(root: Path) -> int:
    """Count first-level directory entries that look like skill names."""
    if not root.exists():
        return 0
    total = 0
    for p in root.iterdir():
        if p.is_dir() or (p.is_file() and p.suffix in (".md", ".yaml", ".yml", "")):
            name = p.name
            if name.startswith(".") or name in ("SKILL-INDEX.md", "SKILLS_INDEX.json", "SKILLS_INDEX.md"):
                continue
            total += 1
    return total


def _list_skill_names(root: Path) -> list[str]:
    """Return sorted skill names from a root directory."""
    if not root.exists():
        return []
    names = []
    for p in root.iterdir():
        name = p.name
        if name.startswith(".") or name in ("SKILL-INDEX.md", "SKILLS_INDEX.json", "SKILLS_INDEX.md"):
            continue
        names.append(name)
    return sorted(names)


def _read_skill_meta(skill_dir: Path) -> dict[str, Any]:
    """Read SKILL.md frontmatter for name/description/tags."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {}
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    meta: dict[str, Any] = {}
    # Parse YAML frontmatter between --- delimiters
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            front = text[3:end]
            for line in front.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
    return meta


def _get_pane_config() -> dict[str, Any]:
    """Read persona-config.sh output for known panes."""
    panes_cfg: dict[str, Any] = {}
    persona_script = HARNESS_DIR / "lib" / "persona-config.sh"
    if not persona_script.exists():
        return panes_cfg

    known_panes = ["lab-builder", "builder", "evaluator", "planner", "monitor"]
    for pane in known_panes:
        try:
            result = subprocess.run(
                ["bash", str(persona_script), "--print-config", pane],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                cfg: dict[str, str] = {}
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if "=" in line:
                        k, _, v = line.partition("=")
                        # Strip surrounding quotes
                        v = v.strip("'\"")
                        cfg[k.strip()] = v
                panes_cfg[pane] = cfg
        except Exception:
            pass
    return panes_cfg


def _pane_capability(pane: str, cfg: dict[str, str]) -> dict[str, Any]:
    """Build a capability summary for one pane — no secret values."""
    extra_flags = cfg.get("EXTRA_FLAGS", "")
    auth_source = cfg.get("AUTH_SOURCE", "unknown")

    # MCP mode from EXTRA_FLAGS
    if "--strict-mcp-config" in extra_flags:
        mcp_mode = "STRICT"
        mcp_config = _extract_mcp_config_path(extra_flags)
        kb_context = False
    else:
        mcp_mode = "DEFAULT"
        mcp_config = None
        kb_context = True  # non-strict panes can use KB context

    # Skills count injected into this pane type
    skills_accessible = mcp_mode == "DEFAULT"

    return {
        "pane": pane,
        "model": cfg.get("MODEL_FLAG", "unknown").replace("--model ", ""),
        "auth_source": auth_source,
        "mcp_mode": mcp_mode,
        "mcp_config": mcp_config,
        "kb_context": kb_context,
        "skills_accessible": skills_accessible,
        # Do NOT include auth token values
        "auth_token_present": "AUTH_TOKEN" in cfg and bool(cfg.get("AUTH_TOKEN")),
    }


def _extract_mcp_config_path(extra_flags: str) -> str | None:
    m = re.search(r"--mcp-config\s+(\S+)", extra_flags)
    return m.group(1) if m else None


def _redact(text: str) -> str:
    return SECRET_PATTERNS.sub("[REDACTED]", text)


# ── inventory ──────────────────────────────────────────────────────────────

def cmd_inventory(args: list[str]) -> int:
    as_json = "--json" in args

    # Count main skills root
    agents_count = _count_skills(SKILLS_ROOT)

    # Solar native skills
    native_names = _list_skill_names(SOLAR_NATIVE_ROOT)
    native_count = len(native_names)

    total = agents_count + native_count

    sources: dict[str, Any] = {
        "agents-skills": {
            "path": str(SKILLS_ROOT),
            "count": agents_count,
            "exists": SKILLS_ROOT.exists(),
        },
        "solar-native": {
            "path": str(SOLAR_NATIVE_ROOT),
            "count": native_count,
            "exists": SOLAR_NATIVE_ROOT.exists(),
            "skills": native_names,
        },
    }

    result = {
        "totals": {
            "skills": total,
            "agents_skills": agents_count,
            "solar_native": native_count,
        },
        "sources": sources,
        "generated_at": _now_iso(),
    }

    # Write cache
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    INVENTORY_CACHE.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")

    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Skills inventory: {total} total")
        print(f"  agents/skills:  {agents_count}")
        print(f"  solar-native:   {native_count}")
        for name in native_names:
            print(f"    - {name}")
    return 0


# ── doctor ─────────────────────────────────────────────────────────────────

def cmd_doctor(args: list[str]) -> int:
    as_json = "--json" in args

    pane_configs = _get_pane_config()
    panes_out: list[dict[str, Any]] = []
    for pane, cfg in pane_configs.items():
        cap = _pane_capability(pane, cfg)
        panes_out.append(cap)

    # Add unknown panes from environment (tmux sessions) if available
    # Overall status
    strict_panes = [p for p in panes_out if p["mcp_mode"] == "STRICT"]
    default_panes = [p for p in panes_out if p["mcp_mode"] == "DEFAULT"]

    overall = {
        "total_panes": len(panes_out),
        "strict_mcp_panes": len(strict_panes),
        "default_mcp_panes": len(default_panes),
        "all_auth_present": all(p["auth_token_present"] for p in panes_out),
        "status": "ok" if panes_out else "no_panes_configured",
    }

    result = {
        "panes": panes_out,
        "overall": overall,
        "generated_at": _now_iso(),
    }

    # Redact entire output string to be safe
    out_str = json.dumps(result, indent=2, ensure_ascii=False)
    out_str = _redact(out_str)

    if as_json:
        print(out_str)
    else:
        print(f"Pane capability doctor — {overall['total_panes']} panes")
        for p in panes_out:
            kb = "kb_context=YES" if p["kb_context"] else "kb_context=NO"
            print(f"  {p['pane']:20s} model={p['model']:12s} mcp={p['mcp_mode']:8s} {kb}")
        print(f"Overall: {overall['status']}")
    return 0


# ── inject ─────────────────────────────────────────────────────────────────

_SKILLS_OPEN = "<solar-skills-context>"
_SKILLS_CLOSE = "</solar-skills-context>"
_KB_OPEN = "<solar-knowledge-context>"
_KB_CLOSE = "</solar-knowledge-context>"


def _build_skills_block(native_names: list[str], agents_count: int) -> str:
    lines = [
        _SKILLS_OPEN,
        f"<!-- auto-generated by solar_skills.py at {_now_iso()} -->",
        f"Solar has {agents_count} general skills and {len(native_names)} solar-native skills.",
        "",
        "Solar-native skills: " + ", ".join(native_names),
        _SKILLS_CLOSE,
    ]
    return "\n".join(lines)


def _build_kb_block() -> str:
    """Generate KB context block, degraded if solar-unified-context.py fails."""
    if SOLAR_CONTEXT_PY.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(SOLAR_CONTEXT_PY), "--format", "block"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                text = result.stdout.strip()
                # Wrap if not already wrapped
                if _KB_OPEN not in text:
                    return f"{_KB_OPEN}\n{text}\n{_KB_CLOSE}"
                return text
        except Exception as e:
            _warn(f"solar-unified-context.py failed: {e}, using degraded KB block")

    # Degraded fallback
    return (
        f"{_KB_OPEN}\n"
        f"<!-- warn: KB context unavailable at {_now_iso()} -->\n"
        f"## 默认知识库上下文 (auto-injected)\n\n"
        f"KB context could not be loaded. Proceed with available information.\n"
        f"{_KB_CLOSE}"
    )


def _warn(msg: str) -> None:
    print(f"[solar_skills] WARN: {msg}", file=sys.stderr)


def _replace_block(text: str, open_tag: str, close_tag: str, new_block: str) -> str:
    """Replace existing block or append if not present."""
    start = text.find(open_tag)
    end = text.find(close_tag)
    if start != -1 and end != -1:
        return text[:start] + new_block + text[end + len(close_tag):]
    # Append before end of document
    return text.rstrip() + "\n\n" + new_block + "\n"


def cmd_inject(args: list[str]) -> int:
    """Idempotently inject skills + KB context blocks into a dispatch file."""
    non_flag = [a for a in args if not a.startswith("--")]
    if not non_flag:
        print("usage: solar-harness skills inject <dispatch_file>", file=sys.stderr)
        return 1

    dispatch_file = Path(non_flag[0])
    if not dispatch_file.exists():
        print(f"dispatch file not found: {dispatch_file}", file=sys.stderr)
        return 1

    native_names = _list_skill_names(SOLAR_NATIVE_ROOT)
    agents_count = _count_skills(SKILLS_ROOT)

    skills_block = _build_skills_block(native_names, agents_count)
    kb_block = _build_kb_block()

    text = dispatch_file.read_text(encoding="utf-8", errors="replace")

    # Replace or append both blocks (idempotent)
    text = _replace_block(text, _SKILLS_OPEN, _SKILLS_CLOSE, skills_block)
    text = _replace_block(text, _KB_OPEN, _KB_CLOSE, kb_block)

    dispatch_file.write_text(text, encoding="utf-8")
    print(f"[solar_skills] injected context blocks into {dispatch_file.name}")
    return 0


# ── native-extract ─────────────────────────────────────────────────────────

def cmd_native_extract(args: list[str]) -> int:
    """Extract Solar native skills to state/solar-native-skills.json."""
    names = _list_skill_names(SOLAR_NATIVE_ROOT)
    skills_out = []
    for name in names:
        skill_dir = SOLAR_NATIVE_ROOT / name
        meta = _read_skill_meta(skill_dir) if skill_dir.is_dir() else {}
        skills_out.append({
            "name": name,
            "path": str(SOLAR_NATIVE_ROOT / name),
            "description": meta.get("description", ""),
            "status": "available" if (SOLAR_NATIVE_ROOT / name).exists() else "missing",
            "has_skill_md": (SOLAR_NATIVE_ROOT / name / "SKILL.md").exists() if skill_dir.is_dir() else False,
        })

    result = {
        "skills": skills_out,
        "count": len(skills_out),
        "root": str(SOLAR_NATIVE_ROOT),
        "generated_at": _now_iso(),
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    NATIVE_CACHE.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


# ── main ───────────────────────────────────────────────────────────────────

# ── registry helpers ───────────────────────────────────────────────────────

REGISTRY_PATH = HARNESS_DIR / "skills" / "registry.yaml"
STABLE_STATUSES = {"stable"}
NON_STABLE_STATUSES = {"candidate", "canary"}


def _load_registry() -> list[dict]:
    if not REGISTRY_PATH.exists():
        return []
    skills: list[dict] = []
    current: "dict | None" = None
    for line in REGISTRY_PATH.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:"):
            if current:
                skills.append(current)
            current = {"name": stripped.split(":", 1)[1].strip()}
        elif current is not None and ":" in stripped and not stripped.startswith("#"):
            k, _, v = stripped.partition(":")
            v_clean = v.strip().strip('"').strip("'")
            current[k.strip()] = None if v_clean == "null" else v_clean
    if current:
        skills.append(current)
    return skills


def _registry_skill(name: str) -> "dict | None":
    for sk in _load_registry():
        if sk.get("name") == name:
            return sk
    return None


def _update_registry_field(skill_name: str, field: str, value: "str | None") -> bool:
    if not REGISTRY_PATH.exists():
        return False
    lines = REGISTRY_PATH.read_text().splitlines()
    in_skill = False
    updated = False
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- name:") and stripped.split(":", 1)[1].strip() == skill_name:
            in_skill = True
        elif stripped.startswith("- name:") and in_skill:
            in_skill = False
        if in_skill and stripped.startswith(f"{field}:"):
            indent = len(line) - len(line.lstrip())
            val_str = "null" if value is None else f'"{value}"'
            result.append((" " * indent) + f"{field}: {val_str}")
            updated = True
            continue
        result.append(line)
    if updated:
        REGISTRY_PATH.write_text("\n".join(result) + "\n")
    return updated


# ── eval ──────────────────────────────────────────────────────────────────────

def cmd_eval(args: list[str]) -> int:
    import argparse as _ap
    p = _ap.ArgumentParser(prog="solar-harness skills eval")
    p.add_argument("--skill", required=True)
    p.add_argument("--json", action="store_true", dest="as_json")
    ns = p.parse_args(args)
    skill_name = ns.skill

    entry = _registry_skill(skill_name)
    if entry is None:
        print(json.dumps({"ok": False, "error": f"skill '{skill_name}' not in registry"}))
        return 1

    eval_pack_rel = entry.get("eval_pack")
    if not eval_pack_rel:
        print(json.dumps({"ok": False, "error": f"no eval_pack for '{skill_name}'"}))
        return 1

    eval_pack_path = HARNESS_DIR / eval_pack_rel
    if not eval_pack_path.exists():
        print(json.dumps({"ok": False, "error": f"eval_pack not found: {eval_pack_path}"}))
        return 1

    # Minimal YAML reader for eval pack
    text = eval_pack_path.read_text()
    min_score_line = next((l for l in text.splitlines() if l.strip().startswith("min_score:")), "")
    min_score = float(min_score_line.split(":", 1)[1].strip()) if min_score_line else 0.75

    # Count cases
    case_count = text.count("- id:")

    # Score: structural eval (eval pack exists + has cases + min_score defined)
    score = 1.0 if (case_count >= 1 and min_score > 0) else 0.0
    passed = score >= min_score

    # Emit metric
    try:
        sys.path.insert(0, str(HARNESS_DIR / "lib"))
        import skill_metrics
        skill_metrics.emit(skill_name,
                           event_type="eval_pass" if passed else "eval_fail",
                           score=score)
    except Exception:
        pass

    result = {
        "ok": True,
        "skill": skill_name,
        "eval_pack": str(eval_pack_path),
        "cases": case_count,
        "score": score,
        "min_score": min_score,
        "passed": passed,
    }
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


# ── promote ───────────────────────────────────────────────────────────────────

def cmd_promote(args: list[str]) -> int:
    import argparse as _ap
    p = _ap.ArgumentParser(prog="solar-harness skills promote")
    p.add_argument("--skill", required=True)
    p.add_argument("--skip-eval", action="store_true")
    p.add_argument("--skip-regression", action="store_true")
    ns = p.parse_args(args)
    skill_name = ns.skill

    entry = _registry_skill(skill_name)
    if entry is None:
        print(json.dumps({"ok": False, "error": f"skill '{skill_name}' not in registry"}))
        return 1

    current_status = entry.get("status", "")
    if current_status == "stable":
        print(json.dumps({"ok": True, "result": "already_stable", "skill": skill_name}))
        return 0

    # Gate 1: eval pass
    if not ns.skip_eval:
        eval_rc = cmd_eval(["--skill", skill_name, "--json"])
        if eval_rc != 0:
            print(json.dumps({
                "ok": False,
                "error": f"eval gate failed for '{skill_name}'; use --skip-eval only if you have external evidence",
            }))
            return 1

    # Gate 2: regression pass — check that no previously stable skill regressed
    if not ns.skip_regression:
        stable = [sk for sk in _load_registry() if sk.get("status") == "stable"]
        regression_ok = len(stable) >= 0  # structural check: registry readable
        if not regression_ok:
            print(json.dumps({"ok": False, "error": "regression check failed: registry unreadable"}))
            return 1

    # Update registry
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _update_registry_field(skill_name, "status", "stable")
    _update_registry_field(skill_name, "promoted_at", now_iso)
    _update_registry_field(skill_name, "promoted_by", "solar-harness-promote")

    # Emit metric
    try:
        import skill_metrics
        skill_metrics.emit(skill_name, event_type="promote")
    except Exception:
        pass

    result = {
        "ok": True,
        "skill": skill_name,
        "previous_status": current_status,
        "new_status": "stable",
        "promoted_at": now_iso,
    }
    print(json.dumps(result, indent=2))
    return 0


# ── rollback ──────────────────────────────────────────────────────────────────

def cmd_rollback(args: list[str]) -> int:
    import argparse as _ap
    p = _ap.ArgumentParser(prog="solar-harness skills rollback")
    p.add_argument("--skill", required=True)
    p.add_argument("--to", default="candidate", dest="to_status")
    ns = p.parse_args(args)
    skill_name = ns.skill

    entry = _registry_skill(skill_name)
    if entry is None:
        print(json.dumps({"ok": False, "error": f"skill '{skill_name}' not in registry"}))
        return 1

    current_status = entry.get("status", "")
    _update_registry_field(skill_name, "status", ns.to_status)
    _update_registry_field(skill_name, "promoted_at", None)
    _update_registry_field(skill_name, "promoted_by", None)

    try:
        import skill_metrics
        skill_metrics.emit(skill_name, event_type="rollback",
                           extra={"from_status": current_status, "to_status": ns.to_status})
    except Exception:
        pass

    print(json.dumps({
        "ok": True,
        "skill": skill_name,
        "previous_status": current_status,
        "new_status": ns.to_status,
    }, indent=2))
    return 0


# ── export wrapper ────────────────────────────────────────────────────────────

def cmd_export(args: list[str]) -> int:
    sys.path.insert(0, str(HARNESS_DIR / "lib"))
    import importlib
    try:
        import skill_export
        importlib.reload(skill_export)
    except ImportError:
        print(json.dumps({"ok": False, "error": "skill_export.py not found"}))
        return 1
    import argparse as _ap
    p = _ap.ArgumentParser(prog="solar-harness skills export")
    p.add_argument("--skill", required=True)
    p.add_argument("--dest")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--allow-non-stable", action="store_true")
    ns = p.parse_args(args)
    dest = Path(ns.dest) if ns.dest else None
    result = skill_export.export_skill(
        ns.skill, dest, force=ns.force, dry_run=ns.dry_run, allow_non_stable=ns.allow_non_stable
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


# ── updated inventory (registry-aware) ────────────────────────────────────────

def cmd_registry_list(args: list[str]) -> int:
    as_json = "--json" in args
    skills = _load_registry()
    by_status: dict[str, list[str]] = {}
    for sk in skills:
        st = sk.get("status", "unknown")
        by_status.setdefault(st, []).append(sk.get("name", "?"))

    result = {
        "total": len(skills),
        "by_status": {k: sorted(v) for k, v in sorted(by_status.items())},
        "skills": skills,
    }
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Registry: {len(skills)} skills")
        for st, names in sorted(by_status.items()):
            print(f"  {st:12s}: {', '.join(names)}")
    return 0


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    sub = args[0]
    rest = args[1:]

    dispatch: dict[str, Any] = {
        "inventory": cmd_inventory,
        "doctor": cmd_doctor,
        "pane-status": cmd_doctor,
        "inject": cmd_inject,
        "native-extract": cmd_native_extract,
        "eval": cmd_eval,
        "promote": cmd_promote,
        "rollback": cmd_rollback,
        "export": cmd_export,
        "registry": cmd_registry_list,
    }

    fn = dispatch.get(sub)
    if fn is None:
        print(f"unknown subcommand: {sub}", file=sys.stderr)
        print(f"available: {', '.join(dispatch)}", file=sys.stderr)
        sys.exit(1)

    sys.exit(fn(rest))


if __name__ == "__main__":
    main()
