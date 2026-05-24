# Contract: Physical Operator Taxonomy Truthification

Sprint: `sprint-20260523-physical-operator-taxonomy-truthification`

## Objective

把 `Pane-as-Physical-Operator` 的 10 类 taxonomy 从 PM addendum 物化为 schema / routing matrix / DAG acceptance 真值。

## Parent Context

- Parent sprint: `sprint-20260523-pane-as-physical-operator-architecture`
- Parent gap: taxonomy 方向已理解，但未完整进入 planner 真值

## Hard Rules

- 使用 Solar 本地 context 作为默认背景，但不要盲从已有粗粒度角色桶。
- 不允许把 taxonomy 简化回 `planner/builder/evaluator/architect/external` 这类旧分法就算完成。
- 不允许直接篡改父 sprint 已完成的 planner artifacts。
- 不允许把 provider/model 枚举伪装成 taxonomy 主轴。
- 不允许在 DAG 节点里直写 `model/provider/profile` 作为正式调度真值。
- 不允许忽略 Browser / Google-stack / Local Privacy 的专门 policy 边界。
- 不允许让 writer/verifier separation 脱离 taxonomy 单独存在。
- 不允许继续使用含糊 runtime state；pane/operator lifecycle 必须是显式有限状态机。
- 不允许 pane 直接裸跑底层 CLI；正式链路必须通过 `operatord run <operator_id>`。
- 不允许直接给 pane 塞自然语言任务；正式执行必须通过结构化 task envelope。
- 不允许写入 raw secret、token、cookie、OAuth 内容。

## Required Deliverables

```text
┌───────────────┬─────────────────────────────────────────────────────────────┐
│ deliverable   │ path / expectation                                          │
├───────────────┼─────────────────────────────────────────────────────────────┤
│ design        │ taxonomy 真值化设计：class/matrix/policy/routing           │
│ plan          │ rollout / repair / compatibility 顺序                      │
│ task_graph    │ 至少覆盖 taxonomy/schema/scheduler/safety/repair 节点      │
│ matrix        │ 10 类 operator taxonomy 对照矩阵                           │
│ validation    │ graph validate + parent gap mapping + residual risks        │
│ report        │ 哪些进 P0，哪些保留为 future follow-up                      │
└───────────────┴─────────────────────────────────────────────────────────────┘
```

## Mandatory Design Decisions

1. 一级 taxonomy 必须按执行角色 / 任务语义建模。
2. provider/model/surface 只能是 implementation binding，不是 taxonomy 主轴。
3. `task_type -> preferred_operator_classes -> fallback ladder` 必须是机器可读真值。
4. DAG 节点必须优先表达逻辑算子需求：
   - `task_type`
   - `required_capabilities`
   - `constraints`
   - `preferred_operator_classes`
   - `verifier_required`
   不得以 `model=...` 代替。
5. 第一版 scheduler 必须给出 rule-based score / penalty 模型，不接受“强模型优先”式拍脑袋策略。
6. Runtime 必须有 canonical lifecycle：`CREATED -> WARMING -> IDLE -> LEASED -> RUNNING -> DRAINING -> IDLE`。
7. Runtime 必须显式定义异常状态：`ERROR / QUOTA_EXHAUSTED / AUTH_EXPIRED / COOLDOWN / DISABLED / STALE_CONTEXT / NEEDS_HUMAN_REVIEW`。
8. 每个 pane 的统一执行宿主必须是 `operatord run <operator_id>`。
9. `Task Envelope` 和 `Task Result` 必须是结构化 contract，不允许只有自由文本 prompt / handoff。
10. `Verifier Operator` 不能退化成泛泛 reviewer 概念，必须与 taxonomy / policy / provider separation 对齐。
11. `Browser / Computer-use`、`Google-stack`、`Local Privacy` 必须单列风险与权限边界。
12. 必须定义旧角色桶到新 taxonomy 的兼容映射。
13. 必须说明父 sprint 如何消费这张 follow-up 的结果，而不是造成双轨真相。

## Scope

### In Scope

- 10 类 operator taxonomy matrix
- schema 中 `operator_class` / `routing` / `policy` 的表达方式
- task_type 到 taxonomy 的调度规则
- DAG 逻辑算子需求 schema
- rule-based scheduler scoring / penalty 规则
- runtime lifecycle / dispatch-state machine
- operatord host shell / adapter boundary
- task envelope / result contract
- taxonomy 下的 verifier / quota / policy 规则
- 父 sprint repair / adoption 边界

### Out of Scope

- 立刻重写所有 provider 真执行器
- 立刻把所有现有 operator 重注册到生产配置
- 立刻删除旧角色字段

## Safety

- No retroactive mutation of parent planner truth without explicit repair rule.
- No raw secret material in any artifact.
- No provider-first taxonomy.
- No silent merge of high-risk operator classes into generic `external`.

## Planner Done Definition

- `design.md` 明确写出 10 类 taxonomy 是否全部进 P0，哪些是 reservation。
- `plan.md` 明确 parent sprint repair / adoption 路径。
- `task_graph.json` 每个节点都写清：
  - `goal`
  - `depends_on`
  - `write_scope`
  - `required_skills`
  - `preferred_operator_classes`
  - `acceptance`
- 至少有一个节点专门输出 taxonomy matrix。
- 至少有一个节点专门输出 scheduler mapping。
- 至少有一个节点专门输出 DAG 节点逻辑需求 schema / anti-model-binding 规则。
- 至少有一个节点专门输出 scheduler score / penalty 规则。
- 至少有一个节点专门输出 runtime lifecycle / state-transition / recovery 规则。
- 至少有一个节点专门输出 operatord host shell / adapter 契约。
- 至少有一个节点专门输出 task envelope / result contract。
- 至少有一个节点专门输出 safety/policy boundary。

## Acceptance Gates

- 缺 taxonomy matrix 不得算完成。
- 缺 `task_type -> operator_class ladder` 不得算完成。
- 缺 “DAG 不直写模型” 规则不算完成。
- 缺 score-based selection 规则不算完成。
- 缺 canonical lifecycle 与异常状态定义不算完成。
- 缺每个状态对应 dispatch 动作不算完成。
- 缺 `operatord run <operator_id>` 宿主契约不算完成。
- 缺结构化 task envelope / result contract 不算完成。
- 缺 Browser / Google-stack / Local Privacy 专门 policy 不得算完成。
- 缺旧角色桶兼容映射不算完成。
- 缺 parent repair / adoption 说明不算完成。
