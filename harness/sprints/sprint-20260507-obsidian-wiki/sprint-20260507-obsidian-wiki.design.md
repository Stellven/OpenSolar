# Design — Solar Harness x Obsidian Wiki Integration

Sprint: sprint-20260507-obsidian-wiki
Source repo: https://github.com/Ar9av/obsidian-wiki

## Architecture

```text
┌────────────────────┐
│ solar-harness wiki │
└─────────┬──────────┘
          │
          ├─ install/status ──> ~/.solar/harness/integrations/obsidian-wiki.sh
          │                         │
          │                         ├─ clone/update upstream repo
          │                         ├─ write ~/.obsidian-wiki/config
          │                         ├─ create vault skeleton
          │                         └─ install safe symlinks
          │
          ├─ export-sprint ──> vault/_raw/solar-harness/<sid>.md
          │                         │
          │                         └─ contract + plan + handoff + eval + status + events summary
          │
          ├─ update/query ───> dispatch file / agent-readable instructions
          │
          └─ status-server ──> /status wiki readiness block
```

## File Plan

```text
┌────────────────────────────────────────────┬──────────────────────────────────────────────┐
│ File                                       │ Responsibility                               │
├────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ integrations/obsidian-wiki.sh              │ install/status/export/update/query commands  │
│ solar-harness.sh                           │ add wiki subcommand routing                  │
│ lib/symphony/status-server.py              │ add wiki readiness to HTTP status            │
│ schemas/obsidian-wiki-status.schema.json   │ validate status JSON                         │
│ test-obsidian-wiki-integration.sh          │ shell tests with temp repo/vault             │
│ docs/obsidian-wiki-integration.md          │ operator docs + examples                     │
└────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

## Command Contract

```bash
solar-harness wiki install --vault "$HOME/Documents/Solar Wiki" [--repo /path/to/obsidian-wiki] [--refresh]
solar-harness wiki status [--json]
solar-harness wiki export-sprint <sid> [--redact|--full]
solar-harness wiki update [--project <path>] [--mode append|full]
solar-harness wiki query "<question>" [--quick]
```

## Data Model

Integration state:

```json
{
  "configured": true,
  "repo_path": "~/.solar/harness/vendor/obsidian-wiki",
  "vault_path": "~/Documents/Solar Wiki",
  "config_path": "~/.obsidian-wiki/config",
  "skills_installed": {
    "codex": true,
    "claude": true,
    "agents": true
  },
  "last_exported_sprint": "sprint-...",
  "last_checked_at": "ISO-8601"
}
```

## Export Rules

- Default export mode is redacted summary.
- Include file paths and result summaries, not full terminal transcript dumps.
- Include event counts and selected structured events.
- Include `visibility/internal` tag for Solar internals.
- Write only under `$OBSIDIAN_VAULT_PATH/_raw/solar-harness/`.
- Never delete or mutate existing vault pages from Solar commands; ingestion remains an agent skill responsibility.

## Implementation Slices

1. S1 installer/status: non-interactive clone/config/vault/skill symlink flow.
2. S2 export-sprint: raw markdown source generation for sprint artifacts.
3. S3 wiki command bridge: update/query instruction generation and dispatch-safe execution.
4. S4 status server: readiness JSON/HTML block.
5. S5 docs/tests: end-to-end temp vault tests, docs, examples.

## Safety Model

- Treat upstream skill files as instructions, not shell code, except `setup.sh` inspection. Do not run upstream interactive setup in tests.
- Symlink only when target is absent or already a symlink. Never replace real directories.
- Use temp vaults in tests.
- Keep QMD optional and detect-only.
- Do not export secrets. Redact obvious tokens and key patterns.

