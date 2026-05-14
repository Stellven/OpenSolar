# Contract: 验证、回归与发布证据

priority: `P0`
epic_id: `epic-20260513-solar-deepresearch-product-line`
sprint_id: `sprint-20260513-solar-deepresearch-product-line-s05-verification-release`
handoff_to: `planner`

## Intent

建立端到端测试、负控、回归报告、文档和验收证据，防止半截完成。

## Required Capabilities

- evaluation
- testing
- documentation

## Acceptance

- 单测、集成测、负控和 activation-proof 全部可复现
- 父 epic 不能在所有 required gate 通过前关闭
- 产出最终 handoff/eval/report 并写入知识库 raw

## Stop Rules

- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突必须回写父级 traceability。
