# PRD — stale Python multi-task runner cleanup

Sprint: `sprint-20260520-multitask-stale-python-runner`
Source: Codex operator report from Mac mini
Priority: P0
Lane: operations/runtime

## Problem

Mac mini shows long-running Python processes even after the related `solar-harness multi-task` sprint is complete. Live evidence captured on 2026-05-20:

- PID `8700`: `multi_task_runner.py start --graph ...sprint-20260520-thunderomlx-qwen36-pane-overhead.task_graph.json --max-workers 2 --profile builder --interval 30 --memory-reserve-gb 8 --no-clear`
- PID `84192`: `multi_task_runner.py start --graph ...sprint-20260520-thunderomlx-cache-warm-advisor.task_graph.json --max-workers 2 --profile builder --interval 30 --memory-reserve-gb 8 --no-clear`
- Both graphs report `parent-check ready=true`, all nodes passed, `missing_gates=[]`.
- `multi-task status --no-clear` still reports many `completed/live` workers and the scheduler logs keep growing.

This creates operator confusion, unnecessary background work, and makes it hard to tell if Mac mini is actually idle.

## Goals

1. Make `multi_task_runner.py start` naturally exit when its target graph is fully complete and no active workers remain.
2. Add a diagnostic surface that clearly reports stale scheduler runners tied to completed graphs.
3. Provide a safe, auditable cleanup path for stale scheduler runners; no broad process killing.
4. Preserve normal behavior for active graphs and intentional long-running screen/status UI.

## Non-goals

- Do not kill unrelated Python processes such as `honcho`, QMD proxy, brain-router, ThunderOMLX MCP, or config server.
- Do not delete task directories or scheduler logs.
- Do not change ThunderOMLX cache settings.
- Do not rewrite completed task handoffs.

## Acceptance

- A completed graph with all nodes passed, `parent-check ready=true`, no ready nodes, and no active workers causes `multi_task_runner.py start` to exit with code 0 within one scheduler interval.
- `solar-harness multi-task status --no-clear` no longer makes completed old workers look like live work without an explicit stale/completed distinction.
- A doctor/report command or equivalent diagnostic identifies PIDs like `8700` and `84192` as stale scheduler runners, including graph path, PID, elapsed time, RSS, and log path.
- Cleanup is constrained to commands whose process argv contains `multi_task_runner.py start --graph <completed graph>` and whose graph passes `parent-check ready=true`.
- Tests or smoke scripts prove active graph scheduling still dispatches ready nodes.

## Evidence To Use

- `/Users/lisihao/.solar/harness/run/multi-task/thunderomlx-qwen36-pane-overhead.scheduler.log`
- `/Users/lisihao/.solar/harness/run/multi-task/thunderomlx-cache-warm-advisor.scheduler.log`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260520-thunderomlx-qwen36-pane-overhead.task_graph.json`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260520-thunderomlx-cache-warm-advisor.task_graph.json`
- `ps axo pid,ppid,etime,%cpu,%mem,rss,command | grep multi_task_runner.py`

## Stop Rules

- Stop and write a blocker if a candidate PID does not point to a completed graph.
- Stop and write a blocker if the change would require killing non-scheduler Python processes.
- Stop and write a blocker if tests cannot distinguish active graph from completed graph behavior.

---

## 背景 / Context

- Mac mini (lisihaodeMac-mini.local, macOS arm64, bash 5.3.9) 是 Solar Harness 治理中枢，4-pane 协同（pane 0 planner opus / pane 1 builder glm-5.1 / pane 2 evaluator glm-5.1 / pane 3 architect opus）持续派发多个并发 sprint。
- `solar-harness multi-task` 通过 `lib/multi_task_runner.py start --graph <task_graph.json>` 拉起 DAG 调度器进程，按 `--interval 30` 秒轮询 ready 节点；每个 sprint 会 spawn 一个独立 runner。
- 2026-05-20 现场证据：两个 thunderomlx graph 全部 `parent-check ready=true / 所有节点 passed / missing_gates=[]`，但 `multi_task_runner.py start` 进程（PID 8700 / 84192，分别活了 3h47m / 4h37m）仍然挂在 `while True` 循环里，每 30s 醒一次什么也不干。
- 这造成 3 个副作用：(1) 操作员困惑——`ps` 输出充满 stale runner；(2) `multi-task status --no-clear` 把 stale 当 live；(3) chain-watcher / autopilot 难以判断 Mac mini 是不是真闲。
- 本 sprint 已经在 2026-05-23T14:27:56Z `finalized`，N1 audit + N2 实施 + N3 smoke validation 全部交付。本次 dispatch 是 coordinator gate_prd_schema 回溯修复：PRD 缺 schema 必需的 7 个标准 section，触发 PM 重补。

## 用户故事 / User Stories

- **US-01 (运维 / 操作员)**：作为 Mac mini 操作员，当一个 sprint 的全部节点都 passed 后，我希望对应的 `multi_task_runner.py start` 进程在 ≤1 个 scheduler interval 内自然退出（exit 0），不要永远挂着。
  - 验收：PRD §Acceptance 第 1 条已涵盖；N3 smoke 已验证 `_all_graphs_terminal()` 返回 True 时主循环 break。
- **US-02 (操作员 / 自动化)**：作为 chain-watcher，我希望能用一条命令枚举所有 stale scheduler PID，附 graph 路径 / 启动时长 / RSS / 日志路径 / reason，便于自动化决策。
  - 验收：`solar-harness multi-task stale-schedulers` 命令产出至少 6 字段；N3 已验证。
- **US-03 (操作员 / 安全)**：作为发起 cleanup 的人，我希望默认只 report、需要显式 `--apply` 才发 SIGTERM；apply 模式必须二次校验 graph 仍然 terminal 才允许 kill。
  - 验收：PRD §Acceptance 第 4 条 + contract §4 已涵盖；smoke 验证 `apply_cleanup=False` 时只产报告。
- **US-04 (操作员 / 风险)**：作为系统看护者，我**不希望**这个修复误杀 honcho / brain-router / ThunderOMLX MCP / qmd-proxy / config-server 等不相关 Python 进程。
  - 验收：N3-handoff 已列 7 个 non-multi_task_runner Python 进程并证明 stale 谓词不应用到它们。
- **US-05 (Evaluator)**：作为 Evaluator，我希望本 sprint 留下可程序化的 stop_rules 和可复现的 smoke 命令，让我能直接判定 sprint passed / failed。
  - 验收：PRD §Stop Rules + N3-handoff §已验证表 已满足。

## 功能需求 / Requirements

- **FR-1 主循环可退出**：`multi_task_runner.py start` 主 `while True` 循环新增退出条件：当 (P1) parent-check ready=true ∧ (P2) 没有 open 节点 ∧ (P3) 没有 active worker ∧ (P4) 没有 ready 节点 全部满足，break 主循环并 exit 0。
- **FR-2 Terminal 状态识别**：定义 `_SCHED_GRAPH_TERMINAL = frozenset({"passed","failed","skipped"})` 作为终态集合；新增 `_all_graphs_terminal(graphs)` 辅助判断。
- **FR-3 Stale 检测器**：实现 `detect_stale_scheduler_runners(apply_cleanup: bool = False)`，扫描所有 `multi_task_runner.py start --graph <path>` 进程；每条记录含 `pid / graph / sprint_id / elapsed / rss_mb / log / reason / action`。
- **FR-4 CLI 子命令**：新增 `solar-harness multi-task stale-schedulers` 入口；默认 `--apply=False` 只 report；`--apply` 时对每个候选进程再次校验 `_all_graphs_terminal` 才 SIGTERM。
- **FR-5 Status 区分**：`multi-task status --no-clear` 输出中显式分类 `running/live` vs `completed/live`（stale）vs `historical/completed`；不再让 stale 看起来像 active。
- **FR-6 安全谓词收敛**：cleanup 谓词必须精确匹配 `multi_task_runner.py start --graph <COMPLETED-GRAPH>` argv；任何不匹配的 Python 进程绝不进入候选集。
- **FR-7 证据落盘**：每次 detection 写一份 monitor report 到 `~/.solar/harness/monitor-reports/`，包含发现的 PID / 决策 / 操作员证据。
- **FR-8 回归测试**：必须有 unit / fixture / smoke 证明：(a) 完成 graph 主循环退出；(b) 活动 graph 不会被误退出；(c) 检测器对真实 stale PID 命中；(d) `py_compile` 通过。

## 约束 / Constraints

- **环境**：macOS arm64 / bash 5.3.9 / Python 3.x；不引入新二进制依赖；不依赖 Linux-only 特性（`/proc` 不可用，必须用 `ps` / `psutil` 或类似跨平台方案）。
- **路径**：实现代码只允许在 `/Users/lisihao/.solar/harness/lib/` 和 CLI wiring；report 写到 `~/.solar/harness/monitor-reports/`；handoff 写到 `~/.solar/harness/sprints/<sid>.N*-handoff.md`；禁 `/tmp`、禁用户 home 根。
- **安全谓词**：cleanup 只允许 SIGTERM；不允许 SIGKILL；不允许批量 `pkill python`；不允许杀任何非 `multi_task_runner.py` 进程。
- **不删数据**：不删 task 目录、不删 graph JSON、不删 scheduler 日志。
- **不动 ThunderOMLX/ASR/honcho/brain-router/qmd-proxy/config-server** 任何配置或进程。
- **API 兼容**：现有 `solar-harness multi-task start / status / dispatch` 调用方式不变；只新增字段和子命令。
- **PM 角色边界**：PM 不写实现代码；本切片是回溯 PRD schema 补全，不动 status 到 implementation；保持 `status=drafting`（虽然实际已 finalized，PM 不应该回写状态）。
- **TUI 经济**：保留 TUI 默认执行路径；本修复不切 API。

## 风险 / Risks

| 风险 | 影响 | 缓解 / 状态 |
|------|------|------|
| 终态判定误判（把 dispatched/reviewing 当 terminal）→ 杀正在跑的 runner | 数据损失 / 任务中断 | `_SCHED_GRAPH_TERMINAL` 严格 `{passed, failed, skipped}`；N1-audit §3 加 P4 "no reviewing nodes"；N3 smoke 已验 ✅ |
| Apply 模式误杀非 scheduler Python | 系统瘫痪 | argv 必须含 `multi_task_runner.py start --graph`；apply 前再校验 `_all_graphs_terminal`；N3 已列 7 个不相关进程证明谓词不命中 ✅ |
| Status 输出过度过滤 → 隐藏真活动 | 操作员失盲 | 约束"不允许通过隐藏所有 python 进程修 status"；分类显式区分 running/completed/historical |
| 跨平台 PID 探测在 macOS 失败 | 检测器不可用 | 用 `ps axo ...` 或 `psutil`，不依赖 `/proc`；N3 在 Mac mini 实测 PID 8700/84192 命中 ✅ |
| `--apply` 与并发派发冲突（kill 时同时 ready 一个新节点） | race condition | apply 前 `_all_graphs_terminal` re-check + SIGTERM 而非 SIGKILL，runner 有机会清理 |
| `multi-task status` 输出格式变更破坏自动化解析 | 调用方坏 | 只新增列，不删除字段；保留旧 `live/completed` 行为，新增 stale 分类列 |
| 长跑 scheduler 在终态后内存累积 | 资源浪费 | FR-1 自然退出已治本；FR-3 stale-schedulers 是治标 fallback |
| PRD schema gate 反复触发 | PM 派发循环 | 本切片即修复；validate.sh prd 必须 PASS 后 coordinator 不再重派 |

## 开放问题 / Open Questions

- **OQ-01 默认是否启用自动 apply 清理？** 当前默认 report-only；是否未来加 cron 自动 `--apply`？需要看 stale 出现频率与误判率。**Owner**: 操作员/未来 sprint。
- **OQ-02 stale-schedulers 是否应当报告到 `~/.solar/harness/.coordinator.log` 让 chain-watcher 看到？** 当前只写 monitor-reports/。**Owner**: 未来 observability sprint。
- **OQ-03 multi_task_runner 主循环是否应当在 graph terminal 后做一次最终 status push（写 sprint.status.json 或 events）？** 当前只 exit，可能丢失"自然结束"事件。**Owner**: 未来 N4 / 后续 sprint。
- **OQ-04 是否需要在 `multi-task start` 加 `--auto-exit-on-terminal=true|false` flag 让操作员显式控制？** 现在是隐式默认 exit。**Owner**: 待操作员反馈。
- **OQ-05 检测器要不要支持 JSON 输出？** 当前 markdown report；自动化消费可能需要 JSON。**Owner**: 未来 sprint。
- **OQ-06 N3-handoff 列出的 7 个 non-multi_task_runner 进程是否需要单独 inventory sprint？** 这些都是合法长跑服务，但目前没有统一注册表。**Owner**: 未来 service-inventory sprint。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（含 Problem / Goals / Acceptance / Non-goals / Stop Rules / Evidence + 本次补的 7 节）。
- `sprint-20260520-multitask-stale-python-runner.contract.md`（Scope / Required Work 1-6 / Constraints / Verification / Deliverables）。
- 实际 sprint 产出：
  - `…N1-audit.md`（根因 + 安全谓词 P1-P4 + 实施选项）
  - `…N1-handoff.md`、`…N2-addendum.md`、`…N2-handoff.md`、`…N3-handoff.md`
  - `lib/multi_task_runner.py`（已加 `_SCHED_GRAPH_TERMINAL` / `_all_graphs_terminal` / `detect_stale_scheduler_runners`）
  - `monitor-reports/stale-runner-audit-20260520T235200Z.md`
  - `monitor-reports/sprint-20260520-multitask-stale-python-runner-N3-validation.md`
- `task_graph.json`（5/26 13:56 已存在；3 节点 N1/N2/N3 完成）。

### 当前实施状态（已交付，本切片不重做）

| 功能 | 状态 | 证据 |
|------|------|------|
| FR-1 主循环可退出 | ✅ 已实施 | N3 smoke：`_all_graphs_terminal=True` → break ✅ |
| FR-2 Terminal 状态识别 | ✅ 已实施 | frozenset `{passed,failed,skipped}` 在 lib 中 |
| FR-3 Stale 检测器 | ✅ 已实施 | `detect_stale_scheduler_runners(apply_cleanup=False)` 命中 PID 8700/84192 |
| FR-4 CLI 子命令 | ✅ 已实施 | `solar-harness multi-task stale-schedulers` 可用 |
| FR-5 Status 区分 | ✅ 已实施 | N3 monitor §5 截图：running/live vs completed/live |
| FR-6 安全谓词收敛 | ✅ 已验证 | N3 测试 7 个非 multi_task_runner 进程不命中 |
| FR-7 证据落盘 | ✅ 已实施 | monitor-reports/ 下两份 report |
| FR-8 回归测试 | ✅ 已通过 | py_compile 0 / 4 smoke tests 全 pass |

### 未尽事项（留给后续 sprint，不在本回溯范围）

- **实际 SIGTERM 清理**：N3 范围只 validation；PID 8700 + 84192 的真 kill 留给操作员（或后续自动化）。
- **OQ-01..OQ-06**：本 sprint 不决议；列入 Planner Handoff 供后续 sprint 消费。
- **本次 PRD 回溯修复**：PM 仅补 7 节使 schema gate PASS；不动 status、不动其他 artifact。

### 给 Coordinator 的明确指令

- **不要回写 status**：本 sprint 已 `finalized` (2026-05-23T14:27:56Z)；coordinator 当前把状态拉回 `drafting/prd_ready` 是 gate_prd_schema 触发的副作用。PM 修复 PRD 后，coordinator 应当在重跑 schema gate 时识别 `.finalized` 文件并不再尝试 advance 到 planner。
- **触发机制**：PRD mtime 已刷新；coordinator 下一 tick 重跑 validate.sh prd → PASS → 关闭 gate。

### Knowledge Context

Knowledge Context: solar-harness context inject used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (context inject), harness-intent (task_status_query 直接 intent, 不重新 capture：本 sprint 早在 2026-05-20 由 Codex operator report 入队，不属于新 raw_intent)。

