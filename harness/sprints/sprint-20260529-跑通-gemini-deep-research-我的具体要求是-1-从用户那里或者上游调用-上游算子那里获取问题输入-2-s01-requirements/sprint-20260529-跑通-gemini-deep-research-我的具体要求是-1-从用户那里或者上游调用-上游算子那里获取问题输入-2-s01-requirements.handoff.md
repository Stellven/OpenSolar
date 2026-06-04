# Handoff — S01 需求拆解与追踪矩阵

Sprint: `sprint-20260529-跑通-gemini-deep-research-...-s01-requirements`
Nodes: R1 → (R2, R3) → R4 | Gate: `requirements-handoff-consolidated`
Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge

## Summary

本切片为**需求工程**,把「跑通 Gemini Deep Research」大需求拆为 6 个可验收
outcome(O1–O6)、7 项非-builder 工作边界、以及 O1–O6 → S02–S05 追踪矩阵。
**未实现任何自动化代码**(切片定位即如此)。三份产物已生成,DAG 节点
R1/R2/R3 已置 reviewing,本 handoff 为 R4。

## 引用的 R1–R3 产物

1. `...-s01-requirements.requirements-matrix.md` (R1) — O1–O6 矩阵,每条含验收标准/风险边界/机器可验证信号。
2. `...-s01-requirements.non-builder-work.md` (R2) — NB1–NB7 非-builder 工作 + 理由 + 与 O1–O6 对应。
3. `...-s01-requirements.traceability-map.md` (R3) — O1–O6 → S02–S05 映射 + 5 个开放项。

## 上游依赖

- 父 epic `...epic.md` / `...traceability.json` / `...epic.task_graph.json`(已读,作为拆解依据)。
- O1 上游算子输入契约 **[未定]** — 需 S02 与上游对齐(NB7)。
- Gemini 账号凭证 / ToS 合规结论 **[需人工]**(NB1/NB2)。

## 下游影响

- S02 architecture 必须先关闭 5 个开放项(输入契约、成功判据、重试边界、凭证合规、选择器策略)才能稳妥派 S03/S04。
- S05 verification-release 的端到端测试(O6)依赖 S03+S04,且依赖 O5 成功判据被冻结。

## 未闭环项 (open items)

1. O1 输入契约(上游算子身份/字段)— 转 S02。
2. O5「成功」判据(可机器判定代理信号)— 转 S02,人工确认(NB5)。
3. O5 重试上限 / 超时 / 退避 — 转 S02,禁止无限循环(NB6)。
4. NB1/NB2 凭证供给与合规 — 人工,跨切片持续约束。
5. NB3 DOM 选择器维护策略 — 转 S02/S04。

## 可复现验证说明

- 三份 .md 产物存在且各自「自检 (acceptance)」全勾。
- 节点状态可经
  `solar-harness.sh graph-scheduler mark --graph <task_graph.json> --node R4 --status reviewing --in-place`
  与读取 task_graph.json 的 node_results 复核。
- 本切片无代码,无测试可跑;符合「需求工程切片,不实现自动化代码」定位(如需运行证据,见下游 S03–S05)。

## Capability / KB Usage Evidence

- `[harness-knowledge]` `solar-harness context inject` 在节点开始时**已使用**(命中父 epic.json/traceability;mirage 部分降级)。命中用于确认 epic 拆解,直接影响 R1–R3 内容。
- 技能 `requirements/planning/documentation`、能力 `product.requirements/workflow.planning`: 用于产出矩阵/边界/追踪三类文档。

## Scope Compliance

- 仅写入各节点 write_scope 指定的 4 个文件(matrix/non-builder/traceability/handoff)。
- 仅读取 epic 三件套与本 sprint PRD/task_graph(read_scope 内)。
- 未改任何 ThunderOMLX/源码;未绕过 planner 派 builder;未动父级 traceability(无 scope 冲突需回写)。

## Not Done / 边界声明

- **本切片 ≠ 父 Epic 完成**: 仅完成需求拆解;O1–O6 的真实「跑通」由 S02–S05 实现与验证。
- 未做架构/接口设计(S02)、未做实现(S03/S04)、未做端到端测试(S05)。
- 5 个开放项尚未关闭,均已显式转交下游。

状态: R4 置 reviewing,交 evaluator。本切片产出为需求文档,**不声称**父 Epic 已跑通。
