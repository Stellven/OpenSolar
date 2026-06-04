# Design — S05 Verification, Regression & Release Evidence

> **Sprint**: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s05-verification-release`
> **Epic**: `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn`
> **Slice**: `verification-release` (builder sprint — test & evidence only)
> **Knowledge Context: solar-harness context inject used**
> **Harness Modules Used: harness-knowledge, harness-graph**

## 0. Slice Posture

本切片是 **verification sprint**：对 S01-S04 全部交付物做端到端测试、负控、回归报告、Epic parent-check 验收，产出最终 handoff/eval/report。**不写功能代码**（只写测试脚本和报告）。

## 1. Upstream Dependencies

| 来源 | 消费内容 |
|---|---|
| S01 outcomes_matrix.md | 14 outcomes 的验收条件 (O1-O14) |
| S01 handoff.md | U7 (105859 未端到端实测) — 本 sprint 必须验证 |
| S02 design.md | A1-A5 架构决策 → 验证它们是否在 S03/S04 中实现 |
| S03 core-runtime | schema v2 + 新 adapters + 新状态 + naming |
| S04 orchestration-ui | GroundingHook + dashboard + coverage report |
| 105859 9 lib files | **build-from-zero 验证，不信任 status=passed** (S01 U7) |

## 2. Test Categories

### V1: Schema Verification (O2, O9, A2)

**验证什么**: SQLite registry schema v2 migration 正确性

**测试**:
1. `sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite ".tables"` → 10 tables
2. `sqlite3 ... ".schema extract_jobs"` → 包含 schema_version, endpoint, started_at, finished_at
3. `sqlite3 ... ".schema extract_outputs"` → 包含 latency_ms, token_input_count, token_output_count, cost_estimate, model_fingerprint
4. `sqlite3 ... "SELECT version FROM migration_log ORDER BY version DESC LIMIT 1"` → version ≥ 2
5. Migration 幂等: 跑两次 `migrate` → exit 0, version 不变

### V2: State Machine Verification (O8, O13, A3)

**验证什么**: 新状态 EXTRACT_FAILED_RETRYABLE + DONE_RAW_ONLY_WARN 可达

**测试**:
1. `python3 -c "import knowledge_ingest_dispatcher as d; print(d.VALID_TRANSITIONS)"` → 包含新转移
2. 提交测试事件 → transition 到 EXTRACT_FAILED_RETRYABLE → 验证 registry 状态
3. 提交测试事件 → extract_policy=skip → transition 到 DONE_RAW_ONLY_WARN
4. 验证 retry max 3 后进入 DONE_RAW_ONLY_WARN
5. 验证旧状态行不受影响

### V3: Naming Verification (O5, A1)

**验证什么**: `*.semantic.md` + symlink `*.extracted.md`

**测试**:
1. 跑一个 extract sample → `*.semantic.md` 存在
2. `*.extracted.md` 是 symlink → `*.semantic.md`
3. `sqlite3 ... "SELECT layer FROM watermarks"` → 包含 `semantic` 而非 `extracted`
4. `sqlite3 ... "SELECT DISTINCT layer FROM qmd_index_events"` → 新写入用 `semantic`

### V4: Adapter Coverage Verification (O1, O11, A4)

**验证什么**: 8 类 source_kind 全部注册，每类 ≥1 样本

**测试**:
1. `solar-harness wiki knowledge-ingest discover-youtube --limit 1 --json` → exit 0
2. `solar-harness wiki knowledge-ingest discover-github --limit 1 --json` → exit 0
3. `solar-harness wiki knowledge-ingest discover-pdf --limit 1 --json` → exit 0
4. `solar-harness wiki knowledge-ingest discover-accepted --limit 1 --json` → exit 0
5. `solar-harness wiki knowledge-ingest discover-solar --limit 1 --json` → exit 0
6. `solar-harness wiki knowledge-ingest discover-vault --limit 1 --json` → exit 0
7. `solar-harness wiki knowledge-ingest discover-raw --limit 1 --json` → exit 0
8. `solar-harness wiki knowledge-ingest coverage-report --json` → 8 类全部列出

### V5: GroundingHook Verification (O10, A5)

**验证什么**: GroundingHook input/output/fallback 正确

**测试**:
1. `python3 -c "from knowledge_grounding_hook import GroundingHook; print('import OK')"` → exit 0
2. 构造 mock extracted_hits + spans → 验证 ground() 返回正确格式
3. 空 spans → confidence=0.5, source_layer=semantic
4. 超时 → fallback raw/vault only

### V6: Dashboard Verification (O12)

**验证什么**: dashboard CLI + HTML 输出

**测试**:
1. `solar-harness wiki knowledge-ingest dashboard --json` → 合法 JSON, 包含 watermarks/state_counts/source_coverage
2. `solar-harness wiki knowledge-ingest dashboard --html` → 生成 HTML 文件
3. JSON 包含 3 层 watermarks (raw/vault/semantic)

### V7: Negative Controls (O4, O7)

**验证什么**: 错误行为被正确拒绝

**测试**:
1. ThunderOMLX 未被当作 embedder: `grep -r "embeddinggemma" lib/knowledge_extract_json.py` → 不存在
2. QUARANTINED 不入 extracted QMD index: 验证 state transition 中无 QUARANTINED → EXTRACTED_QMD_INDEX_PENDING
3. Validation fail 不进 semantic layer: 验证 validator 8 error codes 存在
4. Extraction fail open: circuit breaker paused 时 raw/vault QMD 仍可查

### V8: Regression — 105859 Baseline (U7, S01 铁律)

**验证什么**: build-from-zero 验证 105859 全部 9 个 lib + SQLite

**测试**:
1. `ls ~/.solar/harness/lib/knowledge_*.py` → 9 files
2. `python3 -c "import knowledge_ingest_registry; import knowledge_ingest_dispatcher; import knowledge_source_adapters; import knowledge_spans; import knowledge_extract_json; import knowledge_extracted_renderer; import knowledge_extracted_validator; import knowledge_qmd_indexer; import knowledge_ingest_health; print('all imports OK')"` → exit 0
3. `sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite ".tables"` → ≥10 tables
4. `solar-harness wiki knowledge-ingest status --json` → exit 0
5. `solar-harness wiki knowledge-ingest migrate --json` → idempotent (run twice → same)
6. `solar-harness wiki knowledge-ingest qmd-watermarks --json` → exit 0
7. `solar-harness wiki knowledge-ingest circuit-breaker status --json` → exit 0

### V9: Epic Parent-Check (O14 supplement, S01 U10)

**验证什么**: 父 Epic 不能在任何 required gate 未通过前关闭

**测试**:
1. 检查 `epic-*.traceability.json` 中所有 5 个 child sprint 是否 passed
2. 检查 `epic-*.task_graph.json` 中所有 required_gates 是否 passed
3. `solar-harness epic-decomposer validate-epic --epic epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn` (if command exists)

### V10: Outcome Coverage Matrix

**验证什么**: 14 outcomes 全部有验收证据

**产出**: `test_report.md` 包含每个 outcome 的验证命令 + exit code + 输出摘要

## 3. Write Scope

| Node | 文件 |
|---|---|
| V1-V9 | `tests/test_knowledge_v2.py` (new, test script) |
| V10 | `sprints/*s05*.test_report.md` (new, evidence report) |
| Handoff | `sprints/*s05*.handoff.md` (new) |

**禁止**: 不写功能代码，不修改 S03/S04 的 lib 文件

## 4. Parallelization

V1-V8 可部分并行 (无 write_scope 冲突):
- V1 (schema) + V4 (adapters) + V5 (grounding) + V6 (dashboard) → 可并行
- V2 (state machine) + V3 (naming) → 可并行
- V7 (negative) + V8 (regression) → 可并行
- V9 (parent-check) + V10 (outcome matrix) → 依赖 V1-V8 全部完成

## 5. Testing Strategy

- 每个 V 节点产出具体 CLI 命令 + exit code + stdout 摘要
- 写入 `test_report.md`
- 全部 PASS → sprint passed
- 任一 FAIL → sprint FAIL, 不允许标记 passed

## 6. Stop Rules

- 任一 V 节点 FAIL → sprint 不算 done
- 105859 baseline 任何 import/CLI 失败 → sprint 不算 done (U7 铁律)
- 缺 test_report.md → sprint 不算 done
- Epic parent-check 未通过 → sprint 不算 done
- 缺 task_graph.json → 不派 builder
- 禁止使用 "已完成/implemented/done" 除非有 exit code 证据
