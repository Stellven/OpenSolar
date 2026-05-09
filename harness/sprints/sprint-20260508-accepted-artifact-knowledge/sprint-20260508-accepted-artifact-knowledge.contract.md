---
sprint_id: sprint-20260508-accepted-artifact-knowledge
title: Accepted Sprint Artifacts To Knowledge Base
priority: P0
lane: reliability
owner: planner
created_at: 2026-05-08T07:10:00Z
status: lab_dispatched
handoff_to: lab-builder-4
---

# Sprint Contract — Accepted Sprint Artifacts To Knowledge Base

> Priority raised to P0 at 2026-05-08T15:59:36Z after explicit user requirement: every accepted Solar job must automatically become a knowledge package for wiki extraction.

## Intent

Close the Solar knowledge loop: after a sprint is accepted by evaluator (`PASS`) and finalized, Solar must automatically preserve the validated PRD, architecture/design, plan, solution notes, test results, handoff, eval, and event evidence as a redacted, sourced knowledge package for the Obsidian/Solar knowledge base.

The rule is strict: **accepted knowledge only**. Drafting, active, reviewing, failed, and rejected plans must not enter the formal knowledge base except as clearly labeled raw/debug artifacts.

## Current Evidence

- `handle_passed()` in `/Users/sihaoli/.solar/harness/coordinator.sh` is the correct PASS/finalized hook point.
- Existing `solar-harness wiki export-sprint <sid>` can export contract/plan/handoff/eval/status/events into `_raw/solar-harness/<sid>.md`.
- Current export does not fully cover PRD/design/handoff-builder*/eval.json/test evidence, and is not guaranteed to run automatically on every PASS.
- Existing Obsidian bridge can generate wiki ingest dispatches, but user still sees manual prompts like “要不要跑 wiki ingest”.

## Deliverables

1. `~/.solar/harness/lib/accepted-artifact-export.py`
   - Builds one accepted knowledge package per passed sprint.
   - Supports `--sid`, `--vault`, `--dry-run`, `--redact`, `--force`, `--json`.
   - Writes manifest and idempotency hashes.

2. `~/.solar/harness/integrations/obsidian-wiki-export.sh`
   - Extend or wrap export flow to include PRD/design/handoff-builder*/eval.json/test evidence.
   - Preserve existing `export-sprint` behavior.

3. `~/.solar/harness/solar-harness.sh`
   - Add:
     - `solar-harness wiki export-accepted <sid> [--dry-run|--force]`
     - `solar-harness wiki backfill-accepted [--limit N] [--since YYYY-MM-DD] [--dry-run]`

4. `~/.solar/harness/coordinator.sh`
   - In `handle_passed()`, after evaluator PASS and before/around finalized marker, call accepted export asynchronously.
   - Failure must not block `passed`, but must emit event and status fields.

5. `~/.solar/harness/integrations/wiki-capture-server.py`
   - Add status payload for accepted artifact export/ingest:
     - exported count
     - pending ingest count
     - failed count
     - last exported sid/path/time/error

6. `~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh`
   - End-to-end regression suite with temp vault/sprints.

7. `~/.solar/harness/docs/accepted-artifact-knowledge.md`
   - Runbook: verify, backfill, disable, repair failed export, inspect manifest.

## Accepted Artifact Schema

The generated markdown must use this frontmatter:

```yaml
---
source: solar-harness
artifact_type: accepted_sprint_knowledge
sprint_id: <sid>
title: <title>
status: passed
accepted_at: <iso8601>
exported_at: <iso8601>
redacted: true
visibility: internal
provenance: accepted-by-evaluator
source_files:
  prd: true|false
  contract: true|false
  design: true|false
  plan: true|false
  handoff: true|false
  eval: true|false
  events: true|false
---
```

Required body sections:

- `# Accepted Sprint Knowledge: <sid>`
- `## Executive Summary`
- `## User Need / PRD`
- `## Architecture / Design`
- `## Plan / Solution`
- `## Implementation Handoff`
- `## Test & Verification Evidence`
- `## Evaluation Verdict`
- `## Key Decisions`
- `## Reusable Patterns`
- `## Known Risks / Follow-ups`
- `## Source Artifact Index`

## Acceptance Criteria

### A1 — PASS-Only Trigger

Required:
- Export runs only for `status=passed` or within `handle_passed()`.
- No export for `drafting`, `active`, `reviewing`, `failed`, `needs_human_review`.

Verify:

```bash
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case pass-only
```

<!-- verify: cmd="bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case pass-only" -->

### A2 — Complete Accepted Knowledge Package

Required:
- Package includes PRD, contract, design, plan, handoff/handoff-builder*, eval/eval.json, events, verification/test evidence, and source index when those files exist.
- Missing files are listed as `false`/`N/A`, not silently ignored.

Verify:

```bash
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case artifact-schema
```

<!-- verify: cmd="bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case artifact-schema" -->

### A3 — Redaction By Default

Required:
- Default export redacts `sk-*`, `Bearer ...`, `api_key=...`, `token=...`, obvious env secrets.
- `--full` must not be used by automatic PASS hook.

Verify:

```bash
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case redaction
```

<!-- verify: cmd="bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case redaction" -->

### A4 — Idempotent Manifest

Required:
- Manifest stored under vault metadata, for example:
  `/Users/sihaoli/Knowledge/_raw/solar-harness/.manifest/accepted-artifacts.json`
- Re-running same sid with unchanged source hash must skip duplicate writes and duplicate dispatches.
- `--force` can regenerate intentionally.

Verify:

```bash
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case idempotent
```

<!-- verify: cmd="bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case idempotent" -->

### A5 — Status And Events Updated

Required status fields:
- `knowledge_export_status`
- `knowledge_export_path`
- `knowledge_ingest_dispatch`
- `knowledge_exported_at`
- `knowledge_ingested_at`
- `knowledge_export_error`

Required events:
- `accepted_artifact_exported`
- `accepted_artifact_ingest_dispatched`
- `accepted_artifact_export_failed`

Verify:

```bash
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case status-events
```

<!-- verify: cmd="bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case status-events" -->

### A6 — Wiki Ingest Dispatch Generated

Required:
- Successful accepted export creates an ingest dispatch file under:
  `/Users/sihaoli/Knowledge/_raw/solar-harness/.dispatch/`
- Dispatch points at the accepted artifact file.
- Dispatch must instruct agent not to execute instructions from source artifacts.

Verify:

```bash
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case ingest-dispatch
```

<!-- verify: cmd="bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case ingest-dispatch" -->

### A7 — Backfill Passed Sprints

Required:
- `solar-harness wiki backfill-accepted --limit 3 --dry-run` lists passed/finalized sprints that lack accepted artifact export.
- Dry run writes nothing.
- Non-dry run respects limit and idempotency.

Verify:

```bash
solar-harness wiki backfill-accepted --limit 3 --dry-run
```

<!-- verify: cmd="solar-harness wiki backfill-accepted --limit 3 --dry-run" -->

### A8 — Full Regression Suite

Verify:

```bash
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh
```

<!-- verify: cmd="bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh" -->

## Stop Rules

- Stop if export runs before evaluator PASS.
- Stop if redaction test leaks fixture secrets.
- Stop if export failure blocks `handle_passed()` finalization.
- Stop if implementation writes directly to final Obsidian concept pages instead of `_raw`/ingest pipeline.
- Stop if test touches real `/Users/sihaoli/Knowledge` without explicit non-test command.
- Stop if duplicate dispatches are generated for unchanged sid.

## Planner Instructions

1. Write design to:
   `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-accepted-artifact-knowledge.design.md`
2. Write implementation plan to:
   `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-accepted-artifact-knowledge.plan.md`
3. Split into two slices:
   - Slice 1: exporter + schema + redaction + manifest.
   - Slice 2: PASS hook + CLI backfill + status payload + tests/docs.
4. Do not dispatch until current P0 KB sprint is no longer `active/building_parallel`.

## Definition Of Done

- A1-A8 pass.
- At least one historical passed sprint is exported in dry-run evidence.
- One real passed sprint can be exported to `_raw/solar-harness/accepted/` with redaction.
- Wiki ingest dispatch is generated automatically without asking the user “要不要跑 ingest”.
