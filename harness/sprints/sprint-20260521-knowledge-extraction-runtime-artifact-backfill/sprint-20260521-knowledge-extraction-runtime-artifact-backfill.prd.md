# PRD: Knowledge extraction coverage for runtime design artifacts

## Summary
Mac mini knowledge extraction currently misses many Solar Harness runtime artifacts, especially recent PRD, contract, task_graph, node handoff, and monitor report files created by multi-task/heartbeat work. Build a durable backfill and ongoing export path so these design and requirements documents become searchable in the Knowledge/QMD layer.

## Evidence
Live audit on Mac mini showed:

- Source artifact candidates:
  - `/Users/lisihao/.solar/harness/sprints`: PRD, contract, task_graph, handoff files.
  - `/Users/lisihao/.solar/harness/monitor-reports`: final reports and node evidence.
- Counts:
  - source_count: 448
  - knowledge_file_count: 14058
  - missing_by_filename_count: 211
  - recent_80_missing_filename_count: 77
- Recent missing examples:
  - `sprint-20260521-thunderomlx-readiness-probe-auth.prd.md`
  - `sprint-20260521-thunderomlx-readiness-probe-auth.contract.md`
  - `sprint-20260521-thunderomlx-readiness-probe-auth.task_graph.json`
  - `thunderomlx-readiness-probe-auth.md`
  - `sprint-20260521-thunderomlx-anthropic-cache-usage-observability.*`
  - `sprint-20260521-thunderomlx-anthropic-cache-hit-no-garbled.*`

## Problem
The existing accepted-artifact pipeline focuses on classic `status=passed/finalized` sprint status records. It does not reliably export:

- multi-task DAG `*.task_graph.json`
- node handoff files such as `*.N1-handoff.md`
- monitor reports under `monitor-reports/`
- newly created PRD/contract files that do not have a classic accepted status file.

Therefore recent operational design knowledge is present on disk but absent from the searchable knowledge layer.

## Goals
- Add a coverage auditor that compares runtime artifact sources against exported knowledge files.
- Add a safe exporter/backfill path for runtime artifacts:
  - source files remain immutable;
  - output goes to `/Users/lisihao/Knowledge/_raw/solar-harness/runtime-artifacts/`;
  - manifest goes to `/Users/lisihao/Knowledge/_raw/solar-harness/.manifest/runtime-artifacts.json`;
  - secrets are redacted.
- Backfill all missing runtime artifacts or at least all missing 2026-05-20/2026-05-21 ThunderOMLX and multi-task artifacts first, then report remaining backlog.
- Trigger QMD update/embed pipeline after export when available.
- Produce final report with source_count, exported_count, skipped_count, remaining_missing_count, and sample remaining gaps.

## Non-Goals
- Do not delete or rewrite source sprint artifacts.
- Do not expose API keys/tokens.
- Do not require all artifacts to be semantically summarized by an LLM; raw searchable export is acceptable for P0.
- Do not block on cloud model quota. Shell/Python fallback is allowed.

## Acceptance
- Final report exists:
  - `/Users/lisihao/.solar/harness/monitor-reports/knowledge-extraction-runtime-artifact-backfill.md`
- Coverage manifest exists:
  - `/Users/lisihao/Knowledge/_raw/solar-harness/.manifest/runtime-artifacts.json`
- Recent ThunderOMLX sprint artifacts are present under:
  - `/Users/lisihao/Knowledge/_raw/solar-harness/runtime-artifacts/`
- `solar-harness context inject --query "ThunderOMLX readiness probe auth cache_read_input_tokens" --format markdown` returns at least one of the newly exported runtime artifact entries.
- Graph parent-check is ready=true.
