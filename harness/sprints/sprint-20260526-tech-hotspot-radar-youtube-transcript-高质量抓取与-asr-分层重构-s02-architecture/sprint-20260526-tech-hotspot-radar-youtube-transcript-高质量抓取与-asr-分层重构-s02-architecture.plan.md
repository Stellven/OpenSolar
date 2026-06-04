# Plan — S02 Architecture (YouTube Transcript 链路系统设计切片)

epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture`
slice: `architecture`
gate: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture:passed`
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)

## 0. 切片定位

S02 architecture sprint。上游 S01 已 passed，产出 5 份 requirements docs (1913 行) + 16 outcome + 4 OQ + 13 S02 决策项。本切片产出 architecture / data_models / interfaces / OQ resolutions + traceability，让 S03/S04 可启动。**禁止实施代码**。

## 1. DAG 与并行边界

```
A1_architecture (sonnet, 关键路径)
    ├─→ A2_data_models      ┐
    └─→ A3_interfaces       ├─→ A5_traceability_handoff (sonnet, join)
A4_open_questions_resolutions ┘   (与 A1 并行)
```

**Wave**：

| 批次 | 节点 | 模型 | write_scope |
|------|------|------|-------------|
| Wave 1 | A1, A4 | sonnet ×2 | `architecture.md`, `open_questions_resolutions.md` |
| Wave 2 | A2, A3 | glm-5.1 ×2 | `data_models.md` (depends_on A1), `interfaces.md` (depends_on A1) |
| Wave 3 (join) | A5 | sonnet | `traceability.json`, `handoff.md` |

**write_scope 互斥**：5 个独立文件，零重叠。

**关键路径**：A1 → {A2, A3} → A5。A4 与 A1 并行，A5 join all。

## 2. 每节点验收 gate（hard）

| 节点 | 关键验收 |
|------|----------|
| **A1** (architecture) | 含 10 节 (系统全景 / ≥6 模块 / control vs data plane / R1+R6 状态机表 / R6 5 error_code 恢复 / R13 9 dashboard + SLO / D1-D13 决议 / 冲突依赖降级 / 非目标 / S03+S04 接力)；D1-D13 每项 ≤200 字含决议+理由；模块按 Phase 1-4 拓扑组织 |
| **A2** (data_models) | 含 7 节；7 张表 DDL 草案 (R2 + R7×4 + R11 + R12) 字段全；外键 + 索引含业务热路径；legacy 3 阶段迁移 + 165 条污染清理 SQL 草案；存储估算 per 100/1000 video |
| **A3** (interfaces) | 含 8 节；≥6 模块内部 API 签名草案；R14 6 CLI argparse + 退出码 + 输出 schema；legacy process-transcripts 兼容包装；R15 YAML 5 子段 + 每字段类型/默认/验证；R10 evidence pack JSON schema；R11 cross_source 引用；事件契约 ≥3 类 |
| **A4** (OQ resolutions) | OQ1-OQ4 每条含 6 字段 (decision / rationale ≥3 / alternatives_considered ≥2 / risks_residual / owner_for_implementation / fallback)；14 blocked_by 非空 outcome 各标 "resolved by Dec-XX / OQ-X" 或 "remaining → S03 sub-decision"；禁止"待定" |
| **A5** (join) | traceability.json 含 12 字段 (schema_version='solar.s02_architecture.traceability.v1' / sprint_id / epic_id / generated_at / knowledge_context / decisions[D1..D13] / oq_resolutions[OQ1..OQ4] / module_inventory ≥6 / table_inventory ≥7 / downstream_sprint_kickoff_package / open_questions_carried_over / files_touched)；handoff 含 A1-A4 摘要 + 13 决议摘要 + 4 OQ 决议摘要 + S03/S04 启动 checklist + 剩余风险 + 禁止乐观词 |

## 3. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写 A5 traceability `open_questions_carried_over` (不动 epic, 不动 S01)
- 不写实施代码 (即使 stub)
- 不擅自修 S01 任何 artifact
- 不主动 close 父 epic
- 不放宽 R8 quality_score hard 阈值 (T0≥0.85/T1≥0.70/T2≥0.50)
- 不实施 SQL DDL / config loader
- 不用乐观词

## 4. SLO（本切片）

| 指标 | hard | soft |
|------|------|------|
| 13 决策项落地 | < 13 → FAIL | n/a |
| 4 OQ 全决议 | < 4 → FAIL | n/a |
| A4 每 OQ 6 字段完整 | 任一缺 → FAIL | n/a |
| 模块数 (A1) | < 6 → FAIL | < 8 → WARN |
| 表数 (A2 DDL) | < 7 → FAIL | n/a |
| CLI 命令数 (A3) | < 6 → FAIL | n/a |
| legacy 迁移 3 阶段 (A2) | < 3 → FAIL | n/a |
| 任一文档含实施代码 (python/真 SQL/真 YAML loader) | > 0 → 立即 FAIL | n/a |
| R8 hard 阈值放宽 | > 0 → 立即 FAIL | n/a |
| 用乐观词 | > 0 → FAIL | n/a |

## 5. 失败恢复

- A1 失败：A2/A3 不能启动；A4 可继续；单 A1 重派
- A2/A3 任一失败：单节点重派，不阻塞另一个 + 不阻塞 A4
- A4 失败：单节点重派；A5 join 必须等 A4 才能定 oq_resolutions
- A5 失败：诊断哪个 A 节点决议缺失，回写对应 A 节点修复后重跑
- 若发现 S01 内部矛盾：A4 记 OQ-new 给 PM，不擅自修 S01

## 6. 给下游接力 (S03 + S04)

A5 traceability `downstream_sprint_kickoff_package`：
- **S03 core-runtime inputs**: A1 模块划分 + 状态机 / A2 全部 DDL + 迁移 / A3 内部 API 签名 / A4 OQ 决议
- **S04 orchestration-ui inputs**: A1 dashboard 设计 / A3 CLI 契约 + legacy 兼容 / A4 D11 dashboard 渲染栈决议
- **S05 verification inputs**: A3 测试桩点 / A1 失败恢复 + 观测

coordinator 在 S02 passed 后自动激活 S03 + S04 (epic.task_graph 中 S03/S04 都 depends_on=S02，可同批激活)。

## 7. Knowledge Context

`solar-harness context inject` 已在 planner 入场时跑过；mirage degraded → QMD / Obsidian / Solar DB 默认源。S01 5 份 requirements docs 已 self-contained；本 sprint 节点起草不必额外检索（A4 OQ 决议可视情况补充 web 二级源）。
