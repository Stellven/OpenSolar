# Eval Evidence — sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s03-core-runtime

## Machine-Verifiable Checks

| check | command | result |
|---|---|---|
| syntax | `python3 -m py_compile ...` | PASS |
| unit | `python3 -m pytest tests/runtime/test_mirage_context_access_plane.py -q` | PASS, `4 passed` |
| search | `./solar-harness.sh mirage search 'code unified_search' --json --sources cocoindex --max-hits 3 --max-chars 1200` | PASS, `source_type=cocoindex`, degraded visible |
| sidecar | `python3 lib/runtime_context_inject.py ... --query "code unified_search" --json` | PASS, `sidecar_version=2`, `context_sources.cocoindex=3` |
| verifier | `python3 lib/verifier/context_usage.py runtime/s03-core-runtime-smoke/dispatch.md.runtime-context.json --task-kind code --json` | PASS, `ok=true`, `missing_sources=[]`, `replayable=true` |

## Adapter / Fusion / Inject / Verifier
- Adapter: CocoIndex and understanding adapters output normalized hits with `source_type`, `layer`, `source_hash`, `lineage`, degraded flags.
- Fusion: `solar-unified-context.retrieve()` supports source/layer/task_kind inputs and returns source/degraded/lineage/source_hash metadata.
- Inject: runtime sidecar v2 records `context_sources`, `source_counts`, `degraded_sources`, `lineage_refs`, `source_hash_refs`, `required_sources`, `used_sources`.
- Verifier: `verifier.context_usage` checks required source policy and evidence replayability.

## Non-Goals
- No shell-native FUSE implementation.
- No claim that degraded fallback equals a healthy CocoIndex index.
- No replacement of existing `mirage_path/qmd/solar_db` chain.
