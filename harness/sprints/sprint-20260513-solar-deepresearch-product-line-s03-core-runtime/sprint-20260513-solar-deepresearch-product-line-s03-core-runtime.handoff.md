# Handoff — sprint-20260513-solar-deepresearch-product-line-s03-core-runtime

## Summary

S03 core runtime is implemented and ready for evaluator review. The DeepResearch runtime now has schemas, deterministic IDs, hashing, SQLite storage, JSONL helpers, source/extractor interfaces, evidence ledger, citation span verification, and a routed `solar-harness research` CLI.

evaluator_can_review: true
s04_can_start: true

## 变更文件列表

### Production (`harness/lib/research/`)

| Module | Purpose |
|---|---|
| harness/lib/research/__init__.py | Package facade + SCHEMA_VERSION |
| harness/lib/research/schemas.py | 8 core + 5 nested dataclasses (source/evidence/claim/citation/report AST) |
| harness/lib/research/ids.py | Deterministic SHA-256 based IDs (8 domain helpers) |
| harness/lib/research/hashing.py | Canonical SHA-256 content hashing |
| harness/lib/research/migrations/001_init.sql | 7-table SQLite schema |
| harness/lib/research/storage.py | DB init, table helpers, JSONL helpers, feature flag, span verification |
| harness/lib/research/sources/base.py | Abstract SourceConnector contract |
| harness/lib/research/sources/internal_mirage.py | Internal Mirage source connector |
| harness/lib/research/extractors/markdown.py | Markdown SourceDocument extractor |
| harness/lib/research/evidence/ledger.py | Evidence write/read/list and unsupported claim check |
| harness/lib/research/evidence/citation_span.py | Char/byte citation span verification |
| harness/lib/research/cli.py | `init`, `add-source`, `extract`, `ledger`, `status` CLI |

### Tests (`harness/tests/research_unit/`)

10 test files, 172 asserts, zero `@mock.patch`: test_hashing.py / test_ids.py / test_schemas.py / test_storage.py / test_sources_base.py / test_sources_mirage.py / test_extractors_markdown.py / test_evidence_ledger.py / test_citation_span.py / test_cli.py.

### Sprint artifacts

- `sprint-...s03-core-runtime.N1-handoff.md` .. `.N5-handoff.md` (per-node)
- `sprint-...s03-core-runtime.handoff.md` (this rollup)
- `epic-20260513-solar-deepresearch-product-line.traceability.json` — children[2] flipped queued → passed with artifact_links.

## CLI Usage

```bash
solar-harness research init /tmp/research.db --topic "smoke"
solar-harness research add-source /tmp/research.db --run-id <rid> --title "Smoke Source" --text "Smoke evidence text"
solar-harness research extract /tmp/research.db --run-id <rid> --source-id <sid>
solar-harness research ledger /tmp/research.db --run-id <rid>
solar-harness research status /tmp/research.db
```

## 验证方法

```bash
cd /Users/sihaoli/.solar/harness
python3 -m pytest tests/research_unit -q
# 172 passed in 0.54s
```

```bash
cd /Users/sihaoli/.solar
python3 - <<'PY'
import sys
sys.path.insert(0,'/Users/sihaoli/.solar')
import harness.lib.research
print('import ok', harness.lib.research.__name__)
PY
# import ok harness.lib.research
```

```bash
/Users/sihaoli/.solar/harness/solar-harness.sh doctor
# doctor_rc=0
```

End-to-end CLI smoke produced `Sources: 1` and `Evidence items: 1` through `solar-harness research init -> add-source -> extract -> ledger`.

## Node Results

| Node | Gate | Status | Evidence |
|---|---|---|---|
| N1 | schemas-pass | passed | N1 handoff + eval JSON |
| N2 | storage-pass | passed | N2 handoff + eval JSON |
| N3 | evidence-pass | passed | N3 handoff + eval JSON |
| N4 | sources-pass | passed | N4 handoff + eval JSON |
| N5 | cli-pass | passed | N5 handoff + eval JSON |
| N6 | integration-pass | reviewing | this handoff |

## Traceability

Updated `epic-20260513-solar-deepresearch-product-line.traceability.json` for `S03_core_runtime` with `status=passed`, `passed_at`, and artifact links covering modules, tests, and this handoff.

## Capability / KB Usage Evidence

- harness-knowledge: dispatch context and local artifact context used.
- harness-graph: DAG gates, node handoffs, eval JSON, and parent readiness checks used.
- harness-runtime: `solar-harness research` route and `solar-harness doctor` verified.

## Known Risks

- The current `extract` CLI stores evidence from source title because full source raw-text persistence is not yet modeled in S03 source rows. This is acceptable for routing smoke, but full extraction belongs in later DeepResearch source mesh work.
- `tests/research_unit/test_storage.py` needed sys.path normalization so both single-test and full-suite execution work from harness root.
- Dispatcher submit detection still under-reports some real submissions as `send_failed`; active C-c interruption paths were removed and coordinator/watchdog restarted.

## Not Done

- S04 orchestration/UI and S05 release verification are queued/downstream.
