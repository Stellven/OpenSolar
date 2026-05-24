# Plan — S02 Architecture & Interface Contracts

> **Sprint**: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s02-architecture`
> **Slice**: `architecture`

## Goal

基于 S01 outcomes_matrix 的 14 outcomes，产出 design.md（5 个架构决策 A1-A5）、plan.md、task_graph.json，然后激活 S03 builder。

## Parallelization

本 sprint 只有 planner 工作（planning-only），不派 builder。

| Node | Content | Depends |
|---|---|---|
| P1 | Read upstream: S01 design/handoff/outcomes_matrix/traceability + 105859 design + intake | - |
| P2 | Write design.md (A1-A5 decisions + system layering + interface contracts) | P1 |
| P3 | Write plan.md (this file) | P2 |
| P4 | Write task_graph.json (S03 builder DAG) | P2 |
| P5 | Validate task_graph.json via graph-scheduler | P4 |
| P6 | Render planning.html | P3, P4 |
| P7 | Update status → active, register artifacts | P5, P6 |

All nodes sequential (P1→P2→P3/P4 parallel→P5→P6→P7).

## S03 Builder DAG (what task_graph.json encodes)

S03 core-runtime builder 需实现以下工作：

### S3-A: Schema Migration (A2)
- `ALTER TABLE` 6 columns on extract_jobs + extract_outputs
- Update migration_log version=2
- Verify idempotency (run twice → same result)
- **write_scope**: `harness/lib/knowledge_ingest_registry.py`, `Knowledge/_registry/knowledge_ingest.sqlite`

### S3-B: State Machine Extension (A3)
- Add `EXTRACT_FAILED_RETRYABLE` and `DONE_RAW_ONLY_WARN` to dispatcher transitions
- Add retry loop (max 3, exponential backoff) for EXTRACT_FAILED_RETRYABLE
- Add skip path: EXTRACT_ELIGIBLE → DONE_RAW_ONLY_WARN when extract_policy=skip
- **write_scope**: `harness/lib/knowledge_ingest_dispatcher.py`

### S3-C: Naming Migration (A1)
- Renderer output → `*.semantic.md`
- Create symlink `*.extracted.md → *.semantic.md`
- Update `watermarks` table row: extracted → semantic
- Update `qmd_index_events.layer` writes to use `semantic`
- **write_scope**: `harness/lib/knowledge_extracted_renderer.py`, `harness/lib/knowledge_ingest_registry.py`

### S3-D: New Adapters (A4)
- youtube_adapter (迁移路径)
- github_adapter
- pdf_adapter (call MinerU)
- accepted_adapter
- solar_adapter
- Register all 5 in adapter registry
- **write_scope**: `harness/lib/knowledge_source_adapters.py`

### S3-E: Idempotency Enhancement (O14)
- Extend dedupe key to include (prompt_template_id, schema_version, model)
- Write test: same source + different model → creates new job
- **write_scope**: `harness/lib/knowledge_ingest_dispatcher.py`, `harness/tests/test-idempotency.sh`

### S3-F: Verification
- Run all 105859 CLI commands → verify no regression
- Run new adapter discover commands → verify registration
- Run schema migration → verify column exists
- **write_scope**: `harness/tests/test-s03-regression.sh`

## Acceptance Per S03 Node

| S03 Node | Acceptance | Gate |
|---|---|---|
| S3-A | `sqlite3 ... ".schema extract_jobs"` shows 5 new columns; migration_log version=2 | G1 |
| S3-B | dispatcher transitions include EXTRACT_FAILED_RETRYABLE + DONE_RAW_ONLY_WARN | G2 |
| S3-C | `ls *.semantic.md` exists AND `ls *.extracted.md` is symlink | G3 |
| S3-D | `solar-harness wiki knowledge-ingest discover-{youtube,github,pdf,accepted,solar} --limit 1 --json` returns non-empty | G4 |
| S3-E | dedupe test: same source + different model → 2 jobs | G5 |
| S3-F | All 105859 CLI commands exit 0; no regression | G6 |

## Verification Commands

```bash
# Schema migration
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite ".schema extract_jobs" | grep schema_version
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite "SELECT version FROM migration_log ORDER BY version DESC LIMIT 1"

# State machine
python3 -c "import knowledge_ingest_dispatcher; print(knowledge_ingest_dispatcher.VALID_TRANSITIONS)"

# Naming
find ~/Knowledge -name "*.semantic.md" -type f | head -5
find ~/Knowledge -name "*.extracted.md" -type l | head -5

# Adapters
solar-harness wiki knowledge-ingest discover-youtube --limit 1 --json
solar-harness wiki knowledge-ingest discover-github --limit 1 --json
solar-harness wiki knowledge-ingest discover-pdf --limit 1 --json
solar-harness wiki knowledge-ingest discover-accepted --limit 1 --json
solar-harness wiki knowledge-ingest discover-solar --limit 1 --json

# Idempotency
python3 -c "
import knowledge_ingest_registry as r
# test that different model creates different job
"
```
