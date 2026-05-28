# PRD: 调度、自动化与可视化

epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui`
slice: `orchestration-ui`

## 用户原始需求

P0: Solar Harness TUI Pane Recover 与 Clean Pane 生命周期治理

背景：
当前 graph-dispatch/evaluator 仍以 Claude/GLM/Sonnet TUI pane 为主执行面。TUI 便宜、低开销、能直接使用 Coding Plan，因此继续保留。但当前 pane 会被 Do you want to proceed?、Press up to edit queued messages、权限确认、plan mode、残留 prompt 和跨任务上下文污染卡住，导致 cooldown、假并发和 evaluator 队列拖慢。

目标：
1. 保留 TUI 作为默认执行路径，不切换到 API 默认路径。
2. recover 从“cooldown 等待”升级为“自动清理确认框/queued prompt；失败后重分配或标记 respawn”。
3. 每个 pane 在完成一系列相关任务后自动执行 /clear，清除上下文污染。
4. clean pane 下次被使用前必须重新注入 persona、runtime policy、Solar context、capability/context prompt。
5. evaluator 支持主 Evaluator + clean lab spillover，不再因为单 pane 或 queued prompt 拖住评审队列。
6. 所有 recover/clear/reassign 行为必须写入 dispatch-ledger/model_call_ledger，便于审计。

实现要求：
- 增加 pane hygiene registry：~/.solar/harness/run/pane-hygiene.json。
- 增加状态：clean、dirty、running、cooling、needs_recover、needs_respawn。
- 派发前必须检查 pane hygiene；dirty pane 先 /clear，失败则跳过。
- 任务完成后按 dispatch group 或 sprint sibling 系列边界执行 /clear。
- /clear 成功判定：pane 回到空 prompt，且无 queued prompt、确认框、残留输入。
- 下次派发 clean pane 前强制重新注入 persona/runtime policy/context。
- queued prompt/proceed/permission prompt recover 成功后可继续使用；失败进入 cooldown 或 needs_respawn。
- 同批 dispatch-evals 必须避免重复选择同一 pane。
- 不允许把 cooldown 当最终修复；cooldown 只作为失败保护。
- 不允许删除用户数据、不重启 ThunderOMLX/ASR、不杀主 pane，除非明确进入 needs_respawn 且只重建该 worker pane。

验收标准：
1. 模拟 Do you want to proceed? 时，dispatcher 能自动确认或退出并继续派发。
2. 模拟 Press up to edit queued messages 时，dispatcher 能清理或重分配，不会反复撞同一个 pane。
3. builder 完成 handoff 后自动 /clear，并标记 clean。
4. evaluator 完成 eval.md/eval.json 后自动 /clear，并标记 clean。
5. clean pane 再次接任务前能看到 persona/runtime/Solar context 被重新注入。
6. dispatch-evals --max-items 3 能把三个 eval 分配到不同可用 pane。
7. 坏 pane 不会拖住队列；失败会写 ledger，并触发 reassign。
8. 相关 py_compile 和最小回归测试通过。

## 本切片目标

把核心能力接入 autopilot、DAG 调度、status UI、pane 可视化和运行时证据。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理.epic.md`、`epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理.traceability.json` 和父级 task_graph。
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

- `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui.design.md`
- `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui.plan.md`
- `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui.task_graph.json`
- `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui.handoff.md`
- `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui.eval.md` 或 `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui.eval.json`
