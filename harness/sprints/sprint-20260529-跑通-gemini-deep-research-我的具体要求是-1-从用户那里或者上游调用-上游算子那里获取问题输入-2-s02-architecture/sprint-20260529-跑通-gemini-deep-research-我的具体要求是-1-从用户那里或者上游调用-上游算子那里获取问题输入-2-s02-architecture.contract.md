# Contract: 架构设计与接口契约

priority: `P0`
epic_id: `epic-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2`
sprint_id: `sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s02-architecture`
handoff_to: `planner`

## Intent

基于需求矩阵产出系统分层、接口、数据模型、兼容策略和迁移方案。

## Required Capabilities

- architecture
- distributed-systems

## Acceptance

- 设计覆盖 control/data plane、状态、失败恢复和观测
- 写清楚接口边界和旧系统兼容方式
- 列出冲突、依赖和降级策略

## Stop Rules

- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突必须回写父级 traceability。
