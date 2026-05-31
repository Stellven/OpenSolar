# Design — Multi-Task Stale Python Runner Cleanup (sprint-level)

sprint_id: `sprint-20260520-multitask-stale-python-runner`
epic_id: null (standalone ops/runtime sprint)
role: planner
status: planning_complete
generated_at: 2026-05-28T12:38:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
detail_reference: `<sid>.prd.md` (14K, 8 FRs + 6 OQs + 8 risks + 5 user stories + 4 ACs + stop rules)
historical_status: **PASSED + .finalized 2026-05-23T14:27:56Z** (gates 3/3 passed: audit / impl / smoke)
graph_doctor_drift: 2026-05-26T17:56:53Z — N1/N2/N3 reset to `reviewing`, gate_missing_prd 触发 PM 回补 PRD

## 0. Sprint 性质

**Standalone ops/runtime sprint** — 修复 `multi_task_runner.py start` 在完成的 graph 后不自然退出导致 stale Python process 堆积问题。3-node DAG (N1 audit → N2 implementation → N3 smoke validation) **已 builder 完成 + evaluator PASS**, sprint 已 finalized (5/23). 本 Planner 切片是 sprint-level artifacts 合规化 backfill, 不重做 N1-N3。

## 1. 现状快照

| 维度 | 事实 |
|------|------|
| Sprint 历史 finalized | 2026-05-23T14:27:56Z ✅ (`.finalized` 0 bytes, events seq=3 passed:completed:done) |
| N1 audit | builder PASS @ 2026-05-20, handoff 2846 bytes + audit 6073 bytes |
| N2 implementation | builder PASS @ 2026-05-20, handoff 3731 bytes + addendum 1444 bytes |
| N3 smoke validation | builder PASS @ 2026-05-21, handoff 4397 bytes |
| 3 Gates | 全 passed (audit identifies / implementation adds / final evidence proves) |
| Drift trigger | 2026-05-26T17:56 graph_doctor reset N1/N2/N3 to reviewing (per smoke sprint 同款模式) |
| PM gate trigger | 2026-05-27 gate_missing_prd → PM 回补 PRD (14K, schema PASS) |
| Current phase | prd_ready / status=drafting / handoff_to=planner |
| Capability injection | ATLAS / Autoresearch / Everything Claude Code / MarkItDown / Solar-Harness Runtime / Superpowers / agency-agents / gstack / solar-autopilot-monitor / solar-graph-scheduler / solar-intent-engine / solar-knowledge-ingest (per dispatch) — `injectable_only`, 不重新执行 |
| pane_not_idle 失败 | events seq=16 dispatch_failed (与 UAKG sprint 同款 TUI hygiene 问题) |

## 2. 实施成果 (已 builder 完成, per N1-N3 handoffs)

| FR | 实施 | 验证 |
|----|------|------|
| FR-1 主循环可退出 | `_all_graphs_terminal()` + 4-条件 P1-P4 检查 break 主循环 exit 0 | N3 smoke T1+T2 验证 ✅ |
| FR-2 Terminal 状态识别 | `_SCHED_GRAPH_TERMINAL = frozenset({"passed","failed","skipped"})` | N3 smoke T3 验证 ✅ |
| FR-3 Stale 检测器 | `detect_stale_scheduler_runners(apply_cleanup=False)` 含 pid/graph/sprint_id/elapsed/rss_mb/log/reason/action | N3 smoke T4 命中 PID 8700/84192 ✅ |
| FR-4 CLI 子命令 | `solar-harness multi-task stale-schedulers` 默认 report-only, `--apply` SIGTERM | N3 命令实跑 ✅ |
| FR-5 Status 区分 | `multi-task status --no-clear` 显式分类 running/live vs completed/live vs historical/completed | N3 status snapshot ✅ |
| FR-6 安全谓词收敛 | argv 必须精确匹配 `multi_task_runner.py start --graph <COMPLETED-GRAPH>` | N3 列 7 个 non-multi_task_runner Python 进程证明谓词不命中 ✅ |
| FR-7 证据落盘 | monitor report 写 `~/.solar/harness/monitor-reports/` | N3 实写 sprint-20260520-multitask-stale-python-runner-N3-validation.md ✅ |
| FR-8 回归测试 | (a) 完成 graph break + (b) 活动 graph 不误退 + (c) stale PID 命中 + (d) py_compile | N3 4 项全 PASS ✅ |

## 3. 3-Node DAG (locked, per existing task_graph.json)

```
N1 audit (sonnet, PASS)
    └─→ N2 implementation (sonnet, PASS)
          └─→ N3 smoke validation (sonnet, PASS)
```

**严格串行**: audit → 实施 → 验证。N1 root cause 写完才能进 N2 实施; N2 实施完才能 N3 smoke。

## 4. 写范围 (per existing task_graph)

| 节点 | write_scope |
|------|-------------|
| N1 | `<sid>.N1-audit.md` + `~/.solar/harness/monitor-reports/` |
| N2 | `lib/multi_task_runner.py` + `scripts/` + `<sid>.N2-handoff.md` |
| N3 | `~/.solar/harness/monitor-reports/` + `<sid>.N3-handoff.md` |
| Planner (本切片) | `<sid>.design.md` + `<sid>.plan.md` + `<sid>.planning.html` + `<sid>.task_graph.json` patch + `<sid>.status.json` + ACK |

**严格禁止**: 重做 N1/N2/N3 (已 PASS); 改 `lib/multi_task_runner.py` (N2 已修); 杀任何 non-multi_task_runner Python 进程 (per PRD §约束 + N3 已列 7 个 out-of-scope)。

## 5. Stop Rules (per PRD §Stop Rules)

- 候选 PID 不指向 completed graph → 立即停 + 写 blocker
- 需要 kill non-scheduler Python → 立即停 + 写 blocker
- 测试不能区分 active vs completed → 立即停 + 写 blocker
- 不删 task 目录 / graph JSON / scheduler 日志
- 不动 ThunderOMLX / honcho / brain-router / qmd-proxy / config-server
- cleanup 只允许 SIGTERM, 不允许 SIGKILL / `pkill python`
- 不重启 harness
- 不写实施代码以外的乐观词

## 6. 失败恢复 / 降级

- Drift recurrence: 若 graph_doctor 再次 reset N1-N3 → 本 Planner backfill pattern 可重复执行
- N1-N3 已 builder PASS, 不重做; 若 evaluator 二次审查 FAIL → ATLAS structured repair, 不擅自手改 task_graph status
- pane_not_idle (events seq=16): 与 UAKG / smoke 同款问题, 等 TUI epic S03 实施

## 7. 与同期 sprint 关系

- **sprint-20260527-default-dispatch-smoke**: 同款 PM PRD backfill + Planner artifacts backfill pattern (本 sprint 复用)
- **sprint-20260521-thunderomlx-knowledge-extract-smoke[-rerun]**: 同款 finalized → graph_doctor drift → 4-node 修复模式
- **sprint-20260527-p0-...-tui-pane-recover**: 处理 `pane_not_idle` 根因 (events seq=16)
- **sprint-20260523-lease-based-model-fleet-runtime**: 长期方向, 可整合本 sprint stale runner 检测能力

## 8. 非目标

- 不重做 N1/N2/N3 (已 builder PASS + evaluator PASS, .finalized 5/23)
- 不擅自手改 task_graph N1-N3 status (graph_doctor 之前 reset 后 node-verdict CLI 是正确路径)
- 不主动 SIGTERM PID 8700/84192 (PRD §未验证: 留 post-sprint operator action 或 cron)
- 不动 7 个 non-multi_task_runner Python 进程 (per N3 列表)
- 不重启 harness
- 不写新 implementation (N2 已修)
- 不修 graph_doctor 本身 (TUI epic 范围)

## 9. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; 11 capability `injectable_only`, 不重新执行 (复用 N1-N3 已执行证据)。

PRD 14K + N1 audit 6K + N2 handoff+addendum 5K + N3 handoff 4.4K = 29K total sprint evidence, 已 self-contained。
