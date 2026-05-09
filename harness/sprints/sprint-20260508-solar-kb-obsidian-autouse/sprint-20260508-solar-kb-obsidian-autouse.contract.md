---
sprint_id: sprint-20260508-solar-kb-obsidian-autouse
title: Solar KB default retrieval + Obsidian seamless sync
priority: P0
lane: reliability
owner: planner
created_at: 2026-05-08T06:40:20Z
status: contract_ready
handoff_to: planner
---

# Sprint Contract — Solar KB Default Retrieval + Obsidian Seamless Sync

## Intent

Make Solar's knowledge layer actually usable by default: every relevant agent session should receive bounded, sourced context from `~/.solar/solar.db`, and `/Users/sihaoli/Knowledge` should sync bidirectionally enough that Obsidian notes are searchable by Solar and Solar DB knowledge is exportable to Obsidian without manual glue.

This sprint fixes the current gap: Solar has a large database-backed knowledge base, but active hooks mostly inject reminders or small fixed snippets; Obsidian integration exists, but is not yet a seamless default retrieval path.

## Current Evidence

- Active Claude hooks already touch `~/.solar/solar.db` at session start, prompt submit, and session end.
- `solar-session-start.sh` reads `v_startup_context`, but that view only injects core rules, personality, and up to 5 high-confidence learnings.
- `unified-query.ts` and `knowledge-query.ts` exist, but are not automatically called by active hooks for every relevant prompt.
- `memory-influence.sh` appears schema-incompatible with `evo_memory_semantic`: it queries `content`, while the table uses `value`; it also needs explicit SQL parentheses around namespace/content matching.
- `knowledge-sync.ts` has Obsidian support, but currently points at old paths, not `/Users/sihaoli/Knowledge`.
- No active `com.solar.knowledge-sync` LaunchAgent or knowledge-sync daemon was found.
- Existing Obsidian bridge can export Solar DB rows into `_raw/solar-db-export/`, but `/Users/sihaoli/Knowledge` content is not indexed into `fts_unified_search` by default.

## Non-Goals

- Do not rewrite the whole Solar memory architecture.
- Do not dump full DB rows or full Obsidian pages into prompts.
- Do not require cloud services or new non-stdlib daemons for the status server.
- Do not mutate user vault structure except documented `_raw/`, generated wiki pages, and sync metadata.

## Deliverables

1. `~/.solar/harness/lib/solar-knowledge-context.py`
   - Bounded retrieval router for Solar DB + Obsidian vault.
   - Supports `--query`, `--json`, `--max-chars`, `--timeout-ms`, `--fail-open`.
   - Emits source path/table/id for every hit.

2. `~/.claude/hooks/solar-knowledge-context.sh`
   - UserPromptSubmit hook wrapper.
   - Calls the router only when prompt is likely knowledge-dependent.
   - Injects a compact `<solar-knowledge-context>` block.
   - Fails open silently on timeout or missing DB/vault.

3. `~/.claude/hooks/memory-influence.sh`
   - Fix schema mismatch against `evo_memory_semantic`.
   - Fix SQL precedence with explicit parentheses.
   - Keep output bounded and sourced.

4. `~/.claude/core/cortex/knowledge-sync.ts`
   - Add `/Users/sihaoli/Knowledge` as first-class Obsidian vault source.
   - Prefer configured vault path from Solar wiki config when available.
   - Sync markdown summaries/frontmatter into Solar searchable tables.

5. `~/.solar/harness/integrations/obsidian-wiki-bridge.sh`
   - Keep DB-to-Obsidian export incremental.
   - Add or document `--no-dispatch`, `--since`, and manifest behavior.

6. `~/.solar/harness/integrations/wiki-capture-server.py`
   - Expose sync status for capture, raw queue, dispatch queue, and Solar DB import.
   - Do not block upload/capture while ingest is running.

7. `~/.solar/harness/tests/test-solar-kb-obsidian-autouse.sh`
   - End-to-end smoke tests for default retrieval, Obsidian-to-Solar sync, DB-to-Obsidian export, and fail-open behavior.

8. `~/.solar/harness/docs/solar-kb-obsidian-autouse.md`
   - Operator runbook: install, verify, disable, repair sync, inspect status.

## Acceptance Criteria

### A1 — Default Solar KB Context Is Real

Given a prompt about an existing Solar memory topic, the hook must inject sourced context, not just reminders.

Required behavior:
- Query `~/.solar/solar.db` through an existing or new retrieval path.
- Include source table/path/id.
- Limit injected context to 2,000 chars by default.
- Return within 800ms p95 on local machine or fail open.

Verify:

```bash
python3 ~/.solar/harness/lib/solar-knowledge-context.py \
  --query "Solar 记忆系统" \
  --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hits"] and d["elapsed_ms"] < 800'
```

<!-- verify: cmd="python3 ~/.solar/harness/lib/solar-knowledge-context.py --query 'Solar 记忆系统' --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"hits\"] and d[\"elapsed_ms\"] < 800'" -->

### A2 — Obsidian Vault Is Indexed Into Solar Search

Given `/Users/sihaoli/Knowledge` contains wiki pages, Solar search must find those pages without manual grep.

Required behavior:
- Markdown title, tags, summary/frontmatter, path, and selected body snippets are indexed.
- Existing processed sample `lumen-orbit-why-train-ai-in-space-2024.md` or equivalent must appear in Solar retrieval.
- Sync must be incremental via manifest or mtime tracking.

Verify:

```bash
python3 ~/.solar/harness/lib/solar-knowledge-context.py \
  --query "orbital data center Lumen Orbit" \
  --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert any("Knowledge" in (h.get("source","")+h.get("path","")) for h in d["hits"])'
```

<!-- verify: cmd="python3 ~/.solar/harness/lib/solar-knowledge-context.py --query 'orbital data center Lumen Orbit' --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert any(\"Knowledge\" in (h.get(\"source\",\"\")+h.get(\"path\",\"\")) for h in d[\"hits\"])'" -->

### A3 — Solar DB Exports To Obsidian Incrementally

Existing command `solar-harness wiki import-solar-db` must remain functional and safe.

Required behavior:
- Writes generated markdown under `/Users/sihaoli/Knowledge/_raw/solar-db-export/`.
- Does not expose obvious secrets.
- Does not overwrite true user-authored vault pages.
- Supports dry/no-dispatch mode for tests.

Verify:

```bash
solar-harness wiki import-solar-db --scope solar --per-table-limit 3 --no-dispatch
test -d /Users/sihaoli/Knowledge/_raw/solar-db-export
```

<!-- verify: cmd="solar-harness wiki import-solar-db --scope solar --per-table-limit 3 --no-dispatch && test -d /Users/sihaoli/Knowledge/_raw/solar-db-export" -->

### A4 — `memory-influence.sh` No Longer Silently Misses Semantic Memory

Required behavior:
- Query semantic memories using `value` for `evo_memory_semantic`.
- Use explicit SQL grouping for namespace filters and text filters.
- Keep hook exit code fail-open when DB is missing.

Verify:

```bash
bash -n ~/.claude/hooks/memory-influence.sh
sqlite3 ~/.solar/solar.db "select value from evo_memory_semantic limit 1;" >/dev/null
```

<!-- verify: cmd="bash -n ~/.claude/hooks/memory-influence.sh && sqlite3 ~/.solar/solar.db 'select value from evo_memory_semantic limit 1;' >/dev/null" -->

### A5 — Sync Is Automatic And Observable

Required behavior:
- A launchd job, harness daemon, or capture-server scheduler runs Obsidian-to-Solar sync without manual command execution.
- Status endpoint exposes `solar_kb` and `obsidian_sync` sections.
- The status UI must show last sync time, indexed note count, pending raw files, last error, and whether default hook injection is enabled.

Verify:

```bash
curl -fsS http://127.0.0.1:8765/healthz >/dev/null
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "solar_kb" in d and "obsidian_sync" in d'
```

<!-- verify: cmd="curl -fsS http://127.0.0.1:8765/healthz >/dev/null && curl -fsS http://127.0.0.1:8765/status | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"solar_kb\" in d and \"obsidian_sync\" in d'" -->

### A6 — Fail-Open Safety

Required behavior:
- Missing DB, missing vault, locked DB, or slow query must not block the agent.
- Hook output must be empty or compact warning-free on failure.
- No stack traces in interactive prompt flow.

Verify:

```bash
SOLAR_DB=/tmp/missing-solar.db \
python3 ~/.solar/harness/lib/solar-knowledge-context.py \
  --query "test" --fail-open --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hits"] == []'
```

<!-- verify: cmd="SOLAR_DB=/tmp/missing-solar.db python3 ~/.solar/harness/lib/solar-knowledge-context.py --query test --fail-open --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"hits\"] == []'" -->

### A7 — Regression Tests Cover The Full Path

Required behavior:
- Test suite creates temp vault and temp DB fixtures.
- Covers DB retrieval, vault indexing, export import, hook wrapper, fail-open, and status JSON.
- No test writes outside temp paths except explicit integration smoke tests.

Verify:

```bash
bash ~/.solar/harness/tests/test-solar-kb-obsidian-autouse.sh
```

<!-- verify: cmd="bash ~/.solar/harness/tests/test-solar-kb-obsidian-autouse.sh" -->

## Stop Rules

- Stop if UserPromptSubmit knowledge hook adds more than 800ms p95 latency.
- Stop if implementation requires dumping more than 2,000 chars of retrieved context by default.
- Stop if secrets or credentials appear in generated Obsidian pages.
- Stop if builder proposes full DB/vault rewrite instead of incremental sync.
- Stop if status server requires external dependencies or binds outside `127.0.0.1`.

## Planner Instructions

1. Read this contract and produce an implementation plan:
   `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-solar-kb-obsidian-autouse.plan.md`
2. Split implementation into three independent slices:
   - Slice 1: retrieval hook + `memory-influence.sh` fix.
   - Slice 2: Obsidian-to-Solar indexing + DB-to-Obsidian export hardening.
   - Slice 3: status UI + automation + tests/docs.
3. Dispatch at least two builders when available. Do not put the whole sprint onto one pane.
4. Require evaluator review against A1-A7 before marking `passed`.

## Definition Of Done

- All A1-A7 verify commands pass.
- Status UI exposes Solar KB and Obsidian sync state.
- A new Claude session receives useful sourced Solar/Obsidian context automatically for knowledge-dependent prompts.
- Documentation includes disable/rollback command for the hook and sync job.
