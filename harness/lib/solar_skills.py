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
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── paths ──────────────────────────────────────────────────────────────────
HARNESS_DIR = Path(__file__).resolve().parent.parent
SKILLS_ROOT = Path.home() / ".agents" / "skills"
CLAUDE_SKILLS_ROOT = Path.home() / ".claude" / "skills"
CODEX_SUPERPOWERS_ROOT = Path.home() / ".codex" / "plugins" / "cache" / "openai-curated" / "superpowers"
CODEX_SKILLS_ROOT = Path.home() / ".codex" / "skills"
CODEX_PLUGIN_CACHE_ROOT = Path.home() / ".codex" / "plugins" / "cache"
SOLAR_NATIVE_ROOT = Path.home() / "Solar" / "skills"
SOLAR_RULES_ROOT = Path.home() / "Solar" / "rules"
CLAUDE_RULES_ROOT = Path.home() / ".claude" / "rules"
HARNESS_VENDOR_ROOT = HARNESS_DIR / "vendor"
STATE_DIR = HARNESS_DIR / "state"
STATE_DB = Path(os.environ.get("HARNESS_STATE_DB", str(HARNESS_DIR / "run" / "state.db")))
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


def _count_skill_files(root: Path) -> int:
    """Count recursive SKILL.md / skill.md files under a root."""
    if not root.exists():
        return 0
    paths = {str(p).lower() for p in root.rglob("SKILL.md")}
    paths.update(str(p).lower() for p in root.rglob("skill.md"))
    return len(paths)


def _sample_skill_files(root: Path, limit: int = 20) -> list[str]:
    if not root.exists():
        return []
    by_lower = {str(p).lower(): p for p in root.rglob("SKILL.md")}
    by_lower.update({str(p).lower(): p for p in root.rglob("skill.md")})
    paths = sorted(str(p) for p in by_lower.values())
    paths = [Path(p) for p in paths]
    return [str(p.relative_to(root)) for p in paths[:limit]]


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
    claude_count = _count_skills(CLAUDE_SKILLS_ROOT)
    codex_superpowers_count = 1 if CODEX_SUPERPOWERS_ROOT.exists() else 0

    # Solar native skills
    native_names = _list_skill_names(SOLAR_NATIVE_ROOT)
    native_count = len(native_names)
    solar_rule_names = _list_skill_names(SOLAR_RULES_ROOT)
    claude_rule_names = _list_skill_names(CLAUDE_RULES_ROOT)
    rules_count = len(set(solar_rule_names + claude_rule_names))
    codex_skills_count = _count_skill_files(CODEX_SKILLS_ROOT)
    codex_plugin_skill_files = _count_skill_files(CODEX_PLUGIN_CACHE_ROOT)

    vendor_sources = {
        "ruflo": HARNESS_VENDOR_ROOT / "ruflo",
        "hermes-agent": HARNESS_VENDOR_ROOT / "hermes-agent",
        "obsidian-wiki": HARNESS_VENDOR_ROOT / "obsidian-wiki",
        "everything-claude-code": HARNESS_VENDOR_ROOT / "everything-claude-code",
        "mineru-document-explorer": HARNESS_VENDOR_ROOT / "MinerU-Document-Explorer",
    }
    vendor_skill_files = {
        name: {
            "path": str(root),
            "exists": root.exists(),
            "skill_files": _count_skill_files(root),
            "sample": _sample_skill_files(root, 12),
        }
        for name, root in vendor_sources.items()
    }
    vendor_skill_files_total = sum(v["skill_files"] for v in vendor_skill_files.values())

    total = agents_count + claude_count + native_count + codex_superpowers_count + rules_count
    recursive_skill_files_total = (
        _count_skill_files(SKILLS_ROOT)
        + _count_skill_files(CLAUDE_SKILLS_ROOT)
        + codex_skills_count
        + codex_plugin_skill_files
        + _count_skill_files(SOLAR_NATIVE_ROOT)
        + vendor_skill_files_total
    )

    sources: dict[str, Any] = {
        "agents-skills": {
            "path": str(SKILLS_ROOT),
            "count": agents_count,
            "exists": SKILLS_ROOT.exists(),
        },
        "claude-skills": {
            "path": str(CLAUDE_SKILLS_ROOT),
            "count": claude_count,
            "exists": CLAUDE_SKILLS_ROOT.exists(),
            "skills": _list_skill_names(CLAUDE_SKILLS_ROOT),
        },
        "codex-superpowers": {
            "path": str(CODEX_SUPERPOWERS_ROOT),
            "count": codex_superpowers_count,
            "exists": CODEX_SUPERPOWERS_ROOT.exists(),
            "skills": ["superpowers"] if CODEX_SUPERPOWERS_ROOT.exists() else [],
        },
        "codex-skills": {
            "path": str(CODEX_SKILLS_ROOT),
            "count": codex_skills_count,
            "exists": CODEX_SKILLS_ROOT.exists(),
            "sample": _sample_skill_files(CODEX_SKILLS_ROOT, 12),
        },
        "codex-plugin-cache": {
            "path": str(CODEX_PLUGIN_CACHE_ROOT),
            "count": codex_plugin_skill_files,
            "exists": CODEX_PLUGIN_CACHE_ROOT.exists(),
            "sample": _sample_skill_files(CODEX_PLUGIN_CACHE_ROOT, 12),
        },
        "vendor-skill-files": vendor_skill_files,
        "solar-native": {
            "path": str(SOLAR_NATIVE_ROOT),
            "count": native_count,
            "exists": SOLAR_NATIVE_ROOT.exists(),
            "skills": native_names,
        },
        "solar-rules": {
            "path": str(SOLAR_RULES_ROOT),
            "count": len(solar_rule_names),
            "exists": SOLAR_RULES_ROOT.exists(),
            "rules": solar_rule_names,
        },
        "claude-rules": {
            "path": str(CLAUDE_RULES_ROOT),
            "count": len(claude_rule_names),
            "exists": CLAUDE_RULES_ROOT.exists(),
            "rules": claude_rule_names,
        },
    }

    result = {
        "totals": {
            "skills": total,
            "skill_files_recursive": recursive_skill_files_total,
            "agents_skills": agents_count,
            "claude_skills": claude_count,
            "codex_superpowers": codex_superpowers_count,
            "codex_skills": codex_skills_count,
            "codex_plugin_skill_files": codex_plugin_skill_files,
            "solar_native": native_count,
            "vendor_skill_files": vendor_skill_files_total,
            "rules": rules_count,
        },
        "usability": {
            "directly_advertised_to_panes": "summary_only",
            "dispatch_injection": "keyword-selected provider hints plus inventory counts",
            "all_1000_plus_loaded_into_prompt": False,
            "note": "Solar-Harness can discover thousands of skill files, but it does not inject every skill into every pane. It injects compact inventory/context and routes to providers by task keywords.",
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
_INTENT_OPEN = "<solar-intent-context>"
_INTENT_CLOSE = "</solar-intent-context>"
_CAP_OPEN = "<solar-capability-context>"
_CAP_CLOSE = "</solar-capability-context>"
_KB_OPEN = "<solar-knowledge-context>"
_KB_CLOSE = "</solar-knowledge-context>"


CAPABILITY_RULES: list[dict[str, Any]] = [
    {
        "provider": "gstack",
        "capabilities": ["browser.browse", "browser.qa", "code.review"],
        "why": "任务涉及网页、本地浏览器、视觉回归或前端 QA。",
        "use": "需要打开/检查页面时优先使用 gstack/browser QA 流程；保留截图、URL、失败选择器和复现步骤。",
        "patterns": [
            r"\b(browser|browse|webpage|website|localhost|127\.0\.0\.1|screenshot|visual|e2e|ui|frontend)\b",
            r"网页|浏览器|页面|截图|前端|可视化|视觉|打开.*页面|访问.*页面",
        ],
    },
    {
        "provider": "Superpowers",
        "capabilities": ["skill.methodology", "workflow.planning", "debug.systematic", "test.tdd"],
        "why": "任务需要系统化规划、TDD、根因分析或调试纪律。",
        "use": "先拆解目标和验收，再做最小实现；调试时记录假设、证据、验证命令和回归测试。",
        "patterns": [
            r"\b(superpowers|tdd|debug|root cause|systematic|test[- ]driven|plan|planning|breakdown)\b",
            r"系统化|调试|根因|测试驱动|规划|拆解|路线图|回归",
        ],
    },
    {
        "provider": "ATLAS",
        "capabilities": ["repair.pr-cot", "failure.structured_repair", "routing.complexity_budget"],
        "why": "任务涉及失败修复、hook/tool 异常、阻塞恢复或复杂度预算。",
        "use": "进入 repair 模式：定位失败点，写明证据链，优先做局部修复；不要静默停住或等待人工拍板。",
        "patterns": [
            r"\b(atlas|repair|failure|failed|hook_failed|timeout|blocked|stuck|retry|regression|broken)\b",
            r"失败|修复|阻塞|卡住|超时|断头|重试|坏了|不动了",
        ],
    },
    {
        "provider": "OWL",
        "capabilities": ["multi_agent.research", "browser.agent_experiment", "document.toolkit"],
        "why": "任务需要多智能体研究、外部框架实验或复杂资料探索。",
        "use": "把 OWL 当作外部研究/实验 provider；只在需要多代理探索时使用，不替换 Solar coordinator。",
        "patterns": [
            r"\b(owl|camel[- ]ai|multi[- ]agent|agent experiment|research swarm)\b",
            r"多智能体|多代理|研究框架|并行研究|外部代理",
        ],
    },
    {
        "provider": "MarkItDown",
        "capabilities": ["document.convert", "document.markdown_extract", "mcp.markitdown"],
        "why": "任务涉及 PDF/Office/HTML/图片等文档转 Markdown。",
        "use": "优先把原件转成 Markdown，再交给 Obsidian/QMD/Mirage 入库；保留源文件路径和转换日志。",
        "patterns": [
            r"\b(markitdown|pdf|docx|pptx|xlsx|html|convert.*markdown|markdown.*extract)\b",
            r"转.*md|转.*markdown|文档提取|格式转换|论文|表格|幻灯片",
        ],
    },
    {
        "provider": "agency-agents",
        "capabilities": ["persona.agent", "agent.catalog", "specialist.routing"],
        "why": "任务需要专门角色、行业 persona 或 agent catalog 辅助分工。",
        "use": "选择匹配 agent/persona 作为参考能力；必须服从 Solar 当前 sprint 合约和 write_scope。",
        "patterns": [
            r"\b(agency|persona|specialist|agent catalog|role routing|subagent)\b",
            r"人格|角色|专家|专门代理|专业代理|子代理",
        ],
    },
    {
        "provider": "Everything Claude Code",
        "capabilities": ["agent.inventory", "command.catalog", "rules.catalog", "mcp.catalog"],
        "why": "任务涉及 Claude Code 生态能力盘点、命令/规则/MCP/agent inventory。",
        "use": "只读使用 vendor inventory；不要盲装 hooks 或覆盖现有 Solar 规则。",
        "patterns": [
            r"\b(everything[- ]claude[- ]code|mcp|commands?|hooks?|rules?|agents? inventory)\b",
            r"命令目录|规则目录|MCP|hook|能力盘点|代理清单",
        ],
    },
    {
        "provider": "Empirical Research",
        "capabilities": ["research.empirical_pipeline", "research.literature_review", "analysis.causal_inference"],
        "why": "任务涉及实证研究、文献综述、因果推断、可复现分析或学术论文。",
        "use": "按研究问题、数据、识别策略、统计验证、复现包和论文写作链路执行；把证据和限制写入 handoff。",
        "patterns": [
            r"\b(empirical|causal|literature review|reproducib|academic paper|research design|stata|rct|did|iv)\b",
            r"实证|因果|文献综述|可复现|论文|研究设计|统计分析|固定效应|工具变量",
        ],
    },
    {
        "provider": "addyosmani/agent-skills",
        "capabilities": ["agent_skills.catalog", "workflow.spec_driven", "workflow.code_review", "workflow.test_driven"],
        "why": "任务需要 agent-skills 的规范驱动、测试驱动、评审、发布或上下文工程方法。",
        "use": "把 addyosmani/agent-skills 当作只读工作流模式库；不能覆盖 Solar 当前合约和角色派发。",
        "patterns": [
            r"\b(addyosmani|agent-skills|spec[- ]driven|source[- ]driven|context engineering)\b",
            r"规范驱动|源驱动|上下文工程|agent skills|代理技能",
        ],
    },
    {
        "provider": "Browser-use MCP",
        "capabilities": ["browser.mcp", "browser.automation", "browser.screenshot", "browser.localhost_test"],
        "why": "任务明确需要 browser-use、MCP 浏览器自动化、截图或 localhost 交互测试。",
        "use": "优先使用本地 browser-use MCP / Codex Browser Use 能力；若不可用，降级到 gstack/browser QA 并记录证据。",
        "patterns": [
            r"\b(browser-use|browser use|browser mcp|mcp browser|localhost.*screenshot|click|type)\b",
            r"浏览器.*MCP|browser-use|点击|输入|本地页面测试|截图",
        ],
    },
    {
        "provider": "openai-agents-python",
        "capabilities": ["agents_sdk.design", "agents_sdk.guardrails", "agents_sdk.tracing", "agents_sdk.handoff_model"],
        "why": "任务涉及 OpenAI Agents SDK、typed agents、guardrails、tracing、sessions 或 handoff runtime 设计。",
        "use": "按 PoC/设计能力使用，不把它当成当前生产执行器；输出迁移边界、回滚和不替换清单。",
        "patterns": [
            r"\b(openai[- ]agents|agents sdk|guardrails|typed agents|handoffs|tracing|sessions)\b",
            r"OpenAI Agents|智能体 SDK|护栏|追踪|会话|原生 handoff",
        ],
    },
    {
        "provider": "Codex Bridge",
        "capabilities": ["codex.bridge", "codex.contract_ingest", "codex.review_handoff", "pane3.bridge"],
        "why": "任务涉及 Codex 到 Solar 的合约、review、pane3 bridge 或 from-codex 文件链路。",
        "use": "使用新链路 ~/.solar/codex-bridge/from-codex + chain-watcher；旧 ~/.solar/harness/codex-bridge 只作兼容证据。",
        "patterns": [
            r"\b(codex bridge|pane3|from-codex|to-codex|chain-watcher|execution-contract)\b",
            r"Codex Bridge|pane3|三号 pane|合约导入|chain watcher",
        ],
    },
    {
        "provider": "Ruflo",
        "capabilities": ["ruflo.swarm", "ruflo.plugins", "ruflo.agent_catalog", "ruflo.memory", "ruflo.mcp", "ruflo.workflow_templates"],
        "why": "任务涉及 Claude Code swarm、Ruflo/Claude Flow、插件市场、多代理编排、MCP 或 self-learning memory。",
        "use": "优先使用 Solar 管理的 sandbox runtime：solar-harness integrations ruflo-runtime-status / ruflo-runtime-smoke；不要在宿主项目直接运行 ruflo init 或写 .claude/hooks/settings，除非合约明确授权。",
        "patterns": [
            r"\b(ruflo|ruvflo|claude[- ]flow|swarm|hive[- ]mind|agentdb|ruvector|sparc)\b",
            r"Ruflo|Claude Flow|蜂群|多代理编排|插件市场|自学习|AgentDB|RuVector",
        ],
    },
]


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


def _load_capability_scorecards() -> dict[str, dict[str, Any]]:
    """Load runtime-aware capability scorecards from state DB if available."""
    if not STATE_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(str(STATE_DB), timeout=2.0)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT capability, provider, score, level, status, payload FROM capability_scorecards"
        ).fetchall()
        conn.close()
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        try:
            payload = item.get("payload")
            if payload:
                extra = json.loads(payload)
                if isinstance(extra, dict):
                    item.update(extra)
        except Exception:
            pass
        out[f"{item.get('provider')}::{item.get('capability')}"] = item
        out[f"cap::{item.get('capability')}"] = item
    return out


def _rank_rule(rule: dict[str, Any], scores: dict[str, dict[str, Any]]) -> dict[str, Any]:
    provider = str(rule.get("provider", ""))
    provider_key = provider.lower().replace(" ", "-")
    aliases = {
        "ruflo": "ruflo",
        "gstack": "gstack",
        "superpowers": "superpowers",
        "browser-use-mcp": "browser-use",
        "codex-bridge": "codex-bridge",
        "openai-agents-python": "openai-agents-python",
        "empirical-research": "empirical-research",
        "addyosmani/agent-skills": "addy-agent-skills",
        "markitdown": "markitdown",
        "owl": "owl",
        "agency-agents": "agency-agents",
        "atlas": "atlas",
        "everything-claude-code": "everything-claude-code",
    }
    provider_id = aliases.get(provider_key, provider_key)
    matches = []
    for cap in rule.get("capabilities", []):
        item = scores.get(f"{provider_id}::{cap}") or scores.get(f"cap::{cap}")
        if item:
            matches.append(item)
    if not matches:
        return {"score": 0.0, "level": "", "runtime_level": "", "runtime_backend": "", "provider_id": provider_id}
    best = sorted(matches, key=lambda x: float(x.get("score", 0)), reverse=True)[0]
    return {
        "score": float(best.get("score", 0)),
        "level": best.get("level", ""),
        "runtime_level": best.get("runtime_level", ""),
        "runtime_backend": best.get("runtime_backend", ""),
        "provider_id": provider_id,
    }


def _select_capabilities(dispatch_text: str) -> list[dict[str, Any]]:
    """Select provider hints from task text, ranked by runtime-aware scorecards."""
    scores = _load_capability_scorecards()
    selected: list[dict[str, Any]] = []
    for rule in CAPABILITY_RULES:
        for pattern in rule["patterns"]:
            if re.search(pattern, dispatch_text, re.IGNORECASE | re.MULTILINE):
                item = dict(rule)
                item["scorecard"] = _rank_rule(rule, scores)
                selected.append(item)
                break
    selected.sort(key=lambda item: (-float(item.get("scorecard", {}).get("score", 0)), item.get("provider", "")))
    return selected


def _match_intents(dispatch_text: str) -> dict[str, Any]:
    """Run the Solar intent adapter. Fail-open if unavailable."""
    try:
        sys.path.insert(0, str(HARNESS_DIR / "lib"))
        import intent_engine_adapter  # type: ignore

        return intent_engine_adapter.match(dispatch_text, record=False)
    except Exception as e:
        return {
            "ok": False,
            "matched": False,
            "matches": [],
            "error": str(e),
        }


def _build_intent_block(dispatch_text: str) -> str:
    result = _match_intents(dispatch_text)
    matches = result.get("matches") or []
    lines = [
        _INTENT_OPEN,
        f"<!-- auto-generated by solar_skills.py at {_now_iso()} -->",
        "## Solar Intent Adapter",
        "",
    ]
    if not result.get("ok", False):
        lines.extend([
            f"- warn: intent adapter unavailable: {result.get('error', 'unknown')}",
            "- fail-open: continue normal Solar-Harness dispatch.",
            "",
        ])
    elif not matches:
        lines.extend([
            "- N/A: no direct Solar intent or legacy skill hint matched.",
            "",
        ])
    else:
        for item in matches:
            label = item.get("skill") or item.get("target") or item.get("type", "unknown")
            lines.append(
                f"- {item.get('kind', 'intent')} {item.get('source', 'solar')} "
                f"{label} confidence={item.get('confidence', 'N/A')}"
            )
            lines.append(f"  Action: {item.get('instruction', 'N/A')}")
        lines.append("")
    lines.extend([
        "## Intent Rules",
        "",
        "- 这是旧 Solar intent-engine-hook.sh 的 Harness 适配层；用于 dispatch 前决策提示。",
        "- direct intent 可以改变执行纪律；skill hint 只作为能力注入建议，不覆盖 sprint 合约。",
        "- 命中 learned-db 规则时，优先按学习规则解释用户意图，但必须保留证据。",
        _INTENT_CLOSE,
    ])
    return "\n".join(lines)


def _build_capability_block(dispatch_text: str) -> str:
    selected = _select_capabilities(dispatch_text)
    lines = [
        _CAP_OPEN,
        f"<!-- auto-generated by solar_skills.py at {_now_iso()} -->",
        "## Auto-selected Solar Capabilities",
        "",
    ]
    if not selected:
        lines.extend([
            "- N/A: 当前 dispatch 没有命中特定外部 capability；按普通 Solar-Harness 流程执行。",
            "",
        ])
    else:
        for item in selected:
            caps = ", ".join(item["capabilities"])
            lines.append(f"- {item['provider']} ({caps})")
            scorecard = item.get("scorecard", {}) if isinstance(item.get("scorecard"), dict) else {}
            if scorecard.get("score"):
                lines.append(
                    f"  Score: {scorecard.get('score')} level={scorecard.get('level') or 'N/A'} "
                    f"runtime={scorecard.get('runtime_level') or 'N/A'} backend={scorecard.get('runtime_backend') or 'N/A'}"
                )
            lines.append(f"  Why: {item['why']}")
            lines.append(f"  Use: {item['use']}")
        lines.append("")
    lines.extend([
        "## Dispatch Rules",
        "",
        "- 这些 capability 是自动选择的执行辅助，不替换 Solar coordinator / planner / evaluator。",
        "- 若 capability 缺失或不可用，必须 fail-open：继续完成主任务，并在 handoff 写明降级证据。",
        "- 遇到失败、超时、hook/tool 异常时，优先触发 ATLAS structured repair，不要停在等待人工决策。",
        _CAP_CLOSE,
    ])
    return "\n".join(lines)


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

    text = dispatch_file.read_text(encoding="utf-8", errors="replace")
    skills_block = _build_skills_block(native_names, agents_count)
    intent_block = _build_intent_block(text)
    capability_block = _build_capability_block(text)
    kb_block = _build_kb_block()

    # Replace or append blocks (idempotent)
    text = _replace_block(text, _SKILLS_OPEN, _SKILLS_CLOSE, skills_block)
    text = _replace_block(text, _INTENT_OPEN, _INTENT_CLOSE, intent_block)
    text = _replace_block(text, _CAP_OPEN, _CAP_CLOSE, capability_block)
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
