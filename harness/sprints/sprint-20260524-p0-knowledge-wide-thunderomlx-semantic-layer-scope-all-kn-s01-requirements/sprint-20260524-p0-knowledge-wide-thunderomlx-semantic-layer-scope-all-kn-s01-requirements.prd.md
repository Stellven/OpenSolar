---
title: "PRD: 需求拆解与追踪矩阵 (S01 requirements slice)"
epic_id: epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn
sprint_id: sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements
slice: requirements
priority: P0
status: drafting
phase: prd_ready
handoff_to: planner
created_at: 2026-05-24T13:20:00Z
updated_at: 2026-05-24T17:28:00Z
---

# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn`
sprint_id: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements`
slice: `requirements`

## 背景 / Context

父 Epic `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn` 把"Knowledge-wide ThunderOMLX semantic layer"拆成 5 个子 sprint (S01-S05)，依赖链为 S01 → S02 → {S03, S04} → S05。本 sprint 是该链上的 **S01 (requirements) 切片**，唯一职责是把用户原始大需求拆成可验收的 outcome 矩阵、明确边界与非目标，并产出父 Epic 到 5 个子 sprint 的 traceability map，供 S02 architecture 切片直接消费。

切片层面的上下文：
- 用户原始大需求落在 `/Users/lisihao/Knowledge/_raw/solar-harness/intake/20260524t132500z-knowledge-wide-thunderomlx-semantic-layer.md`，定义了 raw/vault → QMD raw embed → ThunderOMLX JSON-first 抽取 → validator/repair/quarantine → semantic.md → QMD extracted embed 的端到端语义管道。
- 父级 `traceability.json` 和 `task_graph.json` 已经存在但内容是 stub，需要本 sprint 填充 outcome ↔ 子 sprint 的对账关系。
- 同期独立 sprint `sprint-20260524-105859` (Knowledge Ingest Dispatcher) 已 PRD-ready 并已 handoff planner；本 Epic 与它的交叉点必须在 traceability 中显式标注，避免重复实现。

## 用户问题 / Problem

如果跳过 S01 直接进入 S02 架构设计，会出现 3 个具体问题：

1. **outcome 无法对账**: 5 个子 sprint 各自做"局部 PRD"，没有父级 outcome 矩阵，最终验证时无法判断"P0 是否真的整体完成"，只能逐 sprint 看 passed 标记。
2. **边界冲突**: ThunderOMLX 语义层与同期独立 sprint (knowledge ingest dispatcher、obsidian wiki integration) 在 source adapter、registry schema、extract 入口上有重叠，没有显式 traceability 会出现两条链路各自实现 raw adapter 的浪费。
3. **越权派 builder**: 历史上 S01 切片曾被略过、直接由 PM 拍板派 builder，导致 design.md 与实际实现脱节，evaluator 阶段才暴露 acceptance 缺失。本 sprint 要把"哪些工作必须走 planner、哪些不能直接派 builder"明文落地。

## 用户故事 / User Stories

- **As 父 Epic 负责人 (PM)**, I want S01 输出一张 outcome × 子 sprint 矩阵, so that 任意 outcome 都能反向追踪到承接 sprint，避免漏项。
- **As Planner (S02 接收方)**, I want 一份明确的 acceptance 边界与非目标清单, so that S02 架构设计不必反复回去问 PM "这个是否在范围内"。
- **As Builder (后续 S03/S04 接收方)**, I want 一份 "不能直接派 builder" 的 work item 清单, so that 我不会接到一个隐性需要先做架构决策的任务。
- **As Evaluator (S05 验证方)**, I want traceability map 能映射 outcome 到证据要求, so that 我能按 outcome 而不是 sprint 单元逐项验收。
- **As 平台维护者**, I want 本 sprint 显式声明与 `sprint-20260524-105859` (knowledge ingest dispatcher) 的交集与分工, so that 两个并行链路不会重复实现 source adapter 或 registry。

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn.epic.md`、`epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## 约束 / Constraints

- **不越权交付**: 本 sprint 只产出需求拆解 + traceability，**不**输出架构方案、接口契约或代码改动 (那些归 S02/S03)。
- **slice 隔离**: 所有产物文件名必须带 `-s01-requirements.` 前缀，不得污染父 Epic 命名空间或其他 slice。
- **必须复用现有制品**: 父 Epic 的 `epic.md`/`traceability.json`/`task_graph.json` 必须 **读取并对齐**，不重新发明 Epic 拆分。
- **handoff 强契约**: 输出的 `handoff.md` 必须明确指向 `handoff_to: planner` 且列出上游依赖、下游影响、未闭环项 (Stop Rules 第 3 条)。
- **traceability 字段最小集**: outcome_id, parent_epic_id, child_sprint_id, acceptance_ref, evidence_required, builder_safe (bool)，缺一不可。
- **与并行 sprint 的交叉**: 必须在 traceability 中显式标注与 `sprint-20260524-105859` 的交集 outcome (registry / adapter / state machine 等)，标记 "由 105859 主导" 或 "由本 Epic 主导"。
- **不直接落 /tmp**: STATE.md 约束 — 所有产物落 `~/.solar/harness/sprints/`。
- **status 锁定**: 本次 PRD 修改保持 `status=drafting`，由 coordinator 重判 gate 后再由 wake/planner 推进。

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用"已完成"替代可复现证据。

## 风险 / Risks

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | outcome 拆得过细 (>20 项) 导致 S02 架构无法承接 | Planner backlog 膨胀, S02 切片超出预算 | 限制 outcome 数量 ≤ 12, 每个对齐一个或多个子 sprint 的 acceptance |
| R2 | 与 `sprint-20260524-105859` 范围重叠未被识别 | 两条链路重复实现 source adapter/registry, 浪费 builder 配额 | traceability 必须显式列出 cross-sprint outcome 并标 owner |
| R3 | traceability schema 缺字段, 后续 S05 验证无法对账 | evaluator 无法按 outcome 判 pass | 本 sprint 锁定 6 字段最小集 (见 Constraints) 并写入 schema |
| R4 | "不能直接派 builder" 清单遗漏隐性架构决策项 | 后续 builder 任务被退回, sprint 卡循环 | 每个 outcome 必须打 `builder_safe` 布尔 + 理由 |
| R5 | 父 Epic 的 `traceability.json` 仍是 stub, S01 写入后被其他 sprint 覆盖 | 追踪信息丢失 | 本 sprint 写 traceability 时必须用 merge 而非 overwrite, 由 handoff 标注 |
| R6 | PM 在本 slice 偷渡架构决策 (例如指定 SQLite vs DuckDB) | 越界, S02 失去自由度 | 约束 + 非目标 双重锁; design.md 仅描述 "需要决策的点", 不给答案 |

## 开放问题 / Open Questions

| # | 问题 | 决策需要谁 | 本 sprint 处理方式 |
|---|---|---|---|
| Q1 | outcome 粒度是按 source_kind (raw/vault/...) 还是按 pipeline stage (ingest/extract/validate/...)? | Planner (S02) | 本 sprint 同时给出两种视图, 由 S02 在 design.md 选定主视图 |
| Q2 | 与 `sprint-20260524-105859` 的 registry 是合并还是各自独立? | 昊哥 | 本 sprint **不拍板**, 只在 traceability 中标 "decision_pending: registry_unification" |
| Q3 | ThunderOMLX semantic.md 是否要保留中间 JSON candidate 作为 grounding source? | 架构决策, 推迟到 S02 | 列入 builder_safe=false 清单, S02 处理 |
| Q4 | quarantine 是否落到独立 QMD index 还是只落 `_quarantine/` 目录? | S03 实施期 | 本 sprint 只声明 "必须可回放", 不指定存储位置 |
| Q5 | 父 Epic 的 acceptance gate 用 outcome 覆盖率还是子 sprint passed 数? | 昊哥 / Evaluator (S05) | 默认 outcome 覆盖率 ≥ 95%, 待 S05 在 verification slice 确认 |
| Q6 | 与现有 Obsidian wiki integration sprint (5月12) 是否有 raw/_solar-harness/ 路径冲突? | 本 sprint 调研后给 Planner | 列入 handoff "未闭环项" |

## 交付物

- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements.design.md`
- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements.plan.md`
- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements.task_graph.json`
- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements.handoff.md`
- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements.eval.md` 或 `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements.eval.json`

## 架构交接 / Planner Handoff

**Handoff target**: `planner` (S02 architecture slice 直接消费方)

**Planner 必须做的**:

1. 读取本 PRD 的 outcome 矩阵 + traceability map + Open Questions, 输出 `s01-requirements.design.md` 描述 outcome 拆分逻辑 (不输出实现架构, 那归 S02)。
2. 输出 `s01-requirements.plan.md` 给出本切片的 worklog (调研父 Epic / 列 outcome / 写 traceability / 标 builder_safe / 写 handoff)。
3. 输出 `s01-requirements.task_graph.json` 至少包含: `read_epic`, `compile_outcome_matrix`, `merge_traceability`, `mark_builder_safety`, `cross_sprint_overlap_audit`, `write_handoff` 6 个节点, 依赖关系明确。
4. **不得**在本切片内调用 builder pane; 任何代码改动 (例如修改 `traceability.json` schema) 必须等 S02 设计完成后由 S03 承接。
5. 在 handoff.md 中显式回答 Open Questions Q1/Q6, 并把 Q2/Q3/Q4/Q5 列为 "未闭环项 (cross-slice)", 注明承接 sprint。

**Planner 不得做的**:

- 不得在 design.md 中给出 ThunderOMLX 抽取的具体接口契约 (那是 S02 职责)。
- 不得在 plan.md 中安排 builder 节点。
- 不得修改父 Epic 的 `epic.md` 或 `task_graph.json`; 只能写入 sprint 自己的 artifact + 通过 traceability merge 写入父级 `traceability.json`。

**下游影响**:

- S02 architecture: 直接依赖本 sprint 的 outcome 矩阵 + Q1 决策。
- S03 core-runtime / S04 orchestration-ui: 依赖 S02, 间接依赖本 sprint 的 builder_safe 清单。
- S05 verification-release: 依赖本 sprint 的 traceability schema 做 outcome 覆盖率验收。
- 并行 sprint `sprint-20260524-105859`: 等待本 sprint cross-sprint overlap 审计结论 (Q2/Q6)。

---

## 用户原始需求 (source reference)

P0: Knowledge-wide ThunderOMLX semantic layer. Scope: all knowledge sources, not only YouTube transcript. Implement single knowledge_ingest_dispatcher/state registry; accepted, Obsidian, ChatGPT, Web, GitHub, PDF/manual raw, Solar artifacts must flow raw/vault -> QMD raw/vault embed -> ThunderOMLX JSON-first semantic extraction -> validator/repair/quarantine -> semantic.md -> QMD extracted embed. Contract source: `/Users/lisihao/Knowledge/_raw/solar-harness/intake/20260524t132500z-knowledge-wide-thunderomlx-semantic-layer.md`
