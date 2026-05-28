# Plan — S01 Requirements (AI Influence HF Paper Insight Flow / Paper-to-Project)

gate: `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s01-requirements:passed`
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db)

## 0. 切片定位

Epic 第一切片。PRD 极完整 (10 层 / 6 数据对象 / 5 评分 / 4 信号类 / 6 共振级 / 7 输出 / 3 质量门 / 11 V 验收)。本切片把内容编排为 N1-N3 规约节点 + N4 join，**禁止真跑 HF/arXiv/GitHub/Semantic Scholar API / 真调 ChatGPT 5.5 Thinking / 真改 Knowledge ingest**。

## 1. DAG

```
                ┌─→ N1_collection_canonical_enrichment  (O1+O2)    ─┐
   (无上游) ─────┼─→ N2_scoring_packet_resonance_reasoning (O3+O4)  ─┼─→ N4_traceability_handoff
                └─→ N3_compiler_storage_ops_quality      (O5+O6+O7) ─┘     (join)
```

**Wave 1 (3 并行)**: N1 / N2 / N3 (glm-5.1 ×3)
**Wave 2 (join)**: N4 (sonnet)

**write_scope 互斥**:
- N1: `<sid>.requirements.collection_canonical_enrichment.md`
- N2: `<sid>.requirements.scoring_packet_resonance_reasoning.md`
- N3: `<sid>.requirements.compiler_storage_ops_quality.md`
- N4: `<sid>.traceability.json` + `<sid>.handoff.md`

## 2. 每份 requirements 文档结构

按 design §3 八节: outcome_id + PRD 回链 / 目标背景 / 验收 per O-id ≥3 / 数据契约草案 / 接口契约草案 / 依赖与冲突 / 风险边界+非目标 / builder eligibility=NO + 先需 S02 决定。

## 3. 每节点验收

| 节点 | 关键验收 |
|------|----------|
| **N1** (O1+O2) | 文件存在; O1 ≥3 验收 (PaperSnapshot/PaperCanonical schema + dedup key + 不覆盖历史 + 可回放); O2 ≥3 验收 (PaperEnrichment/PaperTaxonomy 5 provider + 5 维度 taxonomy); 引 PRD §L0-L3 + 数据对象 1-4 原文; 标 OQ-01+OQ-02 阻塞 |
| **N2** (O3+O4) | 文件存在; O3 ≥3 验收 (5 评分公式 research/insight/experiment/open_project/deep_research + 4 信号类 + signal_class 字段); O4 ≥3 验收 (PaperEvidencePacket v2 含 identity/ranking/technical/taxonomy/scores/cross_source/local_judgment + R0-R5 共振级 + High Model 4 路由阈值 0.75/0.55/0.40 + override 3 类); 引 PRD §L4-L7 + 数据对象 5-6 原文; 标 OQ-03+OQ-04 阻塞 |
| **N3** (O5+O6+O7) | 文件存在; O5 ≥3 验收 (7 输出资产 + 报告模板 11 节 + Knowledge raw/extracted/QMD/graph 4 通道 + QMD 7 索引 + L10 watch trigger); O6 ≥3 验收 (CLI solar radar hf-papers run 完整签名 + Config hf_paper_insight 5 子段 + 报告模板); O7 ≥3 验收 (3 质量门 Packet/Insight/Resonance fail 条件 + 11 V 验收映射到 O1-O6 + 4 边界); 引 PRD §L8-L10 + CLI/Config + 质量门 + 11 V + 4 边界; 标 OQ-05 阻塞 |
| **N4** (join) | traceability.json 12 字段全集 (含 outcomes[7] / outcome_dependency_matrix / non_goals_aggregate ≥5 / builder_forbidden_aggregate ≥5 / downstream_sprint_kickoff_package S02-S05 / open_questions OQ-01..OQ-05); handoff 含 N1-N3 摘要 + S02 启动 checklist + 5 OQ 列表 + 禁止乐观词 + 禁止 HF ranking 当结论 + 禁止 raw list 喂高模型声明 |

## 4. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写 N4 traceability open_questions
- 不写实施代码
- 不真跑 HF/arXiv/GitHub/Semantic Scholar API
- 不真调 ChatGPT 5.5 Thinking high
- 不真改 Knowledge ingest 或 solar radar CLI 源码
- 不主动 close 父 epic
- 不把 HF ranking 当结论
- 不把 raw list 喂高模型
- 不全量调用 high model
- 不把 YouTube 低质量 transcript 作强证据
- 不用乐观词

## 5. SLO

| 指标 | hard | soft |
|------|------|------|
| outcome 覆盖 (O1-O7) | < 7 → FAIL | n/a |
| 每 O-id 验收数 | < 3 → FAIL | < 5 → WARN |
| OQ 数 | < 5 → FAIL | n/a |
| 任一 OQ 缺 owner+status | 立即 FAIL | n/a |
| 任一 outcome 含实施代码 (真 python/真 SQL/真 API call) | > 0 → 立即 FAIL | n/a |
| 11 V 验收全映射 | < 11 → FAIL | n/a |
| "HF ranking 当结论" 或 "raw list 喂高模型" 出现 | > 0 → 立即 FAIL | n/a |

## 6. 失败恢复

- N1/N2/N3 任一 FAIL: 单节点重派
- N4 FAIL: 诊断 N 节点缺失/不一致, 回写
- PRD 矛盾 → N4 OQ-new

## 7. 给下游接力 (S02)

N4 traceability `downstream_sprint_kickoff_package.S02`:
- O1-O7 全部 requirements docs
- outcome_dependency_matrix (严格线性 O1→O2→O3→O4→O5)
- 5 项 S02 决策 + 5 OQ
- PRD 10 层 + 5 评分公式 + 3 质量门

**S02 必须先解决**: O1 持久化引擎 (OQ-01) + enrichment provider 限流 (OQ-02) + Browser Agent High Model 接入 (OQ-03)，否则 O3-O7 全阻塞。

coordinator 在 S01 evaluator passed 后自动激活 S02。

## 8. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB。PRD 12K 已 self-contained。
