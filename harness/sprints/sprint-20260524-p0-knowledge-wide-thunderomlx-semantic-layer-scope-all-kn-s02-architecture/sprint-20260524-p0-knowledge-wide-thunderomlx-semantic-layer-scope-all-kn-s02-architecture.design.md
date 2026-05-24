# Design — S02 Architecture & Interface Contracts

> **Sprint**: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s02-architecture`
> **Epic**: `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn`
> **Slice**: `architecture` (planning-only — 不写 runtime 代码)
> **Knowledge Context: solar-harness context inject used**
> **Harness Modules Used: harness-knowledge, harness-graph**

## 0. Slice Posture

本切片是 **planning-only**：基于 S01 outcomes_matrix 的 14 个 outcomes，决断 S01 交给 S02 的 5 个未闭环架构决策（U1-U5），产出系统分层、接口契约、数据模型扩展、兼容策略和迁移方案。**不写代码**；S03 builder 依据本 design 实施。

## 1. 上游输入摘要

| 来源 | 关键内容 |
|---|---|
| S01 outcomes_matrix.md | 14 outcomes (O1-O14)，5 个不能直派 builder |
| S01 handoff.md | U1-U10 未闭环项，S02 owner: U1/U2/U4/U5 |
| 105859 design.md | 已落地 9 lib + 10 表 SQLite + 状态机 + circuit breaker |
| 105859 task_graph.json | N1-N8 节点拓扑已 stable |
| intake contract | 10 hard requirements + state machine + 8 类 source |

S02 必须决断的 5 个架构决策：

| ID | 决策 | 影响 |
|---|---|---|
| **A1 (U1)** | `extracted.md` vs `semantic.md` 命名 | 文件系统 + grep 入口 + qmd_index_events.layer |
| **A2 (U2)** | latency/token_cost 字段：add-column vs schema v2 | extract_jobs + extract_outputs 表 |
| **A3 (U5)** | 状态机缺 `EXTRACT_FAILED_RETRYABLE` / `DONE_RAW_ONLY_WARN` | dispatcher 转移逻辑 + 现有 row 兼容 |
| **A4 (U4)** | 5 类缺失 adapter 的路径策略 | adapter 注册模式 + source_kind enum |
| **A5** | O10 query grounding interface contract | solar-knowledge-context.py + report 路径 |

## 2. Architecture Decisions

### A1: File Naming — `*.semantic.md` (新名) + `*.extracted.md` (别名兼容)

**决断**：采用 intake 要求的 `*.semantic.md` 作为正式名称；105859 的 `*.extracted.md` 保留为 symlink 别名，兼容期 2 sprint。

**理由**：
- intake contract 明确要求 `semantic.md`
- `extracted.md` 只在 105859 内部 renderer 代码使用，外部无依赖
- 保留别名防止 grep 断裂

**实施**：
1. `knowledge_extracted_renderer.py` 的输出文件名改为 `*.semantic.md`
2. renderer 在写入 `.semantic.md` 后，创建 `*.extracted.md → *.semantic.md` 的 symlink
3. `qmd_index_events.layer` 字段值从 `extracted` 改为 `semantic`（`layer TEXT NOT NULL -- raw | vault | semantic`）
4. 兼容期结束后（S05 verification 后），移除 symlink 创建逻辑和 grep 中 `extracted` 的 fallback
5. `watermarks` 表的 `layer` 行从 `extracted` 迁移为 `semantic`

**Rollback**：改回 `extracted.md`，移除 symlink，只需改 renderer 一处。

### A2: Schema Extension — In-Place Add Column (schema v2)

**决断**：对 `extract_jobs` 和 `extract_outputs` 做 `ALTER TABLE ADD COLUMN`，不走 schema v2 新表。

**理由**：
- 105859 数据量极小（当前 < 50 rows），不存在 migration 性能问题
- SQLite `ALTER TABLE ADD COLUMN` 是原子操作，向后兼容
- 不需要新表，避免 join 开销

**实施**：
```sql
-- extract_jobs 新增列
ALTER TABLE extract_jobs ADD COLUMN schema_version TEXT NOT NULL DEFAULT 'v1';
ALTER TABLE extract_jobs ADD COLUMN endpoint TEXT;
ALTER TABLE extract_jobs ADD COLUMN started_at TEXT;
ALTER TABLE extract_jobs ADD COLUMN finished_at TEXT;

-- extract_outputs 新增列
ALTER TABLE extract_outputs ADD COLUMN latency_ms REAL;
ALTER TABLE extract_outputs ADD COLUMN token_input_count INTEGER;
ALTER TABLE extract_outputs ADD COLUMN token_output_count INTEGER;
ALTER TABLE extract_outputs ADD COLUMN cost_estimate REAL;
ALTER TABLE extract_outputs ADD COLUMN model_fingerprint TEXT;
```

- `migration_log` 记录 version=2
- 旧数据 `schema_version='v1'`，新增字段为 NULL
- 新数据填写所有字段
- 幂等：`ALTER TABLE ADD COLUMN` 在列已存在时报错但非致命；registry migrate 用 try/except 跳过

### A3: State Machine Extension — 新增 2 个状态

**决断**：新增 `EXTRACT_FAILED_RETRYABLE` 和 `DONE_RAW_ONLY_WARN` 作为独立状态，不合并到 `VALIDATION_FAILED`。

**理由**：
- `EXTRACT_FAILED_RETRYABLE`：抽取阶段（ThunderOMLX 调用）失败但可重试，与 `VALIDATION_FAILED`（抽取成功但校验失败）语义完全不同
- `DONE_RAW_ONLY_WARN`：终态，raw/vault 可查但无 semantic，用于 circuit breaker 暂停或 adapter 不支持抽取的场景
- 合并会导致 retry 逻辑混乱（retry 抽取 vs retry 校验是不同策略）

**完整状态机**（在 105859 design §3.2 基础上扩展）：

```text
NEW
 └► SOURCE_CAPTURED ──► RAW_MATERIALIZED ──► RAW_OR_VAULT_QMD_INDEX_PENDING
                                  │                       │
                                  └► VAULT_DISCOVERED     │
                                          │               │
                                          ▼               ▼
                                      SPAN_MAPPED ──► RAW_OR_VAULT_QMD_INDEXED
                                                          │
                                                          ▼
                                                  EXTRACT_ELIGIBLE
                                                          │
                                            ┌─────────────┼─────────────────┐
                                            │             │                 │
                                            ▼             │                 ▼
                                  (skip extract)          │        THUNDEROMLX_EXTRACT_RUNNING
                                            │             │                 │
                                            ▼             │     ┌──────────┴──────────┐
                                  DONE_RAW_ONLY_WARN      │     │                     │
                                                            ▼     ▼                     ▼
                                                  THUNDEROMLX_EXTRACT_PENDING  EXTRACT_FAILED_RETRYABLE
                                                            │                     │
                                                            ▼                     │ (retry loop, max 3)
                                              EXTRACT_CANDIDATE_GENERATED      │
                                                            │                     │
                                                            ▼                     │
                                              EXTRACT_VALIDATION_PENDING        │
                                                          ┌─┴─┐                 │
                                                          ▼   ▼                 │
                                               EXTRACTED_VALIDATED  VALIDATION_FAILED
                                                          │           │
                                                          ▼           ▼
                                              EXTRACTED_QMD_INDEX_PENDING  REPAIR_PENDING (1x)
                                                          │                     │
                                                          ▼                     ▼ fail again
                                              EXTRACTED_QMD_INDEXED      QUARANTINED
                                                          │
                                                          ▼
                                                        DONE
```

**新状态转移规则**：

| From | To | Trigger |
|---|---|---|
| EXTRACT_ELIGIBLE | DONE_RAW_ONLY_WARN | adapter declares `extract_policy=skip` OR circuit breaker paused AND doc bypass window expired |
| EXTRACT_ELIGIBLE | THUNDEROMLX_EXTRACT_PENDING | normal flow |
| THUNDEROMLX_EXTRACT_RUNNING | EXTRACT_FAILED_RETRYABLE | ThunderOMLX call exception (network/model error) |
| EXTRACT_FAILED_RETRYABLE | THUNDEROMLX_EXTRACT_RUNNING | retry (max 3, exponential backoff) |
| EXTRACT_FAILED_RETRYABLE | DONE_RAW_ONLY_WARN | max retry exceeded |

**兼容**：现有 `documents` 行的 `current_state` 不会出现新值（是旧数据）；dispatcher 读到未知状态时保持不动（safe default）。

### A4: Adapter Strategy — 统一 Adapter Protocol

**决断**：所有 adapter 遵循统一 `AdapterProtocol`，注册到 `knowledge_source_adapters.py` 的 adapter registry。

**8 类 source_kind enum**（扩展自 105859 现有的 `raw_chatgpt | obsidian_vault | accepted`）：

| source_kind | Adapter | Discovery | Status |
|---|---|---|---|
| `obsidian_vault` | `obsidian_adapter` | scan `~/Knowledge/` concepts/references/synthesis/projects | 105859 已建 |
| `raw_chatgpt` | `chatgpt_adapter` | scan `~/Knowledge/_raw/chatgpt/` | 105859 已建 |
| `raw_web` | `web_adapter` | scan `~/Knowledge/_raw/web-captures/` | 105859 已建 |
| `youtube_transcript` | `youtube_adapter` | **迁移**: 现有 `knowledge-semantic-extract.py` 路径 → 改为 submit ingest event | S03 新建 |
| `github_trends` | `github_adapter` | scan `~/Knowledge/_raw/github/` OR `tech-hotspot-radar` output | S03 新建 |
| `pdf_manual` | `pdf_adapter` | scan `~/Knowledge/_raw/` for `.pdf` + call MinerU | S03 新建 |
| `accepted_sprint` | `accepted_adapter` | scan `~/Knowledge/_raw/solar-harness/accepted/` | S03 新建 |
| `solar_artifact` | `solar_adapter` | scan `~/.solar/harness/sprints/*.handoff.md`, `*.eval.md`, `*.prd.md` | S03 新建 |

**Adapter Protocol Interface**（S03 builder 实现）：

```
AdapterProtocol:
  source_kind: str           # enum from above
  discover(limit) -> [IngestEvent]
  verify_spans(doc_id, db) -> VerifyResult
```

每个 adapter 的 `discover()` 扫描对应目录，为每个未注册文件生成 `IngestEvent`（event_id, source_kind, source_path, content_kind, declared_doc_type），然后通过 dispatcher `submit_event` 入 registry。

**YouTube 迁移策略**（intake item 8）：
1. `youtube_adapter` 新建，注册 `source_kind=youtube_transcript`
2. 现有 `knowledge-semantic-extract.py` 保留运行（旁路），直到新路径经过 S05 端到端验证
3. 验证通过后，旧路径的 cron 改为调用 `youtube_adapter discover` → dispatcher
4. 不删旧代码，只移除 cron 调度

### A5: Query Grounding Interface Contract (O10)

**决断**：定义 query grounding hook 的接口契约，实现留给 S04。

**接口**：

```
GroundingHook:
  input:
    query: str
    extracted_hits: [{doc_id, score, candidate_json_path}]
    registry: knowledge_ingest_registry connection

  output:
    grounded_context: [{
      claim_text: str,
      evidence_spans: [{span_id, source_path, text_excerpt}],
      confidence: float,
      source_layer: "semantic" | "raw" | "vault"
    }]

  fallback policy:
    - extracted hit 无 span 引用 → 标记 source_layer=semantic, confidence=0.5
    - span 在 registry 中不存在 → drop 该 claim, log warning
    - raw/vault 查到同一 source_path → 优先用 raw/vault 文本作 grounding
```

**Consumer**：
1. `solar-knowledge-context.py` — context inject 路由时优先用 extracted 但 grounding 回 raw/vault
2. Tech Hotspot report — report reader 优先读 `*.semantic.md`，fallback 到 transcript/raw
3. status server — dashboard 展示 grounding 覆盖率

**约束**：
- Grounding hook 是只读操作，不修改 registry 或文件
- hook 调用不阻塞主查询路径（超时 2s → fallback to raw/vault only）

## 3. System Layering

### 3.1 Control Plane

```text
┌─────────────────────────────────────────────────────────────┐
│  Layer 0: Source Adapters (8 kinds)                         │
│  职责: discover + submit ingest_event                       │
│  依赖: dispatcher API                                       │
└──────────────┬──────────────────────────────────────────────┘
               │ submit_event()
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Dispatcher (state machine driver)                 │
│  职责: idempotency, state transition, queue drain           │
│  依赖: Registry (SQLite)                                    │
│  新增: EXTRACT_FAILED_RETRYABLE retry loop                  │
│        DONE_RAW_ONLY_WARN terminal state                    │
└──────────────┬──────────────────────────────────────────────┘
               │ read/write
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Registry (SQLite, source of truth)                │
│  职责: documents, spans, events, jobs, outputs,             │
│        validation, relations, watermarks, migration_log     │
│  新增: extract_jobs (schema_version, endpoint, latency)     │
│        extract_outputs (latency_ms, token_*, cost, model_fp)│
│        watermarks layer: extracted → semantic               │
└─────────────────────────────────────────────────────────────┘
               ▲
               │ validate + repair
┌──────────────┴──────────────────────────────────────────────┐
│  Layer 3: Extract Pipeline                                  │
│  ├─ JSON-First Extractor (ThunderOMLX)                      │
│  ├─ Deterministic Renderer (*.semantic.md)                  │
│  └─ Validator (8 error codes + repair_once + quarantine)    │
│  新增: schema_version 跟踪, model_fingerprint 记录          │
└──────────────┬──────────────────────────────────────────────┘
               │ on validated
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: QMD Indexer (3 watermarks: raw/vault/semantic)    │
│  职责: microbatch flush, watermark tracking                 │
│  依赖: qmd_adapter.py (existing)                            │
│  新增: layer name extracted → semantic                      │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 5: Query & Reporting                                 │
│  ├─ GroundingHook (O10) — prefer semantic, ground to raw    │
│  ├─ Tech Hotspot report — prefer semantic.md                │
│  └─ Context injection — prefer semantic with raw fallback   │
│  新增: A5 grounding interface                               │
└─────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 6: Observability & Health                            │
│  ├─ Circuit Breaker (pause extract queue, raw/vault safe)   │
│  ├─ Health CLI (status, watermarks, audit)                  │
│  └─ Dashboard UI (3-layer watermarks + counts)              │
│  新增: retry count metrics, DONE_RAW_ONLY_WARN count        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Data Plane Flow

```text
Source File
  → Adapter.discover() → IngestEvent
  → Dispatcher.submit_event()
  → Registry.upsert_document(state=NEW)
  → Adapter triggers: raw materialization / vault scan
  → Dispatcher: NEW → SOURCE_CAPTURED → RAW_MATERIALIZED / VAULT_DISCOVERED
  → Span Mapper: document → spans[]
  → Dispatcher: → SPAN_MAPPED → RAW_OR_VAULT_QMD_INDEXED
  → QMD Indexer (raw/vault layer): flush to qmd_index_events
  → Dispatcher: → EXTRACT_ELIGIBLE
  → [skip path] → DONE_RAW_ONLY_WARN (if extract_policy=skip or circuit breaker)
  → [extract path] → THUNDEROMLX_EXTRACT_PENDING → THUNDEROMLX_EXTRACT_RUNNING
  → Extractor: JSON candidate (extract_jobs + extract_outputs with latency/tokens)
  → [retry path] → EXTRACT_FAILED_RETRYABLE → retry → RUNNING (max 3)
  → [retry exhausted] → DONE_RAW_ONLY_WARN
  → Renderer: *.semantic.md (deterministic, symlink *.extracted.md)
  → Validator: 8 error codes
  → [valid] → EXTRACTED_VALIDATED → EXTRACTED_QMD_INDEXED → DONE
  → [invalid] → REPAIR_PENDING (1x) → [still invalid] → QUARANTINED
  → QMD Indexer (semantic layer): flush extracted to qmd_index_events
  → Watermarks: update per-layer counters
```

## 4. Interface Contracts

### 4.1 Dispatcher → Registry

| Method | Input | Output | Invariant |
|---|---|---|---|
| `submit_event(event)` | IngestEvent (§3.4 105859 design) | `{ok, doc_id}` | idempotent by `(source_kind, source_path, source_sha256)` |
| `transition(doc_id, to_state)` | doc_id, target_state | `{ok, from_state, to_state}` | only valid transitions (§A3 state machine) |
| `drain_queue(state, limit)` | state_name, batch_size | `[doc_id, ...]` | FIFO by updated_at |

### 4.2 Adapter → Dispatcher

| Method | Input | Output |
|---|---|---|
| `discover(limit)` | max docs to discover | `[IngestEvent]` |
| `verify_spans(doc_id)` | doc_id | `{span_count, verified_count, mismatch_count}` |

### 4.3 Extractor → Registry

| Method | Input | Output |
|---|---|---|
| `create_job(doc_id, span_ids, prompt_template_id, model)` | job params | `{job_id}` |
| `write_output(job_id, kind, path, sha256, latency_ms, tokens, cost, model_fp)` | output data | `{output_id}` |
| `update_job_state(job_id, state)` | state | `{ok}` |

### 4.4 Validator → Registry

| Method | Input | Output |
|---|---|---|
| `validate(job_id)` | job_id | `{passed, errors[]}` |
| `write_validation(result)` | ValidationResult | `{result_id}` |

### 4.5 GroundingHook → Registry (Read-only)

| Method | Input | Output |
|---|---|---|
| `resolve_spans(span_ids)` | `[span_id]` | `[{span_id, source_path, text_excerpt}]` |
| `get_relations(doc_id, kind)` | doc_id, relation_kind | `[{target_doc_id, weight}]` |

## 5. Failure Recovery

### 5.1 State Recovery

| 故障场景 | 恢复策略 | 实现 |
|---|---|---|
| Dispatcher crash mid-transition | Registry 记录 from_state → dispatcher restart 后重跑 drain | `ingest_events` 表 audit trail |
| Extractor crash (ThunderOMLX down) | `EXTRACT_FAILED_RETRYABLE` → exponential backoff retry (max 3) | dispatcher retry loop |
| Validator crash | Job stays in `EXTRACT_VALIDATION_PENDING` → next drain cycle re-validates | idempotent validate |
| QMD indexer crash | `qmd_index_events.qmd_status=failed` → retry next microbatch | `retry_count` counter |
| Full pipeline pause (circuit breaker) | raw/vault QMD index continues; only extract queue paused | N7 health module |
| Retry exhausted | `DONE_RAW_ONLY_WARN` terminal state; raw/vault still searchable | state machine terminal |
| Source file changed after extraction | `E_SOURCE_SHA_MISMATCH` → quarantine; reingest from raw | validator check |

### 5.2 Data Recovery

- Registry SQLite WAL mode: crash-safe writes
- `migration_log` + idempotent ALTER TABLE: safe schema evolution
- `ingest_events` full audit trail: any state rebuildable from event log
- Circuit breaker: rolling-25 window, 25% fail threshold OR 5 consecutive

## 6. Observability

### 6.1 Metrics (exposed by health CLI + dashboard)

| Metric | Source | Consumer |
|---|---|---|
| Per-state doc count | `documents` GROUP BY current_state | dashboard, health CLI |
| 3-layer watermarks | `watermarks` table | dashboard |
| Validation pass rate | `validation_results` rolling window | circuit breaker, dashboard |
| Extract queue depth | COUNT where state=EXTRACT_ELIGIBLE | dashboard |
| Quarantine count | COUNT where state=QUARANTINED | dashboard, alerting |
| DONE_RAW_ONLY_WARN count | COUNT where state=DONE_RAW_ONLY_WARN | dashboard (coverage gap) |
| Per-source-kind coverage | `documents` GROUP BY source_kind | coverage audit |
| Per-adapter latency | `extract_outputs.latency_ms` AVG | performance monitoring |

### 6.2 CLI Commands (extended from 105859)

| Command | New in S03/S04 |
|---|---|
| `solar-harness wiki knowledge-ingest status --json` | existing |
| `solar-harness wiki knowledge-ingest discover-vault --json` | existing |
| `solar-harness wiki knowledge-ingest discover-raw --json` | existing |
| `solar-harness wiki knowledge-ingest discover-youtube --json` | **S03 new** |
| `solar-harness wiki knowledge-ingest discover-github --json` | **S03 new** |
| `solar-harness wiki knowledge-ingest discover-pdf --json` | **S03 new** |
| `solar-harness wiki knowledge-ingest discover-accepted --json` | **S03 new** |
| `solar-harness wiki knowledge-ingest discover-solar --json` | **S03 new** |
| `solar-harness wiki knowledge-ingest qmd-watermarks --json` | existing (layer name change) |
| `solar-harness wiki knowledge-ingest circuit-breaker status --json` | existing |
| `solar-harness wiki knowledge-ingest coverage-report --json` | **S04 new** |
| `solar-harness wiki knowledge-ingest grounding-check --query "..." --json` | **S04 new** |

## 7. Compatibility & Migration

### 7.1 Backward Compatibility

| 变更 | 兼容策略 | 过渡期 |
|---|---|---|
| `*.extracted.md` → `*.semantic.md` | symlink alias | 2 sprint |
| `watermarks.layer` extracted → semantic | ALIAS: query both values | 2 sprint |
| `qmd_index_events.layer` extracted → semantic | 新写入用 semantic，旧数据不动 | permanent (both queryable) |
| 新增 2 个状态 | dispatcher 未知状态 safe ignore | permanent |
| 新增 schema columns | NULL default, 不影响旧查询 | permanent |

### 7.2 Migration Steps (S03 builder 执行)

1. `ALTER TABLE extract_jobs ADD COLUMN schema_version TEXT NOT NULL DEFAULT 'v1'` (and 4 more columns)
2. `ALTER TABLE extract_outputs ADD COLUMN latency_ms REAL` (and 5 more columns)
3. `INSERT INTO migration_log(version, applied_at, checksum) VALUES (2, ...)`
4. Update `knowledge_extracted_renderer.py`: output filename → `*.semantic.md` + symlink `*.extracted.md`
5. Update `knowledge_ingest_dispatcher.py`: add EXTRACT_FAILED_RETRYABLE + DONE_RAW_ONLY_WARN transitions
6. Add 5 new adapter stubs to `knowledge_source_adapters.py`
7. Update `watermarks` table: rename `extracted` row to `semantic`

## 8. Dependency & Conflict Analysis

### 8.1 Conflicts

| 冲突 | 涉及方 | 解决 |
|---|---|---|
| `extracted.md` naming | 105859 renderer vs intake spec | A1: symlink alias |
| 105859 status=passed 但未端到端实测 | S05 信任基线 | U7: S05 build-from-zero |
| YouTube 现有路径 vs 新 dispatcher 路径 | intake item 8 | A4: 旁路并行，验证后切换 |

### 8.2 Dependencies

| 依赖 | 方向 | 状态 |
|---|---|---|
| S01 outcomes_matrix | S02 ← S01 | passed |
| 105859 9 lib files | S03 ← 105859 | passed (unverified until S05) |
| 134738 skill/capsule | S02/S03 ← 134738 | passed (optional reference) |
| 133807 prerequisite schema | S02 ← 133807 | active (use new schema for task_graph) |
| solar-knowledge-context.py | S04 ← existing | stable (read-only extension) |

### 8.3 Degradation Strategies

| 降级场景 | 策略 |
|---|---|
| ThunderOMLX 不可用 | 所有 doc → DONE_RAW_ONLY_WARN; raw/vault QMD 照常 |
| QMD embed runner down | extract pipeline 继续跑; qmd_index_events 排队; 恢复后 microbatch flush |
| 新 adapter 扫描失败 | skip 该 source_kind; 记录 health event; 不阻塞其他 adapter |
| Registry SQLite 锁 | WAL mode + retry 3 次; 超时 → 命令级报错，不静默丢数据 |
| Grounding hook 超时 | 2s timeout → fallback raw/vault only; log warning |

## 9. Outcome → Architecture Decision Traceability

| Outcome | S02 Architecture Decision | 下游 Owner |
|---|---|---|
| O1 | Layer 0 adapter protocol (§A4) | S03 |
| O2 | Layer 2 registry schema (§3.2 105859 design, no change) | S03, S05 |
| O3 | Layer 4 QMD watermark gate (§3.1 105859 design) | S04 |
| O4 | Layer 3 extractor as L2 worker (§3.2 105859 design) | S05 |
| O5 | **A1**: naming `*.semantic.md` + symlink | S03 |
| O6 | Layer 3 validator evidence check (§3.5 105859 design) | S05 |
| O7 | Layer 3 quarantine gate (§3.6 105859 design) | S05 |
| O8 | **A3**: DONE_RAW_ONLY_WARN terminal state | S03, S05 |
| O9 | **A2**: schema v2 add-column (latency/tokens/cost) | S03 |
| O10 | **A5**: GroundingHook interface contract | S04 |
| O11 | **A4**: 5 new adapters + YouTube migration | S03 |
| O12 | Layer 6 dashboard UI (§6.1 metrics) | S04 |
| O13 | **A3**: state enum extension (§A3) | S03, S05 |
| O14 | Layer 1 idempotency by extractor identity (§4.1) | S03 |

## 10. Constraints / Invariants

- **不写代码**。S03 builder 依据本 design 实施。
- **不动 105859 已交付的 9 个 lib 文件**（S03 只 extend，不改原有行）。
- `watermarks.layer` 的 `extracted` 行在 migration 后 `DELETE` 并 `INSERT` `semantic` 行（SQLite PRIMARY KEY 是 layer，不能 ALTER）。
- 状态机新增转移必须用白名单，不允许 free-form state string。
- GroundingHook 是只读操作，不修改 registry 或文件系统。
- 所有新 adapter 的 `discover()` 必须支持 `--limit` 参数，防止全量扫描。
- YouTube 迁移期间旧路径和新路径并存，旧路径 cron 不删除直到 S05 验证通过。

## 11. Stop Rules

- 缺 `task_graph.json` → 不派 S03 builder
- 缺 design.md → 不派 S03 builder
- 本 design 中任何 A1-A5 决策未闭环 → 不算 done
- 与 105859 design 的接口冲突未解决 → 不算 done
- O10 grounding hook 接口未定义 input/output/fallback → 不算 done
- 未在 handoff 中写明上游依赖 + 下游影响 + 未闭环项 → 不算 done

## 12. Planner Decisions Log

1. **A1: `semantic.md` 正名 + symlink 兼容** — intake 明确要求；105859 只在内部用 `extracted.md`；影响最小。
2. **A2: add-column vs new-table** — 数据量小，add-column 更简单且向后兼容；新表增加 join 复杂度不值得。
3. **A3: 独立状态 vs 合并** — `EXTRACT_FAILED_RETRYABLE` 是抽取阶段错误，`VALIDATION_FAILED` 是校验阶段错误，语义不同必须分开；`DONE_RAW_ONLY_WARN` 是有意的终态。
4. **A4: YouTube 旁路并行** — intake item 8 明确要求保持旧路径运行；强切风险太高。
5. **A5: grounding hook 只定义接口** — 实现涉及 `solar-knowledge-context.py` 改造，复杂度属于 S04 scope；S02 只定契约。
