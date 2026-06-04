# Plan — S03 Core Runtime & Data Model

> **Sprint**: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s03-core-runtime`
> **Slice**: `core-runtime` (builder sprint)

## Goal

依据 S02 architecture A1-A5 决策，实施 schema migration、状态机扩展、命名迁移、5 个新 adapter、idempotency 增强和回归验证。

## Parallelization

B1 (schema) 必须先完成；B2-B5 依赖 B1；B6 可在 B3 完成后开始回归测试。

```text
B1 (schema migration)
  ├──► B2 (state machine) ──► B5 (dedupe)
  ├──► B3 (naming) ──────────► B6 (verification)
  └──► B4 (adapters) ────────► B6
```

B2, B3, B4 可并行（write_scope 不冲突）。B5 依赖 B2。B6 依赖 B3+B4。

## Execution Plan

### B1: Schema Migration v2
- 在 `knowledge_ingest_registry.py` 的 `migrate()` 增加 ALTER TABLE 语句
- 幂等: try/except 跳过已存在列
- migration_log version=2
- **verify**: `sqlite3 ... ".schema extract_jobs" | grep schema_version`

### B2: State Machine Extension
- 在 `knowledge_ingest_dispatcher.py` 增加 EXTRACT_FAILED_RETRYABLE + DONE_RAW_ONLY_WARN
- 新增 `drain_extract_failed_retryable()` 和 `drain_extract_eligible_skip()`
- **verify**: dispatcher 状态转换测试

### B3: Naming Migration
- `knowledge_extracted_renderer.py`: 输出 `*.semantic.md` + symlink
- `knowledge_ingest_registry.py`: watermarks extracted → semantic
- **verify**: renderer 输出 + symlink 存在

### B4: New Adapters
- 5 个新 adapter 在 `knowledge_source_adapters.py`
- 5 个新 discover 命令在 `knowledge_ingest_dispatcher.py`
- **verify**: 每个新 discover 命令 exit 0

### B5: Idempotency Enhancement
- 扩展 dedupe key 到 (source_kind, source_path, source_sha256, prompt_template_id, schema_version, model)
- **verify**: same source + different model → 2 jobs

### B6: Regression Verification
- 所有 105859 CLI 命令 exit 0
- 新命令 exit 0
- **verify**: complete pass list

## Verification Commands

```bash
# B1
solar-harness wiki knowledge-ingest migrate --json
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite ".schema extract_jobs" | grep schema_version
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite "SELECT version FROM migration_log ORDER BY version DESC LIMIT 1"

# B2
python3 -c "import knowledge_ingest_dispatcher as d; print('EXTRACT_FAILED_RETRYABLE' in str(d.VALID_TRANSITIONS))"

# B3
# (需要先跑一个 extract sample)
solar-harness wiki knowledge-ingest extract-sample --limit 1 --json
# verify semantic.md exists and extracted.md is symlink

# B4
solar-harness wiki knowledge-ingest discover-youtube --limit 1 --json
solar-harness wiki knowledge-ingest discover-github --limit 1 --json
solar-harness wiki knowledge-ingest discover-pdf --limit 1 --json
solar-harness wiki knowledge-ingest discover-accepted --limit 1 --json
solar-harness wiki knowledge-ingest discover-solar --limit 1 --json

# B6 — regression
solar-harness wiki knowledge-ingest status --json
solar-harness wiki knowledge-ingest discover-vault --limit 5 --json
solar-harness wiki knowledge-ingest discover-raw --limit 5 --json
solar-harness wiki knowledge-ingest qmd-watermarks --json
```
