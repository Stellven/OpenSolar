# Design — DeepResearch Professor-Grade Survey Quality Hardening · S02 Architecture

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture`
Epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Slice: `architecture` (Planner pass; spec-only, no code)
Author: Solar Planner
Date: 2026-05-17
Knowledge Context: solar-harness context inject used（命中 S01 `outcomes.md` / `non-builder-boundary.md` / `handoff.md` 三件套 + 现有 `survey/` 包 frozen schemas: SurveyRun / SourceMatrix / ChapterSpec / SectionSpec / SurveyReportAST / EvidencePack / SectionReview / SurveyScorecard / `evaluate_survey()` / `build_evidence_packs()` / `compile_survey()`）

## 1. Problem Framing

S01 落地了 5 outcome × 4 slice = 20 入口矩阵 + 6 QG 质量缺口 + governance boundary（5 frozen modules + 6 frozen files）。S02 必须把 20 入口矩阵翻译成**可被 S03 builder 实现的 schema + interface contract + data flow**，并锁定 6 个 QG 的**评估标准**（不锁阈值数值）。

S02 不写代码，只写 architecture spec markdown（field list / function signature as text / data flow diagram / failure mode / observability）。schema 实际定义在 S03 `survey/schemas.py` 扩展时落地。

S01 显式输出的 S02 责任（来自 `s01-requirements.handoff.md` §1 entry matrix）：

| Outcome | S02 必交付 |
|---------|----------|
| O1 Source Quality Distribution | `SourceQualityDistribution` schema + plugin registration interface + 与 `source_authority.py` 数据流 |
| O2 Argument Density | `ArgumentDensityProfile` schema + applicability mapping interface + 与 `SectionReview` 数据流 |
| O3 Contradiction Matrix | `ContradictionMatrix` schema + 来自 `EvidencePack.contradiction_slots` + `claim_evidence.jsonl` 数据流 + chapter synthesis reference 接口 |
| O4 Multi-Direction Exploration | `EliminationRecord` schema + `exploration_run()` interface + 来自 `SourceMatrix` / `handoff-search` 数据流 |
| O5 E2E Runtime Evidence | `GateReport` schema + 4 gate plugin registration interface + e2e runner artifact layout |

加 6 个 QG 标准锁定（criteria + measurement，不含数值）：

| QG | 标准锁定 |
|----|---------|
| QG-1 文献综述方法学 | literature review methodology checklist + 必查维度 |
| QG-2 分类法原创性 | novel taxonomy 判定条件（是否要求原创 / 引用基线 / diff 维度）|
| QG-3 跨章节一致性 | cross-chapter claim linking 规则（claim_id 复用 / 矛盾检测）|
| QG-4 反证覆盖 | contradiction corpus 选源准则（来源类型 + 平衡度）|
| QG-5 术语稳定性 | terminology consistency metric 定义（不含阈值）|
| QG-6 贡献边界 | contribution boundary 判定规则（声明范围 + 排除范围）|

## 2. Slice Boundaries

- **做**：5 个 architecture spec markdown（每 outcome 一份）+ 1 个 QG lockdown 文档 + 1 个 handoff.md + parent traceability patch
- **不做**：写代码（`.py` / `.sh` / `.json` schema 文件均不写；S03 才落地）；选阈值数值（S03 + S05 才定）；动 frozen interface
- **不允许**：声称 epic 已完成；让 S03 builder 自己决定 schema 字段；让 S04/S05 自己定义 e2e 验收

## 3. Design Goals

| Goal | Why |
|------|-----|
| **每个 arch spec 是 builder 不可代决的 schema** | S03 builder 只实现，不定义字段 |
| **schema 字段以 markdown 表格定义（不是代码）** | S02 是 architecture spec，不是 implementation |
| **每份 arch spec 显式列出与 frozen interface 的 data flow** | 防止 S03 误改 frozen module |
| **QG lockdown 锁标准，不锁数值** | 数值留 S03 / S05；S02 锁哪些维度必须算 |
| **parent traceability 单字段 patch** | 仅 `children[1].architecture_ready=true`，schema_version + children 顺序不变 |
| **handoff.md 给 S03/S04 切入清单（不给 S05，S05 等 S03+S04）** | S03/S04 并行可启动；S05 阻塞 |

## 4. Non-Goals

- 不写 `.py` schema 实现（S03 才写 `survey/schemas.py` 扩展）
- 不写 plugin registration 代码（S03 才写）
- 不选阈值数值（每 spec 仅列"必须有阈值"+ 维度，数值 S03/S05 定）
- 不写 evaluator rubric 实现（S03 写 + S05 验证）
- 不动 frozen 5 module 接口（source_authority / literature_mapping / controversy / chapter_review / chief_editor）
- 不动 frozen 6 file（coordinator / autopilot / dispatcher / phase-state-machine / solar-harness / `survey/__init__.py` 已存导出）

## 5. Architecture Topology (5 new schemas × frozen dependency)

```text
                    ┌──── source_authority.py (frozen) ────┐
                    │                                      │
SourceQualityDistribution ── plugin reg ── survey/gates/__init__.py
                                                          │
                    ┌──── chapter_review.py (frozen) ─────┤
ArgumentDensityProfile ── per SectionReview ─────────────┤
                                                          │
                    ┌──── controversy.py + EvidencePack ──┤
ContradictionMatrix ── chapter synthesis ref ────────────┤
                                                          │
                    ┌──── SourceMatrix + handoff-search ──┤
EliminationRecord ── survey/explorer/ register ──────────┤
                                                          │
                    ┌──── all 4 gates ────────────────────┘
GateReport ── plugin reg ── e2e runner artifact
```

5 新 schema 全部走 plugin registration（`survey/gates/__init__.py` / `survey/explorer/__init__.py`），不动主链路。

## 6. Deliverables

| # | Deliverable | Owner Node | 内容 |
|---|-------------|-----------|------|
| D1 | `…s02-architecture.source-quality-arch.md` | N1 | `SourceQualityDistribution` schema (field × type × required × source) + plugin registration contract（function signature as text）+ 与 `source_authority.check_source_authority()` 数据流 + failure modes + observability + 不动接口声明 |
| D2 | `…s02-architecture.argument-density-arch.md` | N2 | `ArgumentDensityProfile` schema + 5 维度 applicability mapping 接口 + 与 `chapter_review.compile_survey()` / `SectionReview` 数据流 + 同上 |
| D3 | `…s02-architecture.contradiction-matrix-arch.md` | N3 | `ContradictionMatrix` schema + chapter synthesis reference 接口 + 与 `EvidencePack.contradiction_slots` + `controversy.py` + `claim_evidence.jsonl` 数据流 + 同上 |
| D4 | `…s02-architecture.exploration-arch.md` | N4 | `EliminationRecord` schema + `exploration_run()` interface + direction scoring 维度 + 与 `SourceMatrix` / `handoff-search` 数据流 + plugin reg via `survey/explorer/__init__.py` + 同上 |
| D5 | `…s02-architecture.gate-report-arch.md` | N5 | `GateReport` aggregation schema + 4 gate plugin registration contract + e2e runner artifact layout（`runtime/survey-continue/<run>/gate_report.json` 等）+ 与 `evaluate_survey()` 数据流 + 同上 |
| D6 | `…s02-architecture.quality-gap-lockdown.md` + handoff + traceability | N6 (join) | QG-1..QG-6 6 标准锁定（criteria + measurement，不含数值）+ S03/S04 切入清单 + s03_can_start: true + s04_can_start: true + s05_blocked_until: [s03_passed, s04_passed] + parent `children[1].architecture_ready=true` |

## 7. DAG Topology

```text
N1 source-quality ──┐
N2 argument-density┤
N3 contradiction   ├── N6 QG lockdown + handoff + parent patch ── done
N4 exploration     ┤
N5 gate-report  ───┘
```

6 节点 2 层；N1-N5 ∥ 5-way parallel（write_scope 互斥）；N6 join。

## 8. Acceptance Contract

| # | Acceptance | 验证 |
|---|------------|------|
| A1 | 5 个 arch spec markdown 各含：schema 字段表（≥ 5 字段，每字段 name/type/required/source 4 列）/ plugin registration contract / data flow from frozen module / failure modes ≥ 3 / observability ≥ 2 指标 / 不动接口声明 | grep section count + table row |
| A2 | 每 arch spec 必须显式引用 ≥ 1 个 S01 outcome 编号（O1..O5） | grep |
| A3 | quality-gap-lockdown.md 含 QG-1..QG-6 6 节，每节含 criteria + measurement，**禁止含数值阈值** | grep section count + 0 阈值 |
| A4 | handoff.md 含 5 outcome × 2 slice (S03/S04) 切入清单 ≥ 10 行 + s03_can_start + s04_can_start + s05_blocked_until | grep |
| A5 | 父 traceability.json `children[1].architecture_ready=true`（仅此字段；schema_version + children 顺序 + 长度不变） | jq |
| A6 | 全切片**不出现** .py / .ts / .js / .sh / .sql 文件 | find |
| A7 | 不声称 "epic 已完成" / "S03-S05 已就绪" / "schema 已实现" | grep == 0 |
| A8 | 不要求重写 frozen 5 module 接口（source_authority / literature_mapping / controversy / chapter_review / chief_editor） | grep `重写.*xxx` == 0 |
| A9 | 不修改 frozen 6 file（coordinator / autopilot / dispatcher / phase-state-machine / solar-harness / `survey/__init__.py`） | write_scope 检查 |
| A10 | 每 arch spec 含"不能直接派 builder"子项 ≥ 1（如阈值数值 / corpus 选源 / 方向初选） | grep |
| A11 | gate-report-arch.md 含 e2e runner artifact 完整目录布局（≥ 3 个 artifact 文件名 + 期望 schema 引用） | grep |
| A12 | 每 arch spec data flow 段落显式引用 ≥ 1 个 frozen schema（SurveyReportAST / EvidencePack / SectionReview / SourceMatrix / SurveyScorecard 中至少 1）| grep |

## 9. Stop Rules

- 任何节点写代码扩展名 → fail
- 任何节点要求重写 frozen 5 module 接口 → fail
- arch spec 含数值阈值（regex `≥ 0\.\d` / `≥ \d{2,}` / `>= 0\.\d`）→ fail
- arch spec 缺 schema 字段表 / plugin reg contract / data flow 三选一 → fail
- N6 之前父 traceability 被改 → graph_scheduler 阻断
- N6 之前任何节点对 parent traceability 写入 → fail
- handoff 声称 "S03-S05 已就绪" → fail
- quality-gap-lockdown.md 含具体数值（如 "novel taxonomy ratio ≥ 0.5"）→ fail

## 10. Parallelism & Write Scope

- **N1**: `sprints/…s02-architecture.source-quality-arch.md`
- **N2**: `sprints/…s02-architecture.argument-density-arch.md`
- **N3**: `sprints/…s02-architecture.contradiction-matrix-arch.md`
- **N4**: `sprints/…s02-architecture.exploration-arch.md`
- **N5**: `sprints/…s02-architecture.gate-report-arch.md`
- **N6**: `sprints/…s02-architecture.quality-gap-lockdown.md`, `sprints/…s02-architecture.handoff.md`, `sprints/epic-…traceability.json` (`children[1].architecture_ready` only)

write_scope 完全互斥；N1-N5 5-way 并行；N6 join 后写 lockdown + handoff + parent patch。

## 11. Model Routing

- 所有节点 `preferred_model=sonnet`（schema 设计严谨性 + GLM 1210 风险）
- 禁止 worker webfetch / web search
- 上游唯一证据源：S01 `outcomes.md` + `non-builder-boundary.md` + `handoff.md` + 现有 `survey/schemas.py` frozen 类定义

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| arch spec 写得太抽象 → S03 builder 还是要自己拍 schema 字段 | A1 强制 schema 字段表 ≥ 5 字段 × 4 列；A12 要求引用 frozen schema |
| arch spec 偷偷写数值阈值 → 撞 S01 锁定 | stop rule + N6 grep `≥ 0\.\|≥ \d{2,}` |
| QG lockdown 写得太空泛 → S03 还是不知道怎么算术语稳定性 / 贡献边界 | A3 强制 criteria + measurement 两段；N6 join 时 cross-check |
| 父 traceability schema_version 被覆写 | parent_link_policy + N6 用 python json 仅 patch 单字段 |
| N1-N5 并行时引用 frozen schema 不一致 | A12 每节点引用现有 `survey/schemas.py` 类（SurveyReportAST / EvidencePack / SectionReview / SourceMatrix / SurveyScorecard）+ N6 cross-check |
| arch spec 与 S01 outcomes 不对齐 | A2 强制引用 ≥ 1 个 O 编号 |
| S03 误以为 S02 已实现 schema（其实只是 spec） | A7 stop rule + handoff.md 显式声明 "spec only, S03 implements" |

## 13. Knowledge Context Usage

- `solar-harness context inject` 已执行：S01 三件套 + 现有 survey 包 frozen schemas
- S01 `handoff.md` §1 是 mirage_path 可检索证据，每个 N1-N5 必须 read_scope 包含
- 现有 `~/.solar/harness/lib/research/survey/schemas.py` 是 frozen 接口源，arch spec 须引用类名

## 14. Handoff Plan

N6 完成后，handoff.md 必须含：

- 5 arch spec × 2 slice (S03/S04) 切入矩阵（每格写：该 slice 接该 spec 的哪个 deliverable + 依赖哪个 frozen interface）
- QG lockdown 摘要（6 标准的 criteria + measurement，不含数值）
- 不动 frozen 接口声明（重申 S01 governance）
- 已知未闭环项（S03 builder 可能要 inline 决策的项，列出来让 evaluator 卡）
- `s03_can_start: true` + `s04_can_start: true` + `s05_blocked_until: [s03_passed, s04_passed]`
- 不声称 epic 已完成 / S03+ 已就绪 / schema 已实现
