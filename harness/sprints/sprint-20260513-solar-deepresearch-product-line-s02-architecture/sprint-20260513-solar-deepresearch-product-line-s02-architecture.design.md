# Design — Solar DeepResearch Product Line · S02 Architecture

Sprint: `sprint-20260513-solar-deepresearch-product-line-s02-architecture`
Epic: `epic-20260513-solar-deepresearch-product-line`
Slice: `architecture` (Planner pass)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

## 1. Problem Framing

S01 已经把"做什么"压成可验收 PRD + 矩阵 + DoD + Stop Rules。S02 必须把"怎么做"压成可被 S03 builder 直接落地的架构契约：模块分层、Schema 不变量、存储布局、标准 DAG 模板。

为什么单独切 S02：
- DeepResearch 涉及 **8 个数据模型** (SourceConnector / SourceHit / SourceDocument / EvidenceItem / Claim / ClaimEvidenceLink / CitationSpan / ReportAST) — 直接让 S03 builder 边写边设计 = 出现 schema 漂移、span_text 字段名不一致、claim_id 哈希算法不同。
- DAG 模板 R0-R11 必须能被 `graph_scheduler validate` 接受，否则 S04 接 capability plane 时全链路返工。
- 存储层 SQLite MVP vs JSONL artifact 的边界要先画清楚，避免出现 "evidence 既在 SQLite 又在 jsonl 还不一致" 的双写灾难。

本切片是**架构 spec only**：写 4 份规格文档，0 行可执行代码。

## 2. Design Goals

- **Schema 是法律**：8 个数据模型的字段名、类型、不变量、ID/hash 算法必须钉死，S03 builder 不能再讨论。
- **模块分层清晰**：`harness/lib/research/` 下的子模块边界明确，每个子模块写 / 读哪些 schema 由 architecture.md 单一来源。
- **SQLite/JSONL 分工**：SQLite = 索引 + 关系 + 状态；JSONL = 物料 + 增量 + 归档。两者职责互斥。
- **DAG 模板可验证**：`deepresearch.dag-template.json` 必须 `graph_scheduler validate` exit 0，且节点 R0-R11 的 write_scope 不冲突。
- **复用现有基础设施**：DAG scheduler / dispatch / evaluator / capability plane / Mirage / context inject — 全部复用，不重新发明。新增模块只在 `lib/research/` 下生长。

## 3. Non-Goals (本切片显式不做)

- **不写实现代码**：本切片 0 行 `.py`/`.sh`/`.ts`/`.js`。所有产物是 `.md` + `.json`。
- **不接活体 connector**：OpenAlex/Brave 等 connector schema 设计完即止，不实际发请求。
- **不冻结 LLM 选型**：每个 R 节点的 LLM 模型路由是 S03 builder 决定，本切片只规定接口（input/output schema）。
- **不写 SKILL.md**：DeepResearch agent skill 是 S04 的事。
- **不重写 task_graph schema**：复用 `~/.solar/harness/schemas/task-graph.schema.json`，本切片只产出 DAG 模板实例。
- **不替换 Mirage / context inject / evaluator**：现有基础设施完全复用。

## 4. Deliverables (4 份规格 + Planner 三件套)

| Deliverable | Owner | 内容 | 给谁用 |
|---|---|---|---|
| `deepresearch.architecture.md` | N1 builder | 模块分层 / CLI 边界 / capability plane 接入 / DAG/evaluator/Mirage 复用策略 / 失败恢复 + 观测 | S03 实现 + S04 集成 |
| `deepresearch.schemas.md` | N2 builder | 8 个数据模型字段 + 类型 + 不变量 + ID/hash 算法 + 兼容策略 | S03 schemas.py + S05 单测 |
| `deepresearch.storage.md` | N3 builder | SQLite MVP 7 张表 DDL + JSONL artifact 布局 + 索引策略 + hash/span verify 算法 + 向后兼容 | S03 storage.py + 迁移 |
| `deepresearch.dag-template.json` | N4 builder | R0-R11 标准 DAG，machine-readable，可被 graph_scheduler validate | S04 capability plane + research run |
| `…s02-architecture.handoff.md` | N5 builder | 4 份产物路径 + 给 S03/S04 的明确接口 + 已知 risk | S03/S04 启动 |
| `…s02-architecture.design.md` | Planner (本文) | 切片方法论 | self / evaluator |
| `…s02-architecture.plan.md` | Planner | 5-node DAG | 协调器 + builder |
| `…s02-architecture.task_graph.json` | Planner | machine-readable DAG | graph_scheduler |

## 5. DAG Topology

```text
N1 architecture-md         ──┐
N2 schemas-md              ──┤
N3 storage-md              ──┤
N4 dag-template-json       ──┴── N5 integration-and-handoff ── handoff
```

- **N1 / N2 / N3 / N4 完全并行** — write_scope 不重叠 (architecture.md / schemas.md / storage.md / dag-template.json)。
- **N5 join**: 仅当 N1+N2+N3+N4 全部 `passed` 后才能 ready。负责跨文件一致性校验、更新 epic traceability、写 handoff。
- 4-并 1-串结构，最大 builder 占用 = 4 个 pane。

## 6. Acceptance Contract

| # | Acceptance | 验证方式 |
|---|---|---|
| **A1** | 4 份规格文件存在且非空 | `ls -la sprints/*architecture.md sprints/*schemas.md sprints/*storage.md sprints/*dag-template.json`; 每文件 ≥ 100 行（dag-template 除外，按 JSON 大小） |
| **A2** | architecture.md 覆盖 control plane + data plane + 状态 + 失败恢复 + 观测 5 大维度 | grep 命中 `control plane`, `data plane`, `state`, `failure`, `observability` 各 ≥ 1 |
| **A3** | schemas.md 含 8 个数据模型全字段定义 | grep 命中 `SourceConnector`, `SourceHit`, `SourceDocument`, `EvidenceItem`, `Claim`, `ClaimEvidenceLink`, `CitationSpan`, `ReportAST`；每个含 `字段`/`fields` 子节 |
| **A4** | storage.md 含 7 张 SQLite 表 DDL + JSONL artifact 列表 | grep `CREATE TABLE` ≥ 7; grep `.jsonl` ≥ 5 |
| **A5** | dag-template.json 通过 graph_scheduler validate | `solar-harness graph-scheduler validate --graph sprints/*dag-template.json` exit 0 |
| **A6** | dag-template.json 含 R0-R11 全部 12 节点 | jq 验证 `[.nodes[].id]` 包含 R0_scope_rewrite..R11_final_export |
| **A7** | 接口边界 + 旧系统兼容方式 写入 architecture.md | grep `Backward Compatibility` 或 `兼容` 命中 |
| **A8** | epic traceability.json children[1] (S02_architecture) 状态 → passed + artifact_links 4 条 | `jq '.children[1]'` |
| **A9** | task_graph.json (本 sprint 自己的) 通过 graph_scheduler validate | exit 0 |

A8 是 cross-sprint side-effect (写父 epic 文件)，由 N5 集中处理。

## 7. Stop Rules (本切片自身)

- **不写代码**：本 sprint 任何 builder pane 创建 `.py`/`.sh`/`.ts` = 立即 fail，回滚到 planner。
- **不接活体 API**：architecture.md 出现 "已申请 OpenAlex key" 或 "已部署 Brave proxy" → fail，本切片只设计 schema 不接入。
- **不冻结实现细节**：dag-template.json 节点不允许出现 "preferred_model": "claude-sonnet-X.Y" 这类具体版本号，应该是 "auto" 或角色名（"writer"/"evaluator"）。
- **不绕过 N5 join**：N5 在 N1-N4 任一 pending 时 dispatched → graph_scheduler 阻断。
- **不修改 epic.md 或 PRD**：本切片只能写 traceability.json 的 status / artifact_links。
- **不声明 epic 已完成**：任何 deliverable 不允许写「DeepResearch 产品线已 ready」。
- **Schema 不变量不允许互相冲突**：N2 (schemas.md) 必须显式列每个模型的 invariant 集合，且不允许 `EvidenceItem.span_text` 在某处定义为 nullable 而在另一处定义为 required。

## 8. Parallelism & Write Scope

- N1 write_scope = `sprints/*deepresearch.architecture.md`
- N2 write_scope = `sprints/*deepresearch.schemas.md`
- N3 write_scope = `sprints/*deepresearch.storage.md`
- N4 write_scope = `sprints/*deepresearch.dag-template.json`
- N5 write_scope = `sprints/*s02-architecture.handoff.md`, `sprints/epic-*.traceability.json`

4 个上游节点 write_scope 完全互斥 → 可并发 dispatch。N5 read 上游 4 份 + epic 文件，write 集中在 handoff + traceability。

## 9. Model Routing

- **N1 (architecture.md)**: `sonnet` — 系统设计，分层判断，需要叙事 + 决策权衡，GLM 1210 风险高。
- **N2 (schemas.md)**: `sonnet` — schema 严谨性 + 不变量推理，必须 Sonnet。
- **N3 (storage.md)**: `sonnet` — SQL DDL + hash/span 算法描述，Sonnet 稳定。
- **N4 (dag-template.json)**: `sonnet` — 12 节点 JSON，必须通过 graph_scheduler validate，schema 严苛。
- **N5 (integration)**: `sonnet` — 跨文件一致性检查 + handoff 撰写。

全 Sonnet 路由原因：本切片是产品线架构地基，错一个 schema 字段会扩散到 S03/S04/S05 全链路。

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------|
| Builder 把 4 份 deliverable 合成一份巨型文档（违反 write_scope 分离） | task_graph 显式 4 个独立 write_scope；evaluator 用 `ls -la` 单独验证 |
| schemas.md 8 个模型字段互相不一致（e.g., span_text 在 EvidenceItem 必填，在 CitationSpan 选填） | N2 acceptance 要求显式 `Invariants` 子节；N5 跨文件 grep 字段定义冲突 |
| dag-template.json 节点 write_scope 冲突（R7 section_writing_batch 内部并行节点写同一文件） | A5 + A6 联合，graph_scheduler validate 会捕获 write_scope 冲突 |
| Builder 在 architecture.md 中写出 "必须用 SQLite 3.45.1" 这类硬版本 | Stop Rule §7 + evaluator grep 检查 |
| N5 在上游 pending 时被误 dispatch | graph_scheduler validate + `depends_on` 硬约束 |
| Epic traceability.json 被多 pane 同时改 | N5 是唯一 N writer；S02 完成后整个 sprint 关闭 |
| 兼容策略缺失 (旧 sprint 没有 evidence.jsonl) | A7 显式要求 "Backward Compatibility" 章节；提供 "feature_flag: research.evidence_ledger" 默认 off |
| 8 个模型字段太多，builder 漏 1 个 | A3 grep 检查 8 个模型名全部出现 |

## 11. Knowledge Context Usage

- `solar-harness context inject` 已执行（命中 5 条 Solar 架构方法论 / 知识图谱方法论 / 本体设计 / BIOS 宣告机制，作为分层判断参考；mirage_path: no_results — 这是新产品线无 prior art）。
- 复用 Solar 既有 architecture 论文格式（如 `solar-membrain-memory-ab-comparison.md`、`solar-ontology-identity-model.md`）— 含"核心洞察 / 决策 / 验证 / 风险"四段结构。
- DeepResearch 的 8 个 schema 没有 prior art；S03 builder 是唯一参考来源 = 本切片 N2 输出。

## 12. Handoff Plan

N5 完成后，handoff 必须包含：

- 4 份 deliverable 完整路径
- 给 S03 builder 的"必须先读的 3 个章节"清单 (architecture §模块分层 / schemas §不变量 / storage §SQLite DDL)
- 给 S04 capability plane 集成的"必须注册的 capability"清单 (research.source/evidence/claim/citation/report/eval 6 类)
- 给 S05 evaluator 的"factuality eval metric 计算公式参考"
- 已知未闭环项 + risk 转交
- `evaluator_can_review: true` 标记
- `s03_can_start: true` / `s04_can_start: true` 双信号（S03 和 S04 都依赖 S02，passed 后可并行启动）

S02 通过 = DeepResearch 架构地基定型，S03 (core-runtime) 和 S04 (orchestration-ui) 可并行启动。
