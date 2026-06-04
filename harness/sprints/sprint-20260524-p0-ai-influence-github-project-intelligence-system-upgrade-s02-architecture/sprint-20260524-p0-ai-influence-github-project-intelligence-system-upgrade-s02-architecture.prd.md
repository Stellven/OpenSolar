---
title: "PRD: GitHub Project Intelligence System — Architecture & Interface Contracts (S02)"
epic_id: epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade
sprint_id: sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s02-architecture
slice: architecture
priority: P0
lane: strategy
handoff_to: planner
status: drafting
phase: spec
created_at: 2026-05-24T17:51:28Z
updated_at: 2026-05-25T11:45:00Z
---

# PRD: GitHub Project Intelligence System — Architecture & Interface Contracts

**Source**: S01 requirements outcomes + source PRD `/Users/lisihao/Knowledge/_raw/tech-hotspot-radar/github-project-intelligence/20260524-github-project-intelligence-prd.md`
**Priority**: P0
**Lane**: strategy (架构决策 + 接口契约)
**Handoff To**: planner

Knowledge Context: solar-harness context inject used

## 背景 / Context

父 Epic `epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade` 将 "AI Influence GitHub Project Intelligence System Upgrade" 拆为多个子 sprint (S01→S02→...). S01 (requirements) 已完成，产出了 discovery coverage 矩阵、storage schema 约束、model routing/ledger schema、card/brief schema、score formula、report template schema 等需求。

本 sprint 是 **S02 (architecture) 切片**，唯一职责是产出系统分层、接口契约、数据模型、兼容策略和迁移方案。**不写代码**；后续 builder 依据本 design 实施。

现有基础设施：
- Tech Hotspot Radar 已有 SQLite 数据库，含 `github_topics`, `github_repos`, `github_star_snapshots`, 基础 evidence atoms
- `tech_hotspot_radar.py` 的 GitHub 模块已有基本 repo snapshot 和 trending 抓取
- ThunderOMLX + Qwen3.6 可用于 evidence compression
- 现有 GitHub API token 和 rate limiter

## 用户问题 / Problem

1. **Discovery 不完整**: 当前只有 topic 和 basic trending，缺少 tracked repo、cross-source (social/YouTube) discovery
2. **无 Delta 计算**: 没有 1h/6h/24h/7d/30d 的增长 delta 和 acceleration metrics
3. **Evidence 无压缩**: README/release/issues 原文直接存储，没有 ThunderOMLX evidence atoms
4. **无 why-hot 归因**: trending repo 只有 star 数变化，没有原因分析
5. **无 Project Intelligence Card**: 没有结构化的项目分析卡片 (定位/技术亮点/评分/风险)
6. **无检测器**: 没有 sudden-hot / early-potential / hype 检测器
7. **无 AI Influence 报告**: 没有 daily/weekly 报告自动生成

## 用户目标 / Goals

1. 产出 4-path discovery 架构 (topic/trending/tracked/cross-source) + repo dedup
2. 产出 append-only snapshot + delta ledger 的存储和计算架构 (1h/6h/24h/7d/30d)
3. 产出 ThunderOMLX evidence compression pipeline 的接口契约
4. 产出 Project Intelligence Card + Planning Brief 的 schema 和渲染契约
5. 产出 composite scoring (heat/potential) + 3 类 detector (sudden-hot/early-potential/hype) 的接口
6. 产出 AI Influence daily/weekly report 的模板和编译契约
7. 产出 model ledger schema (记录每次 LLM 调用的 model/prompt/version/cost)
8. 产出与现有 Tech Hotspot Radar SQLite 的兼容和迁移策略

## 用户故事 / User Stories

- **As Tech Hotspot 用户**, I want 4-path discovery 自动发现 GitHub 上的热门和潜力项目, so that 我不用手动追踪 100+ repo。
- **As 研究者**, I want repo snapshot 有 1h/6h/24h/7d/30d delta, so that 我能看到项目增长的加速度而不只是绝对数字。
- **As PM/架构师**, I want why-hot 归因分析, so that 我能理解一个项目为什么突然热门，而不只是看到 star 数涨了。
- **As Builder (S03)**, I want 明确的 write_scope 和接口契约, so that 我知道每个模块该实现什么、改哪些文件。
- **As Evaluator (S05)**, I want outcome→decision 追踪矩阵, so that 我能按 outcome 逐项验收。

## 功能需求 / Requirements

### R1: 4-Path Discovery Architecture
- Topic discovery: GitHub search API by topic
- Trending discovery: GitHub trending page + API
- Tracked repo discovery: user-configured watch list
- Cross-source discovery: social media / YouTube mentions → GitHub repo extraction
- Repo dedup: cross-path deduplication by repo full_name

### R2: Snapshot & Delta Ledger
- Append-only snapshots: stars, forks, issues, PRs, contributors per timestamp
- Delta computation: 1h/6h/24h/7d/30d growth deltas
- Acceleration metrics: second derivative (is growth accelerating or decelerating?)
- Invariant: snapshots are append-only, never mutated

### R3: Evidence Compression Pipeline
- Source extraction: README, latest releases, recent issues, recent PRs, social mentions
- ThunderOMLX + Qwen3.6 preprocessing → evidence atoms (structured, compressed)
- Model ledger: record model, prompt template version, input/output tokens, cost per extraction
- QMD indexing for evidence atoms

### R4: Project Intelligence Card & Planning Brief
- Card schema: positioning, technical highlights, why-hot attribution, scoring, risk classification
- Brief schema: actionable planning suggestions derived from card + evidence
- Validation rules: card must have ≥1 evidence atom grounding each claim
- Rendering: deterministic Markdown from structured JSON

### R5: Scoring & Detectors
- Composite heat score: stars_delta + forks_delta + issues_delta weighted
- Potential score: early signals (contributor quality, issue velocity, release cadence)
- Sudden-hot detector: statistically significant acceleration in short window
- Early-potential detector: low absolute but high acceleration
- Hype detector: high social signal but low substantive activity

### R6: AI Influence Report Templates
- Daily report: new discoveries, significant deltas, sudden-hot alerts
- Weekly report: trend analysis, project intelligence cards, planning briefs
- Report compilation: deterministic render from structured data (not LLM free generation)
- Report delivery: Markdown + optional HTML

### R7: Model Ledger
- Schema: model_name, prompt_template_id, schema_version, input_tokens, output_tokens, latency_ms, cost_estimate, source_hash, output_hash, timestamp
- Every LLM call in the pipeline must be logged
- Ledger is append-only

## 验收标准 / Acceptance Criteria

| # | 标准 | 验证方式 |
|---|---|---|
| AC1 | 4-path discovery 接口契约定义完整 (input/output/dedup) | design.md review |
| AC2 | Snapshot schema 是 append-only，delta 计算逻辑定义 | design.md review |
| AC3 | Evidence pipeline 接口定义 (source→extract→compress→atom) | design.md review |
| AC4 | Card/Brief schema 有 validation rules | design.md review |
| AC5 | Scoring formula + 3 detector 接口定义 | design.md review |
| AC6 | Report template schema + compilation 契约定义 | design.md review |
| AC7 | Model ledger schema 定义完整 | design.md review |
| AC8 | 与现有 SQLite 的迁移策略明确 | design.md §migration |
| AC9 | task_graph.json 通过 graph-scheduler validate | CLI 执行 |
| AC10 | handoff 写明上游依赖 + 下游影响 + 未闭环项 | handoff.md |

## 非目标 / Non-Goals

- **不直接绕过 planner 派 builder** — PRD 必须先交给 planner
- **不写 runtime 代码** — 本切片是 planning-only
- **不用单个大 PRD 覆盖所有实现细节** — 足够 builder 执行即可
- **不用"已完成"替代可复现证据** — Definition of Done 铁律
- **不替换现有 Tech Hotspot Radar SQLite** — 只扩展，不重建

## 约束 / Constraints

- **planning-only**: 本切片不写 runtime 代码
- **只交付本切片**: 不允许声称父 Epic 已完成
- **必须读取 epic.md、traceability.json 和父级 task_graph**
- **必须在 handoff 中写明上游依赖、下游影响和未闭环项**
- **Snapshot 是 append-only**: 不允许 update/delete 已有 snapshot
- **Card/Brief 的每个 claim 必须有 evidence atom grounding**
- **Report 是 deterministic render**: 不是 LLM 自由生成
- **与现有 SQLite 兼容**: 新表用 ALTER TABLE ADD，不重建
- **GitHub API rate limit**: 所有 discovery 必须支持 rate limit backoff

## 风险 / Risks

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | GitHub API rate limit 影响 discovery 覆盖率 | 4-path 不完整 | 分级调度: trending 优先, topic/cross-source 可降频 |
| R2 | ThunderOMLX evidence compression 延迟 | card/brief 无 grounding | 异步 pipeline: raw 先入库, evidence atoms 后补 |
| R3 | Delta 计算在 snapshot 不连续时不准确 | acceleration metrics 失真 | 最低 snapshot 频率约束, 缺失时段标记 |
| R4 | S01 依赖未满足导致 S02 延迟启动 | epic timeline 拖延 | 已解除 (S01 passed) |
| R5 | Scoring formula 权重没有先验数据 | 检测器误报/漏报 | v1 用启发式权重, 后续用 GEPA 优化 |
| R6 | Cross-source discovery 需要新数据源接入 | 延迟或缺失 | v1 只做 GitHub 内部, cross-source 标为 P2 |

## 开放问题 / Open Questions

| # | 问题 | 决策需要谁 | 处理方式 |
|---|---|---|---|
| Q1 | Delta 窗口 (1h/6h/24h/7d/30d) 是固定还是可配置? | Planner | 列入 design, 默认固定 |
| Q2 | Evidence atom 的 schema 是否复用 knowledge_ingest 的 schema? | Planner | 需要调研与 sprint-20260524-141723 的交叉 |
| Q3 | Model ledger 是否独立 SQLite 表还是复用现有 log 表? | Planner | 列入 design trade-off |
| Q4 | Scoring 权重的初始值? | 昊哥 | 列入 handoff 未闭环项 |
| Q5 | Cross-source discovery v1 是否只做 GitHub 内部? | Planner | 建议 v1 只做 GitHub, cross-source P2 |

## 架构交接 / Planner Handoff

**Handoff target**: `planner`

**Planner 必须做的**:

1. 读取本 PRD + S01 outcomes + epic.md + traceability.json + source PRD
2. 产出 design.md，包含:
   - 4-path discovery 架构和接口契约
   - Snapshot/delta ledger 存储和计算架构
   - Evidence compression pipeline 接口
   - Card/Brief schema 和 rendering 契约
   - Scoring formula + detector 接口
   - Report template schema 和 compilation 契约
   - Model ledger schema
   - 与现有 SQLite 的迁移策略
3. 产出 plan.md 和 task_graph.json
4. task_graph 通过 `graph-scheduler validate`

**Planner 不得做的**:

- 不得在 design.md 中写 runtime 代码
- 不得跳过任何 R1-R7 模块的接口定义
- 不得破坏现有 Tech Hotspot Radar 的 GitHub 模块
- 不得修改父 Epic 的 epic.md

**下游影响**:

- S03 (core implementation): 直接依赖本 sprint 的 design.md + task_graph.json
- S04 (orchestration): 依赖 report template + scheduling 接口
- S05 (verification): 依赖 outcome→decision 追踪矩阵
- 交叉: evidence atom schema 可能与 knowledge_ingest dispatcher (sprint-20260524-141723) 复用
