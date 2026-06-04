# Handoff — S04 Orchestration-UI: TUI Pane Dashboard + Config UI + Autopilot Respawn 集成

sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui`
epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
node: `C5_traceability_handoff`
generated_at: `2026-05-28T00:20:00Z`

---

## C1-C4 各产出路径与摘要

### C1 — Dashboard Renderer Spec (passed)

**路径**: `sprints/...s04-orchestration-ui.dashboard_renderer_spec.md` (259 行)

**摘要**: 9 指标渲染规约 (pane_state_count/detection_hits/clear_success_rate/clear_retry_avg/spillover_util/reassign_count/ledger_lag_p99/reinject_rate/respawn_count) + HTML 模板草图引用 visual-template + TUI ASCII 替代 + SLO 状态行 (clear≥95%/respawn≤5/lag≤200ms) + 数据源契约假定 S03 API。

### C2 — Pane Status CLI Spec (passed)

**路径**: `sprints/...s04-orchestration-ui.pane_status_cli_spec.md` (263 行)

**摘要**: CLI 规约 `solar-harness pane-status` + 4 subcommands (list-panes/show-pane/show-recover-history/show-ledger-tail) + 10 字段 JSON schema + 4 退出码 (0/1/2/3) + --watch 轮询 + Dashboard 集成点。

### C3 — Config UI Spec (passed)

**路径**: `sprints/...s04-orchestration-ui.config_ui_spec.md` (268 行)

**摘要**: 3 组可编辑配置 (检测组 5 字段 + 清理组 3 字段 + Spillover 组 4 字段) + hot-reload 触发链 (§5) + LedgerWriter config_change 审计 (§6) + 变更约束 + builder_eligible=conditional。

### C4 — Autopilot Respawn Integration Plan (passed)

**路径**: `sprints/...s04-orchestration-ui.autopilot_respawn_integration_plan.md` (356 行)

**摘要**: 5 步 respawn 序列 (kill-pane/split-window/ready-marker/init-register/ledger) per OQ-05 + ATLAS structured repair 失败回退 + PROTECTED_PANES 主 pane 保护 + 4 验证用例 + DispatchScheduler 间接调用 (alt2) + builder_eligible=NO (真跑留 S05)。

---

## S05 启动 Checklist

### 前置条件

- [ ] S03 core-runtime sprint passed (6 模块 + 4 schema 全实施)
- [ ] S04 orchestration-ui sprint passed (C1-C4 全部 spec)
- [ ] PaneHygieneRegistry 实施完成 (58+ tests pass)
- [ ] LedgerWriter 实施完成 (双引擎双写可用)
- [ ] RecoverDetector / PaneClearManager / DispatchScheduler 实施完成
- [ ] init_pane_hygiene.py 可生成 pane-hygiene.json

### S05 测试矩阵

- [ ] S05-T-DASHBOARD-01: Dashboard 9 指标 E2E (mock 数据 + SLO 颜色 + TUI ASCII 格式)
- [ ] S05-T-CLI-01: pane-status CLI E2E (4 subcommands + JSON schema + 退出码 + --watch)
- [ ] S05-T-CONFIG-01: Config UI hot-reload E2E (3 组配置变更 → reload → 审计 → 回滚)
- [ ] S05-T-RESPAWN-01: Autopilot respawn E2E (fixture pane only, 4 用例 + PROTECTED_PANES)
- [ ] S01 32 AC 全部回归验证
- [ ] S02 D1-D7 + OQ-01..OQ-05 决议验证

### 环境约束

- respawn 测试仅在 `solar-harness-test` 专用 tmux session 中执行
- 不杀生产主 pane (solar-harness:0.0-0.2)
- 不改生产 pane-hygiene.json / spillover_config.yaml
- 不重启 ThunderOMLX / ASR

---

## 剩余风险

### R1: Dogfood 风险 — builder pane 撞 proceed/queued prompt

当前 5 panes 天然 spillover 是 S03 实施前唯一保护。若所有 builder pane 同时卡住，dispatch 队列将停滞。S03 RecoverDetector + PaneClearManager 实施后自动检测清理。

### R2: S03 接口偏离 S02 规约

C1-C4 全部基于 S02 interfaces.md 假定接口签名。若 S03 实施时接口名称/参数/返回格式偏离，S05 验收需做 schema 对齐。偏离项记入 OQ-new 给协调器。

### R3: autopilot respawn 失败兜底

respawn 任一步骤失败 → ATLAS structured repair。若 ATLAS 也无法修复 → pane 保持 needs_respawn 状态需人工介入。`respawn_max_concurrent=0` 可禁用自动 respawn 降级为全人工。PROTECTED_PANES 保护主 pane 不被自动 kill。

### R4: Ledger 双写一致性

dispatch-ledger.jsonl + model_call_ledger.sqlite 双引擎可能一方写入失败。S02 D6 定义了 fallback file + ATLAS 对账。C1 指标 7 (ledger_write_lag_p99_ms) 监控写入延迟。

### R5: spillover pool 硬编码 5 pane

data_models.md §3.2 列出具体 pane ID。S03 必须从 pane-hygiene.json 动态读取，不能硬编码。C3 §4 定义了动态池配置 UI。

---

## 禁止乐观词声明

本文档不含 已修复/稳定/完美/无需担忧/done/complete/implemented 等乐观词汇。S04 是 orchestration-ui 规约切片，只产出 spec 文档和集成计划，不实施任何代码或运行时变更。所有 builder_eligible 标记为 conditional 或 NO。

---

## 禁止把 cooldown 当作最终修复声明

cooldown 只是 /clear 或 recover 失败后的临时等待缓冲，不是最终修复手段。cooldown 结束后必须重新评估 pane 状态 (per S02 architecture.md §9.2 硬约束):

- cooldown 结束 pane 仍被卡住 → transition(cooling → needs_recover) 继续恢复流程
- cooldown 结束 pane 未被卡住 → transition(cooling → dirty) 回到待清理
- **禁止** cooling 直接 transition → running
- **禁止** cooldown 作为 pane lifecycle 的终态

---

Knowledge Context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback); Read 工具直接读取 C1-C4 spec + S02 handoff/traceability + PRD + design
Harness Modules Used: harness-knowledge (Read: C1-C4 artifacts + S02 handoff/traceability + PRD + design)
