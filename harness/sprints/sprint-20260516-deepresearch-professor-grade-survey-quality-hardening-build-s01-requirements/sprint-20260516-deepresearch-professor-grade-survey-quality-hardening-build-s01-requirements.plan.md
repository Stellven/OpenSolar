# Plan — DeepResearch Professor-Grade Survey Quality Hardening · S01 Requirements

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s01-requirements`
Epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Slice: `requirements`
Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-contracts

## 1. DAG (3 nodes, 2 layers)

```text
N1 outcomes ──┐
              ├── N3 traceability + handoff
N2 boundary ──┘
```

Layers: `[[N1, N2], [N3]]` — N1 ∥ N2 (write_scope 互斥), N3 join.

## 2. Node-by-Node Execution

| Node | Goal | Write Scope | Depends | Gate |
|------|------|-------------|---------|------|
| N1 | 写 outcomes.md：5 outcome (O1-O5) × 6 字段 | `sprints/…s01-requirements.outcomes.md` | — | G1 |
| N2 | 写 non-builder-boundary.md：治理边界 + 非目标 + 不动接口清单 + 非 builder 决策项 | `sprints/…s01-requirements.non-builder-boundary.md` | — | G2 |
| N3 | join：写 handoff.md + parent traceability patch (`children[0].outcomes_ready=true`) | `sprints/…s01-requirements.handoff.md`, `sprints/epic-…traceability.json` | N1, N2 | G3 |

## 3. Parallelism

- N1 ∥ N2：write_scope 完全互斥（两个独立 .md 文件），可同批派发
- N3 join：必须等 N1 + N2 全部 passed 后才能开始（包含两份证据的 cross-check）
- 单层内最多 2 个 builder pane，layer 2 单 builder

## 4. Dispatch Batches

| Batch | Nodes | Trigger |
|-------|-------|---------|
| B1 | N1, N2 | status=active 后立即派发 |
| B2 | N3 | N1.gate=G1.passed AND N2.gate=G2.passed |

## 5. Per-Node Acceptance

### N1 — outcomes.md
- 含 5 outcome（O1 Source Quality / O2 Argument Density / O3 Controversy Matrix / O4 Multi-Direction Explorer / O5 E2E Runtime Evidence）
- 每个 outcome 6 字段：一句话定义 / 覆盖原始需求 # / acceptance criteria ≥ 3 / risk 边界 / "不能直接派 builder"子项 ≥ 1 / S02-S05 切入点
- 显式引用前置 sprint accepted 的自评质量缺口（文献综述方法学 / 分类法原创性 / 跨章节一致性 / 反证覆盖 / 术语稳定性 / 贡献边界）
- 不出现阈值数值（`≥ 0.\d` / `≥ \d{2,}` 一律 fail）
- 不要求重写前置 source-authority / literature-mapping / controversy / chapter-review / chief-editor 接口

### N2 — non-builder-boundary.md
- 治理边界小节：列出**具体文件**（`coordinator.sh` / `autopilot.sh` / `dispatcher.sh` / `lib/phase-state-machine.sh` / `harness/lib/research/survey/__init__.py` 接口）
- 非目标清单：与 design.md §4 一致
- 不动接口清单 ≥ 5 个（前置 sprint 已落地模块名）
- 非 builder 决策项 ≥ 4 类：阈值数值 / 评分 rubric / 反证 corpus 选源 / 探索方向初选
- 显式声明 plugin registration 路径（`survey/__init__.py` 或 `survey/gates/__init__.py`）

### N3 — handoff.md + parent traceability patch
- handoff.md 含 5 outcome × 4 slice 切入矩阵（≥ 20 行 `s0[2-5]_*`）
- 治理边界摘要 + 已知未闭环项
- `s02_can_start: true` + `s03_blocked_until: s02_passed` + `s05_blocked_until: [s03_passed, s04_passed]`
- 父 `epic-…traceability.json` 仅 patch `children[0].outcomes_ready=true`，schema_version 不变 + children 顺序不变
- 不声称 epic 已完成 / S02-S05 已就绪

## 6. Routing Policy

- 所有节点 `preferred_model=sonnet`（需求拆解 + 文档严谨性；GLM 1210 已踩 5 次）
- 禁止 builder webfetch / web search / 网络写
- 上游唯一证据源：epic.md + 前置 sprint accepted.md（不动接口列表）

## 7. Stop Rules

- 写出 .py / .ts / .js / .sh / .sql 文件 → fail
- outcomes.md 缺"不能直接派 builder"子项 → fail
- outcomes.md 写入阈值数值 → fail
- 任何节点要求重写前置 sprint 已落地接口 → fail
- N3 之前父 traceability 被改 → graph_scheduler 阻断
- handoff 声称 "S02-S05 已就绪" / "epic 完成" → fail

## 8. Exit Criteria (Sprint passed)

- N1/N2/N3 三节点 evaluator verdict 全部 PASS
- 父 `epic-…traceability.json` `children[0].outcomes_ready=true`（schema_version + children 顺序未变）
- D1 outcomes / D2 non-builder-boundary / D3 handoff 三 deliverable 齐备且互相一致
- 10 条 A1-A10 acceptance 全过（design.md §8）

## 9. Evaluator Entry Points

- 看 design.md §8 Acceptance Contract（10 条）
- 看 outcomes.md：grep section count + 5 outcome × 6 字段 + 0 阈值数值
- 看 non-builder-boundary.md：grep ≥ 4 类非 builder 项 + ≥ 5 个不动接口
- 看 handoff.md：grep `s02_can_start`, `s03_blocked_until`, `s05_blocked_until`
- 看 parent traceability：jq `.children[0].outcomes_ready == true` + `.schema_version == "solar.epic.traceability.v1"`

## 10. Out of Scope

- 实现代码（5 gate / explorer / runner 都留 S03+）
- 阈值数值（S02 architecture 写接口 + S05 验证时定）
- ReportAST schema（S02）
- evaluator 评分 rubric（S03 + S05）
- 给前置 sprint 已落地的 source-authority / literature-mapping / controversy / chapter-review / chief-editor 加新功能

## 11. Current Status

- status: drafting → active（本次 planner pass 完成后翻）
- phase: prd_ready → planning_complete
- handoff_to: planner → builder_parallel
- artifacts: design.md ✓ / plan.md ✓ / task_graph.json ✓（本次产物）
