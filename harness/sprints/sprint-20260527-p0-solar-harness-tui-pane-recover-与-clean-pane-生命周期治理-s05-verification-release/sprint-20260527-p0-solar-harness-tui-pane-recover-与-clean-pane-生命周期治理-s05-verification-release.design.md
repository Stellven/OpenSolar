# Design — TUI Pane Recover S05 Verification-Release (epic 最后切片)

epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s05-verification-release`
slice: `verification-release` (epic last slice)
role: planner
status: planning_complete
generated_at: 2026-05-28T15:35:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
upstream: S03 (passed @ 5/28 11:23, 141 tests + 8 V acceptance) + S04 (passed @ 5/27 20:23, C1-C4 spec)
downstream: epic close (parent-check ready=true triggers epic_decomposer auto-close)

## 0. 切片定位 — DOGFOOD 闭环关键节点

**Epic 最后切片**: 验证 S03 实施 + S04 规约能在**真生产环境**跑通, 触发 epic parent-check 关闭。

**Dogfood 关键**: S05 builder pane 在跑测试时, 自己就是 TUI epic 治理能力 (PaneHygieneRegistry + RecoverDetector + PaneClearManager + spillover) 的首个真实使用者。若 builder 撞 proceed/queued, S03 实施应当自动 detect+clear+reassign — 这是 epic 闭环的根本验收。

## 1. 上游消费 (S03 + S04 → S05)

| 上游 | 必须消费 |
|------|----------|
| S03 handoff (6.6K) | 8 S05 启动 checklist 全条 (真 pane init / 真 capture-pane / 真 /clear / 真 reinject / autopilot respawn 链 / ledger 一致性 / spillover 并发 / S01 32 AC) |
| S03 traceability (16K) | 6 模块 / 4 schema / 5 错误码 / 8 acceptance reports / 3 OQ-S03-01..03 carried-over |
| S04 handoff (5.4K) | 6 S05 测试矩阵 (DASHBOARD/CLI/CONFIG/RESPAWN + S01 AC + S02 决议) + 4 环境约束 (test session/PROTECTED/不动 prod config/不重启 ThunderOMLX) |
| S04 traceability (10.8K) | C1-C4 4 spec docs + S03 dependencies assumptions + 5 残留风险 |
| S02 architecture/data_models/interfaces/OQ resolutions | D1-D7 决议 + 5 OQ + 6 状态 FSM 转移表 + 5 错误码 + spillover 池=5 panes |
| S01 7 outcome | O1-O7 全 32 AC (V1+V2→O2 / V3+V4→O3 / V5→O4 / V6→O5 / V7→O6 / V8→O7) |

## 2. S05 内部 DAG (5 实施节点 + 1 join)

```
V1 real_production_e2e (sonnet, 关键)
   ├─→ V2 autopilot_respawn_e2e (sonnet, fixture pane only)
   ├─→ V3 concurrent_stress (glm-5.1, ledger + spillover)
   └─→ V4 regression_aggregation (glm-5.1, S01 32 AC + S02 决议)
                                  └─→ V5 release_docs_epic_close_prep (sonnet)
                                        └─→ V6 join (sonnet)
```

**关键路径**: V1 → V5 → V6 (V1 给后续节点 produce real pane state; V5 编译 release; V6 join + parent-check ready)
**并行**: V2/V3/V4 都依赖 V1 完成 (要真 pane-hygiene + 真 ledger) 后可同批跑

## 3. 写范围 (per S04 §环境约束)

| 节点 | write_scope (互斥) |
|------|---------------------|
| V1 real_production_e2e | `~/.solar/harness/run/pane-hygiene.json` (首次 init, 然后 read-only); `~/.solar/harness/reports/tui-pane/s05-acceptance/V1-*.json`; `<sid>.V1-handoff.md` |
| V2 autopilot_respawn_e2e | `~/.solar/harness/reports/tui-pane/s05-acceptance/V2-*.json` (4 用例 evidence); `<sid>.V2-handoff.md`; **仅在 `solar-harness-test` 专用 tmux session 跑 respawn** |
| V3 concurrent_stress | `~/.solar/harness/reports/tui-pane/s05-acceptance/V3-*.json` (ledger 一致性 + spillover 3 并发); `<sid>.V3-handoff.md` |
| V4 regression_aggregation | `~/.solar/harness/reports/tui-pane/s05-acceptance/V4-*.json` (S01 32 AC + S02 D1-D7 + OQ-01..OQ-05 决议验证); `<sid>.V4-handoff.md` |
| V5 release_docs_epic_close_prep | `~/.solar/harness/docs/tui-pane-recover/RELEASE.md` (release notes + rollback + evidence summary); `<sid>.V5-handoff.md`; `<sid>.eval.md/json` |
| V6 join | `<sid>.handoff.md` + `<sid>.traceability.json` (with `parent_check_ready: true`) |

**严格禁止** (PROTECTED set):
- 杀生产主 pane: `solar-harness:0.0`, `solar-harness:0.1`, `solar-harness:0.2`, `solar-harness:0.3`, `solar-harness-lab:0.0`, `solar-harness-lab:0.1`, `solar-harness-lab:0.2`, `solar-harness-lab:0.3`
- 改生产 `spillover_config.yaml` (除测试 fixture 副本)
- 重启 ThunderOMLX / ASR / honcho / brain-router / qmd-proxy / config-server (per S03 N3 已列 7 个 non-multi_task_runner 进程)
- 修改 `~/.claude/settings.json` / Solar 仓库源代码
- 关闭 epic (V6 不动 epic.* artifact, 由 coordinator parent-check 自动)

## 4. 节点验收

### V1 real_production_e2e
- 真 tmux session `solar-harness-test` 中起 ≥3 fixture panes
- `scripts/init_pane_hygiene.py` 真跑产 pane-hygiene.json (首次)
- `RecoverDetector` 接 real tmux `capture-pane -p` (50 行 scrollback)
- `PaneClearManager.clear_with_retry()` 真 `tmux send-keys` `/clear Enter` 到 fixture pane
- `PersonaReinjector.inject_all()` 真注入 persona + runtime policy + solar context (mock-friendly + real-friendly)
- 验收: 5 件均产 evidence JSON (capture_sample.txt / clear_send_log.txt / reinject_diff.txt / state_transitions.json / pane_hygiene_diff.json)

### V2 autopilot_respawn_e2e (per OQ-05)
- **仅在 `solar-harness-test` 专用 tmux session** 跑; 绝不动 8 PROTECTED panes
- 4 用例: (a) 成功路径 (kill→split→ready→register→ledger) (b) kill-pane 失败 (c) split-window 失败 (d) ready marker 等待超时
- ATLAS structured repair 失败兜底验证
- 验收: 4 evidence JSON + respawn_max_concurrent=0 测试 (验证可禁用)

### V3 concurrent_stress
- Ledger 双写并发真实 load: 起 ≥10 并发线程同时 record_recover/record_clear/record_reassign; 验证 JSONL+SQLite 一致性
- Spillover 3 并发真任务: 派 3 个并发 dispatch 经 DispatchScheduler.spillover_select 验证零撞同
- Ledger 写延迟 p99 ≤ 200ms (per C1 §SLO)
- 验收: ledger_consistency.json + spillover_collision.json + p99_latency.json

### V4 regression_aggregation
- S01 32 AC: O1:5 + O2:5 + O3:5 + O4:5 + O5:4 + O6:4 + O7:4 全验证 (per S03 handoff)
- S02 决议: D1-D7 (FSM/atomic write/3 检测器/3-signal /clear/重注入/双引擎 ledger/spillover round-robin) 全验证
- OQ-01..OQ-05 决议落地验证 (持久化频率/clear retry/重注入频率/spillover 池规模/respawn 命令)
- 验收: regression_report.json (32 AC + 7 决议 + 5 OQ 全 PASS/FAIL 表)

### V5 release_docs_epic_close_prep
- `docs/tui-pane-recover/RELEASE.md`: 含 epic 总览 + S01-S05 各 sprint 摘要 + 验证证据路径 + rollback 命令 (删 5 schema 文件 + 6 模块) + ATLAS hook 注册指引 + OQ-S03-01..03 carried-over 未闭环项
- 禁止乐观词
- `<sid>.eval.md/json` verdict (sprint 整体)

### V6 join + epic close prep
- `<sid>.handoff.md` 含 V1-V5 摘要 + epic close 准备 checklist
- `<sid>.traceability.json` 含 `parent_check_ready: true` + `epic_required_gates_status` (S01..S05 全 passed)
- 不主动 close epic (epic_decomposer auto)

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| V1, V2 | sonnet | 真 tmux 交互 + ATLAS 兜底需 reasoning |
| V3, V4 | glm-5.1 | 测试模板化 |
| V5 | sonnet | release docs + epic close prep |
| V6 | sonnet | join + epic ready |

## 6. Stop Rules (强约束)

- respawn 测试仅 `solar-harness-test` session, **绝不** 触动 8 PROTECTED panes
- 不重启 ThunderOMLX/ASR/honcho/brain-router/qmd-proxy/config-server
- 不动 ADR / 生产 pane-hygiene / spillover_config (除 V1 首次 init)
- 不把 cooldown 当最终修复 (per S03 handoff 硬约束)
- 不切 TUI → API
- 不主动 close epic (coordinator 自动)
- 不用乐观词
- 任一 V 节点验收 FAIL → 不进下一节点; 触发 S03 round-2 (per Stop Rules)

## 7. 失败恢复

- V1 失败 → 真 tmux 交互问题; 切到 `solar-harness-test` 隔离 session 重试
- V2 任一用例失败 → ATLAS structured repair + 写 evidence; 4 用例必须 4/4
- V3 spillover 撞同 → 触发 S03 round-2 (per spillover_select 算法 bug)
- V3 ledger 不一致 → 触发 S03 round-2 (LedgerWriter 双写 bug)
- V4 任一 AC FAIL → 触发对应 S01-S03 节点 round-2; 不放过
- V5/V6 失败 → 单节点重派
- **绝不在 prod pane 跑 respawn**: PROTECTED_PANES 强校验

## 8. 非目标

- 不实施新代码 (S03 已完成 6 模块)
- 不动 S03/S04 artifacts (read-only verification)
- 不主动 close epic (V6 仅 mark parent_check_ready=true)
- 不杀生产 panes
- 不重启服务进程
- 不动 ThunderOMLX / 其他 epic 范围

## 9. Dogfood 闭环达成判据

S05 PASS 后, TUI epic 治理能力首次在真生产链路服务自己:
- ✅ S03 6 模块在生产 pane 上跑通 (V1)
- ✅ Autopilot 真 respawn 在隔离 session 跑通 (V2)
- ✅ Ledger 双写并发一致 + Spillover 真零撞同 (V3)
- ✅ S01 32 AC 全回归 (V4)
- ✅ Release notes 含 rollback (V5)
- ✅ parent-check ready=true 触发 epic auto-close (V6)

之后所有 sprint 的 pane 卡死问题自动 detect+clear+reassign — 整个 multi-pane 派发链路根本性更稳定。

## 10. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; S03 6.6K handoff + 16K traceability + S04 5.4K handoff + 10.8K traceability + S02 handoff/architecture + S01 7 requirements docs 已 self-contained。

11 capability `injectable_only`; V1-V2 真 tmux 交互调用 (非 capability 模拟)。
