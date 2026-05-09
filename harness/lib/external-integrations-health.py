#!/usr/bin/env python3
"""Solar external integration health.

Six-state model per integration:
installed, configured, running, indexed, used_by_default, degraded_reason.
The probe is local-only and fail-open: one broken integration should not break
the whole status payload.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import re
from pathlib import Path


HOME = Path.home()
HARNESS = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
VAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH", HOME / "Knowledge"))
SOLAR_DB = HOME / ".solar" / "solar.db"
CACHE_PATH = HARNESS / "state" / "external-integrations-last-probe.json"


def run(cmd: list[str], timeout: float = 3.0) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as exc:
        return 99, f"{type(exc).__name__}: {exc}"


def port_probe(port: int, hosts: list[str] | None = None, timeout: float = 0.25) -> dict:
    hosts = hosts or ["127.0.0.1", "::1", "localhost"]
    results = {}
    open_hosts = []
    for item in hosts:
        try:
            with socket.create_connection((item, port), timeout=timeout):
                results[item] = "open"
                open_hosts.append(item)
        except OSError as exc:
            results[item] = f"closed:{type(exc).__name__}"
    return {"open": bool(open_hosts), "open_hosts": open_hosts, "hosts": results}


def port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    hosts = [host]
    if host in ("127.0.0.1", "localhost"):
        hosts.append("::1")
    return port_probe(port, hosts=hosts, timeout=timeout)["open"]


def which_qmd() -> str:
    for item in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(item) / "qmd"
        if p.exists() and os.access(p, os.X_OK):
            return str(p)
    fallback = HOME / ".npm-global" / "bin" / "qmd"
    return str(fallback) if fallback.exists() else ""


def local_google_drive() -> dict:
    configured = HARNESS / "config" / "mirage.solar.yaml"
    raw = configured.read_text(errors="ignore") if configured.exists() else ""
    m = re.search(r'root:\s*"([^"]*GoogleDrive[^"]*)"', raw)
    if m and Path(m.group(1)).exists():
        return {"ok": True, "path": m.group(1), "source": "mirage_config"}
    cloud_storage = HOME / "Library" / "CloudStorage"
    if cloud_storage.exists():
        for path in sorted(cloud_storage.glob("GoogleDrive-*")):
            if path.is_dir():
                return {"ok": True, "path": str(path), "source": "macos_file_provider"}
    return {"ok": False, "path": "", "source": ""}


def count_sql(table: str) -> int | None:
    if not SOLAR_DB.exists():
        return None
    try:
        with sqlite3.connect(SOLAR_DB) as conn:
            return int(conn.execute(f"select count(*) from {table}").fetchone()[0])
    except Exception:
        return None


def qmd_status() -> dict:
    qmd = which_qmd()
    if not qmd:
        return {"ok": False, "binary": "", "raw": "", "total": 0, "pending": None, "vectors": None}
    code, out = run([qmd, "status"], timeout=6)
    total = pending = vectors = None
    for raw in out.splitlines():
        line = raw.strip()
        if line.startswith("Total:"):
            total = int(line.split()[1]) if len(line.split()) > 1 and line.split()[1].isdigit() else None
        elif line.startswith("Vectors:"):
            vectors = int(line.split()[1]) if len(line.split()) > 1 and line.split()[1].isdigit() else None
        elif line.startswith("Pending:"):
            pending = int(line.split()[1]) if len(line.split()) > 1 and line.split()[1].isdigit() else None
    return {"ok": code == 0, "binary": qmd, "raw": out[:2000], "total": total or 0, "pending": pending, "vectors": vectors}


def dispatch_backlog() -> dict:
    dispatch_dir = VAULT / "_raw" / "solar-harness" / ".dispatch"
    counts: dict[str, int] = {}
    ignored: dict[str, int] = {}
    if not dispatch_dir.exists():
        return {"available": False, "reason": "dispatch dir missing", "total": 0, "counts": counts}
    for path in dispatch_dir.glob("*.md"):
        status = "no_status"
        try:
            text = path.read_text(errors="ignore")[:1200]
            type_match = re.search(r"^type:\s*([^\n]+)", text, re.M)
            if not type_match or type_match.group(1).strip() != "wiki-dispatch":
                ignored_type = type_match.group(1).strip() if type_match else "no_type"
                ignored[ignored_type] = ignored.get(ignored_type, 0) + 1
                continue
            m = re.search(r"^status:\s*([^\n]+)", text, re.M)
            if m:
                status = m.group(1).strip()
        except OSError:
            status = "read_error"
        counts[status] = counts.get(status, 0) + 1
    unresolved = sum(counts.get(k, 0) for k in ("pending", "dispatched", "running", "no_status", "read_error"))
    return {
        "available": True,
        "total": sum(counts.values()),
        "counts": counts,
        "ignored_non_dispatch": ignored,
        "unresolved": unresolved,
        "dir": str(dispatch_dir),
    }


def latest_upload_audit(deep: bool = False) -> dict:
    upload_dir = VAULT / "_raw" / "file-uploads"
    if not upload_dir.exists():
        return {"available": False, "reason": "file upload dir missing"}
    batches: dict[str, int] = {}
    for path in upload_dir.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if len(name) >= 16 and name[0:8].isdigit() and name[8] == "T" and name[15] == "Z":
            batches[name[:16]] = batches.get(name[:16], 0) + 1
    if not batches:
        return {"available": False, "reason": "no upload batches"}
    if not deep:
        batch, count = sorted(batches.items(), key=lambda kv: (kv[0], kv[1]), reverse=True)[0]
        return {
            "available": True,
            "batch": batch,
            "mode": "fast_metadata",
            "total_files": count,
            "deep_audit": "skipped; run with --deep for per-source qmd/vault/solar_db audit",
        }
    auditor = HARNESS / "lib" / "wiki-upload-audit.py"
    if not auditor.exists():
        return {"available": False, "reason": "wiki-upload-audit.py missing"}
    checked = []
    latest = None
    backlog_gaps = []
    max_batches = 10 if deep else 1
    timeout = 90 if deep else 20
    for batch, _count in sorted(batches.items(), key=lambda kv: (kv[0], kv[1]), reverse=True)[:max_batches]:
        code, out = run(["python3", str(auditor), "--batch", batch, "--json"], timeout=timeout)
        try:
            data = json.loads(out)
        except Exception:
            checked.append({"batch": batch, "error": out[:160], "exit_code": code})
            continue
        checked.append({"batch": batch, "total": data.get("total", 0)})
        if data.get("total", 0) > 0:
            has_gap = bool(
                data.get("solar_db", {}).get("missing", 0)
                or data.get("vault", {}).get("missing", 0)
                or data.get("qmd", {}).get("missing", 0)
                or data.get("dispatch", {}).get("pending", 0)
            )
            if latest is None:
                latest = {"available": True, "batch": batch, "data": data, "checked": checked}
            elif has_gap:
                backlog_gaps.append(
                    {
                        "batch": batch,
                        "total": data.get("total", 0),
                        "qmd_missing": data.get("qmd", {}).get("missing", 0),
                        "vault_missing": data.get("vault", {}).get("missing", 0),
                        "solar_db_missing": data.get("solar_db", {}).get("missing", 0),
                        "dispatch_pending": data.get("dispatch", {}).get("pending", 0),
                    }
                )
    if latest:
        latest["checked"] = checked
        latest["historical_backlog"] = backlog_gaps[:5]
        return latest
    if checked:
        return {"available": False, "reason": "no auditable upload batch with nonzero total found", "checked": checked}
    return {"available": False, "reason": "no upload batches"}


def health_state(ok: bool, warn: bool = False) -> str:
    if not ok:
        return "error"
    return "warn" if warn else "ok"


def result(name: str, source: str, purpose: str, **states) -> dict:
    keys = ["installed", "configured", "running", "indexed", "used_by_default"]
    lifecycle = states.pop("lifecycle", "active")
    optional = bool(states.pop("optional", False))
    candidate = bool(states.pop("candidate", False))
    degraded = states.pop("degraded_reason", "")
    evidence = states.pop("evidence", {})
    complete = states.pop("complete", None)
    dead_ends = states.pop("dead_ends", [])
    basic_available = states.pop("basic_available", None)
    out = {"name": name, "source": source, "purpose": purpose}
    out["lifecycle"] = lifecycle
    out["optional"] = optional
    out["candidate"] = candidate
    for key in keys:
        out[key] = bool(states.get(key, False))
    if basic_available is None:
        basic_available = out["installed"] and out["configured"]
    if complete is None:
        complete = all(out[k] for k in keys) and not degraded and not dead_ends
    out["health"] = {
        "basic_available": health_state(bool(basic_available)),
        "default_available": health_state(out["used_by_default"], warn=out["used_by_default"] and bool(degraded)),
        "complete_closed_loop": health_state(bool(complete), warn=bool(basic_available) and not complete),
        "dead_ends": "warn" if dead_ends else "ok",
    }
    if optional and basic_available and not dead_ends:
        out["status"] = "ok"
    elif candidate and out["installed"]:
        out["status"] = "ok"
    elif not out["installed"]:
        out["status"] = "missing"
    elif complete and not degraded:
        out["status"] = "ok"
    elif basic_available:
        out["status"] = "warn"
    else:
        out["status"] = "error"
    # 4-tier label for A6: dead_end > closed_loop > default_usable > basic_usable
    if optional and basic_available and not dead_ends:
        out["status_label"] = "basic_usable"
    elif candidate and out["installed"]:
        out["status_label"] = "basic_usable"
    elif dead_ends:
        out["status_label"] = "dead_end"
    elif complete and not degraded:
        out["status_label"] = "closed_loop"
    elif out["used_by_default"]:
        out["status_label"] = "default_usable"
    else:
        out["status_label"] = "basic_usable"
    out["status_legacy"] = out["status"]  # backwards compat for 6 weeks
    out["degraded_reason"] = degraded
    out["dead_ends"] = dead_ends
    out["evidence"] = evidence
    return out


def probe(deep: bool = False) -> dict:
    qmd = qmd_status()
    gdrive_local = local_google_drive()
    upload = latest_upload_audit(deep=deep)
    dispatch = dispatch_backlog()
    qmd_port = port_probe(8181)
    status_port = port_probe(8765, hosts=["127.0.0.1"])

    obs_repo = HARNESS / "vendor" / "obsidian-wiki"
    wiki_cfg = HOME / ".obsidian-wiki" / "config"
    unified_context = HARNESS / "lib" / "solar-unified-context.py"
    claude_hook = HOME / ".claude" / "hooks" / "solar-knowledge-context.sh"
    codex_agents = HOME / ".codex" / "AGENTS.md"
    default_context_ready = (
        unified_context.exists()
        and claude_hook.exists()
        and (
            "solar-unified-context.py" in claude_hook.read_text(errors="ignore")
            or "solar-knowledge-context.py" in claude_hook.read_text(errors="ignore")
        )
        and codex_agents.exists()
        and "solar-harness context inject" in codex_agents.read_text(errors="ignore")
    )
    vault_ready = VAULT.exists()
    capture_running = port_open("127.0.0.1", 8788)
    vault_md_count = len(list(VAULT.glob("**/*.md"))) if vault_ready else 0
    upload_reason_parts = []
    if upload.get("available") and upload.get("data"):
        d = upload["data"]
        if d.get("solar_db", {}).get("missing", 0) or d.get("vault", {}).get("missing", 0) or d.get("qmd", {}).get("missing", 0):
            upload_reason_parts.append(
                f"latest batch {upload['batch']}: qmd {d['qmd']['found']}/{d['total']}, "
                f"vault {d['vault']['found']}/{d['total']}, solar_db {d['solar_db']['found']}/{d['total']}"
            )
    if dispatch.get("unresolved", 0):
        upload_reason_parts.append(
            f"global dispatch backlog: unresolved={dispatch['unresolved']}/{dispatch['total']} "
            f"(pending={dispatch['counts'].get('pending', 0)}, dispatched={dispatch['counts'].get('dispatched', 0)}, "
            f"running={dispatch['counts'].get('running', 0)})"
        )

    mineru_repo = HARNESS / "vendor" / "MinerU-Document-Explorer"
    mineru_venv = mineru_repo / ".venv"
    mineru_vendor_venv = HARNESS / "vendor" / "mineru" / ".venv"  # bootstrap venv path
    mineru_venv_ok = mineru_venv.exists() or mineru_vendor_venv.exists()
    mineru_install_report = HARNESS / "vendor" / "mineru" / "install-report.json"
    mineru_skill_count = len(list((mineru_repo / "skills").glob("*/SKILL.md"))) if (mineru_repo / "skills").exists() else 0
    markitdown_skill = HOME / ".agents" / "skills" / "markitdown" / "SKILL.md"
    markitdown_claude_skill = HOME / ".claude" / "skills" / "markitdown"
    markitdown_script = HOME / ".agents" / "skills" / "markitdown" / "scripts" / "batch_convert.py"
    markitdown_owl_toolkit = HOME / ".solar" / "owl" / "venv" / "lib" / "python3.11" / "site-packages" / "camel" / "toolkits" / "markitdown_toolkit.py"
    claude_agents_dir = HOME / ".claude" / "agents"
    addy_agents_dir = HOME / ".claude" / "plugins" / "marketplaces" / "addy-agent-skills" / "agents"
    claude_agents_count = len(list(claude_agents_dir.glob("*.md"))) if claude_agents_dir.exists() else 0
    addy_agents_count = len(list(addy_agents_dir.glob("*.md"))) if addy_agents_dir.exists() else 0

    integrations = [
        result(
            "Ar9av/obsidian-wiki",
            "https://github.com/Ar9av/obsidian-wiki",
            "Obsidian-native knowledge vault, wiki ingest/query/lint/graph skills, Solar artifact export.",
            installed=obs_repo.exists(),
            configured=wiki_cfg.exists() and vault_ready,
            running=capture_running,
            indexed=vault_md_count > 0,
            used_by_default=default_context_ready,
            complete=not upload_reason_parts and default_context_ready,
            degraded_reason="; ".join(upload_reason_parts) or ("" if default_context_ready else "used by commands/status, but not yet guaranteed as default context for every agent"),
            dead_ends=[],
            evidence={
                "repo": str(obs_repo),
                "vault": str(VAULT),
                "capture_port_8788": capture_running,
                "vault_md_count": vault_md_count,
                "unified_context": str(unified_context),
                "claude_hook": str(claude_hook),
                "codex_agents": str(codex_agents),
                "latest_upload_audit": upload,
                "dispatch_backlog": dispatch,
            },
        ),
        result(
            "opendatalab/MinerU-Document-Explorer",
            "https://github.com/opendatalab/MinerU-Document-Explorer",
            "PDF deep-extraction pipeline (magic-pdf CPU mode) + QMD semantic search. venv bootstrapped, PDF extraction active, idle-guarded background worker via launchd.",
            installed=mineru_repo.exists() or (HARNESS / "vendor" / "mineru").exists(),
            configured=mineru_venv_ok,
            running=qmd["ok"],
            indexed=(qmd["total"] or 0) > 0,
            used_by_default=False,
            complete=mineru_venv_ok and bool(qmd["binary"]) and qmd["ok"],
            degraded_reason="" if mineru_venv_ok else "MinerU .venv missing; run: solar-harness mineru bootstrap",
            dead_ends=[] if mineru_venv_ok else ["mineru_venv_missing"],
            evidence={
                "vendor": str(mineru_repo),
                "venv": str(mineru_vendor_venv),
                "venv_exists": mineru_venv_ok,
                "install_report": str(mineru_install_report),
                "skill_count": mineru_skill_count,
                "qmd_binary": qmd["binary"],
                "worker_launchd": (HOME / "Library" / "LaunchAgents" / "io.solar.mineru-worker.plist").exists(),
                "doctor_cmd": "solar-harness mineru doctor --json",
            },
        ),
        result(
            "QMD semantic search/embed",
            "https://github.com/opendatalab/MinerU-Document-Explorer",
            "Local semantic search and idle-only embedding for the solar-wiki collection.",
            installed=bool(qmd["binary"]),
            configured=qmd["ok"] and "solar-wiki" in qmd["raw"],
            running=qmd_port["open"],
            indexed=(qmd["total"] or 0) > 0,
            used_by_default=True,
            complete=qmd["ok"] and qmd_port["open"] and not qmd.get("pending"),
            degraded_reason=(
                f"{qmd['pending']} files need embedding" if qmd.get("pending")
                else ("MCP listens on IPv6 ::1 only; 127.0.0.1 clients will fail" if "::1" in qmd_port["open_hosts"] and "127.0.0.1" not in qmd_port["open_hosts"] else "")
            ),
            dead_ends=["mcp_ipv6_only"] if "::1" in qmd_port["open_hosts"] and "127.0.0.1" not in qmd_port["open_hosts"] else [],
            evidence={
                "total": qmd["total"],
                "vectors": qmd["vectors"],
                "pending": qmd["pending"],
                "mcp_port_8181": qmd_port,
                "embed_launchd": (HOME / "Library" / "LaunchAgents" / "com.solar.qmd-mineru-embed.plist").exists(),
                "embed_status": str(HARNESS / "state" / "qmd-embed-status.json"),
            },
        ),
        result(
            "mermaid-js/mermaid",
            "https://github.com/mermaid-js/mermaid",
            "Local .mmd architecture diagram browser and renderer in Solar Status.",
            installed=(HARNESS / "vendor" / "mermaid-viewer" / "node_modules" / "mermaid").exists(),
            configured=True,
            running=status_port["open"],
            indexed=len(list((HARNESS / "reports").glob("*.mmd"))) > 0,
            used_by_default=True,
            complete=status_port["open"] and len(list((HARNESS / "reports").glob("*.mmd"))) > 0,
            evidence={"viewer": "http://127.0.0.1:8765/mermaid", "mmd_count": len(list((HARNESS / "reports").glob("*.mmd"))), "status_port": status_port},
        ),
        result(
            "openai/symphony",
            "https://github.com/openai/symphony",
            "Adopted SPEC patterns (WORKFLOW, isolated workspace, hooks, scheduler events) as local dry-run sidecar — coordinator/tmux is the real executor; Symphony does not run builders.",
            installed=(HARNESS / "lib" / "symphony").exists(),
            configured=(HARNESS / "lib" / "symphony" / "workflow-loader.py").exists(),
            running=False,
            indexed=(HARNESS / "state" / "symphony").exists(),
            used_by_default=False,
            basic_available=True,
            complete=True,
            degraded_reason="",
            evidence={
                "lib": str(HARNESS / "lib" / "symphony"),
                "mode": "dry_run_sidecar",
                "executes_builders": False,
            },
        ),
        result(
            "strukto-ai/mirage",
            "https://github.com/strukto-ai/mirage",
            "Solar logical VFS wrapper over Knowledge, Raw, Sprints, Solar DB, QMD. SDK/FUSE decision ADR filed: wrapper_only (SIP blocks macFUSE, reboot required). Drive is logical mount requiring credentials.",
            installed=(HARNESS / "lib" / "solar_mirage.py").exists(),
            configured=(HARNESS / "config" / "mirage.solar.yaml").exists(),
            running=True,
            indexed=(qmd["total"] or 0) > 0 and SOLAR_DB.exists(),
            used_by_default=True,
            complete=True,
            degraded_reason="",
            dead_ends=[],
            evidence={
                "wrapper": str(HARNESS / "lib" / "solar_mirage.py"),
                "sdk_decision": "wrapper_only",
                "sdk_decision_doc": str(HOME / ".solar" / "reports" / "mirage-sdk-fuse-decision-2026-05-09.md"),
                "drive": {
                    "state": "local_mount" if gdrive_local["ok"] else "credentials_missing",
                    "local_root": gdrive_local["path"],
                    "unblock_env_var": "GOOGLE_DRIVE_REFRESH_TOKEN",
                    "ui_path": "/integrations#drive",
                },
                "doctor_cmd": "solar-harness mirage doctor --json",
                "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        ),
        result(
            "gstack",
            "https://github.com/graydotdev/gstack",
            "Solar browser/QA/review workflow skills installed under ~/.claude/skills/gstack. Used by Solar rules for browse, qa, review, investigate, ship and visual testing flows.",
            installed=(HOME / ".claude" / "skills" / "gstack" / "SKILL.md").exists(),
            configured=(HOME / ".claude" / "skills" / "gstack" / "bin").exists(),
            running=True,
            indexed=True,
            used_by_default=True,
            complete=(HOME / ".claude" / "skills" / "gstack" / "SKILL.md").exists(),
            evidence={
                "skill": str(HOME / ".claude" / "skills" / "gstack" / "SKILL.md"),
                "solar_rule": str(HOME / "Solar" / "CLAUDE.md"),
                "commands": ["/browse", "/qa", "/review", "/investigate", "/ship"],
            },
        ),
        result(
            "Superpowers",
            "openai-curated/superpowers",
            "Codex and multi-agent skill framework. Installed as Codex plugin plus using-superpowers skills for Claude/agents.",
            installed=(HOME / ".codex" / "plugins" / "cache" / "openai-curated" / "superpowers").exists()
            or (HOME / ".agents" / "skills" / "using-superpowers" / "SKILL.md").exists(),
            configured=(HOME / ".codex" / "config.toml").exists()
            and "superpowers@openai-curated" in (HOME / ".codex" / "config.toml").read_text(errors="ignore"),
            running=True,
            indexed=True,
            used_by_default=True,
            complete=True,
            evidence={
                "codex_plugin": str(HOME / ".codex" / "plugins" / "cache" / "openai-curated" / "superpowers"),
                "agents_skill": str(HOME / ".agents" / "skills" / "using-superpowers" / "SKILL.md"),
                "codex_config": str(HOME / ".codex" / "config.toml"),
            },
        ),
        result(
            "ATLAS repair protocol",
            "Solar local rules",
            "ATLAS-derived repair protocol and PR-CoT failure-repair rules absorbed into Solar rules. Provides structured repair behavior for hook/tool failures.",
            installed=(HOME / "Solar" / "rules" / "atlas-repair-protocol.md").exists()
            or (HOME / ".claude" / "rules" / "atlas-repair-protocol.md").exists(),
            configured=(HOME / ".solar" / "plans" / "atlas-solar-integration.md").exists(),
            running=True,
            indexed=True,
            used_by_default=True,
            complete=True,
            evidence={
                "solar_rule": str(HOME / "Solar" / "rules" / "atlas-repair-protocol.md"),
                "claude_rule": str(HOME / ".claude" / "rules" / "atlas-repair-protocol.md"),
                "plan": str(HOME / ".solar" / "plans" / "atlas-solar-integration.md"),
            },
        ),
        result(
            "camel-ai/owl",
            "https://github.com/camel-ai/owl",
            "External multi-agent/browser execution framework installed locally. Registered as a Solar capability provider for multi-agent research/browser experimentation; not the default coordinator.",
            lifecycle="active",
            installed=(HOME / ".solar" / "owl").exists(),
            configured=(HOME / ".solar" / "owl" / "pyproject.toml").exists(),
            running=(HOME / ".solar" / "owl" / ".owl-service.pid").exists(),
            indexed=True,
            used_by_default=False,
            complete=True,
            degraded_reason="",
            evidence={
                "repo": str(HOME / ".solar" / "owl"),
                "venv": str(HOME / ".solar" / "owl" / "venv"),
                "service_pid_file": str(HOME / ".solar" / "owl" / ".owl-service.pid"),
                "connection_status": "active_capability_provider_not_default_coordinator",
            },
        ),
        result(
            "Microsoft MarkItDown MCP",
            "https://github.com/microsoft/markitdown",
            "Document conversion provider for PDF/Office/HTML/image-to-Markdown. Solar dispatch injects MarkItDown for document extraction; MCP runtime is optional and detected separately.",
            lifecycle="active",
            installed=markitdown_skill.exists() or markitdown_claude_skill.exists() or markitdown_owl_toolkit.exists(),
            configured=markitdown_script.exists() or markitdown_owl_toolkit.exists(),
            running=True,
            indexed=True,
            used_by_default=True,
            complete=markitdown_skill.exists() and (markitdown_script.exists() or markitdown_owl_toolkit.exists()),
            degraded_reason="" if (markitdown_skill.exists() and (markitdown_script.exists() or markitdown_owl_toolkit.exists())) else "MarkItDown skill or conversion script/toolkit missing",
            evidence={
                "agents_skill": str(markitdown_skill),
                "claude_skill": str(markitdown_claude_skill),
                "batch_convert": str(markitdown_script),
                "owl_toolkit": str(markitdown_owl_toolkit),
                "dispatch_capability": "document.convert",
                "mcp_runtime": "optional_not_required_for_solar_dispatch",
            },
        ),
        result(
            "agency-agents persona",
            "local Claude agents + addy-agent-skills",
            "Specialist persona/agent catalog used as Solar routing context. Provides role hints for PM/planner/builder/evaluator without replacing the Harness pane model.",
            lifecycle="active",
            installed=claude_agents_dir.exists() or addy_agents_dir.exists(),
            configured=(claude_agents_count + addy_agents_count) > 0,
            running=True,
            indexed=True,
            used_by_default=True,
            complete=(claude_agents_count + addy_agents_count) > 0,
            degraded_reason="" if (claude_agents_count + addy_agents_count) > 0 else "no agent catalog markdown files found",
            evidence={
                "claude_agents_dir": str(claude_agents_dir),
                "claude_agents_count": claude_agents_count,
                "addy_agents_dir": str(addy_agents_dir),
                "addy_agents_count": addy_agents_count,
                "dispatch_capability": "persona.agent",
            },
        ),
        result(
            "Google Drive mount",
            "external service",
            "Optional Mirage /drive data source. Uses local macOS Google Drive File Provider when installed; service-account credentials are only needed for headless/API mode.",
            lifecycle="optional",
            optional=True,
            installed=True,
            configured=gdrive_local["ok"] or bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")),
            running=gdrive_local["ok"],
            indexed=gdrive_local["ok"],
            used_by_default=False,
            basic_available=True,
            complete=gdrive_local["ok"],
            degraded_reason="" if gdrive_local["ok"] else "Google Drive local mount not found and GOOGLE_APPLICATION_CREDENTIALS not configured",
            evidence={
                "credential_env": "GOOGLE_APPLICATION_CREDENTIALS",
                "state": "local_mount" if gdrive_local["ok"] else "logical_mount",
                "local_root": gdrive_local["path"],
                "local_source": gdrive_local["source"],
            },
        ),
        result(
            "affaan-m/everything-claude-code",
            "https://github.com/affaan-m/everything-claude-code",
            "Claude Code agents, commands, skills, hooks, rules, MCP configs, contexts, scripts, and tests. Registered as a Solar capability provider in safe read-only/vendor mode.",
            lifecycle="active",
            installed=(HARNESS / "vendor" / "everything-claude-code").exists(),
            configured=(HARNESS / "vendor" / "everything-claude-code" / "agent.yaml").exists(),
            running=False,
            indexed=(HARNESS / "reports" / "everything-claude-code-audit-20260508.md").exists(),
            used_by_default=False,
            complete=True,
            degraded_reason="",
            evidence={
                "canonical_source": "https://github.com/affaan-m/everything-claude-code",
                "mirror_or_fork_seen": "https://github.com/WorldFlowAI/everything-claude-code",
                "contract": str(HARNESS / "sprints" / "sprint-20260508-everything-claude-code-integration.contract.md"),
                "mode": "safe_read_only_vendor_provider",
                "related_systems": {
                    "gstack": str(HOME / "Solar" / "CLAUDE.md"),
                    "superpowers": str(HOME / ".codex" / "config.toml"),
                },
            },
        ),
    ]

    summary = {
        "ok": sum(1 for x in integrations if x["status"] == "ok"),
        "warn": sum(1 for x in integrations if x["status"] == "warn"),
        "error": sum(1 for x in integrations if x["status"] == "error"),
        "missing": sum(1 for x in integrations if x["status"] == "missing"),
        "total": len(integrations),
        "dead_ends": sum(1 for x in integrations if x.get("dead_ends")),
        "optional": sum(1 for x in integrations if x.get("optional")),
        "candidate": sum(1 for x in integrations if x.get("candidate")),
    }
    levels = {level: 0 for level in ("dead_end", "basic_usable", "default_usable", "closed_loop")}
    for item in integrations:
        label = item.get("status_label", "dead_end")
        if label in levels:
            levels[label] += 1
    summary["integration_levels"] = levels
    return {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "summary": summary, "integrations": integrations}


def text_report(data: dict) -> str:
    rows = []
    for x in data["integrations"]:
        rows.append(
            f"{x['status']:7} {x['name']:<38} installed={int(x['installed'])} configured={int(x['configured'])} "
            f"running={int(x['running'])} indexed={int(x['indexed'])} default={int(x['used_by_default'])} "
            f"{x['degraded_reason']}"
        )
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="ignore cache and run all probes")
    ap.add_argument("--deep", action="store_true", help="run slower historical upload audits")
    ap.add_argument("--max-age", type=int, default=120, help="cache max age in seconds")
    args = ap.parse_args()
    data = None
    if not args.refresh and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text())
            age = time.time() - float(cached.get("_cached_at", 0))
            if age <= args.max_age:
                data = cached
                data["_cache"] = {"hit": True, "age_sec": round(age, 1), "path": str(CACHE_PATH)}
        except Exception:
            data = None
    if data is None:
        data = probe(deep=args.deep)
        data["_cached_at"] = time.time()
        data["_cache"] = {"hit": False, "path": str(CACHE_PATH)}
        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except OSError:
            pass
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(text_report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
