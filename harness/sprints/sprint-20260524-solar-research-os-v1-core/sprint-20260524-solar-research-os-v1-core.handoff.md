# solar-harness Handoff — sprint-20260524-solar-research-os-v1-core

## Goal

Planner 已完成本 sprint 的实现收敛。后续执行必须从 `task_graph.json` 启动，按 P0 -> P1 -> P2 -> P3 顺序推进，不允许再回到 raw request 粗派发。

## Read First

- [requirement_ir.json](/Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.requirement_ir.json)
- [prd.md](/Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.prd.md)
- [contract.md](/Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.contract.md)
- [design.md](/Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.design.md)
- [plan.md](/Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.plan.md)
- [task_graph.json](/Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.task_graph.json)

## Execution Order

1. 先执行 `N1` 现状审计，确认 builder 文件边界。
2. 优先完成 `N2` P0 默认可靠修复。
3. `N3-N5` 是 v1 Core 主壁垒，优先级高于图表和 future seams。
4. `N6-N7` 只做 minimum viable path / seam，不得拖垮主链。
5. `N8` 负责最后 requirement coverage、测试和 rollout handoff。

## Constraints

- Requirement IR 仍是需求真值。
- `task_graph.json` 是机器执行真值。
- 不允许绕过 final closeout / evidence / citation policy。
- 不允许把未来平台化内容塞回本 sprint 的 P0/P1 主线。

## Acceptance

- graph-scheduler validate 必须 `ok=true`
- planner artifacts 已齐全：`design.md + plan.md + task_graph.json`
- builder 从 `N2` 开始推进，不允许 raw request 直派 builder
