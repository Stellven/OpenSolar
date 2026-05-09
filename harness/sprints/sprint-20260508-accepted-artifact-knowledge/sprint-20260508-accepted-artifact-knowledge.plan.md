# Plan — Accepted Sprint Artifacts To Knowledge Base

Generated: 2026-05-09T01:09:51Z
Planner note: contract A1-A8 is authoritative. Build in two implementation slices plus observability.

## Slice S1 — Exporter Core

Write scope:

- `lib/accepted-artifact-export.py`
- `tests/test-accepted-artifact-knowledge-sync.sh`
- temp fixtures inside test script only

Tasks:

1. Implement `export-accepted --sid <sid> --vault <path> --dry-run --force --json`.
2. Collect existing sprint artifacts: PRD, contract, design, plan, handoff variants, eval, eval.json, events, test evidence.
3. Generate accepted markdown with required frontmatter and body sections.
4. Redact secrets by default: `sk-*`, `Bearer`, `api_key=`, `token=`, obvious env secrets.
5. Maintain manifest hashes under `Knowledge/_raw/solar-harness/.manifest/accepted-artifacts.json`.
6. Emit machine-readable JSON result and status/event updates.

Validation:

```bash
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case pass-only
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case artifact-schema
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case redaction
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case idempotent
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case status-events
```

## Slice S2 — Hook, CLI, Backfill, Ingest Dispatch

Write scope:

- `solar-harness.sh`
- `coordinator.sh`
- `integrations/obsidian-wiki-export.sh`
- `integrations/wiki-capture-server.py`
- `docs/accepted-artifact-knowledge.md`

Tasks:

1. Add CLI commands:
   - `solar-harness wiki export-accepted <sid> [--dry-run|--force]`
   - `solar-harness wiki backfill-accepted [--limit N] [--since YYYY-MM-DD] [--dry-run]`
2. In `handle_passed()`, call exporter asynchronously/non-blocking and emit failures as events.
3. Generate safe wiki ingest dispatch under `Knowledge/_raw/solar-harness/.dispatch/`.
4. Add status-server payload: exported count, pending ingest count, failed count, last sid/path/time/error.
5. Write runbook covering verify, backfill, disable, repair failed export, manifest inspection.

Validation:

```bash
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh --case ingest-dispatch
solar-harness wiki backfill-accepted --limit 3 --dry-run
bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh
```

## Definition Of Done

- A1-A8 pass.
- No export for failed/reviewing/drafting fixtures.
- Automatic PASS hook cannot block finalized.
- Knowledge package includes source index and redaction evidence.
- Status fields and events make export/ingest observable.
