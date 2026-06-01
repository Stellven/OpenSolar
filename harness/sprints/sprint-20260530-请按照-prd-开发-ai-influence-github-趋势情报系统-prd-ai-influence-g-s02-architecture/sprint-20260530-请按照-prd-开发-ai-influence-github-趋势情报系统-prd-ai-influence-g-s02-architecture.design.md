# Design — s02-architecture: GitHub 趋势情报系统架构设计

## 设计目标

为 AI Influence GitHub 趋势情报系统设计完整的 Intelligence Pipeline 架构，涵盖数据采集、增量处理、存储模型、分析引擎和报告生成 5 层，产出接口契约和 schema 设计。

## Intelligence Pipeline 5 层架构

```
┌─────────────────────────────────────────────────────────────┐
│  L1 — 数据源层 (Source)                                      │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │ GitHub   │ GitHub   │ GH       │ X /      │ YouTube  │   │
│  │ REST/    │ Events   │ Archive  │ 外部社媒  │ Trans-   │   │
│  │ GraphQL  │ API      │ BigQuery │          │ cripts   │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘   │
├─────────────────────────────────────────────────────────────┤
│  L2 — 发现层 (Discovery)                                     │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │ Topic    │ Trending │ Tracked  │ Cross-   │              │
│  │ Scan     │ Scrape   │ Repo Mon │ source   │              │
│  └──────────┴──────────┴──────────┴──────────┘              │
├─────────────────────────────────────────────────────────────┤
│  L3 — 处理层 (Processing)                                    │
│  ┌───────────────────────┬───────────────────────┐          │
│  │ 本地清洗               │ 云端推理               │          │
│  │ ThunderOMLX + Qwen3.6 │ Claude/GPT-4          │          │
│  │ → Evidence Atom 压缩   │ → 洞察/归因/策划       │          │
│  └───────────────────────┴───────────────────────┘          │
├─────────────────────────────────────────────────────────────┤
│  L4 — 存储层 (Storage)                                       │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │ Repo     │ Repo     │ Evidence │ Analysis │              │
│  │ Master   │ Snapshot  │ Atom     │ Card     │              │
│  │ (lifecycle)│(immutable)│(local LLM)│(final) │              │
│  └──────────┴──────────┴──────────┴──────────┘              │
├─────────────────────────────────────────────────────────────┤
│  L5 — 分析/输出层 (Analysis + Output)                        │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │ Heat     │ 3 检测器  │ 5 维     │ 日/周报  │              │
│  │ Score    │ Sudden/  │ 归因     │ + 策划   │              │
│  │ Engine   │ Early/   │ Model    │ Brief    │              │
│  │          │ Infra    │          │          │              │
│  └──────────┴──────────┴──────────┴──────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## 数据模型 Schema

### Repo Master
```
repo_id: string (owner/name)
tracking_status: enum(discovered|active|graduated|archived)
first_seen_at: timestamp
last_snapshot_at: timestamp
category: string[]  # ai-agent, mcp, inference, etc.
tier: enum(S|A|B|C|unranked)
```

### Repo Snapshot (不可覆盖)
```
snapshot_id: uuid
repo_id: string
captured_at: timestamp
stars_total: int
stars_delta_1h / 6h / 24h / 7d: int
stars_acceleration: float
forks_total: int
commit_count_7d: int
issue_count_open: int
release_latest: {tag, body_summary, date}
category_percentile: float
```

### Evidence Atom
```
atom_id: uuid
repo_id: string
source: enum(readme|release|issue|x_post|youtube_transcript)
content_compressed: string  # 本地 LLM 压缩
importance_score: int (0-100)
extracted_at: timestamp
model_used: string  # qwen3.6
```

### Analysis Card
```
card_id: uuid
repo_id: string
project_positioning: string
why_it_is_hot: string
potential_score: float
trend_implication: string
attribution: {dimension: string, evidence_ids: uuid[], confidence: float}[]
planning_brief: string | null  # S/A-tier only
generated_at: timestamp
model_used: string  # claude/gpt-4
```

## 评分引擎架构

### Heat Score (6 因子)
```
heat_score = 
  0.30 * growth_percentile +     # stars_delta 在同类中的分位数
  0.15 * acceleration_score +     # 增长加速度
  0.15 * cross_source_resonance + # X+YouTube+GitHub 共振
  0.10 * release_score +          # 最近 release 质量
  0.10 * community_activity +     # issue/PR/commit 活跃度
  0.05 * author_weight            # 作者/org 权重
```

### 3 检测器
- **Sudden Hot**: `stars_delta_24h >= max(50, avg_7d*3)` AND `category_percentile >= 0.95`
- **Early Potential**: `50 <= stars_total <= 2000` AND `depth_score > 70` AND `recent_commits > 0`
- **Foundation Infra**: `category IN (infra_topics)` AND `api_coverage > 0.7`

## Token 经济学路由

```
全量数据 → [本地 ThunderOMLX + Qwen3.6]
                 │
                 ├─→ Evidence Atom (压缩后)
                 │
          [Filter: importance >= 60]
                 │
                 └─→ [云端 Claude/GPT-4] → Analysis Card
```

## 风险矩阵

| 风险 | 等级 | 缓解 |
|------|------|------|
| GitHub API rate limit (5000/h) | 中 | 分级扫描频率 + conditional request |
| ThunderOMLX + Qwen 压缩质量不确定 | 中 | S03 需做 PoC + 质量评估 |
| GH Archive 数据量大 | 低 | P2 延后，先用增量 API |
| X API 访问受限 | 中 | 无头浏览器 fallback |
