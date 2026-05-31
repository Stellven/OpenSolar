# Plan — S02 Architecture (HF Paper Insight Flow 系统设计)

gate: `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture:passed`
knowledge_context: solar-harness context inject used
upstream: S01 requirements passed (7 outcome / 11 V→O / 5 OQ / 5 决策)
downstream: S03 core-runtime · S04 orchestration-ui

## 0. DAG

```
A1_architecture (sonnet, 关键路径)
    ├─→ A2_data_models      (glm-5.1) ┐
    └─→ A3_interfaces       (glm-5.1) ├─→ A5_traceability_handoff (sonnet, join)
A4_open_questions_resolutions (sonnet) ┘   (与 A1 并行)
```

**Wave 1 (2 并行)**: A1, A4
**Wave 2 (2 并行 depends_on A1)**: A2, A3
**Wave 3 (join)**: A5

**write_scope 互斥**:
- A1: `architecture.md`
- A2: `data_models.md`
- A3: `interfaces.md`
- A4: `open_questions_resolutions.md`
- A5: `traceability.json` + `handoff.md`

## 1. 节点验收

| 节点 | 关键验收 |
|------|----------|
| **A1** architecture | 10 节; 6 大组件 + 10 层 L0-L10 时序图 + 5 决议 D1-D5 全决议 (≤200 字); control vs data plane; S03+S04 接力 |
| **A2** data_models | 6 节; 6 数据对象 DDL + 36 权重表 + Knowledge 4 通道 schema + dedup keys 策略 + 生命周期 + 存储估算; **schema 仅 markdown 不真执行** |
| **A3** interfaces | 7 节; 7 大 API 签名 (Collector/Canonicalizer/Enricher/Classifier/Scoring+Packet/Reasoning+Resonance/Compiler+Store+Watch+CLI+Config) 全; **签名仅 markdown 不真执行** |
| **A4** OQ resolutions | OQ-01..OQ-05 每条 6 字段; OQ-04 权重存储必须给出 hot-reload 策略; OQ-05 Knowledge ingest 必须给出 fallback 策略; 任一 decision='待定' → FAIL |
| **A5** join | traceability 12 字段 (含 decisions[D1-D5] + oq_resolutions[OQ-01..OQ-05] + module_inventory ≥10 + data_schema_inventory ≥6); handoff 含 A1-A4 摘要 + 5 决议+5 OQ 摘要 + S03+S04 启动 checklist + 剩余风险 + 禁止乐观词 + 禁止 HF ranking 当结论 + 禁止 raw list 喂高模型声明 |

## 2. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写 A5 traceability `open_questions_carried_over`
- 不写实施代码
- 不真跑外部 API / 真调 high model / 真改 Knowledge / 真改 CLI 源码
- 不擅自修 S01 artifacts
- 不主动 close 父 epic
- 不放宽 OQ 决议
- 不把 HF ranking 当结论
- 不把 raw list 喂高模型
- 不切换 ChatGPT 5.5 Thinking 到其他模型
- 不用乐观词

## 3. SLO

| 指标 | hard | soft |
|------|------|------|
| 5 决策 D1-D5 落地 | < 5 → FAIL | n/a |
| 5 OQ 全决议 | < 5 → FAIL | n/a |
| A4 每 OQ 6 字段 | 任一缺 → FAIL | n/a |
| A4 任一 decision='待定' | > 0 → FAIL | n/a |
| 10 层 L0-L10 全覆盖 | < 10 → FAIL | n/a |
| 6 数据对象 DDL | < 6 → FAIL | n/a |
| 7 API 模块签名 | < 7 → FAIL | n/a |
| 任一文档含实施代码 | > 0 → FAIL | n/a |
| HF ranking 当结论 / raw list 喂高模型 出现 | > 0 → FAIL | n/a |

## 4. 失败恢复

- A1 FAIL → A2/A3 阻塞; A4 可继续
- A2/A3 FAIL → 单节点重派
- A4 FAIL → 单节点重派
- A5 FAIL → 诊断 A 节点
- S01 矛盾 → A4 OQ-new

## 5. 给下游接力

A5 traceability `downstream_sprint_kickoff_package`:
- **S03 core-runtime**: A1 10 层模块边界 + A2 全部 DDL + A3 7 API 签名 + A4 OQ 决议 (5 OQ 全实施)
- **S04 orchestration-ui**: A1 CLI/Watch + A3 CLI/Config API + A4 D4 权重 hot-reload + D5 ingest fallback UI
- **S05 verification**: A1 失败恢复 + A3 测试桩点 + A4 OQ 验证用例 (11 V→O 映射全)

coordinator 在 S02 evaluator passed 后自动激活 S03 + S04 (epic.task_graph)。

## 6. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB。S01 3 份 docs (15K+18K+16K) + traceability + handoff 是 self-contained 输入。
