# Design — s01-requirements: 去除 tmux send-keys 主任务协议需求拆解

## 设计目标

从修复单（6 个问题 + 4 个修复范围 S1-S4）提取结构化需求组，定义 task envelope schema 和 mailbox 协议草案，建立 RG → 5 slice 追踪矩阵。

## 现状问题拓扑

```
现状 (send-keys 主协议):

DAG Scheduler
    │
    ├──→ coordinator.ts dispatchToPane()
    │         │
    │    tmux send-keys + Enter
    │         │  ❌ 自然语言直接注入 pane
    │         │  ❌ 吞键/busy/重入问题
    │         ▼
    │    pane (Claude Code / Codex)
    │
    ├──→ graph_node_dispatcher.py
    │         │
    │    仍偏 pane dispatch 模型
    │         ❌ 交付通道仍是 pane
    │
    └──→ operatord.py
              │
         从 physical-operators.json 启动
              ❌ 不以 mailbox/runtime queue 为中心

actor mailbox (已配置但未用):
  agent-actors.json: inbox/outbox/logs/state.json/heartbeat.json
  pane_mailbox.py: ❌ 不存在

目标 (mailbox runtime 协议):

DAG Scheduler
    │
    └──→ submit(task_envelope)
              │
         actor mailbox (inbox/)
              │
         operatord (mailbox consumer)
              │
         ├──→ result (outbox/)
         ├──→ artifact
         ├──→ state.json
         ├──→ heartbeat.json
         └──→ event log (logs/)

tmux send-keys: 仅用于 bootstrap operatord / 恢复卡死
```

## Task Envelope Schema 草案

```json
{
  "envelope_version": "solar.task_envelope.v1",
  "task_id": "uuid",
  "sprint_id": "string",
  "node_id": "string (DAG node)",
  "actor_id": "string",
  "operator_id": "string",
  "payload": {
    "type": "dispatch | wake | eval | abort",
    "contract_path": "string",
    "task_graph_path": "string",
    "node_goal": "string",
    "write_scope": ["string"],
    "acceptance": ["string"]
  },
  "submitted_at": "ISO8601",
  "ttl_sec": 3600,
  "priority": "P0 | P1 | P2",
  "preemptible": false
}
```

## Mailbox 协议草案

```
~/.solar/harness/actors/<actor_id>/
├── inbox/                    ← scheduler 写入 task_envelope.json
│   └── <task_id>.envelope.json
├── outbox/                   ← operatord 写入结果
│   └── <task_id>.result.json
├── logs/                     ← 运行日志
│   └── <task_id>.log
├── state.json                ← actor runtime 状态
└── heartbeat.json            ← 心跳文件
```

operatord 行为:
1. 轮询 inbox/ → 取出 envelope → 校验 → 执行
2. 执行完 → 写 outbox/<task_id>.result.json
3. 持续更新 state.json + heartbeat.json
4. scheduler 轮询 outbox/ 收集结果

## 需求组提取 (RG)

| RG | 类别 | 描述 | 目标 Slice |
|----|------|------|-----------|
| RG1 | Task Envelope | 定义统一 task_envelope schema（JSON），含 task_id/sprint_id/node_id/actor_id/payload/ttl/priority | S02→S03 |
| RG2 | Mailbox Protocol | 定义 actor mailbox 目录协议: inbox/outbox/logs/state/heartbeat | S02→S03 |
| RG3 | Coordinator Cutover | coordinator.ts 的 dispatchToPane() 切换为 submit(envelope) → inbox/ | S03 |
| RG4 | Dispatcher Cutover | graph_node_dispatcher.py 从 pane dispatch 切换为 mailbox submit | S03 |
| RG5 | operatord Upgrade | operatord 升级为 inbox consumer / runtime daemon，长期轮询 inbox | S03 |
| RG6 | Result Collection | scheduler 轮询 outbox/ 收集 result.json，驱动 DAG 状态转换 | S03→S04 |
| RG7 | send-keys 降级 | tmux send-keys 仅保留为 host bootstrap（启动 operatord / 恢复卡死） | S03 |
| RG8 | 禁止直接 Pane Mutation | 生产链禁止 direct pane mutation 作为任务主协议，有 lint/guard 检查 | S03→S04 |
| RG9 | Compat Fallback | 旧 physical-operators / pane dispatch 路径降为 compatibility fallback | S03→S04 |
| RG10 | pane_mailbox.py 实现 | 创建 mailbox runtime 统一库（目前不存在），实现 submit/poll/collect API | S03 |
| RG11 | 端到端验证 | 验证 scheduler → envelope → inbox → operatord → outbox → result 全链路 | S05 |
| RG12 | send-keys 审计 | 验证 send-keys 不再承担任务内容协议，只承担 daemon bootstrap | S05 |
| RG13 | 状态/日志可见性 | 验证 result/outbox/logs/state/heartbeat 全链在 status 面板可见 | S04→S05 |

## RG → Slice 追踪矩阵

```
┌──────────┬─────────────────────────────────────────────┐
│          │              Target Slice                    │
│ RG       │ S02-arch  S03-core  S04-orch  S05-verify   │
├──────────┼─────────────────────────────────────────────┤
│ RG1      │    ●         ●                              │
│ RG2      │    ●         ●                              │
│ RG3      │              ●                              │
│ RG4      │              ●                              │
│ RG5      │              ●                              │
│ RG6      │              ●         ●                    │
│ RG7      │              ●                              │
│ RG8      │              ●         ●                    │
│ RG9      │              ●         ●                    │
│ RG10     │              ●                              │
│ RG11     │                                  ●          │
│ RG12     │                                  ●          │
│ RG13     │                        ●         ●          │
└──────────┴─────────────────────────────────────────────┘
```

密度: S03 承接 10/13 RG, S02 承接 2 RG, S04 承接 4 RG, S05 承接 3 RG。

## 非目标边界

| 不做 | 原因 |
|------|------|
| 删除 tmux 支持 | tmux 仍用于 bootstrap 和紧急恢复 |
| 重写 DAG scheduler | scheduler 已稳定，只改提交通道 |
| 实现远程/分布式 mailbox | 当前单机，远程是后续 |
| 修改 agent-actors.json 结构 | actor 结构已正确，只补实现 |
| 重构 coordinator.ts 全部逻辑 | 只替换 dispatchToPane()，不动其他 |
| 实现 WebSocket 实时推送 | 文件轮询即可，WebSocket 是后续优化 |

## 文件影响清单

| 文件 | 影响 | 涉及 RG |
|------|------|--------|
| lib/coordinator.ts | dispatchToPane() cutover | RG3 |
| lib/graph_node_dispatcher.py | pane dispatch → mailbox submit | RG4 |
| lib/operatord.py | 升级为 inbox consumer | RG5 |
| lib/pane_mailbox.py (新) | mailbox runtime 统一库 | RG10 |
| config/task-envelope.schema.json (新) | envelope schema | RG1 |
| config/agent-actors.json | mailbox 路径验证 | RG2 |
| docs/DISPATCH-PROTOCOL.md | 更新为 mailbox 协议 | RG7,RG8 |
| tests/ | 端到端 + 审计 | RG11-RG13 |

## 风险矩阵

| 风险 | 等级 | 缓解 |
|------|------|------|
| send-keys 切换中断正在执行的 sprint | 高 | 分阶段: 先加 mailbox 路径再切默认 |
| pane_mailbox.py 从零实现复杂度 | 中 | MVP: submit + poll 两个 API 先行 |
| operatord 升级可能破坏现有 operator 启动链 | 中 | 保留 physical-operators 兼容入口 |
| coordinator.ts 修改影响全局调度 | 高 | 只修改 dispatchToPane()，不动其他方法 |
| 文件轮询 inbox/ 延迟 | 低 | inotify/fswatch 可选优化 |
| envelope schema 设计不足需要后续迭代 | 低 | v1 最小 schema，后续扩展 |
