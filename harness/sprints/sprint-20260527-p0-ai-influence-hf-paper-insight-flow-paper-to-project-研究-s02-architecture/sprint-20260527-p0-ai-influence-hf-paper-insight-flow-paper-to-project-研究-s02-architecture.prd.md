# PRD: 架构设计与接口契约

epic_id: `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究`
sprint_id: `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture`
slice: `architecture`

## 用户原始需求

P0: AI Influence HF Paper Insight Flow — Paper-to-Project 研究信号编译器

背景：
当前 HF Paper 采集已经有 daily/weekly/monthly trending 基线和基础 markdown 报告，但仍停留在榜单/快照层。AI Influence 需要的不是 HuggingFace Papers 榜单搬运，而是面向 AI 研究热点、技术路线、开源机会和产品实验的早期信号雷达。HF Paper 在三源共振中是 Paper Source 主入口：发现研究新东西；GitHub/HF assets 证明能不能跑、有没有代码/模型/数据；社交/YouTube/公司博客证明社区和产业是否开始讨论。

核心决策：
1. HF Paper 不是结论源，而是候选信号源。
2. 排名只是 attention signal，不能等同研究价值。
3. 研究价值必须由论文内容质量、技术路线位置、可复现程度、代码/模型/数据链接、跨源提及、连续上榜、产业耦合、可转成实验/文章/产品/开源项目来共同判断。
4. 产物必须进入 Knowledge raw/extracted/QMD/graph，并能成为三源共振和 Deep Research 的上游资产。

目标：
实现 HF Paper Insight Flow = Paper-to-Project 研究信号编译器。

完整 10 层架构：
L0 Snapshot Collector：采集 HF daily/weekly/monthly 快照，保存 rank/upvote/first_seen/last_seen，不覆盖历史。
L1 Canonicalizer：统一 arXiv ID、HF URL、title、authors、机构、日期、dedup key。
L2 Enrichment：拉 HF metadata、arXiv metadata、HF linked models/datasets/spaces、GitHub repo、Semantic Scholar 元数据。
L3 Classifier：输出 domain、method、task、asset、stack_layer、maturity、research_route。
L4 Signal Scoring：输出 research_signal_score、insight_report_score、experiment_score、open_project_score、deep_research_seed_score。
L5 Evidence Packet：生成 PaperEvidencePacket v2，给高级模型使用，不把 raw list 直接喂给模型。
L6 Resonance Matcher：匹配 Paper ↔ Code ↔ Influence，输出 R0-R5 共振等级。
L7 High Reasoning：通过 Browser Agent 调用 ChatGPT 5.5 Thinking high，做技术路线、趋势、噪声、选题、项目建议。
L8 Compiler：生成 HF insight report、Paper Insight Cards、Three-source Resonance Seeds、AI Influence Topic Pool、Experiment Tasks、Open-source Project Briefs、Deep Research Seed Packs。
L9 Knowledge Store：写 raw/extracted/QMD/graph/claim。
L10 Watch Trigger：把高价值论文/路线送入持续追踪、三源共振、Deep Research 或开源孵化队列。

数据对象要求：
1. PaperSnapshot
- snapshot_id
- window_type: daily | weekly | monthly
- window_start/window_end
- source=huggingface_papers
- paper_id/rank/upvotes/hf_url/observed_at

2. PaperCanonical
- paper_id
- title/authors/orgs/published_at
- hf_url/arxiv_abs_url/arxiv_pdf_url
- first_seen_at/last_seen_at/seen_windows
- dedup_keys: title_hash/arxiv_id/semantic_scholar_id

3. PaperEnrichment
- hf_metadata: summary/ai_summary/github_repo/project_page/upvotes/linked_models/linked_datasets/linked_spaces
- academic_metadata: semantic_scholar citations/references/fields/authors
- code_metadata: github stars/forks/last_commit/license/installable

4. PaperTaxonomy
- primary_domain/secondary_domains
- method_tags/task_tags/asset_tags/stack_layer
- maturity: idea | benchmark | method | system | productizable_tool
- route_tags

5. PaperSignal
- novelty
- technical_depth
- trend_fit
- reproducibility
- cross_source
- benchmark_or_eval_value
- industry_relevance
- report_angle
- projectability
- deep_research_value
- signal_class: strong_signal | weak_signal | watch | hype | noise
- recommended_actions

6. PaperEvidencePacket v2
- identity
- ranking_signals: daily_rank/weekly_rank/monthly_rank/upvotes/first_seen/last_seen/rank_velocity/persistence_days
- technical_summary: problem/method/claimed_contribution/benchmark/main_result/limitations
- taxonomy
- local_scores
- cross_source_refs: github_repos/hf_models/hf_datasets/hf_spaces/social_posts/youtube_mentions/conference_mentions
- local_judgment: why_it_matters/why_now/noise_risk/projectability/deep_research_question

评分体系：
research_signal_score = 0.18 novelty + 0.18 technical_depth + 0.16 trend_fit + 0.12 benchmark_or_eval_value + 0.12 route_importance + 0.10 cross_source + 0.08 institution_authority + 0.06 rank_momentum
insight_report_score = 0.20 narrative_strength + 0.18 industry_relevance + 0.16 controversy_or_difference + 0.14 route_importance + 0.12 audience_fit + 0.10 cross_source + 0.10 explainability
experiment_score = 0.25 code_availability + 0.20 environment_reproducibility + 0.15 benchmark_clarity + 0.15 data_availability + 0.10 compute_affordability + 0.10 expected_learning_value + 0.05 license_safety
open_project_score = 0.22 toolizable_gap + 0.18 engineering_feasibility + 0.16 community_demand + 0.14 differentiation + 0.12 composability_with_solar_harness + 0.10 repo_seed_quality + 0.08 maintenance_cost
deep_research_seed_score = 0.20 strategic_importance + 0.18 uncertainty + 0.16 evidence_gap + 0.14 cross_domain_potential + 0.12 multi_source_availability + 0.10 decision_relevance + 0.10 trend_acceleration

信号分类规则：
True Trend：technical_depth>=0.70, trend_fit>=0.65, weekly/monthly persistence 或 cross_source>=0.50，非纯标题党。
Weak Signal：novelty>=0.75，rank 不一定高，cross_source 暂低，路线有新意。
Hype：rank/upvote 高，narrative 强，但技术增量弱、reproducibility 低或 vendor marketing/benchmark 微调。
Noise：abstract 空泛、无方法细节、无代码/数据/benchmark、与主线弱相关。

三源共振等级：
R0 Paper-only：只做 paper insight/watch。
R1 Paper + Code：可做实验复现。
R2 Paper + Influence：可做 AI Influence 文章。
R3 Paper + Code + Influence：进入三源共振周报。
R4 Paper + Code + Influence + Product/Benchmark：进入 Deep Research 或项目 brief。
R5 Sustained Multi-week Resonance：进入专题报告/路线图/平台研发。

High Model 路由：
- score >= 0.75：full packet → Browser Agent ChatGPT 5.5 Thinking high。
- 0.55-0.75：compact packet → batch reasoning。
- 0.40-0.55：watchlist only。
- <0.40：raw archive only。
- cross-source sudden spike / weekly-monthly persistence / internal priority match：override → high model。

High Model 输入格式：
Daily Signal Brief + PaperEvidencePackets + Routing Questions。
必须包含 run_context、market_context、papers、required_outputs、analysis_questions。
不得直接把 raw paper list 喂给 high model。

High Model 输出必须包括：
1. HF Paper Insight Report
2. Paper Insight Cards
3. Three-source Resonance Seeds
4. AI Influence Topic Pool
5. Experiment / Reproduction Tasks
6. Open-source Project Briefs
7. Deep Research Seed Packs

报告模板：
# AI Influence HF Paper Research Signal Report
0. Run Metadata
1. 今日/本周核心判断
2. Top Research Signals
3. Research Route Map
4. Three-source Resonance Candidates
5. Weak Signals
6. Hype / Noise Filter
7. AI Influence Topic Pool
8. Experiment & Reproduction Candidates
9. Open-source Project Briefs
10. Deep Research Seed Packs
11. Watchlist

CLI：
solar radar hf-papers run \
  --date 2026-05-27 \
  --windows daily,weekly,monthly \
  --profile ai-influence \
  --min-high-model-score 0.75 \
  --enable-github-enrichment \
  --enable-hf-assets \
  --enable-social-match \
  --output report,cards,seeds,topics,experiments,projects,deep-research \
  --store raw,extracted,qmd,graph

配置：
hf_paper_insight:
  windows: [daily, weekly, monthly]
  collection:
    source: huggingface_daily_papers
    snapshot_required: true
    keep_rank_history: true
  enrichment:
    hf_metadata: true
    arxiv: true
    hf_assets: true
    semantic_scholar: true
    github: true
    social_match: true
    youtube_match: gated
  scoring:
    high_model_threshold: 0.75
    watchlist_threshold: 0.55
    raw_only_threshold: 0.40
    override_on_cross_source_spike: true
    override_on_weekly_persistence: true
    override_on_internal_priority: true
  output:
    daily_report: true
    paper_cards: true
    resonance_seeds: true
    ai_influence_topics: true
    experiment_tasks: true
    open_project_briefs: true
    deep_research_seeds: true
  quality:
    packet_gate_required: true
    insight_gate_required: true
    resonance_gate_required: true

知识库存储：
raw:
- hf_snapshots
- arxiv_metadata
- hf_metadata
- github_metadata
- social_mentions

extracted:
- paper_cards
- signal_scores
- evidence_packets
- route_maps
- resonance_seeds
- project_briefs
- deep_research_seeds

graph:
- paper_signal_graph
- route_graph
- resonance_graph
- claim_graph

QMD 索引目录：
by_date, by_topic, by_method, by_asset_type, by_resonance_level, by_projectability, by_deep_research_value。

质量门：
Packet Gate 必须检查 title、arxiv_or_hf_url、summary、topic_tags、local_scores、local_judgment；no_summary、duplicated_paper、malformed_arxiv_id fail。
Insight Gate 必须检查 one_line_judgment、why_it_matters、technical_route、signal_class、recommended_action；only_restates_abstract、no_actionable_output、no_noise_assessment、no_relation_to_internal_priorities fail。
Resonance Gate 必须检查 paper source >=1；code/influence 可选但要可回源；influence_source_unverified、youtube_transcript_low_quality、github_repo_unrelated fail。

验收标准：
1. daily/weekly/monthly snapshot 不覆盖历史，可回放某一天/某周/某月。
2. 同一 arXiv/HF paper 不重复，canonical identity 稳定。
3. 至少支持 HF metadata、arXiv metadata、HF linked assets enrichment。
4. 输出 PaperTaxonomy 和 PaperSignal，且 PaperSignal 有五类主分数。
5. 只把通过 Packet Gate 的 evidence packet 送给 ChatGPT 5.5 Thinking high。
6. 高模型输出不允许只复述摘要，必须有技术路线、为什么重要、风险、推荐动作。
7. 输出 R0-R5 resonance_level。
8. 至少生成 report/cards/seeds/topics/experiments/projects/deep-research 七类资产。
9. 产物写入 Knowledge raw/extracted，QMD 可搜索。
10. 用 2026-05-27 的 HF daily/weekly/monthly 数据跑通第一条完整闭环。
11. py_compile 和相关最小回归通过。

边界：
- 不把 YouTube 低质量 transcript 作为强证据；YouTube match 默认为 gated。
- 不全量调用 high model，只对 gated packet 或 override 触发。
- 不把 HF ranking 当结论，只当 attention signal。
- 不替代 GitHub/Social 模块，而是通过 resonance matcher 与它们连接。

## 本切片目标

基于需求矩阵产出系统分层、接口、数据模型、兼容策略和迁移方案。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究.epic.md`、`epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 设计覆盖 control/data plane、状态、失败恢复和观测
- 写清楚接口边界和旧系统兼容方式
- 列出冲突、依赖和降级策略

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.design.md`
- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.plan.md`
- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.task_graph.json`
- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.handoff.md`
- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.eval.md` 或 `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.eval.json`
