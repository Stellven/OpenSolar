# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束`
sprint_id: `sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements`
slice: `requirements`

## 用户原始需求

# P0 修复单：把 capability/risk/cost 三张画像从配置层升级为 runtime 强约束

## 背景
当前 solar-harness 已经有：
- `agent-actors.schema.json` 中的 `capability_profile` / `risk_profile` / `cost_profile`
- `agent-actors.json` 中的画像实例
- `logical-operators.json` 中的 `required_capabilities` / `risk_constraints` / `cost_hint`
- `actor_profiles.py` 中的局部 `check_risk_denial()` / `check_cost_reserve()`
- `logical_operator_router.py` 中的 `quota_blocked` / `risk_denied` 过滤入口
- `operator_score.py` 中的 `RiskFit` / `CostFit` 因子定义

但当前仍存在明显缺口：
1. `operator_score.rank_actors()` 实际只吃 `task_fit` 和 `historical_success`，没有根据 actor 的 risk/cost profile 计算真实 `RiskFit` / `CostFit`。
2. `logical_operator_router.select_actor()` 只消费外部传入的 `quota_blocked` / `risk_denied` 集合，没有自己基于 logical operator 的 `risk_constraints` / `cost_hint` 与 actor profiles 做主判定。
3. schema 粒度还不够：
   - `risk_profile.allowed_write_scope` 只有 `harness|harness_readonly|project|denied`，没有 `patch_only`
   - `allowed_shell_scope` 没有 `repo_local`
   - `allowed_network` 没有 `docs_only`
   - `allowed_secrets` 没有严格的 `none`
   - `cost_profile.cost_tier` 没有 `premium`
   - `token_budget_class` 没有 `expensive`
   - `effort` 只有 `light|medium|heavy`，没有 `low|medium|high|xhigh|max`
4. handoff 已明确记录“policy blocks / premium reservation / runtime enforcement still pending or partially pending”，说明配置和设计先到了，但主 runtime 没完全收口。

## 用户要求
把模型/算子强制拆成三张画像，并让 DAG/调度器真正基于它们做自动选算子与安全约束：

### 1. Capability Profile
至少支持：
- architecture_reasoning
- code_impl
- root_cause_debug
- test_generation
- test_execution
- research_synthesis
- academic_critique
- browser_use
- gui_use
- long_context
- multi_agent_coordination
- speed

### 2. Risk Profile
至少支持表达：
- allowed_write_scope: `patch_only` 等更细粒度值
- allowed_shell_scope: `repo_local`
- allowed_network: `docs_only`
- allowed_secrets: `none`
- destructive_actions
- git_commit
- git_push
- payment_or_external_action
- requires_human_for[]

要求：不能只靠 prompt 说“别乱动”，必须由 runtime policy / selection / lease acquisition gate 做硬阻断。

### 3. Cost Profile
至少支持表达：
- cost_tier: `premium`
- token_budget_class: `expensive`
- quota_period
- reserve_ratio
- effort: `low|medium|high|xhigh|max`
- prefer_for[]
- avoid_for[]

要求：调度器知道高成本强模型只该留给高价值任务，如 ARCH_DESIGN / ROOT_CAUSE_DEBUG / FINAL_REVIEW，不应用于 BULK_DOC_EDIT / TRIVIAL_RENAME / GREP_SCAN。

## 必须修复的点
### S01 Requirements
- 明确 capability/risk/cost 三张画像的目标 schema
- 定义 logical operator 如何提出 `required_capabilities`、`risk_constraints`、`cost_hint`、`effort_hint`
- 定义 compatibility 迁移策略，不破坏现有 actor fixture

### S02 Architecture
- 扩展 `agent-actors.schema.json` 与相关 registry schema
- 让 risk/cost taxonomy 对齐目标值：`patch_only` / `repo_local` / `docs_only` / `none` / `premium` / `expensive` / `xhigh|max`
- 设计从 logical operator 约束到 actor selection 的完整判定链

### S03 Core Runtime
- `operator_score.rank_actors()` 必须真正计算 `RiskFit` / `CostFit`
- `logical_operator_router` 必须能直接读取 actor profiles + logical operator constraints 决策
- risk gate 必须在 lease acquisition / submit 前形成硬阻断
- reserve_ratio / prefer_for / avoid_for / effort 必须进入真实路由与 fallback
- premium/high-effort actor 不得被 trivial 低价值任务错误占用

### S04 Observability/UI
- 状态页/审计输出中明确展示 capability/risk/cost 摘要
- 明确显示因 `risk_denied` / `quota_reserved` / `cost_avoid` / `effort_mismatch` 被拒绝的原因

### S05 Verification
至少补齐以下验收：
1. 高价值任务可优先选到 premium/high-effort actor
2. `BULK_DOC_EDIT` / `TRIVIAL_RENAME` / `GREP_SCAN` 默认不会选 premium actor
3. `git_push` / destructive / payment / raw_secret_access 等任务会被 risk profile 阻断
4. changing actor binding/profile without editing DAG node 仍能改变选路
5. OperatorScore 输出 machine-readable explanation，能看到 RiskFit / CostFit 分数来源

## 关键证据位置
- `/Users/lisihao/Solar/harness/config/agent-actors.schema.json`
- `/Users/lisihao/Solar/harness/config/agent-actors.json`
- `/Users/lisihao/Solar/harness/config/logical-operators.json`
- `/Users/lisihao/Solar/harness/lib/actor_profiles.py`
- `/Users/lisihao/Solar/harness/lib/logical_operator_router.py`
- `/Users/lisihao/Solar/harness/lib/operator_score.py`
- `/Users/lisihao/Solar/harness/sprints/sprint-20260523-lease-based-model-fleet-runtime/sprint-20260523-lease-based-model-fleet-runtime.handoff.md`

## 优先级
P0

## 期望结果
让三张画像不再只是 registry 描述，而成为：
- 调度选择依据
- 风险硬门禁
- 成本/配额保留机制
- fallback 与 explainable audit 的核心输入

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束.epic.md`、`epic-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements.design.md`
- `sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements.plan.md`
- `sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements.task_graph.json`
- `sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements.handoff.md`
- `sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements.eval.md` 或 `sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements.eval.json`
