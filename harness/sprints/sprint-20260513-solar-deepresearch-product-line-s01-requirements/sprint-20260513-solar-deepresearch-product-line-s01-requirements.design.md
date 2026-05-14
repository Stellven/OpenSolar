# Design — Solar DeepResearch Product Line · S01 Requirements

Sprint: `sprint-20260513-solar-deepresearch-product-line-s01-requirements`
Epic: `epic-20260513-solar-deepresearch-product-line`
Slice: `requirements` (Planner pass)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

## 1. Problem Framing

Epic 是把 Solar-Harness 从「AI-native 研发控制面」升级为「AI-native 研究生产操作系统」。本切片（S01）是**只产规格、不产代码**的需求拆解切片，目的：

- 把用户原始大需求（5934 字 PRD）压成可验收 outcomes、能力边界、显式非目标。
- 输出 **4 份规格文档** + 1 份能力 → 子 sprint 映射矩阵，给 S02 (架构)/S03 (核心 runtime)/S04 (编排 UI)/S05 (验证发布) 当唯一来源。
- 不直接派 builder 写实现代码；本切片所有 deliverables 都是 `.md` / `.json` 规格文件。

为什么单独切一个 requirements sprint：

- 用户原始 PRD 把"产品价值/数据模型/CLI/DAG 节点/Stop Rules/Phase 路线图"全部塞在一份文档里。直接送 builder 会出现 scope 蔓延（10w 字报告编译 vs evidence ledger MVP 谁先做）。
- 我们已经踩过 Control Plane v2 sprint 的坑：S1-S3 PASS 但 S4-S8 没交付，round 3/3 用尽。Requirements 切片就是把"S4-S8 没人收口"的问题消灭在地基阶段。
- 父 epic 已经把 5 个子 sprint 排好顺序，S01 是唯一无依赖节点，是必须先解的契约。

## 2. Design Goals

- **规格而非实现**：本切片不允许写 Python/Shell 代码；所有产物必须是可被下游 sprint 引用的 `.md` / `.json` 文件。
- **能 graph_scheduler validate**：task_graph.json 必须通过 `solar-harness graph-scheduler validate`，否则不准进入 builder 派发。
- **每个核心缺口都有显式 owner**：Source Mesh / Evidence Ledger / Claim Ledger / ReportAST / Factuality Evaluator / Long Report Compiler — 每个都映射到具体 S02/S03/S04/S05 子 sprint + 责任能力 + 验收 gate。
- **Stop Rules 是一等公民**：用户原始 PRD 列了 5 条硬禁止；本切片必须独立成文，便于下游 evaluator 直接引用。
- **DoD 与 CLI 存在性脱钩**：用户已经提示「不能只证 CLI 存在」。DoD 必须用 evidence/claim/citation/report 4 类 gate 替代「命令能跑」式 DoD。

## 3. Non-Goals (本切片显式不做)

- **不写代码**：不创建 `harness/lib/research/*.py`、不写测试、不动 `solar-harness.sh`。
- **不冻结架构选型**：SQLite vs DuckDB、JSONL vs Parquet、connector 顺序等是 S02 的事。本切片只列「需要哪些能力」。
- **不展开 100k 字报告章节模板**：本切片只确认「10w 字报告不能 1-prompt 出」，具体 30-40 section spec 是 S04/S05 的事。
- **不实际接 Source Mesh API**：不申请 OpenAlex/Brave/Tavily key，不写 connector skeleton；只列「应当具备」清单。
- **不评估 LangGraph/CrewAI 替代方案**：epic 已经决定不引入外部框架；本切片不重复论证。
- **不直接派 builder 写 Python**：builder 在本切片只写 Markdown / JSON 规格。

## 4. Deliverables (4 份规格 + 1 份矩阵 + 标准 Planner 三件套)

| Deliverable | Owner | 内容 | 给谁用 |
|---|---|---|---|
| `deepresearch.prd.md` | N1 builder | 用户价值 + 目标报告类型 + 目标字数 + 研究深度档位 + 输出格式 + 失败边界 | S02 架构师，作为 architecture spec 输入 |
| `deepresearch.requirements_matrix.json` | N2 builder | 5 缺口 × Phase 1-5 × 子 sprint × 能力 × 验收 gate 的多维矩阵 | 调度器和 capability plane，识别哪些子 sprint 必须先于哪些 |
| `deepresearch.dod.md` | N3 builder | 5 类 DoD：evidence/claim/citation/report/eval gate，每条都有可验证 metric，禁止「CLI 存在 = 完成」 | S02-S05 evaluator，作为验收 checklist |
| `deepresearch.stop_rules.md` | N3 builder | 5 条硬停止（单 prompt 长报告 / unsupported claim / parent 提前 passed / connector 静默降级 / 10w 字单节点）+ 每条触发后该回滚到哪一节点 | 所有下游 evaluator，作为 fail-fast 引用 |
| `…s01-requirements.design.md` | Planner (本文) | 本切片方法论 | self / evaluator |
| `…s01-requirements.plan.md` | Planner | 4-node DAG 描述 | 协调器 + builder |
| `…s01-requirements.task_graph.json` | Planner | machine-readable DAG | graph_scheduler |

## 5. DAG Topology

```text
N1 deepresearch-prd          ──┐
N2 requirements-matrix       ──┤
N3 dod-and-stop-rules        ──┤
                                  └── N4 traceability-integration  ── handoff
```

- **N1 / N2 / N3 完全并行** — write_scope 不重叠（PRD vs matrix vs dod+stop-rules）。
- **N4 join**: 只能在 N1+N2+N3 全部 `passed` 后启动。它读 3 份 deliverable，校验互相引用一致性，更新 epic traceability map，写最终 handoff。
- N4 不允许在 N1-N3 任一 pending 时跑 — 这是显式 join gate，由 task_graph.json 的 `depends_on` 强制。

## 6. Acceptance Contract (4 个 acceptance，对齐 contract）

| # | Acceptance | 验证方式 |
|---|---|---|
| **A1** | 4 份规格文件存在且非空 | `ls -la sprints/*deepresearch.{prd,dod,stop_rules}.md` + `requirements_matrix.json`；`wc -l` ≥ 50 行 |
| **A2** | requirements matrix 把 5 大缺口完整映射到 S02-S05 子 sprint + capability + gate | `python3 -c "json.load(...)"` 解析 matrix.json；断言键集 ⊇ {source_mesh, evidence_ledger, claim_ledger, report_ast, factuality_evaluator, long_report_compiler}；每条都有 `child_sprint`, `capabilities`, `gate` |
| **A3** | DoD 包含 evidence/claim/citation/report/eval 5 类 gate，禁止「CLI exists ⇒ done」 | grep `unsupported_claim_rate`、`citation_span_accuracy`、`evidence_id` 在 dod.md 中均命中；grep `cli exists`/`命令存在` 应只出现在「禁止」上下文 |
| **A4** | Stop Rules 5 条 + 每条回滚路径 | grep 5 条用户原始 stop rules 在 stop_rules.md 中都命中；每条后跟「→ rollback to」字样 |
| **A5** | Epic traceability.json 被更新，S01 → completed | `jq '.children[0].status' epic-*.traceability.json` == `"completed"` 或 `"passed"`；并新增 `artifact_links` 字段引用 4 份规格文件 |
| **A6** | task_graph.json 通过 `graph-scheduler validate` | exit 0 |

A5 是 cross-sprint side-effect（写 parent epic 文件），属于本切片合约里允许的 write_scope (`harness/sprints/*deepresearch*.json`)。

## 7. Stop Rules (本切片自身)

- **不写代码**：本 sprint 任何 builder pane 创建 `.py`/`.sh`/`.ts` 文件 = 立即 fail，回滚到 planner。
- **不冻结架构选型**：deliverable 中出现 "must use SQLite" / "must use OpenAlex API key xxx" 这类硬决定 → fail，回滚到 N1。
- **不绕过 N4 join**：N4 在 N1+N2+N3 全部 `passed` 前 dispatched → graph_scheduler 阻断。
- **不修改 epic.md**：epic 是用户输入，本切片只能写 traceability.json 的 status / artifact_links，不允许改 epic.md 内容。
- **不声明 epic-level passed**：任何 deliverable 不允许写「整个 DeepResearch 产品线已完成」。

## 8. Parallelism & Write Scope

- N1 write_scope = `sprints/*deepresearch.prd.md`
- N2 write_scope = `sprints/*deepresearch.requirements_matrix.json`
- N3 write_scope = `sprints/*deepresearch.dod.md`, `sprints/*deepresearch.stop_rules.md` (两个文件主题相邻，给同一 builder 保持一致性更高)
- N4 write_scope = `sprint-…s01-requirements.handoff.md`, `epic-…traceability.json` (cross-file 更新)

三个上游节点 write_scope 完全互斥 → 可并发 dispatch。N4 read_scope 包含上游 3 份 + epic 文件，write 集中在 handoff + traceability。

## 9. Model Routing

- **N1 (PRD)**: `sonnet`（默认） — 需要叙事 + 产品判断，Sonnet 在结构化 PRD 上稳定。
- **N2 (matrix JSON)**: `sonnet` — 多维 JSON，需 schema 严谨，避免 GLM 1210 风险（已踩 4 次）。
- **N3 (DoD + stop rules)**: `sonnet` — 规范性强、对齐 epic stop rules，避免幻觉。
- **N4 (integration + handoff)**: `sonnet` — 跨文件一致性 check + 写 handoff，对推理质量敏感。

全 Sonnet 路由原因：本切片是规格文档，质量比成本敏感；GLM-5.1 在中文长上下文规格上有 1210 风险（MEMORY 中已记录 4 次踩坑）。

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------|
| Builder 把 4 个 deliverable 合成一份大文件（违反 write_scope 分离） | task_graph.json 显式列每个 node 的 write_scope；evaluator 用 `ls -la` 逐个文件验证 |
| matrix.json 缺漏 5 大缺口中的某一个 | A2 acceptance 硬编码键集断言 |
| Builder 在 PRD 里写出"必须用 OpenAlex API key" 这类实施细节 | A3 + Stop Rule §7 显式禁止；evaluator grep 检查 |
| N4 在上游 pending 时被误 dispatch | graph_scheduler validate + `depends_on` 强约束 |
| Epic traceability.json 被多 pane 同时改 | N4 是唯一 N writer；S01 完成后整个 sprint 关闭，不会有第二个 writer |
| Stop Rules 5 条用户原文遗漏 | A4 grep 每条原文关键字 |

## 11. Knowledge Context Usage

- `solar-harness context inject` 已执行（命中：3 条历史 accepted sprint，mirage degraded `mirage_path:no_results`）。
- DeepResearch 是新产品线，无可复用 prior art；命中价值在于「确认无历史冲突 sprint」。
- KB 命中不直接决定规格内容；规格唯一来源是 epic.md + PRD（用户已提交完整 5934 字 PRD）。

## 12. Handoff Plan

N4 完成后，handoff 必须包含：

- 4 份 deliverable 的完整路径
- requirements matrix 把 5 缺口映射到 S02-S05 的结果表（直接 paste 矩阵 head）
- `evaluator_can_review: true` 显式标记
- 给 S02 architect 的 3 条「必须解的关键架构问题」 dry-run hint（不含选型，只列问题域）
- 给 S05 evaluator 的「factuality eval metric 基线门槛」初稿
