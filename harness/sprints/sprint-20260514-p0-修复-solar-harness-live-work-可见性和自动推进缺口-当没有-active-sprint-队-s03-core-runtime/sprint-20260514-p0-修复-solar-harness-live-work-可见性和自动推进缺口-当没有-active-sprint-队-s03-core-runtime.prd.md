# PRD: 核心实现与数据模型

epic_id: `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队`
sprint_id: `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s03-core-runtime`
slice: `core-runtime`

## 用户原始需求

P0 修复 Solar-Harness live-work 可见性和自动推进缺口：当没有 active sprint、队列为空、pane idle 时，状态页和 autopilot 必须明确显示 no active work；当用户提交需求时必须自动进入 PM-first PRD 流程，并可从 status 看到 PM/Planner/Builder/Evaluator 的下一步，不允许静默空转或让用户误以为还在开发。

## 本切片目标

实现核心库、状态机、schema、持久化和向后兼容适配层。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队.epic.md`、`epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 核心 API 有单测覆盖
- 旧路径兼容，不破坏现有 wake/dispatch/status
- 状态变更可由元数据或事件重建

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s03-core-runtime.design.md`
- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s03-core-runtime.plan.md`
- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s03-core-runtime.task_graph.json`
- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s03-core-runtime.handoff.md`
- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s03-core-runtime.eval.md` 或 `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s03-core-runtime.eval.json`
