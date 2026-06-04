# Design — S02 Architecture 切片：TUI Pane Recover 与 Clean Pane 生命周期治理系统设计

epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s02-architecture`
slice: `architecture`
role: planner
status: planning_complete
generated_at: 2026-05-27T18:20:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
upstream: S01 requirements finalized + passed (7 outcomes / 32 acceptance / 5 OQ, builder_eligible=0)
downstream: S03 core-runtime · S04 orchestration-ui

## 0. 切片边界

- **S02 是 architecture 切片**: 消费 S01 R1-R7 + 5 OQ + 7 决策项；产 architecture / data_models / interfaces / OQ resolutions + traceability。
- **S02 不写实施代码**: builder 只写 markdown 规约 + DDL 草案 + API 签名草案；禁止改 solar-harness 任何 python/sh/yaml 源码。
- **本 sprint 允许的写范围**:
  - `~/.solar/harness/sprints/<s02-sid>.architecture.md` (A1)
  - `~/.solar/harness/sprints/<s02-sid>.data_models.md` (A2)
  - `~/.solar/harness/sprints/<s02-sid>.interfaces.md` (A3)
  - `~/.solar/harness/sprints/<s02-sid>.open_questions_resolutions.md` (A4)
  - `~/.solar/harness/sprints/<s02-sid>.traceability.json` + `<s02-sid>.handoff.md` (A5 join)
- **严格禁止**:
  - 修改 S01 任何 artifact (3 份 requirements docs + traceability + handoff)
  - 修改父 epic 任何 artifact
  - 修改 solar-harness 任何源码
  - 真改 `~/.solar/harness/run/pane-hygiene.json` (S02 只写 schema 草案，实施留 S03)
  - 真跑 tmux send-keys / /clear / pane respawn / dispatch-evals (本 sprint 是规约层)
  - 把 cooldown 当作最终修复 (S01 PRD 与本 sprint 都明示禁止)
  - 切换到 API 默认路径 (PRD G1 明示 TUI 保留)
- 禁止乐观词；禁止把 OQ 标 resolved 后留空理由。

## 1. 上游消费 (S01 → S02)

| S01 产出 | S02 必须消费 |
|----------|---------------|
| N1 requirements.pane_hygiene_and_recover.md (17727 字节) | O1 (Hygiene Registry + 6 状态机) + O2 (3 类 prompt 检测器) |
| N2 requirements.auto_clear_and_reinject.md (17600 字节) | O3 (/clear 触发链 + 成功判定三件) + O4 (重注入器 + 模板源) |
| N3 requirements.spillover_ledger_safety.md (10799 字节) | O5 (spillover + --max-items 3 不撞同) + O6 (ledger 双写 ≥6 字段) + O7 (4 安全护栏) |
| traceability.json (11219 字节) | 7 outcomes + outcome_dependency_matrix + 5 OQ + 7 S02 决策项 |
| handoff.md (6563 字节) | S02 启动 checklist (Step 1-4) + 8 V→Outcome 映射 |

总计 ≥ 53 KB 需求文档 + 7 outcome 全 blocked_by S02。

## 2. S02 必须解决的 7 项决策 (从 S01 handoff §Step 2)

| Dec-id | 主题 | OQ 关联 | 落入文档 |
|--------|------|---------|----------|
| D1 | pane-hygiene.json 完整物理 schema + 字段定义 + 默认值 | OQ-01 (持久化频率) | A2 |
| D2 | 6 状态转移完整规则 + retry 阈值 + cooldown 时长 + 升级路径 | OQ-02 | A1/A4 |
| D3 | proceed-prompt 检测器实现方式 (tmux text parse / json output / 专用状态文件) | (新决策) | A1/A3 |
| D4 | /clear 成功判定信号采集机制 (tmux capture-pane vs 专用状态文件) | (新决策) | A1/A3 |
| D5 | persona-reinject 模板源路径 + 重注入频率 | OQ-03 | A1/A4 |
| D6 | ledger 字段 schema + 存储引擎 (SQLite / JSONL / 其他) + 同步/异步写 | (新决策) | A2 |
| D7 | spillover 调度策略 + 池规模 (round_robin / least_busy / random) | OQ-04 | A1/A4 |

加上 OQ-05 (needs_respawn 重建命令)，归 A4。共 5 OQ。

## 3. S02 内部 DAG (5 节点)

```
A1_architecture (sonnet, 关键路径)
    ├─→ A2_data_models      ┐
    └─→ A3_interfaces       ├─→ A5_traceability_handoff (sonnet, join)
A4_open_questions_resolutions ┘   (与 A1 并行)
```

**Wave 1 (2 并行)**: A1 (关键路径), A4 (OQ 决议研究, 不消费 A1)
**Wave 2 (2 并行)**: A2 (depends_on A1), A3 (depends_on A1)
**Wave 3 (join)**: A5

**why A1 关键路径**: 模块边界 + 状态机 → A2 知道 schema 落地 + A3 知道 API 签名落在哪些模块
**why A4 与 A1 并行**: OQ 决议主要是研究 / 数值选型 (持久化频率 / retry 阈值 / 重注入频率 / 池规模 / respawn 命令), 不直接消费架构图

## 4. 节点产出结构

### A1 `architecture.md` 必须 10 节

1. **系统全景图** (text/mermaid) — 4 大组件: PaneHygieneRegistry / RecoverDetector / PaneClearManager / PersonaReinjector / LedgerWriter / DispatchScheduler
2. **模块划分** — 与 S01 7 outcome 对齐 (每模块至少覆盖 1 个 outcome)
3. **control plane vs data plane**:
   - Control plane: graph-dispatch / coordinator / DispatchScheduler / autopilot
   - Data plane: pane-hygiene.json registry / ledger files / context inject prompt / tmux pane output
4. **6 状态机完整规则** (D2): 转移表 + 转移触发器 + retry 阈值 + cooldown 时长
5. **3 类 prompt 检测器** (D3): tmux capture-pane 管道 + 正则规则 + 检测频率
6. **/clear 触发链 + 成功判定** (D4): 三件 (空 prompt + 无 queued + 无确认框) + 检测方法
7. **持续注入策略** (D5): clean→running 触发 + 模板源 + 注入失败回退
8. **spillover 调度** (D7): 主 + 几个 clean lab pane + --max-items 3 算法
9. **失败恢复 / 观测**: 5 错误码 → cooldown / needs_respawn / reassign + dashboard
10. **冲突 / 依赖 / 降级 / 非目标 / S03+S04 接力**

### A2 `data_models.md` 必须 5 节

1. **pane-hygiene.json schema** (per D1): ≥10 字段 (pane_id / current_state / last_state_change_at / dispatch_id / persona / runtime_policy_hash / context_hash / clear_attempts / cooldown_until / respawn_count)
2. **ledger schema** (per D6): dispatch-ledger.jsonl + model_call_ledger.sqlite 双引擎; ≥6 字段 (pane_id / action / before_state / after_state / ts / reason); 同步/异步写策略
3. **spillover config schema**: pool 池配置 + per-pane 权重 + reassign 优先级
4. **持久化策略** (per OQ-01): 持久化频率 + atomic write + lock 策略
5. **数据生命周期**: pane-hygiene 滚动归档 / ledger TTL / 备份策略

### A3 `interfaces.md` 必须 6 节

1. **PaneHygieneRegistry API**: `get_pane_state()` / `transition_state()` / `query_clean_panes()` 签名
2. **RecoverDetector API**: `detect_proceed_prompt()` / `detect_queued_message()` / `detect_permission_prompt()` 签名
3. **PaneClearManager API**: `clear_pane()` / `verify_clear_success()` 签名
4. **PersonaReinjector API**: `inject_persona()` / `inject_runtime_policy()` / `inject_solar_context()` 签名
5. **LedgerWriter API**: `record_recover()` / `record_clear()` / `record_reassign()` 签名 + 双写一致性
6. **DispatchScheduler API**: `select_pane()` / `spillover_select()` 签名 (per OQ-04 调度策略)

### A4 `open_questions_resolutions.md` 每 OQ 6 字段

每 OQ 必须含:
- **decision** (明确方案，禁止"待定")
- **rationale** (≥3 项支撑事实)
- **alternatives_considered** (≥2 个被否方案 + 否定理由)
- **risks_residual**
- **owner_for_implementation** (S03/S04/S05)
- **fallback**

5 OQ 决议建议方向 (planner 视角):
- **OQ-01** (持久化频率): 内存缓存 + 状态转移即写盘 (atomic 写入)，避免每次访问写盘
- **OQ-02** (/clear retry 阈值): 3 次 retry + 每次 5s backoff; 第 4 次失败标 needs_respawn
- **OQ-03** (重注入频率): clean→running 时全量注入；同 session 内再次派发不重注 (轻策略)
- **OQ-04** (spillover 池规模): 与现有 5 个 solar-harness-lab pane 对齐 (solar-harness:0.3 主 + lab:0.0..0.3 4 个 spillover)
- **OQ-05** (respawn 命令): `tmux kill-pane -t <pane>` + `tmux split-window -t <window>` + 等待 prompt 就绪信号 (e.g. claude-code session ready marker)

### A5 `traceability.json` 12 字段 + `handoff.md`

```json
{
  "schema_version": "solar.s02_architecture.traceability.v1",
  "sprint_id": "...",
  "epic_id": "...",
  "generated_at": "<UTC>",
  "knowledge_context": "solar-harness context inject used",
  "decisions": [
    {"dec_id": "D1", "outcome": "O1", "decision": "...", "doc": "data_models.md§1"}
    /* D1..D7 */
  ],
  "oq_resolutions": [
    {"oq_id": "OQ-01", "decision": "...", "owner": "S03", "doc": "open_questions_resolutions.md§OQ-01"}
    /* OQ-01..OQ-05 */
  ],
  "module_inventory": ["PaneHygieneRegistry", "RecoverDetector", "PaneClearManager", "PersonaReinjector", "LedgerWriter", "DispatchScheduler"],
  "data_schema_inventory": ["pane-hygiene.json", "dispatch-ledger.jsonl", "model_call_ledger.sqlite", "spillover_config.yaml"],
  "downstream_sprint_kickoff_package": {
    "S03_core_runtime_inputs": [...],
    "S04_orchestration_ui_inputs": [...],
    "S05_verification_inputs": [...]
  },
  "open_questions_carried_over": [],
  "files_touched": [...]
}
```

`handoff.md` 必须含: A1-A4 摘要 + 7 决议摘要 + 5 OQ 决议摘要 + S03/S04 启动 checklist + 剩余风险 + 禁止乐观词声明 + 禁止 cooldown 当最终修复声明。

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| A1 | sonnet | 关键路径; 7 决策 + 6 状态机 + control/data plane 设计需 reasoning |
| A2, A3 | glm-5.1 | DDL/API 签名模板化, 依赖 A1 模块边界 |
| A4 | sonnet | 5 OQ 决议 + alternatives 分析需 reasoning (尤其 OQ-04 与现有 pane 对齐, OQ-05 tmux 命令选型) |
| A5 (join) | sonnet | 跨节点聚合 + downstream package |

## 6. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写父级 traceability `open_questions_carried_over` (不动 epic)
- 不写实施代码 (即使 stub)
- 不擅自修 S01 artifacts
- 不主动 close 父 epic
- 不放宽 OQ 决议 (任一 decision="待定" → FAIL)
- 不真改 pane-hygiene.json (A2 只写 schema 草案)
- 不真跑 tmux / dispatch-evals (本 sprint 是规约层)
- 不把 cooldown 当作最终修复
- 不切换到 API 默认路径

## 7. 失败恢复 / 降级

- A1 失败 → A2/A3 不能启动; A4 可继续; 单 A1 重派
- A2/A3 任一失败 → 单节点重派, 不阻塞另一个 + 不阻塞 A4
- A4 失败 → 单节点重派; A5 必须等 A4 才能定 oq_resolutions
- A5 join 失败 → 诊断哪个 A 节点决议缺失, 回写对应 A 节点
- 若 S01 内部矛盾 → A4 记 OQ-new 给协调器, 不擅自修 S01
- **Dogfood 风险**: 本 sprint 治理的就是 TUI pane 问题; 若 A1-A5 builder pane 撞 proceed/queued prompt, 仅能依赖现有 5 evaluator panes 天然 spillover (实施未上线); 卡死则 ATLAS structured repair

## 8. 非目标

- 不写实施代码
- 不真改 pane-hygiene.json
- 不真跑 tmux / /clear / dispatch-evals
- 不擅自修 S01 artifacts
- 不主动 close 父 epic
- 不放宽 OQ 决议
- 不实施 builder 范围 (S03 core-runtime 与 S04 orchestration-ui)
- 不把 cooldown 当作最终修复 (per S01 PRD)
- 不切换到 API 默认路径 (PRD G1)
- 不删用户数据 / 不杀主 pane / 不重启 ThunderOMLX

## 9. 给 epic 推进的接力

- A5 traceability `downstream_sprint_kickoff_package` 写明 S03/S04/S05 各自 inputs
- coordinator 在 S02 evaluator passed 后自动激活 S03 + S04 (epic.task_graph 中 S03/S04 都 depends_on=S02, 可同批激活)
- S05 verification-release 必须等 S03 + S04 都 passed

## 10. Dogfood 注释

本 sprint 治理 TUI pane 生命周期问题，而本 sprint 的 A1-A5 builder 派发本身也用到 TUI pane。这是真 dogfood：
- A1-A4 是 markdown 规约起草，不实施 pane lifecycle 代码，所以即使现有 pane 卡死，本 sprint 仍可完成
- 但若 builder pane 在起草过程中撞 proceed/queued prompt → 依赖现有 5 panes 的天然 spillover (capacity 已扩到 5)
- 实施 (S03/S04) 完成后, 本 sprint 治理能力将服务于后续 sprint 的派发链路 - 闭环完成
