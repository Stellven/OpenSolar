# Plan — Solar DeepResearch Product Line · S02 Architecture

Sprint: `sprint-20260513-solar-deepresearch-product-line-s02-architecture`
Slice: architecture (spec-only, no code)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

> 配套读 design.md (方法论 + 边界) 和 contract.md (Acceptance + Stop Rules)。

## 1. DAG

```text
N1 architecture-md         ─┐
N2 schemas-md              ─┤
N3 storage-md              ─┤
N4 dag-template-json       ─┴── N5 integration-and-handoff ── handoff
```

5 节点，4 并行上游 + 1 join。Cost = M+M+M+M+S = 约 9 单位 builder time。

## 2. Node-by-Node Execution

| Node | Goal | Depends | Preferred Model | Cost | Gate |
|------|------|---------|-----------------|------|------|
| **N1** | 写 `deepresearch.architecture.md`：模块分层 + CLI 边界 + capability plane + 现有基础设施复用 + 失败恢复 + 观测 | — | sonnet | 2.5 | architecture-pass |
| **N2** | 写 `deepresearch.schemas.md`：8 个数据模型字段 + 类型 + 不变量 + ID/hash 算法 | — | sonnet | 2.5 | schemas-pass |
| **N3** | 写 `deepresearch.storage.md`：SQLite 7 张表 DDL + JSONL artifact 布局 + hash/span verify + 向后兼容 | — | sonnet | 2.0 | storage-pass |
| **N4** | 写 `deepresearch.dag-template.json`：R0-R11 标准 DAG，通过 graph_scheduler validate | — | sonnet | 1.5 | dag-template-pass |
| **N5** | 跨文件一致性校验 + 更新 epic traceability + 写 handoff (s03/s04 双信号) | N1, N2, N3, N4 | sonnet | 1.0 | integration-pass |

Total estimated cost: 9.5 units。

## 3. Parallelism

- **N1 ∥ N2 ∥ N3 ∥ N4** 完全并行：write_scope 互不重叠 (architecture / schemas / storage / dag-template)。
- **N5 join**：仅当 N1+N2+N3+N4 全部 `passed` 才能 ready。任一上游 `pending/reviewing/failed` → N5 holds。
- DAG 单 join 单尾，最大 builder 占用 = 4 个 pane。

## 4. Dispatch Batches

- **batch-1**: `[N1, N2, N3, N4]`，join_gate=`[architecture-pass, schemas-pass, storage-pass, dag-template-pass]`
- **batch-2**: `[N5]`，join_gate=`[integration-pass]`

`graph_scheduler` 在 batch-1 全 passed 后自动扩展 batch-2。

## 5. Per-Node Acceptance（builder/evaluator 共用）

### N1 deepresearch.architecture.md
- 文件 ≥ 200 行
- 必含章节：模块分层 / CLI 边界 / capability plane 接入 / DAG 复用 / Mirage 复用 / context inject 复用 / 失败恢复 / 观测 / 向后兼容
- 含 ASCII 模块依赖图 (`harness/lib/research/` 子模块互相 import 关系)
- 列出 6 类 research.* capability 名 + 责任模块映射
- 不出现 "必须用 SQLite 3.45.1" / "必须用 Brave key xxx" 这类硬实施
- 显式声明：复用现有 DAG scheduler、evaluator、Mirage、context inject；新增模块只在 `lib/research/` 下

### N2 deepresearch.schemas.md
- 文件 ≥ 200 行
- 必含 8 个数据模型独立小节：`SourceConnector`, `SourceHit`, `SourceDocument`, `EvidenceItem`, `Claim`, `ClaimEvidenceLink`, `CitationSpan`, `ReportAST`
- 每个模型含：字段表（字段名 / 类型 / nullable / 默认 / 说明）+ Invariants 列表 + ID/hash 算法
- 关键不变量必须显式：
  - `EvidenceItem` 必有 `source_id`, `content_hash`, `span_start`, `span_end`, `span_text`
  - `Claim` 必有 `text` 且 key claim 必有至少 1 个 `ClaimEvidenceLink`
  - `CitationSpan.span_text` 必须等于源文档对应 byte 范围
- ID 生成算法明确：sha256(canonical_json_normalized) 或 sha256(source_id + span_start + span_end)
- Schema 演进策略：版本字段 + 向后兼容规则

### N3 deepresearch.storage.md
- 文件 ≥ 150 行
- 必含 7 张表 SQL DDL: `research_runs`, `research_sources`, `evidence_items`, `claims`, `claim_evidence`, `report_sections`, `section_checks`
- 每张表含：PRIMARY KEY / FOREIGN KEY / INDEX / UNIQUE 约束
- JSONL artifact 布局列表 ≥ 5: `sources.jsonl`, `evidence.jsonl`, `claims.jsonl`, `contradictions.jsonl`, `final.bibliography.json`
- hash/span verify 算法描述（伪代码即可）
- 向后兼容策略：feature_flag `research.evidence_ledger` 默认 off；旧 sprint 不受影响
- SQLite vs JSONL 分工原则：SQLite = 索引+关系+状态；JSONL = 物料+增量+归档

### N4 deepresearch.dag-template.json
- `solar-harness graph-scheduler validate --graph <file>` exit 0
- 含 12 节点：R0_scope_rewrite, R1_source_matrix, R2_external_search, R3_fetch_extract, R4_claim_mining, R5_contradiction_hunt, R6_report_ast, R7_section_writing_batch, R8_section_fact_check, R9_chapter_compile, R10_global_consistency, R11_final_export
- 每个节点含：id / goal / depends_on / write_scope / read_scope / required_capabilities / gate / acceptance / estimated_cost
- `preferred_model` 使用角色名 ("writer"/"evaluator"/"miner") 或 "auto"，不绑死具体型号
- depends_on 拓扑：R0 → R1 → R2/R3 → R4/R5 → R6 → R7 → R8 → R9 → R10 → R11
- R7 (section writing) 支持子任务并行（write_scope 用 section_id 占位符）
- 含 `no_code_policy` 或等效字段说明该模板的使用边界

### N5 integration-and-handoff
- 读取 N1+N2+N3+N4 四份产物，校验：
  - architecture.md 中提到的 schema 类型 ⊆ schemas.md 列出的 8 个
  - storage.md 中表名 ⊆ architecture.md 提到的 SQLite 表
  - dag-template.json 中节点 capability ⊆ architecture.md 列出的 6 类 research.* capability
- 更新 `epic-20260513-solar-deepresearch-product-line.traceability.json`：
  - `children[1].status` → `"passed"` 或 `"completed"`
  - 新增 `children[1].artifact_links: [4 个 deliverable 路径]`
  - 新增 `children[1].handoff_at` 时间戳
- 写 `…s02-architecture.handoff.md`：
  - 4 份产物路径
  - 给 S03 builder 的 "必读 3 节" 清单
  - 给 S04 集成的 "必须注册 capability" 清单
  - 给 S05 evaluator 的 "factuality metric 公式" 引用
  - 已知未闭环项
  - `evaluator_can_review: true`
  - `s03_can_start: true` 和 `s04_can_start: true`（S02 passed 后两个子 sprint 可并行启动）

## 6. Routing Policy

- 所有节点用 `sonnet`（design.md §9 已论证）。
- GLM-5.1 1210 风险 → 不用（MEMORY 已记录 5 次）。
- 不允许 worker 在节点内调用 webfetch / web search — 本切片所有内容来源 = epic.md + PRD + Solar 现有架构。
- 不允许调用其他 sub-sprint 的 builder（本切片孤立）。

## 7. Stop Rules (执行期)

- Builder 创建 `.py` / `.sh` / `.ts` / `.js` → 立即 fail，evaluator 必须 reject。
- Deliverable 中出现 "已申请 OpenAlex key" / "已部署 Brave proxy" / "已写 schemas.py" → fail（这是 S03 的事）。
- dag-template.json 节点 preferred_model 写具体版本号 (e.g., "claude-sonnet-4.6") → fail，应该是 "auto" 或角色名。
- N5 在上游 `pending` 时被误 dispatch → graph_scheduler validate 阻断。
- 任一 deliverable 声称 "DeepResearch 产品线已完成" → fail。本切片只完成 epic 的 S02 节点。
- Schema 字段在多份文档中定义冲突 → N5 必须发现并 fail。

## 8. Exit Criteria

- 4 份规格文件全部存在且非空
- task_graph 5 个 gates 全 passed: `architecture-pass, schemas-pass, storage-pass, dag-template-pass, integration-pass`
- epic traceability.json 的 S02 节点 status=passed/completed
- handoff.md `evaluator_can_review: true` + `s03_can_start: true` + `s04_can_start: true`

## 9. Evaluator 复核入口（建议）

1. `ls -la sprints/*architecture.md sprints/*schemas.md sprints/*storage.md sprints/*dag-template.json` 验存在
2. `wc -l sprints/*architecture.md` ≥ 200; `wc -l sprints/*schemas.md` ≥ 200; `wc -l sprints/*storage.md` ≥ 150
3. `solar-harness graph-scheduler validate --graph sprints/*dag-template.json` exit 0
4. `jq '[.nodes[].id]' sprints/*dag-template.json` 含 R0-R11 全 12 节点
5. `grep -c 'SourceConnector\|SourceHit\|SourceDocument\|EvidenceItem\|Claim\|ClaimEvidenceLink\|CitationSpan\|ReportAST' sprints/*schemas.md` ≥ 8
6. `grep -c 'CREATE TABLE' sprints/*storage.md` ≥ 7
7. `grep -E '兼容|Backward' sprints/*architecture.md` ≥ 1
8. `jq '.children[1].status' epic-*.traceability.json` == `"passed"`
9. `grep 's03_can_start: true' …s02-architecture.handoff.md`

## 10. Out of Scope (留给下游 sprint)

- **S03 (core-runtime)**: `harness/lib/research/` 全部 Python 实现 + 测试 — 基于本切片 schemas.md + storage.md
- **S04 (orchestration-ui)**: `solar-harness research *` CLI 子命令、capability plane 注册、status UI — 基于本切片 architecture.md + dag-template.json
- **S05 (verification-release)**: fixture → final.md 端到端、活体 connector 接入、Knowledge/_raw 归档

本切片只交付**架构规格**，所有实现由 S03/S04/S05 完成。
