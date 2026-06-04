# Plan — P0 Solar KB Default QMD Fallback

**Sprint**: sprint-20260508-kb-qmd-default-fallback
**Created**: 2026-05-08T15:50:47Z
**Topology**: standard
**Primary Builder**: builder_main

## Goal

Make Solar default knowledge context find qmd-backed Obsidian notes such as `大模型热力学` without requiring the user to explicitly ask for qmd search.

## Tasks

### D1 — Retriever Fallback

Add qmd fallback to `solar-knowledge-context.py`:

- Locate qmd via `QMD_BIN`, `/Users/lisihao/.npm-global/bin/qmd`, then `PATH`.
- Run `qmd search <query> -c solar-wiki --json -n <limit>` with remaining timeout budget.
- Normalize results to existing hit schema with `source=qmd:solar-wiki`.
- Dedupe DB/qmd hits by path/title.
- Enforce `--max-chars`.

### D2 — Hook Behavior

Verify `solar-knowledge-context.sh` still:

- Emits `<solar-knowledge-context>` when qmd fallback hits.
- Emits nothing when `SOLAR_KB_CONTEXT=0`.
- Fails open on qmd missing, bad JSON, timeout, or DB lock.

### D3 — Tests

Create `tests/test-solar-kb-qmd-fallback.sh` covering:

- DB miss + qmd hit for `大模型热力学`.
- qmd missing fail-open.
- disable flag.
- max chars budget.
- valid JSON output.

### D4 — Dispatch Path Clarification

Document whether harness-dispatched panes receive UserPromptSubmit hook context. If not, propose or implement minimal dispatch text sourced-context append.

### D5 — Runbook

Document verify commands, disable flag, qmd path, collection, and common failures.

## Acceptance

- A1 retriever command from PRD passes for `大模型热力学`.
- A2 hook command emits `<solar-knowledge-context>`.
- A3 qmd missing still returns valid JSON.
- A4 `SOLAR_KB_CONTEXT=0` emits no hook output.
- A5 `--max-chars 500` keeps `total_chars <= 500`.
- A6 test script passes.
- A7 dispatch context note exists.

## Handoff

Builder must write `/Users/lisihao/.solar/harness/sprints/sprint-20260508-kb-qmd-default-fallback.handoff.md` with changed files, test output, and dispatch-path conclusion.
