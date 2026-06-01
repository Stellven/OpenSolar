# Contract: 架构设计与接口契约

priority: `P0`
epic_id: `epic-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g`
sprint_id: `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s02-architecture`
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
- [ ] D1: Intelligence Pipeline 5 层架构图（数据源→发现→处理→存储→分析/输出）设计完成
- [ ] D2: 5 个数据源（GitHub REST/GraphQL、Events API、GH Archive、X/社媒、YouTube）接口契约定义
- [ ] D3: 4 个核心 schema 设计完成（Repo Master、Repo Snapshot、Evidence Atom、Analysis Card）
- [ ] D4: 评分引擎架构（Heat Score 6 因子 + 3 Detector）和归因模型（5 维）设计
- [ ] D5: Token 经济学架构（ThunderOMLX+Qwen 本地 → 云端高级推理）处理管道设计
- [ ] D6: 兼容策略 + 迁移方案文档化（与现有系统的接口边界、降级策略）
- [ ] D7: handoff.md 写明设计决策、接口契约、S03/S04 下游接口需求
