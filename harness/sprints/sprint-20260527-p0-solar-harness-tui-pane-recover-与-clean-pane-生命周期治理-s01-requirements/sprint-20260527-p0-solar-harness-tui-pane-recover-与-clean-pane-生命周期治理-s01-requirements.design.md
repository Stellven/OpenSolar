# Design — S01 Requirements 切片：Solar Harness TUI Pane Recover 与 Clean Pane 生命周期治理

epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s01-requirements`
slice: `requirements`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-27T16:19:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)`
upstream: `none (epic 首切片)`
downstream: `S02 architecture → S03 core-runtime · S04 orchestration-ui → S05 verification-release`

## 0. 切片边界（强制 read-first）

- **S01 是 epic 首切片**：上游空；产出供 S02..S05 消费的需求规约 + traceability。
- **PRD 已完整**：6 G 目标 + 9 实现要求 + 8 V 验收 + 子任务图。S01 工作是把这些编排为 N 个 outcome 规约文档 + 聚合 traceability，**不重写 PRD 内容**。
- **本 sprint 允许的写范围**：
  - `~/.solar/harness/sprints/<s01-sid>.requirements.pane_hygiene_and_recover.md` (N1, 覆盖 O1+O2)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.auto_clear_and_reinject.md` (N2, 覆盖 O3+O4)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.spillover_ledger_safety.md` (N3, 覆盖 O5+O6+O7)
  - `~/.solar/harness/sprints/<s01-sid>.traceability.json` + `<s01-sid>.handoff.md` (N4 join)
- **严格禁止**：
  - 修改 solar-harness 任何 python / sh / config 源码（实施归 S03/S04）
  - 真改 `~/.solar/harness/run/pane-hygiene.json`（PRD 指定的 registry 文件由 S03 实施时创建）
  - 真跑 `tmux send-keys` / `/clear` / pane respawn / dispatch-evals 等命令
  - 修改父 epic 任何 artifact
- 禁止乐观词；禁止把"cooldown"当作最终修复方案（PRD 明示禁止）；禁止删用户数据 / 杀主 pane（仅 needs_respawn 才允许重建该 worker pane）。

## 1. PRD 内容 → outcome 映射

PRD 提供 6 G 目标 + 9 实现要求 + 8 V 验收。聚合为 7 个 outcome：

| outcome_id | 标题 | 覆盖 PRD G/I/V | 优先级 | builder 直接派 | 聚合到节点 |
|------------|------|----------------|--------|----------------|------------|
| O1 | Pane Hygiene Registry + 6 状态机 (clean/dirty/running/cooling/needs_recover/needs_respawn) | G1+G2 / I1+I2 / 无独立 V | P0 | NO (S02 决定 registry schema / 状态机存储) | N1 |
| O2 | Recover 自动化 (proceed prompt / queued message / permission prompt 三类清理) | G2 / I7 / V1+V2 | P0 | NO (S02 决定检测器与清理策略) | N1 |
| O3 | Auto /clear + 边界 + 成功判定 (任务完成、dispatch group、sprint sibling 边界；clear 成功=空 prompt+无 queued+无确认框) | G3 / I3+I4+I5 / V3+V4 | P0 | NO (S03 实施 /clear 触发链) | N2 |
| O4 | Clean pane 再次派发前 Persona/Runtime/Solar Context 重注入 | G4 / I6 / V5 | P0 | NO (S03 实施重注入器 + S02 决定模板源) | N2 |
| O5 | 主 Evaluator + clean lab spillover + dispatch-evals 不撞同 pane (--max-items 3 分到 3 个 pane) | G5 / I8 / V6 | P0 | NO (S02 决定调度策略 + S04 实施) | N3 |
| O6 | Ledger 审计 (recover/clear/reassign 全写入 dispatch-ledger + model_call_ledger) | G6 / I9 / V7 | P0 | NO (S02 决定 ledger schema 字段 + S03 实施) | N3 |
| O7 | 安全护栏 + 测试 (不杀主 pane / 不删数据 / 不重启 ThunderOMLX/ASR / cooldown 不作最终修复 / py_compile + 最小回归测试) | I9 安全段 / V8 / G 全否定项 | P0 | NO (S05 实施 py_compile + 回归) | N3 |

7 outcome 全 P0；零 builder-eligible（S01 工作是规约不是实施）。

## 2. S01 内部 DAG（3 路 fan-out + 1 join）

```
                  ┌─→ N1_pane_hygiene_and_recover   (O1, O2)   ─┐
   (无上游) ────────┼─→ N2_auto_clear_and_reinject    (O3, O4)   ─┼─→ N4_traceability_handoff
                  └─→ N3_spillover_ledger_safety    (O5,O6,O7) ─┘     (join)
```

**并行批次**：

| 批次 | 节点 | 模型 | write_scope |
|------|------|------|-------------|
| Wave 1 | N1 / N2 / N3 | glm-5.1 ×3 | 3 个 `.requirements.<topic>.md` 各一份 (零重叠) |
| Wave 2 (join) | N4 | sonnet | `.traceability.json` + `.handoff.md` |

**write_scope 互斥**：N1/N2/N3 各写一个独立的 markdown 文件，N4 写 traceability+handoff。

## 3. 每份 requirements 文档统一结构 (N1..N3)

每份 `*.requirements.<topic>.md` 必含 8 节：

1. **outcome_id 清单** — 本节点覆盖的 O-id + PRD G/I/V 回链
2. **目标与背景** — 引用 PRD 原文要点（不抄全文，引段落）
3. **验收标准 per outcome** — 每 O-id ≥3 条可验证条件（复用 PRD V1-V8）
4. **数据契约草案** — pane-hygiene.json schema（N1）/ /clear 成功判定信号（N2）/ ledger 字段（N3）—— **不实施**
5. **接口契约草案** — Python class/CLI 签名草案 / hooks / tmux keypress 命令 —— **不实施**
6. **依赖与冲突** — 横向 (与其他 O-id) + 纵向 (哪个下游 S02/S03/S04/S05 消费)
7. **风险边界与非目标** — 复用 PRD 否定项；明示 cooldown 不作最终修复
8. **builder eligibility 判定** — 标 NO + 先需 S02 决定什么

## 4. N4 join 产出

**`<s01-sid>.traceability.json` 必须 12 字段**：

```json
{
  "schema_version": "solar.s01_requirements.traceability.v1",
  "sprint_id": "...",
  "epic_id": "...",
  "generated_at": "<UTC>",
  "knowledge_context": "solar-harness context inject used",
  "outcomes": [
    {
      "outcome_id": "O1",
      "title": "Pane Hygiene Registry + 6 状态机",
      "prd_section": "G1+G2 / I1+I2",
      "priority": "P0",
      "acceptance_count": "<n>",
      "downstream_sprints": ["S02", "S03"],
      "downstream_artifacts": ["architecture.md", "data_models.md (pane_hygiene schema)"],
      "builder_eligible": false,
      "blocked_by": ["S02 registry schema decision"],
      "requirements_doc": "sprints/<sid>.requirements.pane_hygiene_and_recover.md"
    }
    /* O2..O7 */
  ],
  "outcome_dependency_matrix": {
    "O2": ["O1"],
    "O3": ["O1"],
    "O4": ["O3"],
    "O5": ["O1"],
    "O6": ["O1", "O2", "O3", "O5"],
    "O7": ["O1", "O2", "O3", "O4", "O5", "O6"]
  },
  "non_goals_aggregate": [
    "不绕过 planner 派 builder",
    "不切换到 API 默认路径 (TUI 保留)",
    "不把 cooldown 当作最终修复",
    "不删用户数据",
    "不重启 ThunderOMLX/ASR",
    "不杀主 pane (仅 needs_respawn 重建 worker pane)"
  ],
  "builder_forbidden_aggregate": [
    "禁止真改 ~/.solar/harness/run/pane-hygiene.json",
    "禁止真跑 tmux send-keys / /clear / dispatch-evals 命令",
    "禁止改 solar-harness python/sh 源码",
    "禁止把 cooldown 当作最终修复"
  ],
  "downstream_sprint_kickoff_package": {
    "S02_architecture_inputs": [
      "O1-O7 requirements docs",
      "outcome_dependency_matrix",
      "PRD 9 项实现要求 + 8 项验收",
      "S02 必须先解决: pane-hygiene.json schema / 状态机存储 / proceed-prompt 检测器 / /clear 成功判定信号 / persona-reinject 模板源 / ledger 字段 schema / spillover 调度策略"
    ],
    "S03_core_runtime_inputs": [
      "pane-hygiene registry 物理 schema (per S02)",
      "/clear 触发链与成功判定",
      "Recover 自动化检测器实现",
      "Persona/Runtime/Context 重注入器",
      "Ledger 字段 ingest"
    ],
    "S04_orchestration_ui_inputs": [
      "dispatch-evals --max-items 3 调度",
      "主 Evaluator + clean lab spillover",
      "dispatch group / sprint sibling 边界检测"
    ],
    "S05_verification_inputs": [
      "V1-V8 8 项验收 + py_compile + 最小回归测试",
      "模拟 proceed / queued / permission prompt 测试用例",
      "spillover 不撞同 pane 测试"
    ]
  },
  "open_questions": [
    {"id": "OQ-01", "topic": "pane-hygiene.json 持久化频率 (每次写盘 vs 内存缓存+定期持久化)", "status": "open", "owner": "S02"},
    {"id": "OQ-02", "topic": "/clear 失败的 retry 次数与升级到 needs_respawn 阈值", "status": "open", "owner": "S02"},
    {"id": "OQ-03", "topic": "Persona/Runtime/Context 重注入是否每次派发都注 (重) vs 仅 clean→running 转换注 (轻)", "status": "open", "owner": "S02"},
    {"id": "OQ-04", "topic": "spillover 池规模 (主 + 几个 clean lab)，与现有 solar-harness-lab pane 个数对齐", "status": "open", "owner": "S02"},
    {"id": "OQ-05", "topic": "needs_respawn 触发时 worker pane 重建的实际 tmux 命令与等待信号", "status": "open", "owner": "S02"}
  ],
  "files_touched": [...]
}
```

**`<s01-sid>.handoff.md` 必须含**：
- N1..N3 各产出路径 + ≤80 字摘要
- traceability 摘要 (outcome 7 / P0 占比 / 阻塞数 / OQ 5)
- S02 启动 checklist (先读 O1..O7 + 7 决策项 + 5 OQ → 输出 architecture/data_models/interfaces)
- 5 OQ 全部 open 列表
- 禁止乐观词声明
- 禁止把 cooldown 当作最终修复声明

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| N1, N2, N3 | glm-5.1 | requirements spec 起草模板化，PRD 完整，省钱 |
| N4 (join) | sonnet | 跨节点聚合 + 7 outcome 依赖矩阵 + 5 OQ owner 分派 |

## 6. 跨 outcome 依赖矩阵

```
O1 (Hygiene Registry + 6 状态)      根
O2 (Recover) depends_on O1          (recover 操作目标 = registry 中的 dirty pane)
O3 (Auto /clear) depends_on O1      (clear 操作目标 = registry 中的 pane)
O4 (Re-inject) depends_on O3        (clean pane 重新被分配前必须 /clear 已完成)
O5 (Spillover) depends_on O1        (spillover 调度查 registry 找 clean pane)
O6 (Ledger) depends_on O1,O2,O3,O5  (ledger 记录所有 recover/clear/reassign)
O7 (安全护栏) depends_on O1..O6     (回归测试覆盖所有 outcome 行为边界)
```

S02 必须先解决 O1 的 registry schema 与状态机，再展开 O2-O7。

## 7. Stop Rules（继承 contract）

- 缺 `task_graph.json` 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写 N4 traceability `open_questions` (不动 epic)
- 不写 python / sh / yaml 实施代码（即使 stub）
- 不真改 `~/.solar/harness/run/pane-hygiene.json`
- 不真跑 tmux / /clear / dispatch-evals
- 不主动 close 父 epic
- 不把 cooldown 当作最终修复
- 不删用户数据 / 杀主 pane
- 不用乐观词

## 8. 失败恢复 / 降级

- N1/N2/N3 任一 FAIL → 单节点重派，不阻塞另 2 个
- N4 FAIL → 诊断哪个 N 节点 outcome 描述缺失/不一致，回写对应 N 节点修复
- 若 PRD 内部矛盾 → N4 记 OQ-new 给 PM，不擅自修 PRD
- mirage degraded → PRD 已完整，本 sprint self-contained

## 9. 非目标（明确禁止）

- 不切换到 API 默认路径 (PRD G1 明示 TUI 保留)
- 不把 cooldown 当作最终修复
- 不实施任何代码 / 真跑命令
- 不擅自修 PRD
- 不主动 close 父 epic
- 不删用户数据 / 杀主 pane / 重启 ThunderOMLX/ASR
- 不实施 OQ 解决方案 (5 OQ 全保持 open，等下游处理)

## 10. 给 epic 推进的接力

- N4 traceability `downstream_sprint_kickoff_package` 写明 S02..S05 各自 inputs。
- coordinator 在 S01 evaluator passed 后自动激活 S02 (per epic schedule)。
- S01 不主动 close 任何东西。

## 11. 与本系统 dogfood 关系

**本 sprint 治理的是 solar-harness 自身的 TUI pane 生命周期**——同时本 sprint 的 N1/N2/N3 builder 派发也会用到这些 TUI pane。这是 dogfood：

- S01 不实施任何 pane 治理代码，所以即使现在 pane 仍有 proceed/queued 卡死问题，本 sprint 仍可完成（PRD 已完整，builder 只起草 markdown）。
- 但本 sprint 完成时若 builder pane 出现卡死（比如本 N1 的 builder 撞 proceed prompt），可能需要 evaluator 手动 unblock；evaluator 已扩到 5 个 panes (solar-harness:0.3 + lab:0.0..0.3) 提供 spillover。
- N4 join 节点必须在 builder 完成 N1-N3 后才执行；如 dogfood 失败导致 wave-1 卡死，N4 不能强推。
