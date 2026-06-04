# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g`
sprint_id: `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s01-requirements`
slice: `requirements`

## 用户原始需求

请按照 PRD 开发 AI Influence GitHub 趋势情报系统: # PRD: AI Influence GitHub 开源社区趋势分析系统

> **致 solar-harness 开发团队：**
> 本需求单旨在重构目前的 GitHub Trends 数据采集与分析逻辑。我们的核心定位不再是“GitHub Trending 榜单搬运”，而是建立一套“开源项目信号情报系统”。系统要能发现潜力项目、识别项目突然爆火、解释爆火原因、提炼技术路线、抽象产业启示，并最终沉淀为 AI Influence 报告里的“GitHub 趋势分析”栏目。

---

## 1. 总体目标
本系统用于持续跟踪 GitHub 开源社区热点，自动发现以下几类项目并转化为洞察资产：
- **突然爆火项目**（例如 24h / 7d stars 暴涨、被多个高权重社媒账号提及、重要 release）
- **早期潜力项目**（当前 star 不高，但增长斜率、技术密度、社区活跃度极高）
- **基础设施型项目**（可能成为 AI agent、推理、训练、MCP、机器人等领域的新基建）
- **社区话题驱动项目**（代表新开发范式、新产品形态或新社区情绪）

**项目级输出要求**：
不仅要输出“它是什么”，还必须回答：*为什么突然火？火的信号来自哪里？核心技术是什么？解决了什么真实痛点？有哪些可复用的架构思想？可以策划什么产品/研究选题？*

---

## 2. 系统定位

### 🚫 不做什么（反模式）
- 每日单纯搬运 GitHub Trending。
- 仅罗列 star 总数和 README 摘要。
- 用高级模型直接喂入完整 repo，无差别浪费 Token。
- 输出泛泛的“这个项目很有潜力”等毫无信息量的套话。

### ✅ 要做什么（Intelligence Pipeline）
建立一条标准的**项目情报流**：
`GitHub / 社媒事件` ➡️ `项目发现与快照` ➡️ `增长异常检测` ➡️ `项目技术画像` ➡️ `爆火原因归因` ➡️ `潜力评分` ➡️ `项目级洞察卡片` ➡️ `AI Influence 报告` ➡️ `产品策划与研究启示`

---

## 3. 核心设计原则

### 3.1 关注增长斜率与相对位次
Star 总数是滞后指标。核心关注：`stars_delta_1h` / `6h` / `24h` / `7d`，以及 `stars_acceleration` 和 `同品类分位数`。要回答：项目是否在所属类别中异常增长？增长是否可持续？

### 3.2 项目级微观洞察
报告必须以“项目”为颗粒度。例如：不仅说“MCP 很火”，而是剖析“`ChromeDevTools/chrome-devtools-mcp` 为什么火？能否基于它策划一个 agent browser control 产品？”

### 3.3 本地预处理 + 云端高级推理 (Token 经济学)
- **本地清洗 (ThunderOMLX + Qwen3.6)**：全量数据（README、Release、Issue、社媒）先用本地小模型压缩成“证据原子”（Evidence Atom）。
- **云端推理**：只将高度浓缩的证据包喂给高级模型进行洞察、归因和策划。

---

## 4. 数据源矩阵

| 数据源 | 核心用途 | 关键抓取字段/事件 |
| :--- | :--- | :--- |
| **GitHub REST/GraphQL** | 元数据、代码库状态 | `stars`, `forks`, `issues`, README, `package.json`, Release Tag/Body |
| **GitHub Events API** | 轮询高频活动 | `WatchEvent`, `ForkEvent`, `PushEvent`, `ReleaseEvent` |
| **GH Archive / BigQuery** | 历史回放、离线补偿 | 爆火前 30 天历史事件轴，大盘基准增长分布 |
| **X / 外部社媒** | 跨源共振、KOL 带货识别 | `author_tier`, `stance`, 提及的 Repo URL, `engagement_delta` |
| **YouTube Transcripts** | 视频传播关联 | 反向关联视频中提及的框架名、仓库名 |

---

## 5. 项目发现机制 (Discovery)

系统支持四路并发的入口扫描：
1. **Topic Discovery**：根据 AI Influence 关注方向（如 `ai-agent`, `coding-agent`, `mcp`, `inference-compute`）配置关键词，每日扫描 Top 200。
2. **Trending Discovery**：抓取 Daily/Weekly/Monthly Trending，按重点语言过滤。
3. **Tracked Repo Monitoring**：对重点项目做高频跟踪（如 `anthropics/claude-plugins-official`），按热度动态调整频次（15分钟 ~ 6小时）。
4. **Cross-source Mention**：从 YouTube / X 逆向发现，如果外部提及了 GitHub Repo，直接送入本地分析队列。

---

## 6. 数据模型设计 (Schema)

- **Repo Master**：记录项目长生命周期状态（`repo_id`, `tracking_status`, `first_seen_at`）。
- **Repo Snapshot**：**不允许覆盖历史**，记录特定时刻的快照与增量（`stars_delta_24h`, `commit_count_7d`）。
- **Repo Evidence Atom**：本地模型压缩出的单一证据点（如：某条 Release 提到 MCP，重要度 80）。
- **Project Analysis Card**：最终卡片，包含`project_positioning`, `why_it_is_hot`, `potential_score`, `trend_implication`。

---

## 7. 热度与潜力算法 (Scoring Engine)

### 7.1 Repo Heat Score (热度分)
`0.30 * 增长分位数` + `0.15 * 加速度分` + `0.15 * 跨源共振分` + `0.10 * Release分` + `0.10 * 社区活跃度` + `0.05 * 作者权重`

### 7.2 异常发现探针 (Detectors)
- **Sudden Hot Detector**：`stars_delta_24h >= max(50, avg_7d*3)` 且分类排名达 95%。
- **Early Potential Detector**：总 Star 50~2000，深度分>70，近期有活跃提交，非纯 Demo。
- **Foundation Infra Detector**：特定主题，具备高 API 覆盖和外部集成，深厚的技术架构。

---

## 8. 爆火归因模型 (Attribution)
每个热点必须从以下维度做自动化归因，并关联 Evidence ID：
1. **Big-name amplification**（大 V 转发，如 karpathy）
2. **Product launch / release**（重要版本发布）
3. **Technical breakthrough**（技术突破，10x 提升）
4. **Ecosystem timing**（踩中当下生态风口）
5. **Demo excellence**（炸裂的 README GIF/Playground）

---

## 9. 项目策划生成 (Planning Brief)
对于 S-tier 和 A-tier 项目，系统需要自动生成**项目策划单**，提供：
- 痛点分析、MVP 范围边界、前后端/模型技术架构拆解、差异化竞争策略。
- 指导我们**“可以基于它做什么开源工具 / 写什么深度文章”**。

---

## 10. AI Influence 最终报告层级
每日/每周报告将摆脱“榜单搬运”，升级为专业趋势分析：
1. **今日核心判断**：一句话定调今日社区主线。
2. **今日爆火项目**：深度解析 1-3 个爆发库。
3. **潜力库雷达**：提前布局早期金矿。
4. **技术趋势地图**：Agent / MCP / 基础设施 的宏观走向。
5. **项目策划池**：可转化为实际行动的产品 / 研究灵感。

---

## 11. 告警机制 (Alerting)
- **Critical**：被 X大V + YouTube + GitHub Trending 同时命中。
- **High**：跟踪库 24h 增长超 10%，或高潜力分但 star < 2000 触发预警。

---

## 12. 验收标准与落地建议

- **P0 核心管线**：实现增量快照、Topic 发现、Sudden Hot 算法、本地 Qwen 清洗、高级模型推导、最终 Markdown 日报生成。
- **P1 生态增强**：社媒逆向发现、归因模型、策划 Brief 生成、控制台 Dashboard。
- **P2 高阶进化**：GH Archive 历史回放、代码级架构分析、水军 (Star Bot) 反欺诈过滤。

> **主编寄语**：每日报告只写 Top 5-10 个项目，但每个项目都要写深。宁可少而准，不要多而水。我们要看透“这些 repo 增长背后，开发者生态正在往哪里走”。

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g.epic.md`、`epic-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s01-requirements.design.md`
- `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s01-requirements.plan.md`
- `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s01-requirements.task_graph.json`
- `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s01-requirements.handoff.md`
- `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s01-requirements.eval.md` 或 `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s01-requirements.eval.json`
