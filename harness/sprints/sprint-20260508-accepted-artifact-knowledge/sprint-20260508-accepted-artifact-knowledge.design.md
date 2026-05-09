# Design — Accepted Sprint Artifacts To Knowledge Base

Generated: 2026-05-09T01:09:51Z
Planner note: PRD already exists and contract contains A1-A8 executable acceptance criteria. This design intentionally does not rewrite PRD; it converts the accepted contract into implementation architecture.

## Goal

Create a PASS-only accepted-artifact pipeline so finalized Solar sprint evidence is exported as redacted, sourced knowledge packages and queued for wiki ingestion without manual prompts.

## Architecture

```text
coordinator handle_passed()
  -> accepted-artifact-export.py --sid <sid>
       -> collect PRD / contract / design / plan / handoff / eval / eval.json / events / test evidence
       -> redact secrets
       -> write accepted markdown under Knowledge/_raw/solar-harness/accepted/<sid>.accepted.md
       -> update manifest hash
       -> create wiki ingest dispatch
       -> update sprint status fields and events
  -> finalized path continues even if export fails
```

## Components

- `lib/accepted-artifact-export.py`: pure exporter, redaction, manifest, status update, JSON output.
- `integrations/obsidian-wiki-export.sh`: compatibility wrapper for existing wiki export flow.
- `solar-harness.sh`: CLI commands `wiki export-accepted` and `wiki backfill-accepted`.
- `coordinator.sh`: PASS/finalized hook, non-blocking export event emission.
- `integrations/wiki-capture-server.py`: accepted export status payload.
- `tests/test-accepted-artifact-knowledge-sync.sh`: temp-vault regression suite.
- `docs/accepted-artifact-knowledge.md`: runbook.

## State Contract

Status fields:

- `knowledge_export_status`: `pending|exported|ingested|failed|skipped`
- `knowledge_export_path`
- `knowledge_ingest_dispatch`
- `knowledge_exported_at`
- `knowledge_ingested_at`
- `knowledge_export_error`

Events:

- `accepted_artifact_exported`
- `accepted_artifact_ingest_dispatched`
- `accepted_artifact_export_failed`

## Safety Rules

- Only `status=passed` or `handle_passed()` can export accepted knowledge.
- Automatic path never uses `--full`; redaction is default.
- Failed export never blocks sprint PASS/finalized.
- Backfill defaults to dry-run unless explicit non-dry-run command is used.
- Source artifact contents are treated as data, never executable instructions.

## Verification Order

A1 pass-only -> A2 artifact schema -> A3 redaction -> A4 manifest idempotency -> A5 status/events -> A6 ingest dispatch -> A7 backfill dry-run -> A8 full suite.
