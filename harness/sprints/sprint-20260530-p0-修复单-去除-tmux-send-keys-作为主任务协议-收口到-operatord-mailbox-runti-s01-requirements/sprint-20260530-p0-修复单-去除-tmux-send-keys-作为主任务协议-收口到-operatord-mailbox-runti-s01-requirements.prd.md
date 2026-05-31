# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti`
sprint_id: `sprint-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti-s01-requirements`
slice: `requirements`

## 用户原始需求

# P0 修复单：去除 tmux send-keys 作为主任务协议，收口到 operatord mailbox runtime

## 背景
当前 runtime 已有 actor mailbox/state/heartbeat 结构，也已有 operatord；但主调度链仍大量使用 `tmux send-keys` 直接向 pane 注入指令，这与可靠任务协议的目标冲突。

## 发现的问题
1. `coordinator.ts` 仍有 `dispatchToPane()`，直接 `tmux send-keys` + Enter 向 pane 发送自然语言/短命令。
2. `graph_node_dispatcher.py` 仍是 builder pane dispatch 模型，主调度对象虽然已经有 actor/logical operator，但交付通道仍偏 pane。
3. `DISPATCH-PROTOCOL.md` 还在记录 send-keys 吞键、busy、重入等问题，说明 send-keys 仍是生产主通道之一。
4. `agent-actors.json` 已经给 actor 配置了 mailbox：`inbox/outbox/logs/state_json/heartbeat_json`，但主链没有完全切到 mailbox 提交协议。
5. `operatord.py` 目前仍主要从 `physical-operators.json` 启动 operator，而不是以 actor mailbox/runtime queue 为中心。
6. 预期中的 `pane_mailbox.py` 主实现文件不存在，说明 mailbox runtime 还没真正收口成统一库。

## 目标
把任务协议收口为：
`DAG Scheduler -> submit(task_envelope) -> actor mailbox / runtime queue -> operatord -> result/artifact/event log`
其中：
- `tmux send-keys` 只允许用于启动/恢复 `operatord run <actor/operator>`；
- 禁止再把自然语言任务文本直接塞进 pane 当主执行协议。

## 修复范围
### S1 protocol cutover
- 定义统一 task envelope schema（JSON/YAML）。
- 定义 actor mailbox 协议：`inbox/ outbox/ logs/ state.json/ heartbeat.json`。
- `graph_node_dispatcher` / `coordinator` 不再直接向 pane 发自然语言任务。

### S2 operatord runtime
- `operatord` 升级为真正的 mailbox consumer / runtime daemon。
- 允许 `operatord run <actor_id>` 或等价形式，长期轮询 inbox 并产出 result/artifact。
- actor runtime state 与 heartbeat 由 operatord 维护。

### S3 compatibility / launch
- `tmux send-keys` 仅保留为 host bootstrap：启动 operatord、恢复卡死 runtime。
- 明确生产链禁止 direct pane mutation 作为任务主协议。
- 旧 `physical-operators` / pane dispatch 路径降为 compatibility fallback。

### S4 acceptance
- 验证调度器提交 task_envelope 到 mailbox 后，无需 direct send natural language 到 pane。
- 验证 result/outbox/logs/state/heartbeat 全链可见。
- 验证 send-keys 不再承担任务内容协议，只承担 daemon bootstrap。

## 产出
- mailbox runtime / queue 库
- operatord cutover patch
- dispatcher/coordinator protocol cutover
- regression tests + migration note

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti.epic.md`、`epic-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti-s01-requirements.design.md`
- `sprint-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti-s01-requirements.plan.md`
- `sprint-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti-s01-requirements.task_graph.json`
- `sprint-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti-s01-requirements.handoff.md`
- `sprint-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti-s01-requirements.eval.md` 或 `sprint-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti-s01-requirements.eval.json`
