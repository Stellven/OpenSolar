# Implementation Plan — P0 Wiki Upload Ingest Closure

Sprint: `sprint-20260508-wiki-upload-ingest-closure`
Created: 2026-05-08T13:13:47Z
Phase: planning_complete
Topology: mixture

## 0. Mainline

Close the upload-to-searchable-knowledge loop for batch `20260508T122047Z`: 23 originals preserved, 23 qmd searchable, 23 Solar DB/FTS searchable, no false-completed dispatches.

## 1. Parallel Slices

### Builder 1 — Dispatch Identity + State Machine

Owns:
- `/Users/sihaoli/.solar/harness/integrations/obsidian-wiki-bridge.sh`
- `/Users/sihaoli/.solar/harness/solar-harness.sh` only where wiki dispatch IDs/status are generated or routed
- `/Users/sihaoli/.solar/harness/tests/test-wiki-upload-ingest-closure.sh` cases `dispatch-unique` and `terminal-state`

Tasks:
- Replace second-resolution wiki ingest IDs with collision-proof IDs.
- Ensure nested/chained dispatch creation uses the same unique ID mechanism.
- Add terminal state semantics: `pending`, `running`, `completed`, `failed`, `skipped`, `chained`.
- Mark chained-only results as `chained`, never `completed`.

### Builder 2 — `.pages` Extraction

Owns:
- `/Users/sihaoli/.solar/harness/lib/wiki-upload-extract.py`
- `/Users/sihaoli/.solar/harness/tests/test-wiki-upload-ingest-closure.sh` cases for `.pages`

Tasks:
- Extract text from `.pages` files using safe local methods.
- Preserve original uploads.
- Write derived artifacts under a generated/raw-safe location.
- Emit explicit `extract_failed` records when extraction is impossible.

### Builder 3 — Audit/Backfill + Solar DB/FTS Indexing

Owns:
- `/Users/sihaoli/.solar/harness/lib/wiki-upload-audit.py`
- `/Users/sihaoli/.solar/harness/lib/wiki-upload-backfill.py`
- `/Users/sihaoli/.solar/harness/solar-harness.sh` only for `wiki audit-uploads` and `wiki backfill-uploads` routing
- `/Users/sihaoli/.solar/harness/tests/test-wiki-upload-ingest-closure.sh` audit/backfill/idempotency cases

Tasks:
- Implement `solar-harness wiki audit-uploads --batch <batch> --json`.
- Implement `solar-harness wiki backfill-uploads --batch <batch> --repair --json`.
- Upsert uploaded documents into Solar searchable DB/FTS surfaces with provenance to original files.
- Ensure second backfill creates no duplicates.

### Builder 4 — Real Batch Closure + Runbook

Owns:
- `/Users/sihaoli/.solar/harness/docs/wiki-upload-ingest-closure.md`
- `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-wiki-upload-ingest-closure.handoff-builder4.md`

Tasks:
- Run the real batch audit after Builder 1-3 land.
- Execute real batch backfill for `20260508T122047Z`.
- Attach JSON evidence showing qmd 23/23 and Solar DB/FTS 23/23.
- Write operator runbook and rollback/quarantine instructions.

## 2. File-Level Boundaries

```text
┌───────────┬──────────────────────────────────────────────┬─────────────────────────────┐
│ Builder   │ Owns                                         │ Must Not Touch              │
├───────────┼──────────────────────────────────────────────┼─────────────────────────────┤
│ B1        │ dispatch naming/state machine                │ extraction/backfill docs     │
│ B2        │ pages extraction helper                      │ dispatch router/DB backfill  │
│ B3        │ audit/backfill/DB indexing                   │ pages extractor internals    │
│ B4        │ real-batch evidence/runbook                  │ code except docs/handoff     │
└───────────┴──────────────────────────────────────────────┴─────────────────────────────┘
```

If two builders must edit `/Users/sihaoli/.solar/harness/solar-harness.sh`, Builder 1 owns dispatch-generation routing and Builder 3 owns only `wiki audit-uploads` / `wiki backfill-uploads` CLI routing. Keep patches narrow.

## 3. Verification Commands

```bash
find /Users/sihaoli/Knowledge/_raw/file-uploads -maxdepth 1 \
  -type f -name '20260508T122047Z-*' | wc -l | tr -d ' '

bash /Users/sihaoli/.solar/harness/tests/test-wiki-upload-ingest-closure.sh --case dispatch-unique
bash /Users/sihaoli/.solar/harness/tests/test-wiki-upload-ingest-closure.sh --case terminal-state

solar-harness wiki audit-uploads --batch 20260508T122047Z --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert not d["pages"]["silent_missing"], d'

solar-harness wiki audit-uploads --batch 20260508T122047Z --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["qmd"]["found"] == 23, d["qmd"]'

solar-harness wiki audit-uploads --batch 20260508T122047Z --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["solar_db"]["found"] == 23, d["solar_db"]'

bash /Users/sihaoli/.solar/harness/tests/test-wiki-upload-ingest-closure.sh
```

## 4. No-Live-Pane-Mutation Rule

Builders must not directly mutate tmux panes or restart `solar-harness`. Implementation tests use temp vault/temp DB fixtures. Only Builder 4 may run the real batch repair after code and tests are in place.

## 5. Stop / Rollback Rules

- Stop if a command would overwrite user-authored vault notes.
- Stop if extraction attempts require executing document content.
- Stop if Solar DB write target is ambiguous and cannot preserve provenance.
- Before real-batch DB writes, create or use an idempotent upsert path; do not bulk delete.

## 6. Handoff Requirements

Each builder writes:

- `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-wiki-upload-ingest-closure.handoff-builder<N>.md`

Required sections:

- `## Summary`
- `## Changed Files`
- `## Done 达成`
- `## Verification Evidence`
- `## Known Risks`
- `## Not Done`
