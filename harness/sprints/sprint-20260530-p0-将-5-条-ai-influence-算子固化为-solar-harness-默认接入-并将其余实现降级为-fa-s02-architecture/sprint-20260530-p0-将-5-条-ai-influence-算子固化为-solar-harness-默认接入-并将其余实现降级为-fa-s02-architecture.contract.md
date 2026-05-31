# Contract: 架构设计与接口契约

priority: `P0`
epic_id: `epic-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa`
sprint_id: `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s02-architecture`
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

## Definition of Done (Planner — Quantified)
- [ ] D1: 9 个 operator 文件的现状审计表完成（接口签名、输出格式、依赖关系）
- [ ] D2: 系统分层设计覆盖 control plane（operator registry + routing）和 data plane（产物流）
- [ ] D3: Primary/Fallback/Executor 配置 schema 定义完成，每个角色有明确的行为契约
- [ ] D4: 统一输出 schema 定义完成（report + raw + metadata/status + log/diagnostic）
- [ ] D5: /ai-influence 状态页数据模型设计完成（6 区块 + GitHub 对照展示）
- [ ] D6: 兼容策略和迁移方案文档化（旧接口保留期、退役条件、回滚策略）
- [ ] D7: handoff.md 写明设计决策、接口边界、S03/S04 下游影响和 open questions
