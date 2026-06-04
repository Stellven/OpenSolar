# Contract: 需求拆解与追踪矩阵

priority: `P0`
epic_id: `epic-20260531-cmux-多标签四分屏-tmux-状态监控工作台`
sprint_id: `sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s01-requirements`
handoff_to: `planner`

## Intent

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## Required Capabilities

- product.requirements
- workflow.planning

## Acceptance

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## Stop Rules

- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突必须回写父级 traceability。

## Done

- [ ] D1: Config Schema 定义 — workspace.yaml 支持 tabs/panes/source(local|remote)/ssh_profile/tmux_target/mode(capture|tail)/lines/interval_sec 已定义含样例
- [ ] D2: 监控模式规格 — capture-pane mirror (轮询镜像) + pipe-pane tail-F (持续日志流) 两种模式的触发条件/输出格式/失败行为已定义
- [ ] D3: 布局规格 — 1-pane(全屏)/2-pane(左右平分)/3-pane(上2下1)/4-pane(2×2等分) 四种布局模式已定义，4-pane 默认平均分屏
- [ ] D4: 启停脚本 + Doctor 规格 — cmux-monitor-up/down/doctor + tmux-pane-view/tmux-pane-log-follow 脚本的输入输出已定义
- [ ] D5: SSH 复用规格 — ControlMaster/ControlPath/ControlPersist 推荐配置已定义，含复用验证方法
- [ ] D6: Epic→Sprint Traceability Matrix — S01-S05 输入/输出/验收/依赖追踪表已生成
