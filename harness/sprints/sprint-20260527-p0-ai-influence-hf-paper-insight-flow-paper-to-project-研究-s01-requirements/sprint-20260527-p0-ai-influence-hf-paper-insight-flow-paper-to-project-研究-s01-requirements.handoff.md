# Handoff — sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s01-requirements

## N1..N3 产出摘要

| 节点 | 产出文件 | 行数 | 覆盖 | 摘要 (≤80字) |
|------|---------|------|------|-------------|
| N1 | requirements.collection_canonical_enrichment.md | 294 | O1+O2 | L0 Snapshot+L1 Canonical+L2 Enrichment+L3 Classifier; PaperSnapshot 10字段+PaperCanonical 12字段+PaperEnrichment 3类+PaperTaxonomy 8字段; 5 provider; OQ-01+OQ-02 阻塞 |
| N2 | requirements.scoring_packet_resonance_reasoning.md | 330 | O3+O4 | L4 Signal Scoring 5公式36权重+PaperSignal 11维度+4信号类; Packet v2 6段+R0-R5+4路由+3 override+7 high model输出; OQ-03+OQ-04 阻塞 |
| N3 | requirements.compiler_storage_ops_quality.md | 282 | O5+O6+O7 | L8 Compiler 7输出资产+报告模板11节+L9 Knowledge 4通道+L10 Watch Trigger; CLI 10 flags+Config 5子段; 3质量门+11 V映射+4边界; OQ-05 阻塞 |

## Traceability 摘要

- **Schema**: `solar.s01_requirements.traceability.v1`
- **Outcomes**: O1-O7 (7 条, 全 P0)
- **依赖矩阵**: O1→[] / O2→[O1] / O3→[O2] / O4→[O3] / O5→[O4] / O6→[O1..O5] / O7→[O1..O6]
- **非目标**: 8 条 (含 HF ranking 不当结论 / raw list 不喂高模型 / 不全量调 high model / YouTube gated / 不替代 GitHub-Social)
- **Builder 禁令**: 7 条 (含禁止真跑外部 API / 真调 high model / 真改 Knowledge / 真改 CLI / 把 raw list 喂高模型)
- **Open Questions**: 5 条 (OQ-01~OQ-05, 全部 status=open, owner=S02)
- **下游启动包**: S02 (11 inputs) / S03 (12 inputs) / S04 (5 inputs) / S05 (6 inputs)

## 11 V→O 验收映射

| V | 验收条件 | O |
|---|---------|---|
| V1 | snapshot 不覆盖历史，可回放某天/周/月 | O1 |
| V2 | 同一 arXiv/HF paper 不重复，canonical identity 稳定 | O1 |
| V3 | 至少支持 HF metadata + arXiv metadata + HF linked assets enrichment | O2 |
| V4 | 输出 PaperTaxonomy 和 PaperSignal，PaperSignal 有五类主分数 | O3 |
| V5 | 只把通过 Packet Gate 的 evidence packet 送给 ChatGPT 5.5 Thinking high | O4 |
| V6 | 高模型输出不允许只复述摘要，必须有技术路线/为什么重要/风险/推荐动作 | O4 |
| V7 | 输出 R0-R5 resonance_level | O4 |
| V8 | 至少生成 report/cards/seeds/topics/experiments/projects/deep-research 7 类资产 | O5 |
| V9 | 产物写入 Knowledge raw/extracted，QMD 可搜索 | O5 |
| V10 | 用 2026-05-27 数据跑通第一条完整闭环 | O5+O6+O7 |
| V11 | py_compile 和相关最小回归通过 | O7 |

## S02 启动 Checklist

### 5 个必须决策

1. **OQ-01 持久化引擎**: 选择 SQLite / PostgreSQL / MongoDB; 决定数据对象 schema 物理存储
2. **OQ-02 Provider 限流**: 5 enrichment provider 的 rate limit + backoff + retry 策略
3. **OQ-03 Browser Agent**: 现有 Browser Agent skill vs 新建实现; ChatGPT 5.5 Thinking high 调用路径
4. **OQ-04 权重存储**: 36 评分权重硬编码 vs YAML config vs database-driven; profile 差异化
5. **OQ-05 Knowledge Ingest**: raw→extracted→QMD→graph 写入串行/并行; 失败 fallback 策略

### 5 个 Open Questions (全部 open, owner=S02)

- OQ-01: 持久化引擎选择
- OQ-02: enrichment provider 限流策略
- OQ-03: Browser Agent ChatGPT 5.5 Thinking high 接入方式
- OQ-04: 评分权重存储方式 (硬编码 vs config-driven)
- OQ-05: Knowledge ingest 4 通道写入顺序与 fallback

## 显式声明

- **禁止把 HF ranking 当结论** — HF ranking 只当 attention signal，研究价值由 5 评分公式 + 4 信号类 + 3 质量门共同判定 (PRD 核心决策 1+2)
- **禁止把 raw paper list 喂高模型** — 必须经 Packet Gate 验证后以 PaperEvidencePacket v2 格式送入 (PRD §L5)
- **禁止乐观词** — 本 handoff 不含 "已修复/稳定/完美/无需担忧/done/complete/implemented"

## 变更的文件

| 文件 | 目的 |
|------|------|
| traceability.json | 聚合 N1-N3 输出的 7 outcome 追踪矩阵 + 依赖 + 非目标 + 下游启动包 |
| handoff.md | N1-N3 摘要 + S02 启动 checklist + V→O 映射 + 显式声明 |

## Scope Compliance

- Write scope: `traceability.json` + `handoff.md` (仅 2 文件) ✓
- Read scope: N1/N2/N3 requirements + PRD + contract + task_graph — 全部在 read scope 内
- 无越界修改

## Known Risks

1. **N3 eval pending**: N3_compiler_storage_ops_quality 仍在 reviewing 状态，eval 已派发到 pane 0.0
2. **N1 eval auto-recovered**: N1 的 eval_json 是从 lease 恢复的，可能缺少完整 session evaluate 输出
3. **5 OQ 全部 open**: S02 必须先解决全部 5 个 OQ 才能开始实施
4. **cross_source 数据不完整**: Social/YouTube/Conference mentions 不在 N1 的 5 enrichment provider 范围内
5. **36 weights 未校准**: 初始权重是 PRD 给出的默认值，需 S02+S03 校准

## Not Done

- N3 eval verdict 未返回 (pane 0.0 处理中)
- 5 OQ 全部 open — 等 S02 决策
- 无实施代码 — S01 是规约层

Knowledge Context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
Harness Modules Used: harness-knowledge (Read: N1/N2/N3 requirements + PRD + contract + task_graph)
