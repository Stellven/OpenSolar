# Design — S03 Core Runtime & Data Model

> **Sprint**: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s03-core-runtime`
> **Epic**: `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn`
> **Slice**: `core-runtime` (builder sprint)
> **Knowledge Context: solar-harness context inject used**
> **Harness Modules Used: harness-knowledge, harness-graph**

## 0. Slice Posture

本切片是 **builder sprint**：依据 S02 architecture design 的 A1-A5 决策，实施 schema migration、状态机扩展、命名迁移、5 个新 adapter、idempotency 增强和验证。

## 1. Upstream Dependencies

| 来源 | 消费内容 |
|---|---|
| S02 design.md (A1-A5) | 全部 5 个架构决策的实施规格 |
| S01 outcomes_matrix.md | O1/O2/O5/O8/O9/O11/O13/O14 (S03 owner) |
| 105859 9 lib files | extend-only, 不改原有行 |
| intake contract | 10 hard requirements |

## 2. Implementation Scope

### B1: Schema Migration v2 (A2 → O9)

**改什么**: `knowledge_ingest_registry.py` 的 `migrate()` 函数

**新增列**:
```sql
-- extract_jobs
ALTER TABLE extract_jobs ADD COLUMN schema_version TEXT NOT NULL DEFAULT 'v1';
ALTER TABLE extract_jobs ADD COLUMN endpoint TEXT;
ALTER TABLE extract_jobs ADD COLUMN started_at TEXT;
ALTER TABLE extract_jobs ADD COLUMN finished_at TEXT;

-- extract_outputs
ALTER TABLE extract_outputs ADD COLUMN latency_ms REAL;
ALTER TABLE extract_outputs ADD COLUMN token_input_count INTEGER;
ALTER TABLE extract_outputs ADD COLUMN token_output_count INTEGER;
ALTER TABLE extract_outputs ADD COLUMN cost_estimate REAL;
ALTER TABLE extract_outputs ADD COLUMN model_fingerprint TEXT;
```

**幂等**: `try: ALTER TABLE ADD COLUMN; except OperationalError: pass`，然后 `INSERT OR IGNORE INTO migration_log(version, ...) VALUES (2, ...)`

**测试**: migration 跑两次 → exit 0, `.schema` 显示新列, migration_log version=2

### B2: State Machine Extension (A3 → O8/O13)

**改什么**: `knowledge_ingest_dispatcher.py`

**新增常量**:
```python
EXTRACT_FAILED_RETRYABLE = "EXTRACT_FAILED_RETRYABLE"
DONE_RAW_ONLY_WARN = "DONE_RAW_ONLY_WARN"
MAX_EXTRACT_RETRIES = 3
```

**新增 VALID_TRANSITIONS**:
```python
# Skip path (circuit breaker or extract_policy=skip)
("EXTRACT_ELIGIBLE", "DONE_RAW_ONLY_WARN"),
# Extract failure
("THUNDEROMLX_EXTRACT_RUNNING", "EXTRACT_FAILED_RETRYABLE"),
# Retry
("EXTRACT_FAILED_RETRYABLE", "THUNDEROMLX_EXTRACT_RUNNING"),
# Retry exhausted
("EXTRACT_FAILED_RETRYABLE", "DONE_RAW_ONLY_WARN"),
```

**新增 dispatcher 逻辑**:
- `drain_extract_failed_retryable()`: 查询 EXTRACT_FAILED_RETRYABLE 且 repair_count < MAX_EXTRACT_RETRIES → transition to RUNNING with exponential backoff delay
- `drain_extract_eligible_skip()`: 查询 EXTRACT_ELIGIBLE 且 extract_policy=skip → transition to DONE_RAW_ONLY_WARN
- `cmd_drain()` 中增加对 EXTRACT_FAILED_RETRYABLE 的处理

**测试**: 提交测试事件 → 验证状态转换 → 验证 max retry 后进入 DONE_RAW_ONLY_WARN

### B3: Naming Migration (A1 → O5)

**改什么**: `knowledge_extracted_renderer.py` + `knowledge_ingest_registry.py`

**renderer 变更**:
1. 输出文件名从 `*.extracted.md` 改为 `*.semantic.md`
2. 写入后创建 symlink: `*.extracted.md → *.semantic.md`
3. layer 字符串从 `"extracted"` 改为 `"semantic"`

**registry 变更**:
1. `migrate()` 中增加: `DELETE FROM watermarks WHERE layer='extracted'` + `INSERT INTO watermarks(layer, ...) VALUES ('semantic', ...)`
2. 所有写入 `qmd_index_events.layer` 的地方改用 `"semantic"`

**兼容**: symlink 确保 grep `*.extracted.md` 仍然命中

**测试**: renderer 输出 → `*.semantic.md` 存在 AND `*.extracted.md` 是 symlink

### B4: New Adapters (A4 → O1/O11)

**改什么**: `knowledge_source_adapters.py`

**5 个新 adapter 实现**:

| Adapter | source_kind | Discovery |
|---|---|---|
| `youtube_adapter` | `youtube_transcript` | scan `~/Knowledge/_raw/` for `*youtube*` or `*transcript*` markdown files |
| `github_adapter` | `github_trends` | scan `~/Knowledge/_raw/` for `*github*` or tech-hotspot-radar output |
| `pdf_adapter` | `pdf_manual` | scan `~/Knowledge/_raw/` for `*.pdf` files |
| `accepted_adapter` | `accepted_sprint` | scan `~/Knowledge/_raw/solar-harness/accepted/` for `*.md` files |
| `solar_adapter` | `solar_artifact` | scan `~/.solar/harness/sprints/` for `*.handoff.md`, `*.eval.md`, `*.prd.md` |

**每个 adapter 实现**:
- `source_kind: str` 类属性
- `discover(limit: int) -> list[dict]`: 扫描目录，过滤未注册文件，返回 IngestEvent 列表
- `verify_spans(doc_id: str, db_path: Path) -> dict`: 基本验证

**注册**: 在 `ADAPTER_REGISTRY` dict 中注册 5 个新 adapter

**dispatcher 新命令**: 在 `cmd_discover_raw` 旁边增加 `cmd_discover_youtube`, `cmd_discover_github`, `cmd_discover_pdf`, `cmd_discover_accepted`, `cmd_discover_solar`

**测试**: 每个新 adapter 的 `discover --limit 1 --json` 返回非空 (如果目录有文件) 或空列表但不报错

### B5: Idempotency Enhancement (O14)

**改什么**: `knowledge_ingest_dispatcher.py` / `knowledge_ingest_registry.py`

**当前 dedupe key**: `(source_kind, source_path, source_sha256)`

**扩展为**: `(source_kind, source_path, source_sha256, prompt_template_id, schema_version, model)`

**实施**:
1. `extract_jobs` 表查询 dedupe 时增加 `prompt_template_id`, `model` 条件
2. `schema_version` 默认 `'v1'`，新 job 用 `'v2'`
3. 测试: same source + different model → 创建 2 个独立 job

### B6: Verification & Regression

**执行**:
1. `solar-harness wiki knowledge-ingest migrate --json` → exit 0
2. `solar-harness wiki knowledge-ingest status --json` → 显示 states 包含新状态
3. `sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite ".schema extract_jobs"` → 包含新列
4. 5 个新 discover 命令 → 各自 exit 0
5. 旧 105859 命令 (`discover-vault`, `discover-raw`, `qmd-watermarks`) → 无回归

## 3. Write Scope

| Node | 文件 |
|---|---|
| B1 | `lib/knowledge_ingest_registry.py` (migrate 函数) |
| B2 | `lib/knowledge_ingest_dispatcher.py` (状态机 + drain) |
| B3 | `lib/knowledge_extracted_renderer.py` (输出名), `lib/knowledge_ingest_registry.py` (watermarks) |
| B4 | `lib/knowledge_source_adapters.py` (5 个新 adapter), `lib/knowledge_ingest_dispatcher.py` (新命令) |
| B5 | `lib/knowledge_ingest_dispatcher.py` / `lib/knowledge_ingest_registry.py` (dedupe) |
| B6 | 无写 (verification only) |

**禁止动**: 105859 已有代码的核心逻辑行（只 extend, 不删改已有行）

## 4. Testing Strategy

- 每个 B 节点至少 1 个 smoke test (CLI 命令 → exit 0)
- B1: migration 幂等
- B2: 状态转换测试 (submit → transition → verify)
- B3: renderer 输出 + symlink 验证
- B4: adapter discover 命令
- B5: dedupe 逻辑测试

## 5. Risks

| Risk | Mitigation |
|---|---|
| ALTER TABLE 在列已存在时报错 | try/except 跳过 |
| 新 adapter 扫描目录不存在 | 返回空列表，不报错 |
| 状态机新增转移与现有逻辑冲突 | 白名单，未知状态 safe ignore |
| watermarks DELETE+INSERT 非原子 | 用事务包裹 |
| symlink 在 NTFS 不支持 | macOS only (项目约束) |

## 6. Stop Rules

- migration 不幂等 → B1 不算 done
- 状态转换未通过白名单校验 → B2 不算 done
- renderer 不输出 .semantic.md → B3 不算 done
- 新 adapter discover 命令报错 → B4 不算 done
- 旧 105859 命令回归 → B6 不算 done
- 缺 task_graph.json → 不派 builder

## 7. Planner Decisions Log

1. **B1-B5 串行**: B1 (schema) → B2 (state) → B3 (naming) → B4 (adapters) → B5 (dedupe)，因为后续节点依赖前序节点的 schema 变更
2. **B6 可与 B3/B4 部分并行**: regression test 在 B1 完成后即可开始
3. **测试用 smoke test**: 完整单测留给 S05；本 sprint 确保 CLI 命令 exit 0
