# Plan — S01 Requirements (Solar Harness TUI Pane Recover 与 Clean Pane 生命周期治理切片)

epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s01-requirements`
slice: `requirements`
gate: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s01-requirements:passed`
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)

## 0. 切片定位

Epic 第一切片，治理 solar-harness 自身 TUI pane 生命周期。PRD 已完整 (6 G / 9 I / 8 V)。本切片把内容编排为 N1-N3 规约节点 + N4 join，产 traceability + handoff，**禁止实施代码 / 真跑 tmux / 真改 pane-hygiene.json**。

## 1. DAG 与并行边界

```
                  ┌─→ N1_pane_hygiene_and_recover   (O1+O2) ─┐
   (无上游) ────────┼─→ N2_auto_clear_and_reinject    (O3+O4) ─┼─→ N4_traceability_handoff
                  └─→ N3_spillover_ledger_safety    (O5+O6+O7) ┘     (join)
```

**Wave**：

| 批次 | 节点 | 模型 | write_scope |
|------|------|------|-------------|
| Wave 1 | N1 / N2 / N3 | glm-5.1 ×3 | 3 个 `.requirements.<topic>.md` 各一份 (零重叠) |
| Wave 2 (join) | N4 | sonnet | `.traceability.json` + `.handoff.md` |

**write_scope 互斥**：

- N1: `sprints/<sid>.requirements.pane_hygiene_and_recover.md`
- N2: `sprints/<sid>.requirements.auto_clear_and_reinject.md`
- N3: `sprints/<sid>.requirements.spillover_ledger_safety.md`
- N4: `sprints/<sid>.traceability.json` + `sprints/<sid>.handoff.md`

## 2. 每份 requirements 文档统一结构

按 design §3 八节：outcome_id 清单 / 目标背景 / 验收 per O-id ≥3 / 数据契约草案 / 接口契约草案 / 依赖与冲突 / 风险边界 + 非目标 / builder eligibility=NO + 先需 S02 决定。

## 3. 每节点验收 gate

| 节点 | 关键验收 |
|------|----------|
| **N1** (O1+O2) | 文件存在；O1 ≥3 验收 (pane-hygiene.json schema 字段 + 6 状态机转移表 + 派发前 hygiene 检查规则)；O2 ≥3 验收 (3 类 prompt 检测器：proceed/queued/permission + 清理成功判定 + 失败升级到 cooldown 或 needs_respawn)；引 PRD G1+G2 / I1+I2+I7 / V1+V2 原文；标 OQ-01+OQ-02+OQ-05 阻塞 |
| **N2** (O3+O4) | 文件存在；O3 ≥3 验收 (任务完成 /clear 触发 + dispatch group / sprint sibling 边界检测 + clear 成功判定="空 prompt + 无 queued + 无确认框")；O4 ≥3 验收 (Persona + Runtime Policy + Solar Context 重注入清单 + 模板源 + clean→running 重注入触发点)；引 PRD G3+G4 / I3+I4+I5+I6 / V3+V4+V5；标 OQ-03 阻塞 |
| **N3** (O5+O6+O7) | 文件存在；O5 ≥3 验收 (主 Evaluator + clean lab spillover + dispatch-evals --max-items 3 不撞同 pane 算法)；O6 ≥3 验收 (recover/clear/reassign 全写 dispatch-ledger + model_call_ledger + 字段含 pane_id/action/before_state/after_state/ts/reason)；O7 ≥3 验收 (4 安全护栏: 不杀主 pane / 不删数据 / 不重启 ThunderOMLX-ASR / cooldown 不当最终修复 + py_compile + 最小回归测试)；引 PRD G5+G6 / I8+I9 / V6+V7+V8；标 OQ-04 阻塞 |
| **N4** (join) | traceability.json 含 12 字段全集 (schema_version='solar.s01_requirements.traceability.v1' / sprint_id / epic_id / generated_at / knowledge_context / outcomes[O1..O7] / outcome_dependency_matrix / non_goals_aggregate / builder_forbidden_aggregate / downstream_sprint_kickoff_package / open_questions / files_touched)；outcomes 数组 = 7 条；outcome_dependency_matrix 覆盖 O1..O7；non_goals ≥6；builder_forbidden ≥4；downstream_sprint_kickoff_package 含 S02/S03/S04/S05 inputs；open_questions ≥5 (OQ-01..OQ-05 全 owner=S02)；handoff 含 N1..N3 摘要 + 7 决策项 + S02 启动 checklist + 5 OQ 列表 + 禁止乐观词 + 禁止 cooldown 当最终修复声明 |

## 4. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写 N4 traceability `open_questions` (不动 epic)
- 不写实施代码 (即使 stub)
- 不真改 `~/.solar/harness/run/pane-hygiene.json`
- 不真跑 tmux send-keys / /clear / dispatch-evals 任何命令
- 不主动 close 父 epic
- 不把 cooldown 当作最终修复 (PRD 明示)
- 不删用户数据 / 杀主 pane / 重启 ThunderOMLX
- 不切换到 API 默认路径 (PRD G1 明示 TUI 保留)
- 不用乐观词

## 5. SLO

| 指标 | hard | soft |
|------|------|------|
| outcome 覆盖率 (O1..O7) | < 7 → FAIL | n/a |
| 每 O-id 验收条件数 | < 3 → FAIL | < 5 → WARN |
| OQ 在 traceability 中条数 | < 5 → FAIL | n/a |
| 任一 OQ 未带 owner+status | 立即 FAIL | n/a |
| 任一 outcome 含实施代码 (python/sh/yaml/真 tmux 命令) | > 0 → 立即 FAIL | n/a |
| 8 V 验收全覆盖到 outcome | < 8 → FAIL | n/a |
| builder_eligible 标记 | 任一未标 → FAIL | n/a |
| "cooldown 当最终修复" 在任一文档出现 | > 0 → 立即 FAIL | n/a |

## 6. 失败恢复

- N1..N3 任一 FAIL：单节点重派，不阻塞另 2 个
- N4 FAIL：诊断哪个 N 节点 outcome 描述缺失/不一致，回写对应 N 节点修复
- **Dogfood 风险**：本 sprint 的 builder 起草 markdown 时若撞 proceed/queued prompt → 因为本 sprint 治理的就是这类问题但实施未上线，仅能依赖现有 5 个 evaluator panes 的 spillover；如卡死无法恢复，标 wave-1 FAIL 等待用户介入

## 7. 给下游接力 (S02 architecture)

N4 traceability `downstream_sprint_kickoff_package.S02_architecture_inputs`：
- O1..O7 requirements docs
- outcome_dependency_matrix
- PRD 9 项实现要求 + 8 项验收
- 7 决策项 (registry schema / 状态机存储 / 3 类 prompt 检测器 / /clear 成功判定 / persona 模板源 / ledger 字段 / spillover 调度策略)

**S02 必须先解决**: O1 registry schema 与状态机（O2-O7 全部依赖 O1）。

coordinator 在 S01 evaluator passed 后自动激活 S02。

## 8. Knowledge Context

`solar-harness context inject` 已在 planner 入场时跑过；mirage degraded → QMD / Obsidian / Solar DB 默认源；ATLAS / Everything Claude Code / Solar-Harness Runtime / Superpowers / solar-graph-scheduler capabilities injected (per runtime context)。本 sprint self-contained，PRD 已完整。

## 9. Dogfood 备注

本 sprint 治理的是 solar-harness 自身 TUI pane 生命周期。S01 不实施代码，所以即使现在 pane 仍卡死，本 sprint 也能完成（只起草 markdown）。但下游 S03/S04 实施后，S05 验证时本 sprint 治理的能力将服务于后续 sprint 的派发链路—— 这是 dogfood 闭环的关键节点。
