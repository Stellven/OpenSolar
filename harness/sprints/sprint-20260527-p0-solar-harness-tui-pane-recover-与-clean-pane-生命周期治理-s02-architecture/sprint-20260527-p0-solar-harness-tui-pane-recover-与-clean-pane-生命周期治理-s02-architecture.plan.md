# Plan — S02 Architecture (TUI Pane Recover 系统设计切片)

gate: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s02-architecture:passed`
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db)
upstream: S01 requirements finalized + passed (7 outcomes / 32 acceptance / 5 OQ / 7 S02 决策项)
downstream: S03 core-runtime · S04 orchestration-ui

## 0. DAG 与并行边界

```
A1_architecture (sonnet, 关键路径)
    ├─→ A2_data_models      (glm-5.1) ┐
    └─→ A3_interfaces       (glm-5.1) ├─→ A5_traceability_handoff (sonnet, join)
A4_open_questions_resolutions (sonnet) ┘   (与 A1 并行)
```

**Wave 1 (2 并行)**: A1 (关键), A4 (OQ 决议)
**Wave 2 (2 并行 depends on A1)**: A2, A3
**Wave 3 (join)**: A5

**write_scope 互斥**:
- A1: `<sid>.architecture.md`
- A2: `<sid>.data_models.md`
- A3: `<sid>.interfaces.md`
- A4: `<sid>.open_questions_resolutions.md`
- A5: `<sid>.traceability.json` + `<sid>.handoff.md`

## 1. 节点验收

| 节点 | 关键验收 |
|------|----------|
| **A1** architecture | 含 10 节 (系统全景 / 模块划分 ≥6 / control vs data plane / 6 状态机表 D2 / 3 类 prompt 检测器 D3 / /clear 触发链+成功判定 D4 / 持续注入 D5 / spillover 调度 D7 / 失败恢复+观测 / 接力); 7 决策 D1-D7 全决议 (≤200 字); 模块按 outcome dependency 拓扑组织 |
| **A2** data_models | 含 5 节; pane-hygiene.json schema ≥10 字段 (D1); ledger 双引擎 schema (D6, dispatch-ledger.jsonl + model_call_ledger.sqlite, ≥6 字段); spillover config schema; 持久化策略 (D1+OQ-01); 数据生命周期; **不真实施 DDL** |
| **A3** interfaces | 含 6 节; 6 模块 API 签名 (PaneHygieneRegistry / RecoverDetector / PaneClearManager / PersonaReinjector / LedgerWriter / DispatchScheduler); 与 A1 模块清单一一对应; **不真实施代码** |
| **A4** OQ resolutions | OQ-01..OQ-05 全 5 OQ 每条含 6 字段 (decision / rationale ≥3 / alternatives_considered ≥2 / risks_residual / owner_for_implementation / fallback); 任一 decision='待定' → FAIL; OQ-04 spillover 池规模必须与现有 solar-harness-lab pane 个数对齐 (5 panes) |
| **A5** join | traceability.json 含 12 字段 (含 decisions[D1-D7] / oq_resolutions[OQ-01-OQ-05] / module_inventory ≥6 / data_schema_inventory ≥4); handoff 含 A1-A4 摘要 + 7 决议 + 5 OQ + S03/S04 启动 checklist + 剩余风险 + 禁止乐观词 + 禁止 cooldown 当最终修复声明 |

## 2. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写 A5 traceability `open_questions_carried_over` (不动 epic, 不动 S01)
- 不写实施代码 (即使 stub)
- 不擅自修 S01 任何 artifact
- 不主动 close 父 epic
- 不放宽 OQ 决议
- 不真改 pane-hygiene.json
- 不真跑 tmux / /clear / dispatch-evals 任何命令
- 不把 cooldown 当作最终修复 (per S01 PRD + 本 sprint 明示)
- 不切换到 API 默认路径 (per PRD G1)
- 不用乐观词

## 3. SLO

| 指标 | hard | soft |
|------|------|------|
| 7 决策项 D1-D7 落地 | < 7 → FAIL | n/a |
| 5 OQ 全决议 | < 5 → FAIL | n/a |
| A4 每 OQ 6 字段 | 任一缺 → FAIL | n/a |
| A4 任一 decision='待定' | > 0 → 立即 FAIL | n/a |
| A1 模块数 | < 6 → FAIL | < 8 → WARN |
| A2 schema 数 | < 4 → FAIL | n/a |
| A3 API 模块数 | < 6 → FAIL | n/a |
| 任一文档含实施代码 (真 python/sh/yaml) | > 0 → 立即 FAIL | n/a |
| 任一文档"cooldown 当最终修复" | > 0 → FAIL | n/a |
| OQ-04 spillover 池规模与 solar-harness-lab pane 个数对齐 | 不对齐 → FAIL | n/a |

## 4. 失败恢复

- A1 FAIL → A2/A3 阻塞; A4 可继续; 单 A1 重派
- A2/A3 任一 FAIL → 单节点重派
- A4 FAIL → 单节点重派; A5 等 A4 才能定 oq_resolutions
- A5 FAIL → 诊断哪个 A 节点缺失, 回写
- S01 内部矛盾 → A4 记 OQ-new
- **Dogfood 风险**: A1-A4 builder pane 撞 proceed/queued → 依赖现有 5 evaluator panes (capacity 已扩到 5) 天然 spillover; 卡死则 ATLAS structured repair

## 5. 给下游接力 (S03 core-runtime + S04 orchestration-ui)

A5 traceability `downstream_sprint_kickoff_package`:
- **S03 core-runtime inputs**: A1 模块边界 + 6 状态机 + A2 全部 schema 草案 + A3 6 模块 API 签名 + A4 OQ 决议 (OQ-01/OQ-02/OQ-03/OQ-05 实施)
- **S04 orchestration-ui inputs**: A1 spillover 调度 + A3 DispatchScheduler API + A4 OQ-04 (池规模决议)
- **S05 verification inputs**: A1 失败恢复 + 观测 / A3 测试桩点 / A4 OQ 验证用例 (V1-V8 → O1-O7)

coordinator 在 S02 evaluator passed 后自动激活 S03 + S04 (epic.task_graph 中 S03/S04 都 depends_on=S02, 可同批激活)。

## 6. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; ATLAS / Everything Claude Code / Solar-Harness Runtime / Superpowers / solar-graph-scheduler capabilities injected。S01 3 份 requirements docs (≥45 KB) + traceability (11 KB) + handoff (6.5 KB) 是本 sprint self-contained 输入。
