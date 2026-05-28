# Design — S01 Requirements 切片：AI Influence HF Paper Insight Flow / Paper-to-Project 需求拆解

epic_id: `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究`
sprint_id: `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s01-requirements`
slice: `requirements`
role: planner
status: planning_complete
generated_at: 2026-05-27T22:21:30Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
upstream: none (epic 首切片)
downstream: S02 architecture → S03 core-runtime · S04 orchestration-ui → S05 verification-release

## 0. 切片边界

- **S01 是 epic 首切片**: 上游空; 产 supplied to S02..S05 的需求规约 + traceability。
- **PRD 已极完整**: 10 层架构 L0-L10 + 6 数据对象 + 5 评分公式 + 4 信号类 + 6 共振级 R0-R5 + High Model 路由 + 7 输出资产 + CLI + Config + 知识库存储 + 3 质量门 + 11 验收 + 4 边界。S01 工作是把这些编排为节点 + 聚合 traceability，**不重写 PRD**。
- **本 sprint 允许的写范围**:
  - `~/.solar/harness/sprints/<s01-sid>.requirements.collection_canonical_enrichment.md` (N1)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.scoring_packet_resonance_reasoning.md` (N2)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.compiler_storage_ops_quality.md` (N3)
  - `~/.solar/harness/sprints/<s01-sid>.traceability.json` + `<s01-sid>.handoff.md` (N4 join)
- **严格禁止**:
  - 真跑 HF API / arXiv API / GitHub API / Semantic Scholar API (本 sprint 是规约层, 真跑留 S03/S05)
  - 真调 ChatGPT 5.5 Thinking high (Browser Agent 真调留 S03)
  - 真改 Knowledge raw/extracted/QMD/graph 任何 ingest
  - 修改父 epic 任何 artifact
  - 真改 solar radar CLI 源码
  - 触动 Knowledge vault 已有 paper artifacts
- 禁止乐观词；禁止把 HF ranking 当作研究价值结论 (per PRD §核心决策 1-2)；禁止把 raw paper list 直接喂 high model (per PRD)；禁止 YouTube 低质量 transcript 作强证据 (per PRD §边界, 复用 YouTube epic 治理)

## 1. PRD 内容 → outcome 映射

PRD 提供 10 层 + 6 数据对象 + 5 评分 + 4 信号 + 6 共振 + 7 输出 + 操作层 + 3 质量门 + 11 V 验收 + 4 边界。聚合为 7 outcome:

| outcome_id | 标题 | PRD 章节 | 优先级 | builder 直接派 | 聚合到节点 |
|------------|------|----------|--------|----------------|------------|
| O1 | L0 Snapshot Collector + L1 Canonicalizer + PaperSnapshot/PaperCanonical 数据对象 | 10层 §L0-L1 + 数据对象 1-2 | P0 | NO (S02 决定持久化引擎与 dedup 策略) | N1 |
| O2 | L2 Enrichment + L3 Classifier + PaperEnrichment/PaperTaxonomy 数据对象 | §L2-L3 + 数据对象 3-4 | P0 | NO (S02 决定 enrichment provider 优先级 + classifier 模型) | N1 |
| O3 | L4 Signal Scoring (5 评分公式: research/insight/experiment/open_project/deep_research) + PaperSignal 数据对象 + 4 信号分类 | §L4 + 数据对象 5 + 信号分类规则 + 评分体系 | P0 | NO (S02 决定权重存储 + 评分 pipeline 位置) | N2 |
| O4 | L5 Evidence Packet v2 + L6 Resonance Matcher (R0-R5) + L7 High Reasoning (High Model 路由 + 输入格式) | §L5-L7 + 数据对象 6 + 三源共振 + High Model 路由 | P0 | NO (S02 决定 packet schema + Browser Agent 接入 + 路由阈值存储) | N2 |
| O5 | L8 Compiler (7 输出资产) + L9 Knowledge Store (raw/extracted/QMD/graph) + L10 Watch Trigger | §L8-L10 + 报告模板 + 知识库存储 + QMD 索引 | P0 | NO (S03 实施 compiler + ingest; S04 Watch UI) | N3 |
| O6 | CLI + Config + High Model 路由阈值 + 报告模板 | CLI § + 配置 § + 报告模板 | P0 | NO (S04 实施 CLI + S03 实施 config loader) | N3 |
| O7 | 3 质量门 (Packet/Insight/Resonance) + 11 V 验收标准 + 4 边界 + Non-goals 聚合 | 质量门 § + 验收标准 § + 边界 § | P0 | NO (S05 实施 verification + S03 实施 gate) | N3 |

7 outcome 全 P0; 零 builder-eligible (S01 工作是规约不是实施)。

## 2. S01 内部 DAG (3 路 fan-out + 1 join)

```
                  ┌─→ N1_collection_canonical_enrichment   (O1+O2)   ─┐
   (无上游) ────────┼─→ N2_scoring_packet_resonance_reasoning (O3+O4)   ─┼─→ N4_traceability_handoff
                  └─→ N3_compiler_storage_ops_quality      (O5+O6+O7) ─┘     (join)
```

**Wave 1 (3 并行)**: N1, N2, N3 (write_scope 互斥)
**Wave 2 (join)**: N4

## 3. 每份 requirements 文档统一结构 (N1..N3)

每份 `*.requirements.<topic>.md` 必含 8 节:
1. **outcome_id 清单** + PRD 章节回链
2. **目标与背景** (引段不抄全文)
3. **验收标准 per outcome** (≥3 条 / outcome, 复用 PRD V1-V11)
4. **数据契约草案** (per outcome 涉及的数据对象 schema 字段; 不实施)
5. **接口契约草案** (CLI subcommand / API 签名 / pipeline step 调用串; 不实施)
6. **依赖与冲突** (横向 + 纵向到 S02-S05)
7. **风险边界 + 非目标** (复用 PRD §边界)
8. **builder eligibility 判定** (NO + 先需 S02 决定什么)

## 4. N4 join 产出

**`<s01-sid>.traceability.json` 12 字段**:

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
      "title": "L0 Collector + L1 Canonicalizer + PaperSnapshot/PaperCanonical",
      "prd_section": "§L0-L1 + 数据对象 1-2",
      "priority": "P0",
      "acceptance_count": "<n>",
      "downstream_sprints": ["S02", "S03"],
      "downstream_artifacts": ["architecture.md (L0-L1 模块)", "data_models.md (PaperSnapshot/PaperCanonical schema)"],
      "builder_eligible": false,
      "blocked_by": ["OQ-01 (持久化引擎: SQLite vs JSON files)"],
      "requirements_doc": "sprints/<sid>.requirements.collection_canonical_enrichment.md"
    }
    /* O2..O7 */
  ],
  "outcome_dependency_matrix": {
    "O2": ["O1"],
    "O3": ["O2"],
    "O4": ["O3"],
    "O5": ["O4"],
    "O6": ["O1", "O2", "O3", "O4", "O5"],
    "O7": ["O1", "O2", "O3", "O4", "O5", "O6"]
  },
  "non_goals_aggregate": [
    "不把 HF ranking 当作研究价值结论 (per PRD 核心决策 1+2)",
    "不把 raw paper list 直接喂给 high model (必须经 Packet Gate)",
    "不全量调用 high model (只对 gated packet 或 override 触发)",
    "不把 YouTube 低质量 transcript 作强证据 (复用 YouTube epic 治理)",
    "不替代 GitHub/Social 模块 (通过 Resonance Matcher 连接)"
  ],
  "builder_forbidden_aggregate": [
    "禁止真跑 HF API / arXiv API / GitHub API / Semantic Scholar API (本 sprint 规约层)",
    "禁止真调 ChatGPT 5.5 Thinking high (Browser Agent 真调留 S03)",
    "禁止真改 Knowledge raw/extracted/QMD/graph",
    "禁止真改 solar radar CLI 源码",
    "禁止把 raw list 喂高模型"
  ],
  "downstream_sprint_kickoff_package": {
    "S02_architecture_inputs": [
      "O1-O7 全部 requirements 文档",
      "outcome_dependency_matrix (O2→O1, O3→O2, ..., O7→O1..O6)",
      "PRD 10 层架构 + 6 数据对象 + 5 评分公式 + 4 信号分类 + 6 共振级 + 3 质量门",
      "5 项 S02 必须先解决的决策: (1) 持久化引擎 (SQLite vs JSON files vs Solar DB) (2) enrichment provider 优先级 + 限流 (3) 评分 pipeline 模块位置与依赖图 (4) Browser Agent High Model 接入实现 (5) Knowledge store 写入路径 (raw/extracted/QMD/graph 分别落哪)",
      "5 OQ open"
    ],
    "S03_core_runtime_inputs": [
      "10 层 pipeline 模块实施",
      "6 数据对象 schema 落地",
      "5 评分公式实施",
      "Browser Agent 接入 (ChatGPT 5.5 Thinking high)",
      "Knowledge ingest (raw/extracted/QMD/graph)",
      "3 质量门实施"
    ],
    "S04_orchestration_ui_inputs": [
      "solar radar hf-papers run CLI",
      "Daily/Weekly/Monthly schedule",
      "Watch trigger UI (高价值论文持续追踪)",
      "7 输出资产展示 (insight report / cards / seeds / topics / experiments / projects / deep-research)"
    ],
    "S05_verification_inputs": [
      "11 V 验收全集",
      "2026-05-27 数据真跑闭环",
      "3 质量门 hard 阈值验证 (Packet/Insight/Resonance)",
      "py_compile + 最小回归"
    ]
  },
  "open_questions": [
    {"id": "OQ-01", "topic": "持久化引擎 (SQLite vs JSON files vs Solar DB) + snapshot 保留期", "status": "open", "owner": "S02"},
    {"id": "OQ-02", "topic": "enrichment provider 优先级 + 限流 (HF API 速率 / arXiv 速率 / GitHub token / Semantic Scholar quota)", "status": "open", "owner": "S02"},
    {"id": "OQ-03", "topic": "Browser Agent ChatGPT 5.5 Thinking high 接入实现 (现有 Browser Agent vs 新实现)", "status": "open", "owner": "S02"},
    {"id": "OQ-04", "topic": "5 评分公式权重是否硬编码 vs config-driven; 不同 profile 是否需要不同权重", "status": "open", "owner": "S02"},
    {"id": "OQ-05", "topic": "Knowledge ingest 4 通道 (raw/extracted/QMD/graph) 写入顺序与失败 fallback", "status": "open", "owner": "S02"}
  ],
  "files_touched": [...]
}
```

`handoff.md` 必须含: N1-N3 各产出路径 + ≤80 字摘要; traceability 摘要 (outcome 7 / P0 100% / 阻塞数 / OQ 5); S02 启动 checklist (5 决策项 + 5 OQ); 禁止乐观词 + 禁止把 HF ranking 当结论 + 禁止把 raw list 喂高模型声明。

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| N1, N2, N3 | glm-5.1 | requirements spec 起草模板化, PRD 极完整, 省钱 |
| N4 (join) | sonnet | 跨节点聚合 + 7 outcome 依赖矩阵 + 5 OQ owner 分派 |

## 6. 跨 outcome 依赖矩阵

```
O1 (L0+L1 采集+标准化) 根
O2 (L2+L3 enrichment+classifier) depends_on O1
O3 (L4 评分+信号) depends_on O2
O4 (L5+L6+L7 packet+共振+高模型) depends_on O3
O5 (L8+L9+L10 输出+存储+追踪) depends_on O4
O6 (CLI+Config+路由) depends_on O1..O5
O7 (质量门+验收+边界) depends_on O1..O6
```

10 层 pipeline 是严格线性数据流 → S02 必须按此拓扑设计模块。

## 7. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写 N4 traceability open_questions
- 不写实施代码 (即使 stub)
- 不真跑 HF API / arXiv API / GitHub API / Semantic Scholar API / ChatGPT 5.5 Thinking
- 不真改 Knowledge ingest / solar radar CLI 源码
- 不主动 close 父 epic
- 不把 HF ranking 当结论 (PRD §核心决策 1-2)
- 不把 raw list 喂高模型 (必须经 Packet Gate)
- 不全量调用 high model (只对 gated packet 或 override)
- 不把 YouTube 低质量 transcript 作强证据
- 不用乐观词

## 8. 失败恢复

- N1/N2/N3 任一 FAIL: 单节点重派, 不阻塞另 2 个
- N4 FAIL: 诊断哪个 N 节点 outcome 描述缺失/不一致, 回写
- PRD 内部矛盾 → N4 记 OQ-new

## 9. 非目标 (复用 PRD §边界 + 通用 S01 准则)

- 不真跑外部 API
- 不真调 high model
- 不写实施代码
- 不擅自修 PRD
- 不主动 close epic
- 不把 HF ranking 当结论
- 不把 raw list 喂高模型
- 不全量调用 high model
- 不替代 GitHub/Social 模块
- 不实施 OQ 解决方案 (5 OQ 全 open, 等下游)

## 10. 给 epic 接力

- N4 traceability `downstream_sprint_kickoff_package` 写明 S02..S05 各自 inputs
- coordinator 在 S01 evaluator passed 后自动激活 S02 (per epic schedule)
- S01 不主动 close
