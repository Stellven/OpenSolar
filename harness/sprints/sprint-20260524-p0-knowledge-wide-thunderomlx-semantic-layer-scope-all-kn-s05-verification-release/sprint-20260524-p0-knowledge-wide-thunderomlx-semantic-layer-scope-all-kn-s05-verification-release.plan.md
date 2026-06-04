# Plan — S05 Verification, Regression & Release Evidence

> **Sprint**: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s05-verification-release`
> **Slice**: `verification-release` (test & evidence only)

## Goal

对 S01-S04 全部交付物做端到端验证，产出 test_report.md + handoff.md，确保 Epic 可安全关闭。

## Parallelization

```text
V1 (schema)     ─┐
V2 (state)      ─┤
V3 (naming)     ─┼──► V9 (parent-check) ──► V10 (outcome matrix)
V4 (adapters)   ─┤
V5 (grounding)  ─┤
V6 (dashboard)  ─┤
V7 (negative)   ─┤
V8 (regression) ─┘
```

V1-V8 可并行。V9 依赖全部。V10 依赖 V9。

## Verification Commands (Complete List)

```bash
# V1: Schema
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite ".tables"
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite ".schema extract_jobs" | grep schema_version
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite ".schema extract_outputs" | grep latency_ms
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite "SELECT version FROM migration_log ORDER BY version DESC LIMIT 1"

# V2: State machine
python3 -c "import knowledge_ingest_dispatcher as d; t=str(d.VALID_TRANSITIONS); assert 'EXTRACT_FAILED_RETRYABLE' in t; assert 'DONE_RAW_ONLY_WARN' in t; print('OK')"
solar-harness wiki knowledge-ingest status --json

# V3: Naming
# (need extract sample first)
solar-harness wiki knowledge-ingest extract-sample --limit 1 --json
# then: ls *.semantic.md and check symlink
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite "SELECT layer FROM watermarks"

# V4: Adapters
for src in youtube github pdf accepted solar vault raw; do
  solar-harness wiki knowledge-ingest discover-$src --limit 1 --json
done
solar-harness wiki knowledge-ingest coverage-report --json

# V5: GroundingHook
python3 -c "from knowledge_grounding_hook import GroundingHook; print('OK')"

# V6: Dashboard
solar-harness wiki knowledge-ingest dashboard --json
solar-harness wiki knowledge-ingest dashboard --html

# V7: Negative controls
grep -r "embeddinggemma" ~/.solar/harness/lib/knowledge_extract_json.py; echo "exit=$?"
python3 -c "
import knowledge_ingest_dispatcher as d
t=str(d.VALID_TRANSITIONS)
assert 'QUARANTINED' not in t or 'EXTRACTED_QMD_INDEX_PENDING' not in t
print('OK')
"

# V8: 105859 regression (build-from-zero)
ls ~/.solar/harness/lib/knowledge_*.py | wc -l  # expect 9
python3 -c "
import knowledge_ingest_registry
import knowledge_ingest_dispatcher
import knowledge_source_adapters
import knowledge_spans
import knowledge_extract_json
import knowledge_extracted_renderer
import knowledge_extracted_validator
import knowledge_qmd_indexer
import knowledge_ingest_health
print('all 9 imports OK')
"
solar-harness wiki knowledge-ingest status --json
solar-harness wiki knowledge-ingest migrate --json
solar-harness wiki knowledge-ingest qmd-watermarks --json
solar-harness wiki knowledge-ingest circuit-breaker status --json

# V9: Epic parent-check
cat ~/.solar/harness/sprints/epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn.traceability.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
for c in d['children']:
    print(f\"{c['node_id']}: {c['status']}\")
"
```
