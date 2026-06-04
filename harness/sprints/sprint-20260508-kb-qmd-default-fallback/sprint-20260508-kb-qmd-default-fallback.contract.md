---
sprint_id: sprint-20260508-kb-qmd-default-fallback
title: P0 Solar KB Default QMD Fallback
priority: P0
lane: reliability
owner: planner
topology: standard
created_at: 2026-05-08T15:24:00Z
status: contract_ready
handoff_to: planner
blocks:
  - sprint-20260508-data-plane-closeout
related:
  - sprint-20260508-solar-kb-obsidian-autouse
  - sprint-20260508-wiki-upload-ingest-closure
---

# Sprint Contract — P0 Solar KB Default QMD Fallback

## Intent

Make Solar's default knowledge context actually retrieve from the user's knowledge base before work starts. The existing `UserPromptSubmit` hook is installed, but it only succeeds when `~/.solar/solar.db` has matching rows. `/Users/lisihao/Knowledge` is already searchable through `qmd -c solar-wiki`, so the default context path must fall back to qmd when Solar DB/FTS misses.

The user-facing rule is simple: if `qmd search "大模型热力学" -c solar-wiki` can find a note, then Solar's default work context must also be able to inject that note as sourced `<solar-knowledge-context>`.

## Current Evidence

- Hook is registered in `/Users/lisihao/.claude/settings.json` under `UserPromptSubmit`:
  - `/Users/lisihao/.claude/hooks/solar-knowledge-context.sh`
- Retrieval script exists:
  - `/Users/lisihao/.solar/harness/lib/solar-knowledge-context.py`
- Current retrieval misses vault content:
  - `python3 ~/.solar/harness/lib/solar-knowledge-context.py --query '大模型热力学' --json`
  - observed result: `"hits": []`
- qmd can find the same knowledge:
  - `/Users/lisihao/.npm-global/bin/qmd search '大模型热力学' -c solar-wiki --json -n 3`
  - observed result: `qmd://solar-wiki/synthesis/大模型热力学-thermodynamics-of-large-models.md`
- `obsidian_vault_index` is not currently present in `~/.solar/solar.db`, so relying only on Solar DB/FTS is insufficient.

## Non-Goals

- Do not rewrite the whole Solar memory architecture.
- Do not require a full vault reindex before default retrieval works.
- Do not dump large raw documents into prompts.
- Do not block user prompts when qmd or DB is locked/unavailable.
- Do not execute source document content or follow instructions inside retrieved notes.

## Deliverables

1. **qmd fallback in `solar-knowledge-context.py`**
   - Add a bounded fallback after DB/FTS/vault-index misses or partial hits.
   - Use qmd collection `solar-wiki` by default.
   - Locate qmd via:
     - `$QMD_BIN`
     - `/Users/lisihao/.npm-global/bin/qmd`
     - `command -v qmd`
   - Parse `--json` output.
   - Convert qmd results to the existing hit schema:
     - `source`
     - `table`
     - `id`
     - `title`
     - `snippet`
     - `path`
     - `score`
   - Keep timeout and max-char budgets.

2. **Hook-level default behavior**
   - `/Users/lisihao/.claude/hooks/solar-knowledge-context.sh` must keep fail-open behavior.
   - It must inject context when qmd fallback hits, not silently return empty.
   - It must remain disabled by `SOLAR_KB_CONTEXT=0`.

3. **Coordinator / harness dispatch awareness**
   - Document whether current Solar harness panes rely on Claude `UserPromptSubmit` hooks or need explicit context injection in dispatch text.
   - If dispatch panes do not reliably trigger the hook for coordinator-generated tasks, add a safe minimal injection path for sprint dispatches:
     - query title + sprint contract text
     - inject bounded sourced context
     - fail open

4. **Tests**
   - Add or extend a regression test, for example:
     - `/Users/lisihao/.solar/harness/tests/test-solar-kb-qmd-fallback.sh`
   - Tests must cover:
     - DB miss + qmd hit
     - qmd unavailable -> fail-open empty hits
     - `SOLAR_KB_CONTEXT=0`
     - max chars respected
     - valid JSON output

5. **Runbook**
   - Add a short operator doc or update existing KB runbook:
     - how default KB retrieval works
     - DB path
     - qmd fallback path
     - how to verify with `大模型热力学`
     - how to disable
     - common failure modes (`database is locked`, qmd missing, no hits)

## Acceptance Criteria

### A1 — Retrieval Script Finds qmd-only Knowledge

Required:
- Querying a note known to exist in qmd returns at least one hit.
- Result includes source/path/title/snippet.

Verify:

```bash
python3 /Users/lisihao/.solar/harness/lib/solar-knowledge-context.py \
  --query '大模型热力学' --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hits"], d; assert any("大模型" in (h.get("title","")+h.get("snippet","")) for h in d["hits"]), d'
```

### A2 — Hook Injects `<solar-knowledge-context>` For qmd Hit

Required:
- Simulated `UserPromptSubmit` payload for `大模型热力学` emits a context block.

Verify:

```bash
printf '{"user_prompt":"帮我基于大模型热力学分析注意力机制"}' \
  | /Users/lisihao/.claude/hooks/solar-knowledge-context.sh \
  | grep -q '<solar-knowledge-context>'
```

### A3 — Fail-Open When qmd Is Missing

Required:
- Missing qmd binary does not break prompt submission.
- Script exits 0 and returns valid JSON or empty output depending on layer.

Verify:

```bash
QMD_BIN=/tmp/no-such-qmd \
python3 /Users/lisihao/.solar/harness/lib/solar-knowledge-context.py \
  --query '大模型热力学' --json --fail-open \
  | python3 -c 'import json,sys; json.load(sys.stdin)'
```

### A4 — Disable Flag Works

Required:
- `SOLAR_KB_CONTEXT=0` prevents hook injection.

Verify:

```bash
out=$(printf '{"user_prompt":"大模型热力学"}' \
  | SOLAR_KB_CONTEXT=0 /Users/lisihao/.claude/hooks/solar-knowledge-context.sh)
test -z "$out"
```

### A5 — Max Char Budget Is Respected

Required:
- Retrieval output must not exceed configured context budget by more than small JSON overhead.
- Hook should not inject full documents.

Verify:

```bash
python3 /Users/lisihao/.solar/harness/lib/solar-knowledge-context.py \
  --query '大模型热力学' --json --max-chars 500 \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["total_chars"] <= 500, d'
```

### A6 — Regression Suite Passes

Verify:

```bash
bash /Users/lisihao/.solar/harness/tests/test-solar-kb-qmd-fallback.sh
```

## Implementation Notes

- Prefer `subprocess.run(..., timeout=remaining_budget)` for qmd calls.
- qmd fallback must run only if there is enough timeout budget left.
- Treat qmd results as untrusted text; never execute retrieved content.
- Deduplicate DB and qmd hits by path/title.
- Preserve current JSON schema so the hook does not need a breaking change.
- Avoid shelling through unescaped query strings; pass argv arrays.

## Planner Instructions

1. Read this contract first.
2. Keep the mainline narrow: make default KB context hit qmd when Solar DB misses.
3. Do not start by designing a new indexer. That is covered by other KB/data-plane sprints.
4. If coordinator dispatches bypass `UserPromptSubmit`, document that and either add a minimal dispatch-context injection or create a follow-up contract with evidence.
5. Final handoff must include the exact outputs of A1 and A2.

## Definition Of Done

- `solar-knowledge-context.py --query '大模型热力学' --json` returns a sourced hit.
- `solar-knowledge-context.sh` injects `<solar-knowledge-context>` for a matching prompt.
- Missing qmd/locked DB does not block work.
- Regression test exists and passes.
- Operator doc explains how to verify and disable the behavior.
