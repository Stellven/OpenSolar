# Plan — DeepResearch Professor-Grade Survey Quality Hardening · S02 Architecture

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture`
Epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Slice: `architecture`
Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-contracts

## 1. DAG (6 nodes, 2 layers)

```text
N1 source-quality-arch ──┐
N2 argument-density-arch ┤
N3 contradiction-matrix  ├── N6 QG lockdown + handoff + parent patch
N4 exploration-arch      ┤
N5 gate-report-arch    ──┘
```

Layers: `[[N1, N2, N3, N4, N5], [N6]]` — 5-way parallel + 1 join.

## 2. Node-by-Node Execution

| Node | Goal | Write Scope | Depends | Gate |
|------|------|-------------|---------|------|
| N1 | 写 `source-quality-arch.md`：`SourceQualityDistribution` schema + plugin reg + 与 `source_authority.py` 数据流 | `sprints/…s02-architecture.source-quality-arch.md` | — | G1 |
| N2 | 写 `argument-density-arch.md`：`ArgumentDensityProfile` schema + 5 维度 applicability + 与 `SectionReview` 数据流 | `sprints/…s02-architecture.argument-density-arch.md` | — | G2 |
| N3 | 写 `contradiction-matrix-arch.md`：`ContradictionMatrix` schema + chapter synthesis ref + 与 `EvidencePack` / `claim_evidence.jsonl` 数据流 | `sprints/…s02-architecture.contradiction-matrix-arch.md` | — | G3 |
| N4 | 写 `exploration-arch.md`：`EliminationRecord` schema + `exploration_run()` interface + 与 `SourceMatrix` 数据流 + plugin reg via `survey/explorer/__init__.py` | `sprints/…s02-architecture.exploration-arch.md` | — | G4 |
| N5 | 写 `gate-report-arch.md`：`GateReport` aggregation + 4 gate plugin reg + e2e runner artifact layout + 与 `evaluate_survey()` 数据流 | `sprints/…s02-architecture.gate-report-arch.md` | — | G5 |
| N6 | join：QG lockdown + handoff + parent traceability patch (`children[1].architecture_ready=true`) | `sprints/…s02-architecture.quality-gap-lockdown.md`, `sprints/…s02-architecture.handoff.md`, `sprints/epic-…traceability.json` | N1, N2, N3, N4, N5 | G6 |

## 3. Parallelism

- N1-N5 ∥ 5-way：每个写独立 .md 文件，write_scope 互斥；依赖只读 S01 三件套 + frozen `schemas.py`
- N6 join：必须等 5 个 arch spec 全部 passed 后才能开始（用 5 spec 做 QG cross-check + 写 handoff matrix）
- 单 batch 同时派 5 builder pane 略激进；建议 batch 拆 2 + 3（见 §4），避免 pane 资源饿死

## 4. Dispatch Batches

| Batch | Nodes | Trigger | 备注 |
|-------|-------|---------|------|
| B1 | N1, N2, N3 | status=active 后立即派发 | 3 个 schema 起头（最熟的现有 frozen 接口）|
| B2 | N4, N5 | B1 中任意 ≥ 1 passed 后派发 | N4/N5 引用更多上游，留半个 lane 复用 |
| B3 | N6 | N1-N5 全部 G1-G5 passed | join 单 pane |

如 pane 资源充足，B1+B2 可合并为单 batch 5-way；调度器 layers ready 自动决定。

## 5. Per-Node Acceptance

### N1 — source-quality-arch.md
- `SourceQualityDistribution` schema 字段表 ≥ 5 字段 × 4 列（name / type / required / source）
- plugin registration contract（function signature as text，引用 `survey/gates/__init__.py`）
- data flow 段：from `source_authority.check_source_authority()` → distribution build → verdict
- failure modes ≥ 3
- observability ≥ 2 指标（如 distribution 计算耗时 / 异常源比率）
- 不动接口声明（`source_authority.py` public API frozen）
- 显式引用 S01 outcome O1
- 引用现有 frozen schema（EvidencePack 至少 1 次）
- "不能直接派 builder"子项 ≥ 1（如 distribution 阈值数值留 S03）

### N2 — argument-density-arch.md
- `ArgumentDensityProfile` schema 字段表 ≥ 5 字段 × 4 列
- 5 维度 applicability mapping interface（mechanism_comparison / method_taxonomy / evaluation_protocol / failure_negative_evidence / engineering_implication）
- data flow 段：from `SectionReview` + `chapter_review.compile_survey()` → density profile
- failure modes / observability / 不动接口声明 / S01 O2 引用 / frozen schema 引用 / builder 边界子项 同 N1

### N3 — contradiction-matrix-arch.md
- `ContradictionMatrix` schema 字段表 ≥ 5 字段 × 4 列
- chapter synthesis reference interface（matrix row → chapter synthesis 引用规则）
- data flow 段：from `EvidencePack.contradiction_slots` + `claim_evidence.jsonl` + `controversy.py` → matrix build
- failure modes / observability / 不动接口声明 / S01 O3 引用 / frozen schema 引用 / builder 边界子项

### N4 — exploration-arch.md
- `EliminationRecord` schema 字段表 ≥ 5 字段 × 4 列（含 direction_id / score / kill_reason / evidence_refs / decision_ts）
- `exploration_run()` interface（function signature as text；输入 question + candidate directions；输出 SurveyReportAST + elimination_log.jsonl）
- data flow 段：from `SourceMatrix` + `handoff-search` → direction scoring → elimination log
- plugin reg via `survey/explorer/__init__.py`（新建包入口；不动 `survey/__init__.py` 已有导出）
- failure modes / observability / 不动接口声明 / S01 O4 引用 / frozen schema 引用 / builder 边界子项

### N5 — gate-report-arch.md
- `GateReport` aggregation schema 字段表 ≥ 5 字段 × 4 列（含 4 gate verdict 子结构）
- 4 gate plugin registration contract（O1-O4 各一份 registration spec）
- e2e runner artifact layout（≥ 3 artifact 文件名：`runtime/survey-continue/<run>/gate_report.json`、`elimination_log.jsonl`、`contradiction_matrix.json` 等）
- data flow 段：from 4 gate verdicts + `evaluate_survey()` → aggregated GateReport
- failure modes / observability / 不动接口声明 / S01 O5 引用 / frozen schema 引用 / builder 边界子项

### N6 — quality-gap-lockdown.md + handoff.md + parent traceability patch
- quality-gap-lockdown.md 含 QG-1..QG-6 6 节，每节 criteria + measurement 两段（**禁止数值阈值**）
- handoff.md 含 5 arch spec × 2 slice(S03/S04) 切入清单 ≥ 10 行 `s0[3-4]_*` 标识符
- handoff.md 含 `s03_can_start: true` + `s04_can_start: true` + `s05_blocked_until: [s03_passed, s04_passed]`
- handoff.md 不声称 epic 已完成 / S03+ 已就绪 / schema 已实现
- 父 traceability.json 仅 `children[1].architecture_ready=true`（schema_version + children 顺序 + 长度不变）

## 6. Routing Policy

- 所有节点 `preferred_model=sonnet`（schema 严谨性 + GLM 1210 风险）
- 禁止 builder webfetch / web search / 网络写
- 上游证据源（必须 read_scope）：
  - `sprints/…s01-requirements.outcomes.md`
  - `sprints/…s01-requirements.non-builder-boundary.md`
  - `sprints/…s01-requirements.handoff.md`
  - `harness/lib/research/survey/schemas.py`（frozen 类列表）

## 7. Stop Rules

- 写出 .py / .ts / .js / .sh / .sql 文件 → fail
- arch spec 含数值阈值 → fail
- arch spec 缺 schema 字段表 / plugin reg / data flow 三件套 → fail
- 任何节点要求重写 frozen 5 module 接口 → fail
- N6 之前任何节点动 parent traceability → graph_scheduler 阻断
- handoff 声称 "S03-S05 已就绪" / "epic 完成" / "schema 已实现" → fail
- quality-gap-lockdown.md 含具体数值 → fail

## 8. Exit Criteria (Sprint passed)

- N1-N6 6 节点 evaluator verdict 全部 PASS
- D1-D6 6 deliverable 齐备且 cross-consistent
- 父 `epic-…traceability.json` `children[1].architecture_ready=true`（schema_version + children 顺序未变）
- A1-A12 12 条 acceptance 全过（design.md §8）

## 9. Evaluator Entry Points

- 看 design.md §8 Acceptance Contract（12 条）
- 看 5 arch spec：grep schema 字段表 row count + plugin reg + data flow 三段 + frozen schema 引用 + S01 O 引用 + builder 边界子项
- 看 quality-gap-lockdown.md：grep 6 QG 节 + criteria/measurement 段 + 0 数值阈值
- 看 handoff.md：grep `s0[3-4]_*` ≥ 10 行 + `s03_can_start` + `s04_can_start` + `s05_blocked_until`
- 看 parent traceability：jq `.children[1].architecture_ready == true` + `.schema_version == "solar.epic.traceability.v1"` + `len(.children) == 5`

## 10. Out of Scope

- schema `.py` 实现（S03）
- plugin registration 代码（S03）
- 阈值数值（S03 + S05）
- evaluator rubric 实现（S03 + S05）
- e2e runner 代码（S03）
- 给 frozen 5 module 加新功能

## 11. Current Status

- status: drafting → active（本次 planner pass 完成后翻）
- phase: prd_ready → planning_complete
- handoff_to: planner → builder_parallel
- target_role: planner → builder_main
- artifacts: design.md ✓ / plan.md ✓ / task_graph.json ✓
