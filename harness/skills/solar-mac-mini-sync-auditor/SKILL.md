---
name: solar-mac-mini-sync-auditor
description: Use this skill when Solar or solar-harness needs Mac mini sync auditing, local-vs-remote harness drift checks, sync-required manifest review, remote SSH verification, sha256 comparison, or safe sync planning without overwriting active remote work.
---

# Solar Mac Mini Sync Auditor

Use this skill to audit whether `/Users/lisihao/.solar/harness` and
`lisihao@100.122.223.55:/Users/lisihao/.solar/harness` are consistent enough
for Solar/Solar-Harness work.

## Command

Run the bundled deterministic auditor:

```bash
~/.codex/skills/solar-mac-mini-sync-auditor/scripts/run.sh --json
```

For local-only smoke tests:

```bash
~/.codex/skills/solar-mac-mini-sync-auditor/scripts/run.sh --no-remote --json
```

## Checks

- Local harness directory exists.
- `state/mac-mini-sync-required.jsonl` is parsed and summarized.
- Required/blocked sync entries are highlighted.
- Remote SSH reachability is verified when enabled.
- Remote harness directory, `coord-status`, and status-file count are checked.
- A small critical file set is compared by sha256 when remote is reachable.

## Rules

- Do not create a sprint.
- Do not blindly copy active sprint artifacts.
- Do not overwrite Mac mini files unless a backup path and sync manifest exist.
- If SSH fails, report `error` and do not claim remote parity.
- If manifest has `required` or `blocked` entries, report `warn/error` with the
  most recent reasons and files.

## Output

The script emits JSON with:

- `ok`
- `severity`
- `local`
- `manifest`
- `remote`
- `drift`
- `current_problem`
- `next_step`
