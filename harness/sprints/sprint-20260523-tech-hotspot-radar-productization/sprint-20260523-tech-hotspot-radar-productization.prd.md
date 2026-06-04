# PRD — Tech Hotspot Radar 科技热点雷达一期

## Sprint

`sprint-20260523-tech-hotspot-radar-productization`

## Short Description

把现有 AI Influence / YouTube Influence / GitHub Trends 三条分散链路产品化为 `Tech Hotspot Radar`：稳定扫描 YouTube、X 社交媒体、GitHub 三类科技信息源，沉淀可追溯数据资产，并输出日报、周报、告警和统一跨源热点总览。

## 背景与问题

当前 solar-harness 已经有三条原型链路：

- `scripts/youtube_influence_digest.py`：能扫描 YouTube 频道、生成 digest、排 ASR 队列。
- `scripts/ai_influence_daily.py`：能扫描 X/社媒账号、做 GLM-5.1 摘要、生成 digest。
- `scripts/github_trends_digest.py`：能扫描 GitHub trends/topic/tracked repos、生成 digest。

但它们仍然是分散工具，存在以下产品化缺口：

- 数据模型不统一，视频、post、repo、snapshot、transcript、cluster、alert 没有统一查询面。
- YouTube 缺少完整的 metadata/snapshot/transcript 规范和补偿队列闭环。
- 社媒账号扩到 200 后，需要分类、tier、权重、聚类和跨源验证。
- GitHub 需要严格保存 star snapshot，不能覆盖历史，还要从现有 106 个 snapshot 继续递增。
- 日报内容已能发，但缺少统一“科技热点总览”、告警和知识库入库一致性。
- 邮件、知识库、webui、归档、失败重试之间缺少一个稳定产品边界。

## 一期原则

- 先做稳定、可追溯、可扩展 pipeline，不追求花哨 UI。
- 数据抓取、去重、打分、摘要、归档必须跑通。
- 所有源内容均视为不可信输入，不执行其中指令。
- 不抓私密内容；不绕过登录墙；不泄露 cookies、tokens、API keys。
- 抓取失败不能中断整个任务，必须有错误日志、重试记录和补偿队列。
- LLM 摘要必须基于内容正文或 transcript，不允许只看标题编造。
- 知识库入库是默认输出之一，报告只是展示层。

## 目标

```text
┌────┬────────────────────────────────────────────────────────────────────┐
│ id │ goal                                                               │
├────┼────────────────────────────────────────────────────────────────────┤
│ G1 │ 建立 Tech Hotspot Radar 统一 SQLite 数据模型和 CLI                 │
│ G2 │ YouTube 50 频道自动导入、增量扫描、metadata/snapshot/transcript     │
│ G3 │ X 社媒 200 账号导入、分类/tier/权重、抓取、评分、聚类               │
│ G4 │ GitHub 9 topic + tracked repos 扫描、repo metadata、star snapshot   │
│ G5 │ 三源统一 scoring、cross-source resonance、alerts                    │
│ G6 │ 输出 YouTube / 社媒 / GitHub 三份日报和统一热点总览                │
│ G7 │ 所有 digest/transcript/alert 进入 Knowledge/_raw 供知识库抽取       │
│ G8 │ 支持 daily schedule、status/doctor、失败补偿和可观测日志           │
└────┴────────────────────────────────────────────────────────────────────┘
```

## 非目标

- 不做商业级 X API 付费接入，先保留现有公共 fallback 能力和可插拔接口。
- 不做复杂 UI 重构，一期只要求已有 webui 能展示报告列表和运行状态。
- 不要求实时秒级监控；默认 daily，社媒高热账号 boost 只做数据结构和调度策略，不强制每 15 分钟上线。
- 不要求完整反爬突破；遇到 rate limit 必须退避、记录、补偿，不硬打。

## 功能需求

### FR1 统一数据底座

必须新增或扩展一个统一数据库，默认：

`~/.solar/harness/state/tech-hotspot-radar/tech-hotspot-radar.sqlite`

核心表至少覆盖：

- `youtube_channels`
- `youtube_videos`
- `youtube_video_snapshots`
- `youtube_transcripts`
- `social_accounts`
- `social_posts`
- `social_post_snapshots`
- `social_clusters`
- `github_topics`
- `github_repos`
- `github_star_snapshots`
- `hotspot_events`
- `cross_source_links`
- `hotspot_alerts`
- `pipeline_runs`
- `retry_queue`

必须提供 CLI：

```bash
solar-harness wiki tech-hotspot-radar init
solar-harness wiki tech-hotspot-radar scan --source youtube|social|github|all
solar-harness wiki tech-hotspot-radar report --date YYYY-MM-DD
solar-harness wiki tech-hotspot-radar status
solar-harness wiki tech-hotspot-radar doctor
```

### FR2 YouTube 热点扫描

必须支持用户给定的 50 个频道 seed，字段：

`channel_name, channel_url, channel_id, category, priority, scan_rotation_group, enabled, last_scanned_at`

频道输入必须支持：

- `@handle`
- channel URL
- `UC...` channel ID

视频抓取至少保存：

`channel_id, channel_name, video_id, video_url, title, description, published_at, duration_seconds, thumbnail_url, view_count, like_count, comment_count, tags, fetched_at`

增量规则：

- 默认回看 14 天。
- 新视频必须处理。
- 热门视频延长跟踪 30 天。
- `video_id` 去重。
- 指标写 `youtube_video_snapshots`，不能覆盖历史。

Transcript 规则：

- 保存 `transcript_raw`，保留时间戳。
- 保存 `transcript_clean`。
- 保存 `transcript_status = missing | fetched | auto_generated | failed`。
- 多语言优先级：英文、中文、自动字幕。
- 失败视频进入补偿队列。
- 长视频必须分段处理。
- 每条 transcript 生成可归档 `.txt` 和 JSONL 行。

内容理解输出：

`summary_zh, summary_en, key_points, entities, topic_tags, why_it_matters, actionable_insight, quotable_segments`

YouTube 热度分：

```text
youtube_hot_score =
  0.30 * view_velocity_score
+ 0.20 * engagement_velocity_score
+ 0.20 * channel_weight_score
+ 0.15 * semantic_importance_score
+ 0.10 * novelty_score
+ 0.05 * cross_source_signal_score
```

### FR3 社交媒体热点监控

必须导入 200 个 X 账号 seed，标准化为：

`platform, handle, display_name, category, tier, enabled, weight, last_scanned_at`

handle 必须去掉 `@` 存储。

分类权重：

```text
core_leader=1.50
paper_research=1.30
ai_lab=1.40
open_source=1.25
chip_semiconductor=1.20
agent_coding=1.25
multimodal=1.10
investment_trend=1.00
chinese_circle=1.10
deepseek_supplement=1.15
safety_governance=1.20
```

Tier 权重：

`tier1=1.50, tier2=1.00`

最终：

`account_weight = category_weight * tier_weight`

抓取范围：

- 原创 posts。
- quote posts。
- replies 可选，默认不进主热点榜。
- reposts 不作为独立内容，但可作为传播信号。

每条 post 保存：

`post_id, author_handle, author_category, author_tier, post_url, text, created_at, lang, reply_count, repost_count, quote_count, like_count, view_count, bookmarks, media_urls, mentioned_handles, urls, fetched_at`

社媒热度分：

```text
social_hot_score =
  0.25 * engagement_velocity_score
+ 0.20 * account_weight_score
+ 0.20 * semantic_importance_score
+ 0.15 * network_spread_score
+ 0.10 * novelty_score
+ 0.10 * cross_source_signal_score
```

必须识别事件类型：

`model_release, paper_release, product_launch, open_source_release, agent_workflow, chip_compute, funding_market, safety_governance, china_ai, multimodal, infra_systems`

必须聚类：

- URL 相同：强聚类。
- GitHub repo 相同：强聚类。
- arXiv/paper 链接相同：强聚类。
- 模型名/产品名相同：中强聚类。
- 语义相似度超过阈值：弱聚类。
- 默认窗口：48 小时。

### FR4 GitHub 热点扫描

必须导入 9 个 topic：

```text
ai
large-model
training-framework
compute-framework
agent-skill
infra-software
context-engineering
ai-coding-agent
physical-ai-robotics
```

必须导入 tracked repos：

```text
anthropics/claude-plugins-official
mattpocock/skills
addyosmani/agent-skills
colbymchenry/codegraph
ChromeDevTools/chrome-devtools-mcp
obra/superpowers
rohitg00/agentmemory
multica-ai/andrej-karpathy-skills
TauricResearch/TradingAgents
```

repo metadata 至少保存：

`repo_id, full_name, owner, repo, html_url, description, topics, language, license, stars, forks, watchers, open_issues, default_branch, created_at, updated_at, pushed_at, latest_release_tag, latest_release_at, readme_text, fetched_at`

Star snapshot 必须追加，不覆盖：

`full_name, snapshot_id, snapshot_at, stars, forks, open_issues, watchers, stars_delta_1d, stars_delta_7d, stars_delta_30d`

要求：

- 现有 snapshot 数从 106 继续递增。
- 每次扫描生成新的 snapshot_id。
- 支持按 topic、repo、日期查询趋势。

GitHub 热度分：

```text
github_hot_score =
  0.30 * star_growth_score
+ 0.20 * recent_activity_score
+ 0.15 * release_signal_score
+ 0.15 * semantic_relevance_score
+ 0.10 * social_cross_signal_score
+ 0.10 * maintainer_quality_score
```

趋势桶：

`agent_runtime, agent_skill, coding_agent, context_engineering, inference_compute, training_framework, infra_os, robotics_physical_ai, market_signal`

### FR5 告警和跨源共振

必须生成 `hotspot_alerts`：

- tracked repo 24h stars 增长超过 10%：high。
- tracked repo 发布新 release：medium。
- 新 repo 7 日 stars 增长进入 topic Top 5：high。
- repo 被 tier 1 社媒账号提及：high。
- repo 同时被社媒和 YouTube 提及：critical。
- README 出现 `mcp, agent memory, codex, triton, vla`：medium。
- repo archived 或删除：high。

跨源链接至少识别：

- GitHub repo URL/name。
- YouTube video URL/title/entity。
- paper/arXiv URL。
- model/company/product/technology entity。

### FR6 输出物

每日必须输出：

- YouTube 科技热点日报。
- 社交媒体科技热点日报。
- GitHub 科技热点日报。
- 今日科技热点总览。
- 告警 JSON/MD。
- transcript `.txt` 附件包和 JSONL。

输出目录：

```text
Knowledge/_raw/tech-hotspot-radar/YYYY-MM-DD/
Knowledge/_raw/youtube-influence-digest/
Knowledge/_raw/ai-influence-daily-digest/
Knowledge/_raw/github-trends-digest/
```

统一总览必须包含：

- 今日最重要 5 个趋势。
- 跨源共振。
- 需要人工重点看的内容。
- 高热但高噪声。
- 低热但高价值。
- 可能影响产品/研究路线。

### FR7 本地预处理与高级推理洞察引擎

必须新增 `Local Preprocess and Reasoning Engine`，作为三源 raw data 到高级模型洞察之间的强制中间层。

核心原则：

- 高级模型不得直接处理 YouTube 完整 transcript、X 全量 posts、GitHub README/release/issue/PR 全文。
- 本地 ThunderOMLX + Qwen3.6 承担 80%-95% 的清洗、切分、去重、实体抽取、主题标注、初步摘要、证据压缩和候选热点打分。
- 高级推理模型只能消费本地压缩后的 `reasoning_packet`。
- 所有趋势判断、技术判断、战略判断必须能追溯到 `evidence_id`，再反查原始 video/post/repo/timestamp/path。
- 所有模型调用必须写 `token_ledger`，记录模型版本、prompt 版本、输入 hash、输出 hash、token、成本、耗时和置信度。

推荐 pipeline：

```text
Raw Data
  ↓
Canonical Normalization
  ↓
Local Preprocess: ThunderOMLX + Qwen3.6
  ↓
Evidence Atom
  ↓
Cluster & Ranking
  ↓
Reasoning Packet
  ↓
Premium Reasoner Pool
  ↓
Insight Report
  ↓
Verifier & Evidence Linking
  ↓
Final Daily / Weekly Report
```

#### Evidence Atom

所有原始内容必须先压缩成 `evidence_atom`：

```json
{
  "evidence_id": "yt_abc123_0007",
  "source": "youtube | x | github",
  "source_id": "video_id | post_id | repo_full_name",
  "source_url": "string",
  "source_author": "channel_name | x_handle | repo_owner",
  "published_at": "datetime",
  "captured_at": "datetime",
  "raw_ref": {
    "transcript_timestamp": "00:13:24",
    "post_url": "https://x.com/...",
    "github_path": "README.md#L10-L30"
  },
  "content_type": "claim | release | opinion | benchmark | architecture | market_signal | controversy | tutorial | funding | safety",
  "language": "en | zh | mixed",
  "one_sentence_summary": "一句话摘要",
  "compressed_content": "100-250 字以内的证据内容",
  "entities": {
    "people": [],
    "companies": [],
    "models": [],
    "products": [],
    "repos": [],
    "papers": [],
    "technologies": []
  },
  "topic_tags": [],
  "claim": {
    "subject": "string",
    "predicate": "string",
    "object": "string",
    "polarity": "positive | negative | neutral | uncertain",
    "confidence": 0.0
  },
  "importance_score": 0,
  "novelty_score": 0,
  "technical_depth_score": 0,
  "source_weight_score": 0,
  "cross_source_hint": false
}
```

压缩目标：

- YouTube transcript 压缩到原始 token 的 3%-8%。
- GitHub README 压缩到原始 token 的 5%-10%。
- X posts 保留原文，但必须抽出结构化 claim。

#### Hotspot Cluster

Evidence atoms 必须聚合成 `hotspot_cluster`：

```json
{
  "cluster_id": "cluster_2026_05_23_agent_memory_001",
  "cluster_title": "Agent memory 与 context engineering 继续升温",
  "source_mix": {
    "youtube_count": 3,
    "x_post_count": 18,
    "github_repo_count": 4
  },
  "representative_evidence_ids": [],
  "local_cluster_summary": "300-600字中文摘要",
  "local_hot_score": 0,
  "novelty_score": 0,
  "cross_source_score": 0,
  "technical_depth_score": 0,
  "premium_reasoning_required": true,
  "reason_for_premium_reasoning": "string"
}
```

#### Premium Reasoning Gate

默认不调用高级模型。满足任一条件才升级：

- `cross_source_score >= 70`
- `local_hot_score >= 85`
- `novelty_score >= 80`
- `technical_depth_score >= 75`
- `tier1_account_count >= 3`
- `github_star_delta_24h_rank <= topic_top_5`
- `source_mix` 至少包含 YouTube/X/GitHub 中两个来源
- 人工标记 important
- 触发 critical alert

分级策略：

```text
Bronze   = 规则 + 本地 Qwen3.6，全量数据
Silver   = 本地 Qwen3.6 深度摘要，Top 100 clusters
Gold     = 单个高级模型推理，Top 20 clusters
Platinum = 多高级模型交叉推理，Top 3-5 trends
Human    = 涉及重大判断、投资、战略方向
```

#### Reasoning Packet

高级模型输入必须是 `reasoning_packet`，不能是 raw text：

```json
{
  "packet_id": "rp_2026_05_23_001",
  "cluster_id": "cluster_2026_05_23_agent_memory_001",
  "packet_type": "trend_analysis | technical_deep_dive | viewpoint_synthesis | weekly_summary",
  "compressed_evidence": [],
  "local_observations": {
    "what_changed": "string",
    "why_it_may_matter": "string",
    "uncertainties": []
  },
  "questions_for_premium_model": [],
  "token_budget": {
    "max_input_tokens": 6000,
    "max_output_tokens": 2000
  }
}
```

预算裁剪规则：

1. 优先保留跨源证据。
2. 优先保留 tier 1 账号观点。
3. 优先保留 star 增速异常 repo。
4. 优先保留带 timestamp 的 transcript 片段。
5. 删除重复观点。
6. 删除低权重来源。
7. 删除纯情绪内容。

#### Model Router

必须实现可配置模型路由，不硬编码具体商业模型名：

```json
{
  "task_type": "trend_analysis | technical_deep_dive | viewpoint_synthesis | repo_analysis | final_report",
  "preferred_model": "local_qwen | gemini_pro | claude_opus_like | codex_or_gpt_coding_reasoner",
  "fallback_model": "string",
  "max_cost_usd": 0.5,
  "max_input_tokens": 8000,
  "max_output_tokens": 2000,
  "reasoning_effort": "low | medium | high"
}
```

路由规则：

- `repo_analysis` 使用 `codex_or_gpt_coding_reasoner`。
- `viewpoint_synthesis` 使用 `claude_opus_like_model`。
- `long_context_cross_source_analysis` 使用 `gemini_pro_like_model`。
- `cheap_preprocess` 使用 `local_qwen3_6`。
- `cluster_score < threshold` 时绝不调用 premium model。

#### Token Ledger

必须新增成本账本：

```json
{
  "call_id": "string",
  "pipeline_stage": "local_preprocess | premium_reasoning | verification | final_report",
  "model": "string",
  "provider": "local | openai | anthropic | google",
  "input_tokens": 0,
  "output_tokens": 0,
  "cached_input_tokens": 0,
  "estimated_cost_usd": 0.0,
  "latency_ms": 0,
  "packet_id": "string",
  "cluster_id": "string",
  "prompt_version": "v1.3",
  "schema_version": "v1.0",
  "created_at": "datetime"
}
```

必须提供每日成本统计：

- total local calls
- total premium calls
- premium input/output tokens
- estimated cost
- cost per final insight
- premium call breakdown

#### Verifier

高级模型输出必须经本地 verifier 检查：

```json
{
  "insight_id": "string",
  "verification_status": "passed | weak_evidence | unsupported | contradiction_found",
  "unsupported_claims": [],
  "missing_evidence_ids": [],
  "contradictions": [],
  "recommended_action": "accept | revise | escalate_to_human"
}
```

检查项：

- 每个关键结论是否绑定 evidence_id。
- 是否忽略明显反例。
- 是否只来自单一传播链。
- 是否过度推断。
- repo/model/paper 名称是否匹配。
- 时间是否一致。
- 是否过度相信低权重账号。

#### 成本目标

一期目标：

- ≥ 90% token 在本地处理。
- ≤ 10% token 进入高级模型。
- 每日高级模型调用数量可配置上限。
- 相同 data hash / reasoning packet hash 不重复付费分析。
- 高级模型 prompt 必须使用固定系统前缀 + 固定 schema + 动态 evidence 末尾结构，支持 prompt caching。
- 离线分类、embedding、批量摘要优先走 batch/offline 模式。

## 验收标准

```text
┌─────┬────────────────────────────────────────────────────────────────────┐
│ id  │ acceptance                                                         │
├─────┼────────────────────────────────────────────────────────────────────┤
│ A1  │ tech-hotspot-radar sqlite 初始化成功，核心表存在                   │
│ A2  │ 50 个 YouTube 频道 seed 可导入，支持 handle/url/channel_id          │
│ A3  │ YouTube 增量扫描识别新视频并去重                                   │
│ A4  │ YouTube metadata、snapshot、transcript status 均可持久化            │
│ A5  │ transcript txt + JSONL 格式符合附件规范                            │
│ A6  │ 200 个社媒账号 seed 可导入，handle 清洗且权重正确                   │
│ A7  │ 社媒 post 可保存原文、指标、链接、媒体、提及账号                   │
│ A8  │ 社媒事件类型识别和 48h 聚类可运行                                  │
│ A9  │ 9 个 GitHub topic 和 9 个 tracked repo 可导入                       │
│ A10 │ GitHub repo metadata 和 star snapshot 追加保存，不覆盖历史          │
│ A11 │ stars_delta_1d/7d/30d 可计算                                       │
│ A12 │ 三源 hot score 均可计算并写入                                      │
│ A13 │ 至少三类跨源信号可识别：repo、YouTube、paper/model/entity           │
│ A14 │ 告警规则可生成 critical/high/medium/low alert                      │
│ A15 │ 三份日报 + 统一总览可生成 HTML/MD/JSON                             │
│ A16 │ 所有产物写入 Knowledge/_raw 并创建 wiki ingest dispatch             │
│ A17 │ 单源失败不影响其他源，失败写 pipeline_runs 和 retry_queue           │
│ A18 │ doctor/status 能显示最近运行、pending、失败、存储占用、入库状态     │
│ A19 │ evidence_atoms 表存在，且 YouTube/X/GitHub fixture 都能生成 atom    │
│ A20 │ reasoning_packets 表存在，premium 输入只能来自 evidence atoms       │
│ A21 │ token_ledger 表存在，记录模型、prompt、hash、token、成本、耗时       │
│ A22 │ premium gating 可配置，低分 cluster 不调用高级模型                  │
│ A23 │ verifier 可标记 unsupported / weak_evidence / contradiction_found    │
│ A24 │ 日报成本统计展示 local/premium token 占比和 cost_per_final_insight   │
└─────┴────────────────────────────────────────────────────────────────────┘
```

## 风险

- YouTube watch page/字幕接口可能限流，必须退避和补偿，不硬打。
- X 抓取受公开页面和搜索质量限制，必须保留 provider abstraction。
- GitHub API rate limit 需要 ETag/cache/token 可选支持。
- 三条旧链路已有产物，不允许破坏现有日报和知识库入库。
- 大量 transcript 可能占磁盘，必须支持归档和缓存清理策略。

## Stop Rules

- 账号/频道/topic seed 解析失败时，停止对应源扫描，不影响其他源。
- transcript 获取失败不阻断视频 metadata 入库。
- LLM 摘要失败必须降级为 metadata-only digest，不能编造内容。
- Gmail/邮件失败不能阻断 raw + knowledge ingest。
- 数据库迁移失败时停止写入，避免半结构数据污染。
