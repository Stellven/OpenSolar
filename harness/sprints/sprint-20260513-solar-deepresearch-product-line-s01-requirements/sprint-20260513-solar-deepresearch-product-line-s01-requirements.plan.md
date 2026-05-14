# Plan — Solar DeepResearch Product Line · S01 Requirements

Sprint: `sprint-20260513-solar-deepresearch-product-line-s01-requirements`
Slice: requirements (spec-only, no code)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

> 配套读 design.md (方法论 + 边界) 和 contract.md (Acceptance + Stop Rules)。

## 1. DAG

```text
N1 deepresearch-prd          ─┐
N2 requirements-matrix       ─┤
N3 dod-and-stop-rules        ─┴── N4 traceability-integration ── handoff
```

4 节点，3 并行上游 + 1 join。Cost = M+S+M+S = 约 6 单位 builder time。

## 2. Node-by-Node Execution

| Node | Goal | Depends | Preferred Model | Cost | Gate |
|------|------|---------|-----------------|------|------|
| **N1** | 写 `deepresearch.prd.md`：产品 PRD（价值/报告类型/字数/深度/输出/失败边界） | — | sonnet | 2.0 | prd-pass |
| **N2** | 写 `deepresearch.requirements_matrix.json`：5 缺口 × Phase × 子 sprint × 能力 × gate 矩阵 | — | sonnet | 2.0 | matrix-pass |
| **N3** | 写 `deepresearch.dod.md` + `deepresearch.stop_rules.md`：DoD + 5 条硬停止 | — | sonnet | 1.5 | gates-pass |
| **N4** | 跨文件一致性校验 + 更新 epic traceability + 写 handoff | N1, N2, N3 | sonnet | 1.0 | integration-pass |

Total estimated cost: 6.5 units。

## 3. Parallelism

- **N1 ∥ N2 ∥ N3** 完全并行：write_scope 互不重叠（prd.md vs requirements_matrix.json vs dod.md+stop_rules.md）。
- **N4 join**：仅当 N1+N2+N3 全部 `passed` 才能 ready。任一上游 `pending/reviewing/failed` → N4 holds。
- DAG 单 join 单尾，最大 builder 占用 = 3 个 pane（一个 builder 跑 3 节点 / 三个 builder 各跑一节点都可，由 coordinator decide）。

## 4. Dispatch Batches

- **batch-1**: `[N1, N2, N3]`，join_gate=`[prd-pass, matrix-pass, gates-pass]`
- **batch-2**: `[N4]`，join_gate=`[integration-pass]`

`graph_scheduler` 应在 batch-1 全 passed 后自动扩展 batch-2；若 patrol 兜底也可，但 planner 不依赖 patrol。

## 5. Per-Node Acceptance（builder/evaluator 共用）

### N1 deepresearch-prd
- `sprints/sprint-20260513-solar-deepresearch-product-line-s01-requirements.deepresearch.prd.md` 存在，≥ 200 行
- 必含 7 节：用户价值 / 目标报告类型 / 目标字数档位 / 研究深度档位 / 输出格式 / 失败边界 / 与 epic 关系
- 显式声明「单 prompt 长报告 = 禁止」、「unsupported claim = 禁止」、「connector 静默降级 = 禁止」
- 不出现 `必须用 SQLite/OpenAlex/Brave/Tavily/<具体技术>`（架构选型留给 S02）

### N2 requirements-matrix
- `…s01-requirements.deepresearch.requirements_matrix.json` 合法 JSON
- 顶层键集 ⊇ `{schema_version, generated_at, capability_gaps, phase_mapping, sprint_mapping}`
- `capability_gaps` 至少含 6 条：`source_mesh, evidence_ledger, claim_ledger, report_ast, factuality_evaluator, long_report_compiler`
- `sprint_mapping`: 每个 S02-S05 子 sprint 都列其负责的 gap 子集 + capability + acceptance gate
- 通过 `python3 -c "import json; json.load(open(...))"` 不报错

### N3 dod-and-stop-rules
- `…s01-requirements.deepresearch.dod.md`: ≥ 100 行，5 类 DoD（evidence / claim / citation / report / eval），每类至少 3 条可验证 metric
- 必含 `unsupported_claim_rate`、`citation_span_accuracy` 关键字（grep 命中）
- `…s01-requirements.deepresearch.stop_rules.md`: 5 条用户原始 stop rules 全覆盖
- 每条 stop rule 后写「→ rollback to <node>」格式的回滚路径

### N4 traceability-integration
- 读取 N1+N2+N3 三个 deliverable，校验：PRD 失败边界 ⊆ stop_rules；matrix 中 gap 列表 ⊆ DoD 5 类
- 更新 `epic-20260513-solar-deepresearch-product-line.traceability.json`：
  - `children[0].status` → `"passed"` 或 `"completed"`
  - 新增 `children[0].artifact_links: [4 个 deliverable 路径]`
  - 新增 `children[0].handoff_at` 时间戳
- 写 `…s01-requirements.handoff.md`：4 份产物路径 + matrix head 表 + `evaluator_can_review: true`

## 6. Routing Policy

- 所有节点用 `sonnet`（design.md §9 已论证）。
- 单一 GLM-5.1 1210 风险 → 不用。
- 不允许 worker 在节点内调用 webfetch / web search — 本切片不接外部 source。所有内容唯一来源 = epic.md + 原始 PRD。

## 7. Stop Rules (执行期)

- Builder 在任一节点尝试创建 `.py` / `.sh` / `.ts` / `.js` → 立刻 fail，evaluator 必须 reject。
- Deliverable 中出现具体技术选型（"必须用 SQLite vN.M"、"用 Tavily key"） → fail，回滚到对应 N1/N2/N3。
- N4 在上游 `pending` 时被误 dispatch → graph_scheduler validate 阻断（`depends_on` 硬约束）。
- 任一 deliverable 声称「epic 已完成」 → fail。本切片只完成 epic 的 S01 节点。

## 8. Exit Criteria

- 4 份规格文件全部存在且非空
- task_graph 5 个 gates 全 passed: `prd-pass, matrix-pass, gates-pass, integration-pass, sprint-passed`
- epic traceability.json 的 S01 节点 status=passed/completed
- handoff.md `evaluator_can_review: true`

## 9. Evaluator 复核入口（建议）

1. `ls -la sprints/sprint-20260513-solar-deepresearch-product-line-s01-requirements.deepresearch.{prd,dod,stop_rules}.md sprints/*matrix.json` 验存在
2. `python3 -c "import json; d=json.load(open('...matrix.json')); assert {'source_mesh','evidence_ledger','claim_ledger','report_ast','factuality_evaluator','long_report_compiler'} <= set(d['capability_gaps']), d['capability_gaps']"`
3. `grep -E '(unsupported_claim_rate|citation_span_accuracy|evidence_id)' dod.md` ≥ 3 命中
4. `grep '→ rollback to' stop_rules.md` ≥ 5 命中
5. `jq '.children[0].status' epic-*.traceability.json` == `"passed"` 或 `"completed"`
6. handoff 包含 5 大缺口 → S02-S05 映射表

## 10. Out of Scope (留给下游 sprint)

- **S02 (architecture)**: SourceConnector schema / Evidence Ledger 表结构 / SQLite vs DuckDB / DAG template JSON Schema
- **S03 (core-runtime)**: `harness/lib/research/` 全部 Python 实现 + 测试
- **S04 (orchestration-ui)**: `solar-harness research *` CLI 子命令、capability plane 注册、status UI 接入
- **S05 (verification-release)**: fixture → final.md 端到端、活体 connector 接入、Knowledge/_raw 归档

本切片只交付**规格**，所有实现产物由下游 sprint 独立完成。
