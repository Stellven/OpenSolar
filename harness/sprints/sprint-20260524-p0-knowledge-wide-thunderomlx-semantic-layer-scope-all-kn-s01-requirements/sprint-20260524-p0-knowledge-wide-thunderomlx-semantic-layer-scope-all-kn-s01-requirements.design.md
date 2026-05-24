# Design — S01 Requirements & Traceability (Epic child)

> **Sprint**: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements`
> **Epic**: `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn`
> **Slice**: `requirements` (planning-only — 不写 runtime 代码)
> **Knowledge Context: solar-harness context inject used** (Mirage degraded; QMD/Obsidian/Solar DB 命中)
> **Harness Modules Used: harness-knowledge, harness-graph, harness-skills (inventory)**

## 0. Slice Posture

本切片是 **planning-only**：把用户原始需求（intake `20260524t132500z-knowledge-wide-thunderomlx-semantic-layer.md`）拆成可验收 outcomes、边界、非目标、风险，并产出 **outcome → Epic 下游切片** 的 traceability matrix。**不写代码**；S01 builder 的工作只是写 outcome matrix + traceability JSON。

## 1. Epic 上下文 (Parent)

| 字段 | 值 |
|---|---|
| Epic ID | `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn` |
| Priority | P0 |
| Goal | 把 ThunderOMLX 语义后处理从 YouTube transcript 专项链路推广为**所有知识库入口**的默认 L2 语义抽取层 |
| Activation policy | DAG 自动（max 2 同时活跃） |

Epic DAG（来自 `epic-*.task_graph.json` + `traceability.json`）：

```text
S01_requirements (active)  ← 本 sprint
  └► S02_architecture
       ├► S03_core_runtime
       └► S04_orchestration_ui
            └► S05_verification_release
```

## 2. 关键发现：与 sprint-20260524-105859 的重叠 (Reality Check)

**实证检查（grep & sqlite，2026-05-24）：**

| 检查 | 结果 |
|---|---|
| `lib/knowledge_ingest_registry.py` | ✅ exists (365 lines) |
| `lib/knowledge_ingest_dispatcher.py` | ✅ exists (275 lines) |
| `lib/knowledge_source_adapters.py` | ✅ exists |
| `lib/knowledge_spans.py` | ✅ exists |
| `lib/knowledge_extract_json.py` | ✅ exists |
| `lib/knowledge_extracted_renderer.py` | ✅ exists |
| `lib/knowledge_extracted_validator.py` | ✅ exists |
| `lib/knowledge_qmd_indexer.py` | ✅ exists |
| `lib/knowledge_ingest_health.py` | ✅ exists |
| `~/Knowledge/_registry/knowledge_ingest.sqlite` | ✅ exists; 10 tables (documents/spans/ingest_events/qmd_index_events/extract_jobs/extract_outputs/validation_results/relations/watermarks/migration_log) |
| `sprint-20260524-105859.status` | `passed` / `finalized` |

**结论**: `sprint-20260524-105859`（knowledge-ingest-dispatcher 统一控制面，今日早上 105859 流程刚跑完）**已经实质性交付了本 Epic 大约 60-70% 的核心实现**。本 Epic 必须 **消费 105859 已落地工作**，**不要重造**；本 S01 的 traceability 把 Epic 14 个 outcomes 分成三档：`reuse-from-105859` / `extend-from-105859` / `epic-net-new`。

⚠ **未验证**：上述 9 个 lib 文件已 exist，但本 sprint 没跑它们的测试/contract，无法保证 PRD 全部 acceptance 实际通过；S05 verification-release 切片必须做端到端实测，不能只看 status=passed。

## 3. Outcome Decomposition (O1-O14)

> Source：intake §Hard Requirements (10) + §Acceptance Criteria (9 areas) + §Immediate Work Items (8)；合并去重得 14 个 outcome。

| ID | Outcome | Acceptance | Risk | 现状 vs 105859 | 下游 owner |
|---|---|---|---|---|---|
| **O1** | 所有知识源进入同一 ingest dispatcher | adapters submit `event_id` → dispatcher 一处状态机驱动；无 bypass | adapter coverage 不全 | reuse: dispatcher+registry 已建；extend: YouTube/GitHub/PDF/Solar adapter 尚需补 | **S03** |
| **O2** | SQLite registry 是事实源 | `documents/spans/extract_jobs/validation_results/watermarks` 等 10 张表；migration 幂等 | migration 脏库 | reuse: 已建（10 表全） | **S03** (维护) + **S05** (验证) |
| **O3** | Raw/Vault 必先 QMD 索引才能进 semantic 抽取 | state 必经 `RAW_OR_VAULT_QMD_INDEXED` 才允许 `EXTRACT_ELIGIBLE` | QMD 长批次滞后 | reuse: 105859 design §3.2 已锁；extend: 实测 watermark 抖动需 S04 dashboard 暴露 | **S04** |
| **O4** | ThunderOMLX 是 L2 语义 worker，不是 embedder | QMD 仍用 embeddinggemma；ThunderOMLX 只在 EXTRACT_RUNNING 状态被调 | 误把 ThunderOMLX 当 embedder | reuse: 设计已强制；extend: contract check 写到 S05 negative test | **S05** |
| **O5** | ThunderOMLX 输出 JSON-first；Markdown 由 deterministic renderer 生成 | `extracted.candidate.json` schema + `*.extracted.md`（也叫 `*.semantic.md`，**命名待统一**） | LLM JSON 输出不稳 | reuse: extract_json + renderer 已建；**gap: 命名 `extracted.md` vs intake 要求 `semantic.md`** | **S02** (定名) + **S03** (改名) |
| **O6** | 每个 semantic claim 引用 source spans | candidate.evidence[] 引用 spans 表存在的 span_id；mismatch 触发 `E_SOURCE_SHA_MISMATCH` | span_id 漂移 | reuse: validator 已实现 8 个错误码 | **S05** (实测) |
| **O7** | Validation fail 不污染 QMD extracted index | QUARANTINED/VALIDATION_FAILED 永不入 EXTRACTED_QMD_INDEX_PENDING | quarantine 路径未跑过 | reuse: validator + indexer 守门；**gap: 实测覆盖** | **S05** |
| **O8** | Extraction fail open: raw/vault 仍可被查询 | extract pipeline crash 不阻塞 raw/vault QMD indexer worker | worker 共用进程模型 | reuse: circuit breaker 设计已暂停 only-extract-queue；**gap: 实测进程隔离** | **S03** (确认隔离) + **S05** (实测) |
| **O9** | Registry 记录 model/endpoint/prompt/schema/source_hash/output_hash/latency/cost/status | extract_jobs + extract_outputs + validation_results 字段完整 | **gap: 当前 schema 没有 latency / token_cost 字段** | **partial**: 大部分字段在；latency + token/cost 需 S03 schema 扩展 | **S03** (schema v2) |
| **O10** | Reports 与 context injection 优先 semantic md，但回源 raw/vault | `solar-knowledge-context.py` query runtime 检查 evidence → 回 raw/vault；Tech Hotspot report 同 | **gap: 当前 query runtime 未实现 grounding hook (D9 deferred from 105859)** | **net-new**: 不在 105859 scope | **S04** (UI/route) + **S05** (实测) |
| **O11** | Coverage：accepted / Obsidian / ChatGPT / Web / YouTube / GitHub / PDF / Solar 8 类来源全部进 registry | 每类至少 20 样本 discovered | adapter coverage 不全 → false 完工 | **partial**: Obsidian/raw/ChatGPT 已（complete 自 105859 N3）；**gap: YouTube transcript / GitHub trends / PDF/manual / accepted-sprint / Solar artifact 5 类 adapter 需 S03 补** | **S03** |
| **O12** | Dashboard 显示 raw/vault/extracted 三层 watermark + pending + validation_failed + quarantine count | UI / status server 暴露 metrics | UI 不存在 | reuse: watermarks 表已建；**net-new**: dashboard UI 需 S04 | **S04** |
| **O13** | 状态机完整覆盖 intake 列出的失败分支 (`EXTRACT_FAILED_RETRYABLE` / `VALIDATION_FAILED` / `REPAIR_PENDING` / `QUARANTINED` / `DONE_RAW_ONLY_WARN`) | dispatcher state machine enum + tests | **gap: `EXTRACT_FAILED_RETRYABLE` 与 `DONE_RAW_ONLY_WARN` 未在 105859 design 中显式列出** | **extend**: S02 把 state enum 补齐；S03 实施 + S05 实测 | **S02** + **S03** + **S05** |
| **O14** | Idempotency：unchanged source_hash + prompt/schema/model → 跳过重抽 | dedupe by `(source_kind, source_path, source_sha256)` + extractor identity | **gap: 105859 实现的 dedupe 只看 source；未对比 prompt_template_id + schema_version + model** | **extend**: S03 加 extractor identity tuple 进 dedupe key | **S03** |

## 4. 边界 (Out-of-Scope this Sprint AND this Epic)

| 不做 | 原因 |
|---|---|
| 替换 QMD embedding 模型（embeddinggemma → 别的） | intake §Non-goals 明示 |
| 覆写 raw 或 Obsidian 原文 | intake §Non-goals |
| 让未验证 LLM 输出进 extracted QMD index | intake §Non-goals + O7 |
| 全量历史 backfill 在 sample pass 前启动 | sprint-20260524-105859 已建立 circuit breaker 守门 |
| 让 RAGFlow / ThunderOMLX 成为事实源 | intake §"QMD 继续做确定性索引，不得替换成 ThunderOMLX" |
| 把 YouTube transcript 现有路径强行下线 | intake §Immediate Work Items #8："keep current YouTube transcript semantic path running, but migrate it onto the common dispatcher after MVP" |

## 5. "不能直接派 Builder" 的 outcomes (PRD Acceptance #2)

下列 outcomes **不能** 直接派给 builder（需要 planner / architect / human decision 先收敛），否则 builder 会做错方向：

| Outcome | 为什么不能直接派 builder | 谁来收敛 |
|---|---|---|
| **O5** semantic.md 命名 | 105859 已用 `extracted.md`；intake 要求 `semantic.md`；改名涉及历史 file 重命名 + qmd_index_events.layer 字段 + 所有 grep 入口。需 architect (S02) 决断 + migration plan | **S02 architect** |
| **O9** latency / token_cost 字段加 schema | schema migration 涉及 extract_jobs / extract_outputs 表；改字段牵 105859 已写入数据；需架构决策："新表 v2 vs in-place add column"。直接派 builder 会乱改 schema | **S02 architect** |
| **O10** semantic-vs-raw query grounding | 涉及 `solar-knowledge-context.py` query 路径 + report 路径多个 consumer；需 architect 写 interface contract（input/output、fallback policy） | **S02 architect** + **S04 builder** |
| **O13** state enum 补 `EXTRACT_FAILED_RETRYABLE` / `DONE_RAW_ONLY_WARN` | 状态机改动牵 dispatcher 转移逻辑 + 所有现有 row 的兼容；需架构决策："新 state vs 合并到 VALIDATION_FAILED" | **S02 architect** |
| **O11** 缺的 5 类 adapter (YouTube transcript / GitHub / PDF / accepted-sprint / Solar artifact) | YouTube 现有路径需迁移（intake item 8）；accepted-sprint 和 Solar artifact 来源是 sprint-internal 文件，路径策略未定 | **S02 architect** 定 adapter strategy + **S03 builder** 实施 |

**O1/O2/O3/O4/O6/O7/O8/O12/O14** 可以直接派 builder（设计已稳，只是补 implementation 或测试）。

## 6. Risk Register (Epic-level)

| Risk | Level | Mitigation | Owner |
|---|---|---|---|
| 105859 deliverables 与 Epic 设计漂移（status=passed 但实际未全跑） | high | S05 必须 build-from-zero 跑端到端测试，不信任 status flag | **S05** |
| ThunderOMLX JSON 输出不稳 → backfill 大面积 quarantine | high | circuit breaker 已设；小样本验收 ≥ 90% 后再放量 | **S05** |
| 命名混乱（extracted.md vs semantic.md）导致 grep / 链接断 | med | S02 定名 + 提供 alias 兼容期 ≥ 1 sprint | **S02** |
| query grounding (O10) 不实现 → 用户得到无证据答案 | med | intake hard req #10，必须 S04 实现 + S05 验证 | **S04**, **S05** |
| 5 类缺失 adapter 数量被低估 | med | S02 architect 先 stub-out + count；不达 8 类 coverage 不允许 Epic close | **S02** |
| Epic close 时 105859 sprint 的 `parent-check` 未做 | low | S05 跑 epic decomposer `validate_epic`；任何 child 未 passed → epic 不 close | **S05** |

## 7. Cross-Epic / Cross-Sprint Dependencies

| 依赖 | 类型 | 当前状态 |
|---|---|---|
| `sprint-20260524-105859` (knowledge-ingest-dispatcher) | **upstream baseline**, deliverables 已落地 | passed/finalized — Epic 必须 reuse，不重造 |
| `sprint-20260524-134738` (Skill/MCP/Capsule architecture) | **adjacent**, 可能影响 adapter 注册方式 (skill-as-implementation) | passed/finalized — S02 architect 可参考但不强依赖 |
| `sprint-20260524-133807` (prerequisite schema) | **adjacent**, Epic 子 sprint 间 prerequisite 应使用新结构化 schema | active in builder — S02 写 task_graph 时用新 schema 表达 `{sprint_id, required_node_id, required_node_status}` |
| `sprint-20260523-agent-plan-optimizer-foundation` | **adjacent**, optimizer 可能选择 adapter / capsule 组合 | queued — 不强依赖 |

## 8. S01 Deliverables (本 sprint 真要产出的)

| File | 写者 | 内容 |
|---|---|---|
| `*.design.md` (this file) | planner (me) | 14 outcomes + 5 不能派 builder 的 + risk + cross-sprint 重叠分析 |
| `*.plan.md` | planner | DAG + acceptance per node |
| `*.task_graph.json` | planner | 4 节点（S1 planner / S2 builder writes outcome matrix / S3 verifier / S4 critic） |
| `*.planning.html` | planner | 可视化 |
| `*.outcomes_matrix.md` | **S2 builder of this sprint** | 把 §3 outcomes 表渲染到独立 file，供下游 sprint 直接读 |
| `*.traceability.json` | **S2 builder of this sprint** | machine-readable: outcome → epic_child_sprint → 现状 (`reuse-from-105859` / `extend` / `net-new`) |
| `*.handoff.md` | planner | 上游依赖 + 下游影响 + 未闭环项（PRD scope 要求） |

## 9. Constraints / Invariants

- **不写代码**。S2 builder 也只写 md/json。
- **不动 105859 已交付的 9 个 lib 文件 + sqlite**。
- 不动其他 Epic 子 sprint (S02-S05) 的 PRD/contract/status.json — Epic 调度器自动按 traceability 推进。
- Traceability JSON 必须遵循 epic.traceability.json 的 schema_version `solar.epic.traceability.v1`，可扩展 per-outcome 字段。

## 10. Stop Rules

- Outcome matrix 任一 outcome 缺 acceptance / risk / owner → S2 不算 done
- traceability.json 任一 outcome 缺 `current_state` (reuse/extend/net-new) → S2 不算 done
- handoff.md 不写 "上游依赖 + 下游影响 + 未闭环项" 三段 → S2 不算 done（PRD scope 强制）
- 任何对 105859 deliverables 的"等价于已完成"声明未附 grep / ls / sqlite 证据 → 视为乐观词，violates DoD #6（禁用乐观词）
- 缺 verifier 决策 → 不进 DONE
