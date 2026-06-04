# Plan — S04 Orchestration-UI (TUI Pane Dashboard + Config UI + Autopilot Respawn 集成)

gate: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s04-orchestration-ui:passed`
knowledge_context: solar-harness context inject used
upstream: S02 architecture passed (D1-D7 + OQ-01..OQ-05); S03 core-runtime in parallel
downstream: S05 verification-release

## 0. DAG

```
                ┌─→ C1_dashboard_renderer_spec       (glm-5.1) ─┐
                ├─→ C2_pane_status_cli_spec         (glm-5.1) ─┤
   (上游 S02 ok) ─┼─→ C3_config_ui_spec              (glm-5.1) ─┼─→ C5_traceability_handoff (sonnet)
                └─→ C4_autopilot_respawn_integration_plan (sonnet) ┘
```

**Wave 1 (4 并行)**: C1 / C2 / C3 / C4
**Wave 2 (join)**: C5

## 1. 节点验收

| 节点 | 关键验收 |
|------|----------|
| **C1** dashboard | 9 指标渲染规约 (per S02 §9.3) + HTML/TUI 双方案草图 + 数据源 LedgerWriter+PaneHygieneRegistry + SLO 状态行 hard/soft 阈值; ≥5 验收 |
| **C2** pane-status CLI | `solar-harness pane-status [--json] [--pane] [--watch]` + JSON schema 10 字段 + 4 subcommand (list/show/recover-history/ledger-tail) + 退出码 0/1/2/3; ≥4 验收 |
| **C3** config UI | 3 组可编辑项 (检测/清理/spillover) + hot-reload + 配置审计写 ledger; ≥4 验收 |
| **C4** autopilot respawn | OQ-05 命令序列 5 步集成 (kill-pane/split-window/等待 ready marker/init+全 clean/写 ledger) + 失败回退 ATLAS + 不杀主 pane + 验证用例 (成功+3 类失败); **只写计划不真调 tmux**; ≥5 验收 |
| **C5** join | traceability.json 12 字段 (含 outcomes_4 / decisions_consumed S02 §9.3+§10.6+OQ-05 / s03_dependencies / downstream S05); handoff 含 C1-C4 摘要 + S05 启动 checklist + 剩余风险 + 禁止乐观词 + 禁止 cooldown 当最终修复声明 |

## 2. Stop Rules

- 缺 task_graph.json 不得派 builder
- 发现 S03 接口偏离 S02 → C5 记 OQ
- 不真改 Solar 源码 (本 sprint 是规约层)
- 不真跑 tmux 命令 / dashboard 启动 / config UI 上线
- 不调 autopilot 真触发 respawn (C4 只写计划; 真跑留 S05)
- 不杀主 pane (本 sprint 不真跑)
- 不真改生产配置文件
- 不打印 API key / OAuth
- 不主动 close 父 epic
- 不假装 S03 已实施
- 不把 cooldown 当作最终修复 (S02 D2 硬约束)
- 不切换到 API 默认路径 (PRD G1)
- 不用乐观词

## 3. SLO

| 指标 | hard | soft |
|------|------|------|
| outcome 覆盖 (C1-C4) | < 4 → FAIL | n/a |
| C1 dashboard 指标数 | < 9 → FAIL | n/a |
| C2 CLI subcommand 数 | < 4 → FAIL | n/a |
| C3 配置组数 | < 3 → FAIL | n/a |
| C4 respawn 命令步骤 | < 5 → FAIL | n/a |
| C4 失败路径数 | < 3 → FAIL | n/a |
| 任一节点含真跑命令 (shell exec / tmux send-keys / curl autopilot) | > 0 → 立即 FAIL | n/a |
| 杀主 pane 命令出现 | > 0 → 立即 FAIL | n/a |
| "cooldown 当最终修复" 出现 | > 0 → 立即 FAIL | n/a |

## 4. 失败恢复

- C1-C4 任一 FAIL: 单节点重派
- C5 FAIL: 诊断哪个 C 节点缺失/不一致, 回写
- 若 S03 偏离 S02: C5 记 OQ 给协调器, 不擅自修 S02
- **Dogfood 风险**: builder pane 撞 proceed/queued → 现有 5 panes 天然 spillover

## 5. 给下游接力 (S05)

C5 traceability `downstream_sprint_kickoff_package.S05`:
- C1-C4 全部规约文档
- dashboard 9 指标 E2E 测试用例
- pane-status CLI E2E 测试
- config UI hot-reload 集成测试
- autopilot respawn E2E 真跑用例 (fixture pane only, 不杀主 pane)
