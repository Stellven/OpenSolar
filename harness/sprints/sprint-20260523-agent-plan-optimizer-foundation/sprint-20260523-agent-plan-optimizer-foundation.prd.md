# PRD: Agent Plan Optimizer Foundation

Sprint: `sprint-20260523-agent-plan-optimizer-foundation`
Priority: `P0`
Lane: `strategy`
Handoff To: `planner`
Created: `2026-05-24T03:19:23Z`
Dependency: `blocked_by [requirement-compiler-backend-foundation, requirement-compiler-quality-loop]`

## 背景 / Context

Solar-harness 经过过去几周的演进，已经形成了一套相对完整的"底层执行能力栈"：

- **operator**（物理算子）— pane-as-physical-operator 架构定版（父 sprint `sprint-20260523-pane-as-physical-operator-architecture`）
- **lease / quota / capability profile** — `operator_runtime.py` + `operatord.py` + `physical-operators.json`
- **evidence ledger** — sprint events.jsonl + accepted artifacts + sqlite
- **operator taxonomy**（10 类执行算子）— `sprint-20260523-physical-operator-taxonomy-truthification`
- **compatibility cutover**（legacy ↔ canonical）— `sprint-20260523-operator-class-compatibility-cutover`
- **completion audit**（13 升级点核查）— `sprint-20260524-actor-host-runtime-completion-audit`
- **Requirement Compiler v1**（PM pane 升级为 IR-driven 编译器）— `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`（in-flight）

但这些组件加起来还停留在 **"更精细的调度器"** 层面，没有上升到 **优化器** 层面。具体差距：

- 系统能 "选对一个 operator"，但不能 "枚举多个等价计划再选最佳"
- 系统能 "按 capability 过滤"，但没有 cost / risk / quota / verifier 的统一 cost model
- 系统能 "失败重试"，但不能 "运行时根据反馈做 adaptive replan"
- 系统能 "派单"，但不能 "explain why this plan was chosen / why alternatives rejected"

数据库领域 30 年前就用 **Volcano / Cascades / Calcite** 的 logical-to-physical 优化器解决了同类问题；Spark AQE 把 runtime feedback 用在 plan rewrite 上。本 sprint 把这套优化器思路迁移到 agent planning 层，让 Solar-harness 从 **scheduler** 升级到 **APO (Agent Plan Optimizer) / AQO (Agent Query Optimizer)**。

**关键时序约束**：本 sprint 必须 **等待 2 张前序 Requirement Compiler sprint 完成** 后才能进入 planner/builder 开发：
- `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`（Requirement IR 编译底座）
- `sprint-20260523-requirement-compiler-quality-loop`（编译质量回环）

否则会出现编译层和优化器层并行施工 → 不稳定的输入层被固化为优化器接口 → 后续返工成本极高。

参考资产：
- Calcite Volcano/Cascades planner（logical-to-physical 枚举 + cost-based 选择）
- Spark AQE（runtime statistics → adaptive plan rewrite）
- DuckDB optimizer（轻量、规则驱动、可解释）
- DSPy / GEPA（agent prompt/plan optimization，已 accepted `sprint-20260522-gepa-optimize-anything-implementation`）

## 0. 执行摘要

这张单的目标不是再做一个 scheduler，而是把 Solar-harness 升级为 **APO / AQO**：

```text
APO = Agent Plan Optimizer
AQO = Agent Query Optimizer
```

核心价值：

```text
User Goal
  -> Intent IR
  -> Logical Agent Plan
  -> Rule Rewrite
  -> Physical Plan Enumeration
  -> Cost / Risk / Quota Optimization
  -> Lease-based Execution
  -> Runtime Feedback / Adaptive Re-Optimization
```

这张单必须 **等待前序两张 Requirement Compiler 相关 sprint 完成后再进入正式 planner/builder 开发**，避免编译层和优化器层并行施工造成链路冲突：

- `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`
- `sprint-20260523-requirement-compiler-quality-loop`

## 1. Problem
当前 Solar-harness 在 operator、pane、lease、quota、capability profile、evidence ledger 这些底层能力逐步补齐后，已经不该再只被定义为“调度器”。

P0 目标是把它升级成真正的 **Agent Plan Optimizer**：

- 把自然语言任务编译成 `Intent IR`
- 把任务抽象成 `Logical Agent Plan`
- 用规则系统做 rewrite
- 枚举 physical operators 与 enforcers
- 基于 cost / risk / quota / evidence 选择计划
- 在运行时根据测试、benchmark、quota、verifier 结果做 adaptive replan

可借鉴方向：

- Calcite / Volcano / Cascades 的 logical-to-physical optimization
- Spark AQE 的运行时重优化
- plan caching / memoization

## 2. Users / Stakeholders
- PM
- Planner
- Builder
- Evaluator

## 用户故事 / User Stories

> 用户 = Solar-Harness 内部角色 + 人类操盘者 + 下游 sprint 设计者。

- **US1 — 作为 Planner**，我希望接到一个 task / IR，能让 APO 枚举至少 2-3 个等价 logical plan，再按 cost / risk / quota / verifier 选最优 — 而不是只产出"唯一确定方案"。
- **US2 — 作为 Builder / 执行 operator**，我希望当我的 lease 失败 / quota 耗尽 / verifier reject 时，系统能基于运行时反馈做 local replan（AQE 风格），而不是把整个 plan 推倒重来。
- **US3 — 作为 Evaluator**，我希望每个被派发的 plan 都附 explain — 为什么选这个 plan、为什么拒绝其他候选 — 这样我能审"选择是否合理"，而不是只审"执行结果"。
- **US4 — 作为人类操盘者**，我希望我能用 `solar-harness optimize explain <task>` CLI 看到 logical plan、candidates、cost vector、selected plan、why，全可读、可对比、可 replay；不需要看代码就能判断 APO 是否走偏。
- **US5 — 作为 PM / 上游需求方**，我希望我从 Requirement Compiler 输出的 IR 能直接喂给 APO，不需要重新人工编译；IR → Intent IR → Logical Plan 的边界清晰。
- **US6 — 作为下游 sprint 设计者**，我希望 APO 的 Explain Plan / Candidates / Replay / Why 4 个接口在本 sprint 就有 contract 草案，让我后续做 UI / dashboard / learned optimizer 都能锚定。
- **US7 — 作为安全/合规守门人**，我希望 enforcer 系统（VerifyAfterWrite / WriterVerifierSeparation / SandboxEnforcer / QuotaReserve）是 plan-time 硬注入，不是 runtime soft-check — high-risk task 不能因为 cost 低就跳过 verifier。
- **US8 — 作为 Research mode 用户**，我希望 APO 知道我这个任务是 research-type（来自 Requirement Compiler classification），自动启用 Exploratory 模式 + 强制 evidence ledger，不需要我每次手动声明。

## 3. Goals / Non-goals
Goals:
- 定义 APO/AQO 的产品定位、架构边界与命名。
- 定义 `Intent IR -> Logical Plan -> Physical Plan -> Runtime Re-Optimization` 的 P0 链路。
- 定义 Agent Logical Algebra、rule engine、cost model、enforcers、plan memo。
- 复用现有 operator/pane/lease/quota/capability/evidence/Requirement Compiler，不另起第二套 runtime。
- 首版只做 heuristic optimizer，不直接上 learned optimizer。
- 输出 Explain Plan / candidates / replay / why 这类可解释接口草案。

Non-goals:
- 不在本单里重写 Requirement Compiler。
- 不在本单里直接实现 learned optimizer。
- 不在本单里绕过前序 sprint 直接进 builder。

## 4. User Scenarios
用户目标不再直接映射成“把任务派给哪个 pane”，而是：

1. 先被编译成 logical plan
2. 再被 rewrite 成更稳的等价计划
3. 再枚举 physical operators / enforcers
4. 再按质量、成本、风险、额度选出执行计划
5. 失败后局部 replan

## 5. Functional Requirements
- 定义 Agent Logical Algebra：
  - `ScanContext`
  - `UnderstandGoal`
  - `DecomposeTask`
  - `DesignSolution`
  - `ExploreAlternatives`
  - `ImplementPatch`
  - `GenerateTests`
  - `RunTests`
  - `RunBenchmark`
  - `DebugRCA`
  - `ReviewPatch`
  - `VerifyClaim`
  - `SynthesizeReport`
  - `CompressContext`
  - `AskHuman`
- 定义 rewrite rules：
  - LocalPreScan
  - FanOutExploration
  - VerifyAfterWrite
  - WriterVerifierSeparation
  - QuotaReserve
  - SandboxEnforcer
  - ContextMaterialization
  - AdaptiveReplan
- 定义 cost model：
  - capability_fit
  - historical_success
  - quota_health
  - risk_fit
  - latency_fit
  - context_affinity
  - cost_efficiency
  - recent_failure_penalty
  - stale_context_penalty
  - verifier_conflict_penalty
- 定义 3 种运行模式：
  - Conservative
  - Exploratory
  - Economy
- 定义 Explain / Optimize / Run / Candidates / Replay 接口草案。

## 6. Non-functional Requirements
- 可解释：必须能 explain why a plan was selected
- 可回放：支持 replay / compare / candidates
- 可追溯：plan / evidence / verifier / runtime feedback 均可落 ledger
- 与现有 PM -> Planner -> Builder 主链兼容
- 不与前序 Requirement Compiler 开发链路冲突

## 7. UX / Interaction Model
首批仅提供编译结果视图与 handoff bar，不重做完整 UI。

## 8. Data Model
P0 需要定义的数据层：

- `Intent IR`
- `Logical Agent Plan`
- `Physical Agent Plan`
- `PlanMemo`
- `Runtime Feedback Record`
- `ExplainPlan`

## 9. Acceptance Criteria
- APO/AQO 的逻辑层、物理层、rule engine、cost model、enforcer、memo、adaptive replan 都有正式 contract。
- 首版明确是 heuristic optimizer，不误报为 learned optimizer。
- 明确声明依赖 Requirement Compiler 完成后再接入 planner/builder 主链。
- Explain Plan 输出结构完整，可回答 why selected / why rejected。

## 10. Risks / Open Questions
- [high] 前序 Requirement Compiler 未完成时，直接做 optimizer 会把不稳定输入层固化成优化器接口 -> 本单必须 blocked by 前序 sprint。
- [high] 过早引入 learned optimizer，数据不足导致过拟合 -> P0 只做 heuristic optimizer。
- [medium] 逻辑计划和物理计划边界不清 -> 强制 logical algebra / physical operator / enforcer 三层分离。
- [medium] runtime state 污染 plan spec -> 单独定义 runtime feedback / state artifact。

Open Questions:
- APO 的首版 explain 接口是 CLI-only 还是也要出 status/UI 视图？
- PlanMemo 是 repo-local 先做，还是 fleet-global？
- adaptive replan 的 stop rule 是按 node、plan 还是 verifier confidence？

## 11. Release Plan
先完成 Requirement Compiler 基础层，再启动 APO 的 planner/builder 实现；首版先交付 optimizer contracts、logical algebra、cost model、rule engine、explain CLI 和 replay scaffolding，再逐步扩展 learned cost model 与 runtime adaptation。

## 约束 / Constraints

| ID | 约束 | 说明 |
|----|------|------|
| C1 | **必须等前序 2 张 Requirement Compiler sprint 完成** | 在 `requirement-compiler-backend-foundation` + `requirement-compiler-quality-loop` 都进入 `accepted/finalized` 之前，本 sprint 保持 `status=queued, phase=epic_waiting_dependency`；不允许 planner / builder 提前开工 |
| C2 | 不另起第二套 runtime | 复用现有 operator / pane / lease / quota / capability / evidence 真值；APO 只在它们之上加 logical/physical/rewrite/cost 层 |
| C3 | 不破坏现有 API 接口 | `operator_runtime` / `operatord` / `graph_node_dispatcher` / `status-server` 调用方向后兼容；只扩字段不改语义 |
| C4 | 不直接上 learned optimizer | 首版必须是 deterministic heuristic（cost model 系数可手调，可单元测试）；ML / LLM-based ranking 推到下一代 |
| C5 | logical / physical / enforcer 三层严格分离 | logical algebra 不引用 operator_id；physical plan 不写自然语言；enforcer 是 plan-time 注入，不是 runtime soft-check |
| C6 | runtime state 不污染 plan spec | 运行态写 `task_dag.state.json` / `runtime_feedback.jsonl`；plan spec（logical + physical）保持 declarative |
| C7 | macOS arm64 + bash 5.3.9 + Python stdlib | 禁止新 PyPI 依赖；cost model / rule engine 用 Python stdlib + JSON Schema |
| C8 | 不写 /tmp | plan memo / explain artifact 落 `~/.solar/harness/sprints/<sid>.plan-memo/` 或 sprint 目录 |
| C9 | 不动 in-flight sprint | 父 / 兄弟 sprint 仍在跑；APO 不持其 lock，不 mutate 其 artifact，不读其 secret |
| C10 | secret 不入 plan | logical / physical plan / cost model / explain 一律不允许写 raw key/token；只允许 `secret_ref`（沿用父 sprint 红线） |
| C11 | enforcer 不可绕过 | high-risk task（Browser / Google-stack / LocalPrivacy / payment / secret-form-fill）的 enforcer 是 plan-time 硬约束；任何 "cost 太高跳过" 视为违规 |
| C12 | adaptive replan 必须有 stop rule | 不允许无限 replan；每个 plan 必须声明 max_replan_rounds + max_total_cost + verifier_confidence_threshold；触发任一即停 |
| C13 | Explain 必须可机读 | Explain Plan 输出必须有 schema（JSON / YAML）；不允许 prose-only；让 evaluator / dashboard / replay 都能消费 |
| C14 | 不引入新进程模型 | 不允许 systemd / launchd / Docker / k8s；继续走 `solar-harness` CLI + tmux pane + sqlite + plan memo 文件 |

## 12. Dependency Gate

这张单在前序两张单完成前必须保持：

```text
status = queued
phase  = epic_waiting_dependency
```

Blocked by:

- `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`
- `sprint-20260523-requirement-compiler-quality-loop`

## 架构交接 / Planner Handoff

**Handoff Target**: `pane 0 (planner, opus)` + `pane 3 (architect, opus)` 二审
**Handoff Mode**: 正式 `PM → Planner`，但 **Planner 不立即开工**，先确认 2 张前序 sprint 状态
**Dependency Gate**: 前序 sprint 全部 finalized 之前，本 sprint 保持 `status=queued, phase=epic_waiting_dependency`
**Stop Rules**: 前序解锁后 → Planner 产出 `design.md + plan.md + task_graph.json + algebra-spec.md + cost-model-spec.md + explain-schema.json` 六件套通过 → `planning_complete`

### 强制 Planner 回答的设计点

1. **Logical Algebra Lock** — 把 PRD §5 列出的 15 个 logical operator（ScanContext / UnderstandGoal / DecomposeTask / DesignSolution / ExploreAlternatives / ImplementPatch / GenerateTests / RunTests / RunBenchmark / DebugRCA / ReviewPatch / VerifyClaim / SynthesizeReport / CompressContext / AskHuman）正式定义为 `agent-logical-algebra.schema.json`；明确每个 operator 的 input / output / properties / cost-hints；与 task_type taxonomy 的映射关系
2. **Rewrite Rule Engine Lock** — 把 PRD §5 列出的 8 条 rule（LocalPreScan / FanOutExploration / VerifyAfterWrite / WriterVerifierSeparation / QuotaReserve / SandboxEnforcer / ContextMaterialization / AdaptiveReplan）正式定义为 `rewrite-rules-v1.yaml`；每条 rule 写：trigger 条件 / pattern match / rewrite action / cost delta / safety class；明确哪些是 P0 必须、哪些 P1 可选
3. **Cost Model Lock** — 10 项 cost vector（capability_fit / historical_success / quota_health / risk_fit / latency_fit / context_affinity / cost_efficiency / recent_failure_penalty / stale_context_penalty / verifier_conflict_penalty）的 **可手算公式**；各项权重默认值 + 3 种模式（Conservative / Exploratory / Economy）的权重 profile；明确数据来源（哪个 sqlite 表 / 哪个 evidence ledger 字段）
4. **Physical Plan Enumeration Lock** — logical operator → physical operator 的展开规则；何时枚举多 candidate / 何时单 candidate；plan memo 缓存策略（key / TTL / invalidation）；与 operator taxonomy 10 类的对接点
5. **Adaptive Replan Lock** — runtime feedback triggers（lease failed / quota exhausted / verifier rejected / test failed / benchmark regressed）；replan scope（local node / sub-plan / full plan）；stop rule（max_replan_rounds / max_total_cost / verifier_confidence_threshold）
6. **Explain Plan Schema Lock** — `explain-schema.json` 必须包含：selected_plan / candidates / cost_vectors / rewrite_trace / rule_firings / why_selected / why_rejected / replan_history；可由 `solar-harness optimize explain <task>` 输出

### 必备产出物

| 产出 | 路径 | 验收方 |
|------|------|--------|
| `design.md` | `~/.solar/harness/sprints/sprint-20260523-agent-plan-optimizer-foundation.design.md` | evaluator + architect 二审 |
| `plan.md` | `~/.solar/harness/sprints/...plan.md` | evaluator |
| `task_graph.json` | `~/.solar/harness/sprints/...task_graph.json` | `solar-harness graph-scheduler validate` |
| `agent-logical-algebra.schema.json v1 草案` | `~/.solar/harness/schemas/agent-logical-algebra.schema.v1.draft.json` | evaluator + architect |
| `rewrite-rules-v1.yaml 草案` | `~/.solar/harness/schemas/rewrite-rules.v1.draft.yaml` | evaluator + architect |
| `cost-model-spec.md`（10 项 cost + 3 模式权重 + 公式） | `~/.solar/harness/sprints/...cost-model-spec.md` | evaluator + architect |
| `explain-schema.json v1 草案` | `~/.solar/harness/schemas/explain-plan.schema.v1.draft.json` | evaluator |
| `dependency-gate-evidence.md`（证明 2 张前序 sprint 已 finalized） | `~/.solar/harness/sprints/...dependency-gate-evidence.md` | PM + evaluator |

### task_graph.json 必须满足

- 每 node 写 `task_type` + `required_capabilities` + `preferred_operator_classes`，不写 model 字符串
- 至少 6 个 workstream node：
  - N0: dependency_gate_check（证明 2 张前序 sprint finalized）
  - N1: Logical Algebra Schema
  - N2: Rewrite Rule Engine
  - N3: Cost Model + 3 模式
  - N4: Physical Plan Enumeration + Plan Memo
  - N5: Adaptive Replan + Runtime Feedback
  - N6: Explain Plan Schema + CLI scaffolding
- N0 必须是 N1-N6 全部的 hard dependency（前序未解锁就 fail-loud，不允许跳过）
- 每 node 满足 `verifier_operator_class != writer_operator_class`
- 1 个 sink node 做 `end-to-end-smoke`：用一个真实任务跑通 IR → Logical Plan → Rewrite → Physical Plan → Explain（不需要真派发，只验证 plan-time 链路）

### Stop Rules

- **STOP-A**：前序 2 张 sprint 任一未 finalized 时，planner / builder 不允许动手；只能在 PRD / handoff 写"等 X 完成"，不能开 design.md
- **STOP-B**：round 3 仍未产出 6 件套 → PM 介入缩范围（可砍 N5 adaptive replan 推到下一 sprint）
- **STOP-C**：Logical Algebra 与现有 operator taxonomy 严重冲突无法调和 → 升级 architect (pane 3) 二审
- **STOP-D**：Cost Model 公式无法 deterministic（必须靠 LLM）→ 停下重评 C4 红线
- **STOP-E**：发现某 enforcer（如 SandboxEnforcer）在现有 runtime 没有 hook 点 → flag 为 P1 follow-up，不在本 sprint 自己加 hook（守 C2）

### Non-Negotiables (PM 红线)

- 不允许 Planner 在前序 sprint finalized 前开 design.md（C1 + STOP-A）
- 不允许 Planner 把 cost model 外包给 LLM ranking（C4）
- 不允许 Planner 把 logical algebra 写成 prose（必须 schema-driven）
- 不允许 Planner 把 enforcer 标为 "best-effort" 或 "可绕过"（C11）
- 不允许 Planner 跳过 architect (pane 3) 二审直接交付（APO 是策略层，需要 opus 判断力）

### Knowledge Context

Knowledge Context: `solar-harness context inject` used (mirage nonzero，QMD/Solar DB/Obsidian Vault 命中)
Harness Modules Used: `harness-knowledge`（context inject）, `harness-graph`（dependency gate），`Superpowers`（systematic planning + TDD for algebra/cost model unit tests）
ACK File: `~/.solar/harness/sprints/sprint-20260523-agent-plan-optimizer-foundation.ack-d-20260524T033142Z-735f99.json`
Blocked-By: `sprint-20260523-pm-pane-requirement-compiler-backend-foundation` + `sprint-20260523-requirement-compiler-quality-loop`
