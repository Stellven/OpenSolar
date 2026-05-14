# Contract: 核心实现与数据模型

priority: `P0`
epic_id: `epic-20260513-solar-deepresearch-product-line`
sprint_id: `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime`
handoff_to: `planner`

## Intent

实现核心库、状态机、schema、持久化和向后兼容适配层。

## Required Capabilities

- python
- state-machine
- testing

## Acceptance

- 核心 API 有单测覆盖
- 旧路径兼容，不破坏现有 wake/dispatch/status
- 状态变更可由元数据或事件重建

## Stop Rules

- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突必须回写父级 traceability。
