# Contract: Pane-as-Physical-Operator Architecture

Sprint: `sprint-20260523-pane-as-physical-operator-architecture`

## Objective

把 Solar-Harness 对 tmux 无头 pane 的使用方式，从“后台终端窗口管理”正式提升为“Physical Operator Runtime”。

## Hard Rules

- 使用 Solar 本地 context 作为默认背景，但不要盲从历史方案。
- 正式调度单位必须是 `operator_id`，不是 provider/model/profile 字符串。
- 不允许在任务执行中临时切模型、切 wrapper、切 auth。
- 不允许写入 raw secret、token、cookie、OAuth 内容。
- 不允许 kill 无关 tmux pane 或删除历史 task 目录。
- 不允许破坏现有 DAG / graph-dispatch / evaluator 流程。
- 不允许让 builder/evaluator 直接绕过 planner artifacts。

## Required Deliverables

```text
┌────────────┬──────────────────────────────────────────────────────┐
│ deliverable│ path / expectation                                   │
├────────────┼──────────────────────────────────────────────────────┤
│ design     │ 明确三层架构、状态机、绑定边界、迁移边界             │
│ plan       │ 拆成可实施的 workstreams 和 rollout 顺序             │
│ task_graph │ 可由 graph scheduler 执行的正式 DAG                  │
│ validation │ graph validate + targeted tests + evidence           │
│ report     │ 风险、兼容、fallback、剩余缺口                       │
└────────────┴──────────────────────────────────────────────────────┘
```

## Mandatory Design Decisions

1. `tmux pane` 是 operator physical host，不是独立调度真值。
2. `preferred_operator` 保留为硬指定覆盖。
3. 逻辑调度必须优先表达为：
   - `task_type`
   - `required_capabilities`
   - `preferred_operator_classes`
   - `constraints`
4. `writer` 与 `verifier` 在要求审查时不能是同一个 `operator_id`。
5. quota reserve 要保护高价值任务：
   - `ARCH_DESIGN`
   - `ROOT_CAUSE_DEBUG`
   - `FINAL_REVIEW`
6. registry 中 secret 只能以 `secret_ref` / `key_env` 形式存在。
7. 运行中模型漂移视为 contract violation，不得成为“灵活性”借口。

## Scope

### In Scope

- operator registry 正式字段定版
- operator runtime 生命周期/lease/state 统一
- scheduler 逻辑选择 operator 的规范
- observability / alerts / recent results 总览
- migration / compatibility / rollout strategy

### Out of Scope

- 一次性删除所有 legacy profile 路由
- 一次性启用全部 disabled operator
- 在本 sprint 中完成所有 provider 真执行器重写

## Safety

- No production auto-apply outside sprint scope.
- No secret material in artifacts.
- No silent fallback that hides runtime drift.
- No “task 内临时切模型” escape hatch.

## Planner Done Definition

- `design.md` 清楚回答 Registry / Runtime / Scheduler 分层。
- `plan.md` 明确 rollout 顺序、兼容策略和 failure transfer。
- `task_graph.json` 每个节点都写清：
  - `goal`
  - `depends_on`
  - `write_scope`
  - `required_skills`
  - `acceptance`
- 所有关键风险有 stop rules。

## Acceptance Gates

- 缺 `task_graph.json` 不得派 builder。
- 缺 migration/fallback 章节不算设计完成。
- 缺 secret/quota/policy 约束不算架构完成。
- 缺 tmux physical host 与 operator binding 说明不算定版完成。
