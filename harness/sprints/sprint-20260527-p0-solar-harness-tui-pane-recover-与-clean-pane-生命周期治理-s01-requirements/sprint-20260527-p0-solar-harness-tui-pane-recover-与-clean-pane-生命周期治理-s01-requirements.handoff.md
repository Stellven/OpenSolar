# Handoff — S01 Requirements: TUI Pane Recover 与 Clean Pane 生命周期治理

sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s01-requirements`
epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
node: `N4_traceability_handoff`
generated_at: `2026-05-27T18:15:00Z`

---

## N1..N3 各产出路径与摘要

### N1 — Pane Hygiene Registry + Recover Automation (O1 + O2)

**路径**: `sprints/sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s01-requirements.requirements.pane_hygiene_and_recover.md`

**摘要** (≤80 字):
O1: pane-hygiene.json ≥7 字段 + 6 状态机 (clean/dirty/running/cooling/needs_recover/needs_respawn) 转移表 + 派发前 hygiene 检查。O2: 3 类 prompt 检测器 (proceed/queued/permission) + 清理策略 + 失败升级路径。阻塞项: OQ-01/OQ-02/OQ-05。builder_eligible=false。

**节点状态**: passed

### N2 — Auto /clear + Context Reinject (O3 + O4)

**路径**: `sprints/sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s01-requirements.requirements.auto_clear_and_reinject.md`

**摘要** (≤80 字):
O3: /clear 触发时机 (task_completed + dispatch group/sprint sibling 边界) + 成功判定三件齐 (空 prompt + 无 queued + 无确认框)。O4: clean→running 时注入 persona/runtime policy/Solar context + 模板源 + 失败回退。阻塞项: OQ-03。builder_eligible=false。

**节点状态**: passed

### N3 — Spillover Ledger Safety (O5 + O6 + O7)

**路径**: `sprints/sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s01-requirements.requirements.spillover_ledger_safety.md`

**摘要** (≤80 字):
O5: 主 Evaluator + clean lab spillover + --max-items 3 不撞同 pane 算法。O6: recover/clear/reassign → ledger 双写 (≥6 字段)。O7: 4 安全护栏 + py_compile + 回归测试草案。阻塞项: OQ-04。builder_eligible=false。

**节点状态**: passed

---

## Traceability 摘要

| 指标 | 值 |
|------|-----|
| Outcome 总数 | 7 (O1..O7) |
| P0 占比 | 100% (7/7) |
| Builder 可派 | 0 (全部 blocked by S02 decisions) |
| Open Questions | 5 (OQ-01..OQ-05, 全部 owner=S02) |
| 验收标准总数 | 32 (O1:5 + O2:5 + O3:5 + O4:5 + O5:4 + O6:4 + O7:4) |
| V→Outcome 映射 | V1+V2→O2 / V3+V4→O3 / V5→O4 / V6→O5 / V7→O6 / V8→O7 |
| 依赖矩阵深度 | O1(root) → O2,O3,O5(layer1) → O4,O6(layer2) → O7(layer3) |
| 非目标 | 8 条 |
| Builder 禁止项 | 6 条 |

---

## S02 启动 Checklist

S02 (Architecture) 启动前必须完成以下步骤：

### Step 1: 读取全部 7 份 outcome requirements

- [ ] 读 N1 requirements doc (O1: Pane Hygiene Registry + O2: Recover Automation)
- [ ] 读 N2 requirements doc (O3: Auto /clear + O4: Context Reinject)
- [ ] 读 N3 requirements doc (O5: Spillover + O6: Ledger + O7: Safety)

### Step 2: 解决 7 项架构决策

1. **pane-hygiene.json 完整物理 schema** — 含持久化频率 (OQ-01)
2. **6 状态转移完整规则** — 含 retry 阈值 + cooldown 时长 (OQ-02)
3. **proceed-prompt 检测器实现方式** — tmux text parse / json output / 专用状态文件
4. **/clear 成功判定信号采集机制** — tmux capture-pane vs 专用状态文件
5. **persona-reinject 模板源路径** — 重注入频率 (OQ-03) + 模板文件位置
6. **ledger 字段 schema + 存储引擎** — SQLite / JSONL / 其他 + 同步/异步写
7. **spillover 调度策略 + 池规模** — round_robin / least_busy / random (OQ-04)

### Step 3: 回答 5 个 Open Questions

| OQ ID | 问题 | 期望 S02 产出 |
|-------|------|--------------|
| OQ-01 | pane-hygiene.json 持久化频率 | 持久化策略文档 + 性能评估 |
| OQ-02 | /clear 失败 retry 阈值 | 阈值数值 + 升级路径文档 |
| OQ-03 | 重注入频率 (重 vs 轻) | 策略选择 + kill_criteria |
| OQ-04 | spillover 池规模 | 池大小数值 + 与现有 pane 配置对齐 |
| OQ-05 | respawn 重建命令 | tmux 命令序列 + 等待信号 |

### Step 4: S02 输出

- `architecture.md` — 整体架构 + 模块划分 + 数据流
- `data_models.md` — pane-hygiene schema + ledger schema + spillover config
- `interfaces.md` — PaneHygieneRegistry / RecoverDetector / PaneClearManager / PersonaReinjector / LedgerWriter / SafetyGuardrails 接口签名

---

## Open Questions 全列表

| ID | Topic | Status | Owner |
|----|-------|--------|-------|
| OQ-01 | pane-hygiene.json 持久化频率 (每次写盘 vs 内存缓存 + 定期持久化) | open | S02 |
| OQ-02 | /clear 失败的 retry 次数与升级到 needs_respawn 阈值 | open | S02 |
| OQ-03 | Persona/Runtime/Context 重注入频率: 每次派发全量注 (重) vs 仅 clean→running 转换注 (轻) | open | S02 |
| OQ-04 | spillover 池规模: 主 + 几个 clean lab, 与现有 solar-harness-lab pane 个数对齐 | open | S02 |
| OQ-05 | needs_respawn 触发时 worker pane 重建的实际 tmux 命令与等待信号 | open | S02 |

---

## 禁止乐观词声明

本文档及本 sprint 所有产出中禁止使用以下词语：
- "已修复" / "稳定" / "完美" / "无需担忧" / "done" / "complete" / "implemented"

S01 为需求规约阶段，未实施任何代码。所有功能描述均为需求层面，不代表已实施或已验证。

## 禁止 cooldown 当最终修复声明

**显式声明**: cooldown 不作为任何 pane 生命周期问题的最终修复手段。

cooldown 仅在 recover 失败后作为过渡保护状态使用。cooldown 超时后必须升级到以下动作之一：
- 重新尝试 recover（回到 `needs_recover` 状态）
- 标记 `needs_respawn` 并触发 worker pane 重建
- 将任务 reassign 到其他可用 pane

不允许 pane 永久停留在 `cooling` 状态。

---

## Scope Compliance

Write scope:
- ✅ `traceability.json` — 已写入 (12 字段 + 7 outcomes + dependency matrix + 5 OQ + downstream package)
- ✅ `handoff.md` — 已写入 (本文件)

Read scope (全部已读):
- ✅ N1 requirements doc
- ✅ N2 requirements doc
- ✅ N3 requirements doc
- ✅ PRD
- ✅ Contract
- ✅ Design
- ✅ Epic
- ✅ Task graph

No out-of-scope writes.

---

## Not Done

- S02..S05 未启动 (依赖 S01 evaluator passed)
- OQ-01..OQ-05 均未解决 (全 open, 等 S02)
- 无任何代码实施 (S01 为规约阶段)

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge (Read: N1/N2/N3 requirements docs + PRD + design + contract + epic + task graph)
