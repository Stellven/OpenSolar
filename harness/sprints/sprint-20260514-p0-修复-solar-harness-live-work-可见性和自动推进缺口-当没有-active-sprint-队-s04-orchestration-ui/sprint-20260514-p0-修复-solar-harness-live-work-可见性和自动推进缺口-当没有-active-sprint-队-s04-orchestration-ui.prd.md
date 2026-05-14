# PRD: 调度、自动化与可视化

epic_id: `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队`
sprint_id: `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s04-orchestration-ui`
slice: `orchestration-ui`

## 用户原始需求

P0 修复 Solar-Harness live-work 可见性和自动推进缺口：当没有 active sprint、队列为空、pane idle 时，状态页和 autopilot 必须明确显示 no active work；当用户提交需求时必须自动进入 PM-first PRD 流程，并可从 status 看到 PM/Planner/Builder/Evaluator 的下一步，不允许静默空转或让用户误以为还在开发。

## 本切片目标

把核心能力接入 autopilot、DAG 调度、status UI、pane 可视化和运行时证据。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队.epic.md`、`epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- ready 子任务能自动激活并派到正确角色
- UI 显示 epic、child sprint、能力使用和阻塞原因
- pane 输出不再只靠自然语言声称完成

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s04-orchestration-ui.design.md`
- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s04-orchestration-ui.plan.md`
- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s04-orchestration-ui.task_graph.json`
- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s04-orchestration-ui.handoff.md`
- `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s04-orchestration-ui.eval.md` 或 `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s04-orchestration-ui.eval.json`
