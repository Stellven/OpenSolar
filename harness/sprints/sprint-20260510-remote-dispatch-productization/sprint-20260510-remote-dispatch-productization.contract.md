---
id: sprint-20260510-remote-dispatch-productization
title: Solar Remote Dispatch Productization
priority: P0
lane: reliability
bypass_pm: true
handoff_to: builder_main
target_role: builder
owner: solar-harness
---

# Contract — Solar Remote Dispatch Productization

## Intent

把“本地 Solar Harness 能把合约发到 Mac mini 跑一次”升级为产品级远端执行能力：可配置、可测试、可恢复、可观测、可审计，并且默认通过 Solar Harness 的 builder/evaluator/DAG gate 执行，而不是 Codex 手工 SSH 跑命令。

## Product Outcomes

- 用户可以显式选择本地或 Mac mini 执行，不需要记住 SSH/rsync 细节。
- 本地派发后，远端 Solar Harness 自动接收 sprint 合约、执行 DAG node、评审 gate，并把状态收口为 `passed|failed|blocked`。
- 派发失败、断网、重复派发、pane 忙、runner 未提交等情况都有可解释状态和自动恢复路径。
- 所有远端执行都有审计证据：dispatch id、remote host、remote user、remote harness version、file checksum、events.jsonl、graph node/gate verdict。
- 不同步 secrets，不把本机绝对路径/用户名硬编码进远端产品逻辑。

## Scope

### In Scope

- `/Users/lisihao/.solar/bin/solar-remote-dispatch`
- `/Users/lisihao/.solar/harness/lib/graph_node_dispatcher.py`
- `/Users/lisihao/.solar/harness/lib/graph_scheduler.py`
- 新增远端配置、doctor、reconcile/pull 状态所需的轻量脚本或 Python 模块。
- 新增测试：fake ssh/rsync/wake、graph dispatch pane submit、parent_ready_check、Mac mini smoke。
- 状态页面或 CLI 至少要能显示 remote sprint 的核心状态。

### Out of Scope

- 不重写整个 coordinator。
- 不要求支持任意云机器；本 sprint 产品化目标先支持 Mac mini remote target，但设计不能写死 `lisihao@100.122.223.55`。
- 不下载大型 benchmark 数据。
- 不把任何 API key、token、Google Drive 凭据同步到远端。

## Acceptance

- D1: `solar-remote-dispatch doctor --json` 存在，能输出 remote target、ssh、rsync、remote harness、remote tmux、remote pane、remote version、last sync 状态。
- D2: `solar-remote-dispatch <sid>` 支持配置驱动，不硬编码 remote user/host；支持 `--host` 覆盖；缺配置时报可执行错误。
- D3: 派发前生成 manifest，记录合约/status/task_graph/checksum；远端落盘后校验 checksum；校验失败必须失败，不允许继续 wake。
- D4: 重复派发幂等：同一 `sid + manifest checksum` 不重复 wake；`--force` 会记录 forced redispatch 事件。
- D5: 远端状态回收：提供 `solar-remote-dispatch pull <sid>` 或等价命令，能把 remote status/events/graph/eval/handoff 拉回本地，并标注 source host。
- D6: graph pane submit 不依赖人工 Enter；派发后能检测 pane 是否从 idle 进入 working 或至少写入 ack/submit evidence；失败要释放 lease 并 requeue。
- D7: parent sprint 只能由 `parent_ready_check` 自动收口；普通 evaluator 不得绕过 DAG gate 把 parent 标 passed。
- D8: 测试套覆盖 fake ssh/rsync/wake、断网、重复派发、checksum mismatch、busy pane、pane submit failure、parent_ready_check。
- D9: Mac mini e2e smoke：创建一个最小 remote sprint，由 Mac mini Solar Harness builder/evaluator 完成，并本地 pull 回最终 `passed` 证据。
- D10: README 或 status UI 文案说明用户怎么配置 Mac mini、怎么派发、怎么看状态、怎么恢复失败。

## Stop Rules

- 任一 D1-D9 失败，不允许声称“产品级完成”。
- 若发现 secrets 被同步或写入报告，立即停止并标 `failed`。
- 若无法访问 Mac mini，可先完成 fake/integration tests，但最终状态只能是 `warn`，不能 `passed`。

## Verify Commands

```bash
bash -n /Users/lisihao/.solar/bin/solar-remote-dispatch
python3 -m py_compile /Users/lisihao/.solar/harness/lib/graph_node_dispatcher.py
/Users/lisihao/.solar/bin/solar-remote-dispatch doctor --json
/Users/lisihao/.solar/bin/solar-harness graph-scheduler validate --graph /Users/lisihao/.solar/harness/sprints/sprint-20260510-remote-dispatch-productization.task_graph.json
```

## Required Evidence

- `sprint-20260510-remote-dispatch-productization.handoff.md`
- `sprint-20260510-remote-dispatch-productization.eval.md`
- `sprint-20260510-remote-dispatch-productization.eval.json`
- `reports/remote-dispatch-productization/<timestamp>/` with manifest, fake test logs, and Mac mini smoke logs.
