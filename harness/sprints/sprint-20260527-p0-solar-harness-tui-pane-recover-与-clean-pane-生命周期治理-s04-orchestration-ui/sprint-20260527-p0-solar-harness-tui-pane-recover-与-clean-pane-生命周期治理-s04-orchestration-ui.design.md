# Design — S04 Orchestration-UI 切片：TUI Pane Dashboard + Config UI + Autopilot Respawn 集成

epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui`
slice: `orchestration-ui`
role: planner
status: planning_complete
generated_at: 2026-05-27T22:18:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
upstream: S02 architecture passed (D1-D7 + OQ-01..OQ-05 全决议; 4 项 S04 启动 checklist); S03 core-runtime in parallel
downstream: S05 verification-release

## 0. 切片边界

- **S04 是 orchestration-ui 切片**：消费 S02 §10.6 dashboard 9 指标 + pane-status --json schema + config UI 集成点 + spillover 池配置 UI；与 S03 并行 (epic.task_graph schedule), 但实施依赖 S03 完成 6 模块 + 4 schema 后才能真接入
- **本 sprint 允许的写范围**:
  - `~/.solar/harness/sprints/<s04-sid>.dashboard_renderer_spec.md` (C1)
  - `~/.solar/harness/sprints/<s04-sid>.pane_status_cli_spec.md` (C2)
  - `~/.solar/harness/sprints/<s04-sid>.config_ui_spec.md` (C3)
  - `~/.solar/harness/sprints/<s04-sid>.autopilot_respawn_integration_plan.md` (C4)
  - `~/.solar/harness/sprints/<s04-sid>.traceability.json` + `<s04-sid>.handoff.md` (C5 join)
- **严格禁止**:
  - 真改 Solar status server / dashboard / config UI 源码 (本 sprint 是规约层, 真实施留 S04 后续 builder)
  - 真跑 `tmux send-keys` / pane respawn / dashboard 启动 / config UI 上线 (本 sprint 不真跑)
  - 修改 S02/S03 任何 artifact (有问题 → C5 OQ-new)
  - 修改父 epic 任何 artifact
  - 调用 autopilot 真触发 respawn (C4 只写集成计划)
  - 真改 `~/.solar/harness/run/pane-hygiene.json` 或 `spillover_config.yaml` (S03 + S04 实施层才写)
- 禁止乐观词；禁止假装 S03 已实施完成；禁止把 cooldown 当作最终修复

## 1. 上游消费

| S02 产出 (per handoff §S04 启动 checklist) | S04 必须消费 |
|--------------------------------------------|---------------|
| architecture.md §9.3 (9 dashboard 指标) | C1 dashboard 渲染规约 9 指标 |
| architecture.md §10.6 (pane-status --json 输出 schema) | C2 pane-status CLI 规约 |
| architecture.md §10.6 (config UI 集成点: 轮询频率/检测间隔/spillover 池配置可编辑) | C3 config UI 规约 |
| data_models.md §3 (spillover_config.yaml schema) | C3 spillover 池配置 UI |
| OQ-05 决议 (tmux kill-pane + split-window + 等待 claude-code session ready marker) | C4 autopilot respawn 集成计划 |
| S03 6 模块 API (PaneHygieneRegistry / DispatchScheduler etc.) | C1-C4 假定接口 |

## 2. S04 内部 DAG (4 路 fan-out + 1 join)

```
                  ┌─→ C1_dashboard_renderer_spec        ─┐
                  ├─→ C2_pane_status_cli_spec           ─┤
   (上游 S02 ok) ─┼─→ C3_config_ui_spec                 ─┼─→ C5_traceability_handoff (sonnet, join)
                  └─→ C4_autopilot_respawn_integration_plan ┘
```

**Wave 1 (4 并行)**: C1, C2, C3, C4 (write_scope 互斥)
**Wave 2 (join)**: C5

注: 本 sprint 只产 markdown 规约 + UI 草图 + 集成计划; 真实施代码留 S04 后续 builder phase (在 S03 完成后启动)。本 S04 sprint 是 "规约 + 集成计划" 层, 类似 YouTube S04 模式。

## 3. C1-C4 内容大纲

### C1 `dashboard_renderer_spec.md`
- 消费 S02 architecture §9.3 (9 dashboard 指标)
- 9 指标渲染: pane_state_count_by_state (clean/dirty/running/cooling/needs_recover/needs_respawn) / detection_hits_by_type (proceed/queued/permission) / clear_success_rate_24h / clear_retry_attempts_avg / spillover_pool_utilization_pct / reassign_count_24h / ledger_write_lag_p99_ms / persona_reinject_success_rate / respawn_count_24h
- HTML 模板草图 (visual-template 引用)
- TUI 替代方案 (基于现有 Tech Hotspot Radar / Solar status server)
- 数据源: 调用 S03 LedgerWriter.query_history() + PaneHygieneRegistry.query_clean_panes()
- SLO 状态行: hard/soft 阈值显示 (clear_success_rate ≥95%/≥90% / respawn ≤5/24h / ledger_lag ≤200ms)
- 验收 ≥5 条

### C2 `pane_status_cli_spec.md`
- 消费 S02 architecture §10.6 (pane-status --json 输出 schema)
- CLI 命令: `solar-harness pane-status [--json] [--pane <id>] [--watch <interval>]`
- 输出 schema (JSON): pane_id / current_state / last_transition_at / dispatch_id / persona / runtime_policy_hash / clear_attempts / cooldown_until / respawn_count / last_error_code
- subcommands: list-panes / show-pane / show-recover-history / show-ledger-tail
- 退出码统一 0/1/2/3 (per S02 interfaces)
- 验收 ≥4 条

### C3 `config_ui_spec.md`
- 消费 S02 data_models.md §3 + architecture.md §10.6 (config UI 集成点)
- Config UI 草图: 3 组可编辑项
  - **检测组**: RecoverDetector 轮询频率 (default 2s) / capture-pane 行数 (default 50) / 3 正则 visible
  - **清理组**: PaneClearManager retry 次数 (default 3) / backoff 序列 (default 5s/10s/15s) / cooldown 时长 (default 30s)
  - **Spillover 组**: spillover_config.yaml 池 pane 列表 / round_robin 权重 / reassign 优先级 / --max-items 默认值
- 配置变更触发 hot-reload (per S02 D5 持续注入)
- 配置审计 → 写 LedgerWriter (per S02 D6)
- 验收 ≥4 条

### C4 `autopilot_respawn_integration_plan.md`
- 消费 S02 OQ-05 决议 (tmux kill-pane + split-window + 等待 claude-code session ready marker)
- Autopilot 触发链: PaneHygieneRegistry 状态 → needs_respawn → autopilot 检测 → 执行 respawn 序列
- respawn 命令序列: (1) tmux kill-pane -t <pane> (2) tmux split-window -t <window> (3) 等待 claude-code session ready marker (prompt 出现) (4) 调用 init_pane_hygiene 注册新 pane + 全 clean 初始化 (5) 写 LedgerWriter record_respawn
- 失败回退: 命令任一失败 → 升级 ATLAS structured repair + 不杀主 pane + dispatch-ledger 记录失败原因
- 验证用例: 模拟 needs_respawn 触发 → autopilot 检测 → mock tmux 命令成功路径 + 失败路径 (kill-pane 失败 / split-window 失败 / ready marker 等待超时)
- **本节点只写集成计划, 不真调 tmux 命令 (留 S05 真跑)**
- 验收 ≥5 条

### C5 `traceability.json` + `handoff.md` (join)
- traceability.json 12 字段 (含 outcomes_4 / decisions_consumed S02 §9.3 §10.6 OQ-05 / s03_dependencies / downstream_sprint_kickoff_package S05 / open_questions_carried_over)
- handoff.md 含 C1-C4 摘要 + S05 启动 checklist + 剩余风险

## 4. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| C1, C2, C3 | glm-5.1 | 规约 + UI 草图模板化 |
| C4 | sonnet | autopilot 集成 + tmux 命令时序 + 失败回退需 reasoning |
| C5 (join) | sonnet | 跨节点聚合 |

## 5. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 S03 接口偏离 S02 决议 → C5 记 OQ
- 不真改 Solar 源码
- 不真跑 tmux 命令 / dashboard 启动 / config UI 上线
- 不调 autopilot 真触发 respawn (C4 只写计划)
- 不真改生产 pane-hygiene.json / spillover_config.yaml
- 不打印 API key / OAuth
- 不主动 close 父 epic
- 不假装 S03 已实施
- 不用乐观词
- 不把 cooldown 当作最终修复 (S02 D2 + cooling → needs_recover/dirty 强制)

## 6. 与 S03 的并行 / 接力

本 sprint 与 S03 并行启动 (epic schedule), 但实施依赖 S03 完成:

- C1 依赖 S03 LedgerWriter + PaneHygieneRegistry 实施 → 本节点写规约不阻塞
- C2 依赖 S03 PaneHygieneRegistry.query_clean_panes() → 本节点写挂载点和 schema 规约不阻塞
- C3 依赖 S03 lifecycle_jobs + DispatchScheduler 实施 → 本节点写 UI 草图基于 S02 schema 即可
- C4 依赖 S03 PaneHygieneRegistry transition_state(→needs_respawn) → 本节点写集成计划 (不真跑), 真跑留 S05

S04 sprint passed 后, S03 + S04 都 passed 才解锁 S05。

## 7. 失败恢复

- C1-C4 任一 FAIL: 单节点重派, 不阻塞另 3 个
- C5 FAIL: 诊断哪个 C 节点缺失/不一致, 回写
- 若 S03 偏离 S02 D1-D7 → C5 记 OQ 给协调器
- **Dogfood 风险**: builder pane 撞 proceed/queued → 现有 5 panes 天然 spillover (S03 实施前唯一保护)

## 8. 非目标

- 不实施任何代码 (本 sprint 是规约层)
- 不真跑 tmux / dashboard / config UI
- 不调 autopilot 真触发 respawn
- 不真改生产配置文件
- 不擅自修 S02/S03 artifacts
- 不主动 close 父 epic
- 不杀主 pane / 不删用户数据 / 不重启 ThunderOMLX
- 不把 cooldown 当作最终修复
- 不切换到 API 默认路径

## 9. 给下游接力 (S05 verification-release)

C5 traceability `downstream_sprint_kickoff_package.S05`:
- C1-C4 全部规约文档
- dashboard 9 指标验收测试用例
- pane-status CLI E2E 测试
- config UI 集成测试 (含 hot-reload)
- autopilot respawn E2E 真跑用例 (mock 测试环境 fixture pane, 不杀生产主 pane)
