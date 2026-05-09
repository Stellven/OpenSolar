# Design — Solar Capability Plane Unification

Sprint: `sprint-20260509-solar-capability-plane-unification`  
Priority: P0  
Lane: reliability

## 1. Current Architecture Finding

```text
┌──────────────────────────────┬────────────────────────────────────────────────────┐
│ Layer                        │ Reality                                            │
├──────────────────────────────┼────────────────────────────────────────────────────┤
│ Solar source                  │ /Users/sihaoli/Solar, contains 38 native skills    │
│ Solar runtime                 │ /Users/sihaoli/.solar, contains solar.db/cortex    │
│ Harness live control          │ /Users/sihaoli/.solar/harness, real CLI/coordinator│
│ Skills universe               │ ~/.agents + ~/.claude + ~/.codex + ~/Solar + vendor│
│ Dispatch path                 │ tmux send-keys reads .dispatch.md                 │
└──────────────────────────────┴────────────────────────────────────────────────────┘
```

The system has assets but no capability plane. The fix is not another wiki/report; it is a small runtime bridge inserted before dispatch.

## 2. Target Stack

```text
User / Autopilot / Coordinator
        │
        ▼
dispatch_to_pane()
        │
        ├─ skills inject
        │    ├─ read instruction/PRD/contract
        │    ├─ inventory skills from all roots
        │    ├─ rank top skills by keyword/name/description
        │    ├─ call solar-unified-context.py for KB hits
        │    └─ append idempotent context blocks
        │
        ▼
tmux pane receives: "读取并执行 <dispatch.md>"
        │
        ▼
Claude pane sees dispatch + skill context + KB context + MCP limits
```

## 3. New Modules

```text
┌──────────────────────────────┬────────────────────────────────────────────────────┐
│ File                         │ Responsibility                                     │
├──────────────────────────────┼────────────────────────────────────────────────────┤
│ lib/solar_skills.py           │ inventory, doctor, rank, inject                   │
│ lib/harness_graph.py          │ static dependency graph generation                │
│ tests/test-skills-bridge.sh   │ CLI + idempotent inject + no secret regression    │
│ tests/test-harness-graph.sh   │ graph JSON/Mermaid + duplicate case regression    │
│ status-server.py              │ expose pane capability summary                    │
│ pane-launcher.sh              │ startup banner displays skill/MCP/context summary │
│ coordinator.sh                │ pre-dispatch inject wrapper                       │
└──────────────────────────────┴────────────────────────────────────────────────────┘
```

## 4. CLI Contract

```bash
solar-harness skills inventory [--json|--markdown] [--refresh]
solar-harness skills doctor [--json]
solar-harness skills inject --sid <sid> --instruction-file <path> [--json]
solar-harness skills pane-status [--json]
solar-harness graph [--json|--markdown|--format mermaid] [--out <path>]
```

## 5. Inventory Model

Each skill record:

```json
{
  "name": "review",
  "root": "/Users/sihaoli/Solar/skills",
  "runtime": "solar-native",
  "path": "/Users/sihaoli/Solar/skills/review/SKILL.md",
  "description": "first heading or frontmatter description",
  "status": "usable",
  "conflicts": ["~/.agents/skills/review"]
}
```

Runtime labels:

- `solar-native`: `/Users/sihaoli/Solar/skills`
- `claude`: `~/.claude/skills`
- `codex`: `~/.codex/skills`
- `agents`: `~/.agents/skills`
- `obsidian-wiki-vendor`: `~/.solar/harness/vendor/obsidian-wiki/.skills`
- `mineru-vendor`: `~/.solar/harness/vendor/MinerU-Document-Explorer/skills`
- `ecc-vendor`: `~/.solar/harness/vendor/everything-claude-code/skills`

## 6. Inject Block Format

```xml
<solar-skills-context generated_at="..." sid="...">
- recommended: review | reason: task mentions eval/review
- available_roots: claude=46 agents=1533 codex=3 solar=38 vendor=...
- pane_constraints: lab-builder uses strict empty MCP; builder uses full tools
</solar-skills-context>

<solar-knowledge-context generated_at="..." sid="...">
- [qmd] ...
- [solar_db] ...
- degraded_sources: ...
</solar-knowledge-context>
```

Markers make injection idempotent. Replace existing block instead of appending duplicates.

## 7. Pane Capability Summary

Data source should be computed by `solar-harness skills pane-status --json`:

```json
{
  "solar-harness:0.2": {
    "persona": "builder",
    "model": "Claude Sonnet",
    "mcp_mode": "full",
    "skill_roots": ["~/.claude/skills", "~/.agents/skills", "~/Solar/skills"],
    "kb_context": "dispatch-injected"
  }
}
```

Lab builders should show `mcp_mode=empty-strict` when they use `--strict-mcp-config --mcp-config config/empty-mcp.json`.

## 8. Graph Command

`lib/harness_graph.py` statically scans:

- `solar-harness.sh`
- `coordinator.sh`
- `pane-launcher.sh`
- `lib/*.sh`, `lib/*.py`
- `integrations/*.sh`
- `personas/*.md`
- `templates/*.md`
- `schemas/*`
- `vendor/*`

It outputs both machine JSON and Mermaid. This is a live dependency graph, not another hand-written architecture document.

## 9. Solar Original Skill Extraction

Initial Solar native list has 38 skills:

`a2a-hub`, `agent`, `agent-orchestrator`, `apple-calendar`, `banner`, `benchmark`, `browser-automation`, `build`, `clawdwork`, `commit`, `docs`, `email-to-calendar`, `fast-browser-use`, `mcp-builder`, `mode`, `obsidian-daily`, `obsidian-direct`, `office`, `office-email`, `office-notes`, `office-notion`, `office-reminders`, `office-tasks`, `office-trello`, `phase`, `pr`, `report`, `restore`, `review`, `save`, `skill-creator`, `skin-check`, `solar`, `solar-web`, `stats`, `status`, `test`, `webapp-testing`.

Builder must classify each as `usable | conflict | stale | needs_migration`, but must not overwrite runtime skills.

## 10. Stop Rules

- If dispatch injection breaks any existing coordinator test, revert injection to fail-open wrapper before proceeding.
- If duplicate case cleanup affects `solar-harness wiki`, `mirage`, `data-plane`, or `status-server` CLI output, stop and report.
- If any token appears in inventory/doctor output, fail sprint.
