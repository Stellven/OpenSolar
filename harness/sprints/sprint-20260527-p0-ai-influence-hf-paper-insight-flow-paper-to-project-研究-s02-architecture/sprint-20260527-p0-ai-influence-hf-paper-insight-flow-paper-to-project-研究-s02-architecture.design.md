# Design — S02 Architecture 切片：AI Influence HF Paper Insight Flow 系统设计

epic_id: `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究`
sprint_id: `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture`
slice: `architecture`
role: planner
status: planning_complete
generated_at: 2026-05-28T02:18:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
upstream: S01 requirements passed (7 outcome / 11 V→O 映射 / 5 OQ open / 5 必须决策)
downstream: S03 core-runtime · S04 orchestration-ui

## 0. 切片边界

- **S02 是 architecture 切片**: 消费 S01 7 outcome + 5 OQ + 5 决策项 + 11 V 验收; 产 architecture/data_models/interfaces/OQ resolutions + traceability
- **S02 不写实施代码**: builder 只写 markdown 规约 + DDL 草案 + API 签名草案
- **本 sprint 允许的写范围**:
  - `<s02-sid>.architecture.md` (A1)
  - `<s02-sid>.data_models.md` (A2)
  - `<s02-sid>.interfaces.md` (A3)
  - `<s02-sid>.open_questions_resolutions.md` (A4)
  - `<s02-sid>.traceability.json` + `<s02-sid>.handoff.md` (A5)
- **严格禁止**:
  - 真跑 HF/arXiv/GitHub/Semantic Scholar API
  - 真调 ChatGPT 5.5 Thinking high (Browser Agent 真调留 S03)
  - 真改 Knowledge raw/extracted/QMD/graph
  - 真改 solar radar CLI 源码
  - 修改 S01 任何 artifact (有问题 → A5 OQ-new)
  - 修改父 epic 任何 artifact
- 禁止乐观词；禁止把 HF ranking 当结论 (PRD 核心决策 1+2); 禁止把 raw list 喂高模型 (必须经 Packet Gate); 禁止把 OQ 决议留"待定"

## 1. 上游消费 (S01 → S02)

| S01 产出 | S02 必须消费 |
|----------|---------------|
| requirements.collection_canonical_enrichment.md (294 行) | O1+O2: L0-L3 + 4 数据对象 schema 字段 |
| requirements.scoring_packet_resonance_reasoning.md (330 行) | O3+O4: L4-L7 + 5 评分公式 36 权重 + 4 信号类 + R0-R5 + 7 high model 输出 |
| requirements.compiler_storage_ops_quality.md (282 行) | O5+O6+O7: L8-L10 + 7 输出 + CLI 10 flags + Config 5 子段 + 3 质量门 + 11 V 映射 |
| traceability.json (10K) | 7 outcome + 严格线性 dependency O1→...→O5 + 5 OQ + 5 S02 决策 |
| handoff.md (5K) | S02 启动 checklist + 11 V→O 映射 + 显式约束 |

## 2. S02 必须解决的 5 项决策 (从 S01 handoff §S02 启动 Checklist)

| Dec-id | 主题 | OQ 关联 | 落入文档 |
|--------|------|---------|----------|
| D1 | PaperSnapshot/PaperCanonical/Enrichment/Taxonomy 持久化引擎 (SQLite vs PG vs MongoDB) + schema 物理实现 | OQ-01 | A2 |
| D2 | 5 enrichment provider rate limit + backoff + retry 策略 (HF/arXiv/HF assets/Semantic Scholar/GitHub) | OQ-02 | A1/A4 |
| D3 | Browser Agent ChatGPT 5.5 Thinking high 与 `TechnologyDiagramPainter` 共用接入实现 (复用现有 vs 新建) | OQ-03 | A1/A3/A4 |
| D4 | 36 评分权重存储方式 (硬编码 vs YAML config vs DB) + profile 差异化 | OQ-04 | A2/A4 |
| D5 | Knowledge ingest 4 通道写入顺序与 fallback (raw→extracted→QMD→graph 串行/并行) | OQ-05 | A1/A4 |

## 3. S02 内部 DAG (5 节点)

```
A1_architecture (sonnet, 关键路径)
    ├─→ A2_data_models      ┐
    └─→ A3_interfaces       ├─→ A5_traceability_handoff (sonnet, join)
A4_open_questions_resolutions ┘   (与 A1 并行)
```

**Wave 1 (2 并行)**: A1 (关键), A4 (OQ 决议)
**Wave 2 (2 并行)**: A2, A3 (depends_on A1)
**Wave 3 (join)**: A5

## 4. 节点产出结构

### A1 `architecture.md` 必须 11 节

1. **系统全景图** + 7 大组件 (Collector / Canonicalizer / Enricher / Classifier / Scoring+Packet / Reasoning+Resonance / Compiler+FigureBundle / Store / Watch / CLI / Config)
2. **模块划分** — 与 S01 O1-O7 outcome 对齐 + 10 层 L0-L10 拓扑
3. **control plane** (CLI + Config + Watch trigger) **vs data plane** (raw → canonical → enriched → scored → packet → resonance → compiled → store)
4. **L0-L10 pipeline 时序图** (含 5 评分 + 4 信号 + R0-R5 + High Model 路由 + 3 质量门)
5. **持久化引擎决议** (per D1+OQ-01): 选定方案 + schema 物理实现
6. **5 Provider 限流 + retry** (per D2+OQ-02): per-provider 速率 + 失败 backoff + circuit breaker
7. **Browser Agent 接入** (per D3+OQ-03): 复用 / 新建 + ChatGPT reasoning 与 `TechnologyDiagramPainter` 的共享调用路径 + 失败回退
8. **Knowledge ingest 4 通道** (per D5+OQ-05): 写入顺序 (raw 先, extracted/QMD/graph 后) + 失败 fallback + 部分写入处理
9. **Figure Bundle 架构**: `figure-spec` 编译、`TechnologyDiagramPainter` 调度、`figure-manifest`、图文渲染位置与 evidence-grounding gate
10. **失败恢复 / 观测**: 4 信号 retry / High Model quota / Packet Gate fail / figure paint fail / 全 pipeline dashboard
11. **冲突 / 依赖 / 降级 / 非目标 / S03+S04 接力**

### A2 `data_models.md` 必须 6 节

1. **6 数据对象 DDL 草案** (per D1+OQ-01): PaperSnapshot / PaperCanonical / PaperEnrichment / PaperTaxonomy / PaperSignal / PaperEvidencePacket v2 字段 + 类型 + 约束 + 索引
2. **权重存储** (per D4+OQ-04): 36 评分权重表 schema + profile 字段
3. **Knowledge store schema**: raw 索引 / extracted 索引 / QMD 索引 / graph schema (paper_signal_graph / route_graph / resonance_graph / claim_graph)
4. **dedup keys 策略**: title_hash / arxiv_id / semantic_scholar_id 优先级 + 冲突解决
5. **数据生命周期**: snapshot 永久保留 / canonical 保留 / enrichment TTL / packet 缓存策略 / graph 重建
6. **存储估算 + 降级路径** (SQLite vs PG vs MongoDB)

### A3 `interfaces.md` 必须 7 节

1. **Collector API** (L0): fetch_daily_snapshot / fetch_weekly_snapshot / fetch_monthly_snapshot 签名
2. **Canonicalizer API** (L1): canonicalize_paper / dedup_check 签名
3. **Enricher API** (L2): enrich_hf / enrich_arxiv / enrich_hf_assets / enrich_semantic_scholar / enrich_github 签名
4. **Classifier API** (L3): classify_paper 签名 + taxonomy 输出
5. **Scoring + Packet API** (L4+L5): compute_scores (5 公式) / build_packet_v2 / packet_gate_check 签名
6. **Reasoning + Resonance API** (L6+L7): match_resonance / call_high_model (Browser Agent) / insight_gate_check / resonance_gate_check 签名
7. **Figure API**: `build_figure_specs(report_plan, sections, packets) -> list[FigureSpec]` / `paint_figure(spec) -> FigureResult` / `validate_figure_bundle(bundle) -> FigureValidation`
8. **Compiler + Store + Watch API** (L8+L9+L10): compile_outputs (7 资产 + figure bundle) / store_to_knowledge (4 通道) / trigger_watch 签名 + CLI 入口签名 + Config schema

### A4 `open_questions_resolutions.md` 每 OQ 6 字段

每 OQ 必须含:
- **decision** (明确方案, 禁止"待定")
- **rationale** (≥3 项支撑)
- **alternatives_considered** (≥2 个被否方案 + 否定理由)
- **risks_residual**
- **owner_for_implementation** (S03/S04/S05)
- **fallback**

5 OQ 推荐方向 (planner 视角):
- **OQ-01** (持久化引擎): SQLite (WAL 模式) + JSON 字段; 数据量 ≤100k papers 可控; 后期 PG 迁移 in scope
- **OQ-02** (provider 限流): HF 5/s + arXiv 3/s + HF assets 5/s + Semantic Scholar 100/5min (API key) + GitHub 5000/h (token); per-provider circuit breaker + exponential backoff 3 retry
- **OQ-03** (Browser Agent): 复用现有 Browser Agent skill；ChatGPT 5.5 Thinking high 与 `TechnologyDiagramPainter` 共用同一浏览器控制面与 profile/lease/session 体系
- **OQ-04** (权重存储): YAML config (`~/.solar/config/hf_paper_insight_weights.yaml`) per profile (ai-influence / research-radar / experiment-only); hot-reload 支持
- **OQ-05** (Knowledge ingest): raw 先同步写盘 → 异步触发 extracted/QMD/graph (并行) → 失败 fallback file 缓冲 + ATLAS structured repair

### A5 `traceability.json` 12 字段 + `handoff.md`

```json
{
  "schema_version": "solar.s02_architecture.traceability.v1",
  "sprint_id": "...",
  "epic_id": "...",
  "generated_at": "<UTC>",
  "knowledge_context": "solar-harness context inject used",
  "decisions": [
    {"dec_id": "D1", "outcome": "O1", "decision": "...", "doc": "architecture.md§5"}
    /* D1..D5 */
  ],
  "oq_resolutions": [
    {"oq_id": "OQ-01", "decision": "...", "owner": "S03", "doc": "open_questions_resolutions.md§OQ-01"}
    /* OQ-01..OQ-05 */
  ],
  "module_inventory": ["Collector", "Canonicalizer", "Enricher", "Classifier", "Scoring", "PacketBuilder", "ResonanceMatcher", "HighModelRouter", "Compiler", "KnowledgeStore", "WatchTrigger", "CLI", "ConfigLoader"],
  "data_schema_inventory": ["PaperSnapshot", "PaperCanonical", "PaperEnrichment", "PaperTaxonomy", "PaperSignal", "PaperEvidencePacket v2", "PaperWeights", "paper_signal_graph", "route_graph", "resonance_graph", "claim_graph"],
  "downstream_sprint_kickoff_package": {
    "S03_core_runtime_inputs": [...],
    "S04_orchestration_ui_inputs": [...],
    "S05_verification_inputs": [...]
  },
  "open_questions_carried_over": [],
  "files_touched": [...]
}
```

`handoff.md` 含: A1-A4 摘要 + 5 决议摘要 + 5 OQ 决议摘要 + S03/S04 启动 checklist + 剩余风险 + 禁止乐观词 + 禁止 HF ranking 当结论 + 禁止 raw list 喂高模型声明。

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| A1 | sonnet | 关键路径; 5 决策 + 10 层 pipeline + control/data plane 需 reasoning |
| A2, A3 | glm-5.1 | DDL/API 签名模板化, 依赖 A1 模块边界 |
| A4 | sonnet | 5 OQ 决议 + alternatives 分析需 reasoning (尤其 OQ-03 Browser Agent 选型) |
| A5 (join) | sonnet | 跨节点聚合 + downstream package |

## 6. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写父级 traceability `open_questions_carried_over` (不动 epic, 不动 S01)
- 不写实施代码
- 不真跑外部 API / 真调 high model / 真改 Knowledge / 真改 CLI 源码
- 不擅自修 S01 artifacts
- 不主动 close 父 epic
- 不放宽 OQ 决议 (任一 decision="待定" → FAIL)
- 不把 HF ranking 当结论
- 不把 raw list 喂高模型
- 不全量调 high model
- 不把 YouTube 低质量 transcript 作强证据 (复用 YouTube epic 治理)
- 不用乐观词

## 7. 失败恢复 / 降级

- A1 失败 → A2/A3 阻塞; A4 可继续; 单 A1 重派
- A2/A3 任一失败 → 单节点重派
- A4 失败 → 单节点重派; A5 等 A4 才能定 oq_resolutions
- A5 join 失败 → 诊断 A 节点缺失, 回写
- 若 S01 内部矛盾 → A4 记 OQ-new

## 8. 非目标

- 不实施代码
- 不真跑外部 API
- 不擅自修 S01 artifacts
- 不主动 close 父 epic
- 不放宽 OQ 决议
- 不实施 S03/S04 范围
- 不切换 ChatGPT 5.5 Thinking 到其他模型 (PRD 已锁)
- 不替代 GitHub/Social 模块

## 9. 给 epic 接力

- A5 traceability `downstream_sprint_kickoff_package` 写明 S03/S04/S05 各 inputs
- coordinator 在 S02 evaluator passed 后自动激活 S03 + S04 (epic schedule)
- S05 verification 等 S03+S04 都 passed
