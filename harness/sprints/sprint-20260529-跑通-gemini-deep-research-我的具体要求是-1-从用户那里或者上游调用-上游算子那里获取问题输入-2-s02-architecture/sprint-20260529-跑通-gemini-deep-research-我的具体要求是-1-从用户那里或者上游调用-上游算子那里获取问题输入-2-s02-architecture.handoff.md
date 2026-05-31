# Handoff — S02 架构设计与接口契约

Sprint: `sprint-20260529-跑通-gemini-deep-research-...-s02-architecture`
Nodes: A1 → (A2, A3) → A4 | Gate: `compat-conflict-degradation`
Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge

## Summary

把 S01 outcome 矩阵转成架构: 分层(control/data plane)、阶段交接 schema、失败恢复/重试/成功判据、
兼容与降级。**核心决策: Gemini DR 流程复用既有 `DeepResearchBrowser` 物理算子,不新建浏览器栈**,
实现落新增包 `operator/gemini_deep_research`(S03),不侵入 harness 核心。**架构切片,未写实现代码。**
A1–A4 已置 reviewing。

## 引用产物(本 sprint A1–A4)

1. `...-s02-architecture.architecture.md` (A1) — 分层 + 状态归属 + O1 输入契约(函数 entrypoint `submit_research`)。
2. `...-s02-architecture.interface-contracts.md` (A2) — ResearchRequest/OptimizedPrompt/DRPlan/DRRunHandle/DRResult/Reference 字段级 schema;O2→O3 回灌路径;分类文献结构。
3. `...-s02-architecture.failure-recovery.md` (A3) — 错误分类、重试三参数、O5 机器可判成功判据、观测信号。
4. `...-s02-architecture.compat-migration.md` (A4) — 兼容/迁移/降级/冲突依赖。

## 上游依赖

- S01 requirements(matrix/traceability/non-builder)— reviewing。
- 既有 `sprint-20260525-browser-agent-research-operators`: `DeepResearchBrowser` 逻辑算子、async submit→poll→collect 状态机、Session/Auth Broker、Evidence Ledger、ChatGPT↔Gemini fallback ladder。
- 真实调用 Gemini DR 额度需**人工授权开关**(沿用该 sprint 边界)。

## 下游影响

- S03 core-runtime: 在 `operator/gemini_deep_research` 包按 A2 schema 实现 InputIntake/PromptOptimizer/GeminiDRController/RetryPolicy;不直接 click/type,委托算子。
- S04 orchestration-ui: 编排 O1→O6 链 + 监控可视化(复用 Monitor bridge)。
- S05 verification-release: 凭 A3 观测信号(async_state 轨迹 + evidence_refs + DRResult)做端到端 activation-proof。

## 关闭的 S01 开放项

- O1 输入契约(NB7)→ A1: 函数 entrypoint `submit_research(ResearchRequest)`。
- O5 成功判据(NB5)→ A3: async_state==done + report_text 非空 + references>=MIN_REFS + 分类块 + URL 合法。
- O5 重试边界(NB6)→ A3: max_attempts/per_attempt_timeout_min/backoff(默认值待人工最终确认)。
- 选择器策略(NB3)→ A4: 复用算子层,失效走 fallback ladder。

## 未闭环项

- 重试三参数**默认值**需人工/planner 拍最终数值(A3 给出参数化形态,非最终值)。
- 凭证供给与 ToS 合规结论(NB1/NB2)仍需人工,贯穿 S03–S05。
- 真实调用开关默认关闭,生产接入边界由人工授权。

## 可复现验证说明

- 4 份 .md 产物存在,各自「自检 (acceptance)」全勾。
- 节点状态可经读取 `...-s02-architecture.task_graph.json` node_results 复核(A1–A4=reviewing)。
- 架构切片无代码,无测试可跑;符合「架构切片,不写实现代码」定位。

## Scope Compliance

- 仅写入各节点 write_scope 指定文件(architecture/interface-contracts/failure-recovery/compat-migration/handoff)。
- 仅读取 epic 三件套、S01 三产物、S02 PRD/contract/task_graph(read_scope 内)。
- **scope 冲突核对: 无冲突**(A4),故未回写父级 traceability.json。

## Not Done / 边界声明

- 本切片 ≠ 父 Epic 完成;仅完成架构设计。
- 未实现任何代码(S03/S04)、未做端到端验证(S05)。
- 重试默认值、凭证/合规、真实调用开关为显式遗留,转下游与人工。

状态: A4 置 reviewing,交 evaluator。本切片为架构文档,**不声称**父 Epic 已跑通。
