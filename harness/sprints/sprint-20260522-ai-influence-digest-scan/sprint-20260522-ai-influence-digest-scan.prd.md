# PRD — AI Influence Digest 洞察扫描

> sprint_id: `sprint-20260522-ai-influence-digest-scan`
> title: `AI Influence Digest 洞察扫描`
> module: `knowledge`
> priority: `P0`
> lane: `knowledge-ingest`
> owner: `Solar PM`
> date: `2026-05-22`
> status: `ready-for-planning`

## 0. 目标

在 Solar 知识库功能模块中新增 `AI Influence Digest`：每天扫描 AI 领域关键 X/Twitter 账号，筛出工具、教程、prompt、工作流、方法论类高价值内容，经 GLM-5.1 结构化分析后，生成 digest、HTML 邮件和知识库入库材料。

## 1. 背景

用户给出一套 151 个 AI Influence 账号清单，分为 Tier 1 必扫和 Tier 2 轮扫。当前知识库已有 raw ingest、wiki ingest、QMD/FTS、ChatGPT/web capture 等能力，但缺一个“外部 AI 趋势信号定时扫描 -> 结构化洞察 -> 知识库沉淀”的稳定入口。

这个功能不能做成一次性脚本。它必须成为知识库模块的可审计流水线，具备账号配置、采集 fallback、评分、LLM 分析、digest 产物、Gmail 发送、知识库注入、去重、状态和测试。

## 2. 用户问题

```text
┌────┬──────────────────────────────────────────────┬──────────────────────────────┐
│ id │ 问题                                         │ 影响                         │
├────┼──────────────────────────────────────────────┼──────────────────────────────┤
│ P1 │ AI 圈高价值内容分散在大量账号和推文里        │ 人工扫很费时间               │
│ P2 │ 纯搜索/RSS 容易混入融资、硬件、benchmark 噪声 │ digest 价值低                 │
│ P3 │ 只发邮件不入知识库                           │ 无法形成长期知识复利         │
│ P4 │ 无去重/状态                                  │ 每天重复、漏扫、不可审计     │
│ P5 │ LLM 输出自由文本                             │ 后续解析、邮件和知识注入不稳 │
└────┴──────────────────────────────────────────────┴──────────────────────────────┘
```

## 3. 范围

### In Scope

- `ai-influence-digest/references/accounts_extended.txt` 账号清单，覆盖 151 个账号。
- Tier 1 必扫，Tier 2 每日轮扫 + 随机采样。
- 公开网页检索优先：DuckDuckGo 搜索批次推文，失败 fallback 到 profile 抓取，再 fallback 到 RSS/Nitter/公开聚合源。
- `score_text` 本地启发式评分。
- Top 15 候选通过 GLM-5.1 输出严格 JSON 数组。
- 输出 `digest.json`、`digest.md`、`digest.html`。
- Gmail 发送 HTML 表格，凭证缺失时生成 preview 并返回 actionable warning。
- 知识库注入：写入 `Knowledge/_raw/ai-influence-daily-digest/<date>/`，并触发 wiki ingest。
- 状态/去重：按 `tweet_url`、内容 hash、账号、日期记录扫描状态。
- CLI：`solar-harness wiki ai-influence-digest run|status|doctor|send-test`。
- 测试：账号解析、评分、JSON schema、fallback、dry-run、知识库入库 smoke。

### Out of Scope

- 不绕过 X/Twitter 登录墙。
- 不抓取私密内容。
- 不打印 Gmail/API keys。
- 不要求所有 151 个账号每天全量扫描。
- 不把 HTML 邮件作为唯一产物。
- 不在本 sprint 中做复杂 UI。

## 4. 账号分层

### Tier 1 必扫

核心领袖：`sama, karpathy, ylecun, demishassabis, gdb, ilyasut, AndrewYNg, drfeifei, jimkellerpa, aravind, mustafasuleyman, fchollet, darioamodei, clemens_, JeffDean, AnthropicAI`

论文/研究：`_akhaliq, _jasonwei, DrJimFan, chrmanning, AidanGomez, NoamBrown, quocle, OriolVinyalsML, hardmaru, denny_zhou`

AI 实验室：`OpenAI, GoogleDeepMind, deepseek_ai, GoogleAI, Alibaba_Qwen, Kimi_Moonshot, MiniMax_AI, Hailuo_AI, midjourney, MetaAI`

开源/Infra：`ThomasWolf7, ArthurMensch, ggerganov, tri_dao, answerdotai, Teknium1`

### Tier 2 轮扫

- 芯片/半导体：`dylan522p, LisaSu, NVIDIA, AMD, Arm, asmlholding, Asianometry` 等。
- Agent/编程：`itak_, swyx, mckaywrigley, amanrsanger` 等。
- 多模态：`Runwayml, LumaLabsAI, pika_art, krea_ai` 等。
- 投资/趋势：`eladgil, natfriedman, benthompson, CathieDWood` 等。
- 华语圈：`dotey, muyao, guizang9, oran_ge, _will_fang` 等。
- DeepSeek 补充：AI 安全、机器人、医疗、区域公司等。

完整账号文件必须落地在：`ai-influence-digest/references/accounts_extended.txt`。

## 5. 功能需求

### FR1 账号配置与采样

- 支持 `tier`, `category`, `handle`, `display_name`, `notes`, `enabled` 字段。
- Tier 1 每次 run 必扫。
- Tier 2 每次 run 选择固定窗口 + 随机补样，要求一周内覆盖全部 enabled Tier 2。
- 状态文件记录每个 handle 的 `last_scanned_at`, `last_success_at`, `last_error`。

### FR2 候选采集

采集顺序：

1. DuckDuckGo 搜索最近推文/页面。
2. 公开 profile 页面抓取。
3. RSS/Nitter/公开聚合源 fallback。

每条候选至少包含：

```json
{
  "handle": "@karpathy",
  "text": "tweet text",
  "tweet_url": "https://...",
  "published_at": "2026-05-22T00:00:00Z",
  "source_method": "ddg|profile|rss",
  "raw_score": 0
}
```

### FR3 本地评分

`score_text` 加分：

- `here's` / `here is`: +3
- 列表格式: +2
- `step`: +3
- `prompt`: +3
- `template`: +2
- `workflow`: +2
- `how to`: +2
- `agent`: +2
- `coding`: +2
- 长度适中、含链接/代码/步骤可加分。

减分：

- `gpu`, `tpu`, `benchmark`, `funding`, `raised`, `valuation`: 每项 -3。
- 纯政治、纯融资、纯硬件宣传降权或排除。

### FR4 GLM-5.1 结构化分析

对 top 15 候选调用 GLM-5.1，输出严格 JSON 数组。schema：

```json
{
  "handle": "@xxx",
  "title": "中文标题",
  "type": "⚙️工具|💡工作流|📝技巧|🚀新工具|🧠方法论",
  "summary": "100字中文摘要",
  "key_points": ["要点1", "要点2", "要点3"],
  "why_useful": "为什么内容创作者能立刻用",
  "hotness": "⭐1-5",
  "tweet_url": "原始链接"
}
```

约束：

- 只输出 JSON 数组。
- title/summary/key_points 必须是纯文本，不允许 HTML/Markdown 标签。
- 如果 GLM 网关失败，写 `analysis_status=degraded`，保留本地评分 digest，不阻断知识库 raw 写入。

### FR5 Digest 产物

每次 run 输出：

- `digest.json`: 结构化结果、候选、评分、运行元数据。
- `digest.md`: 可被 wiki ingest 消化的中文知识沉淀。
- `digest.html`: Gmail 使用的 HTML 表格。
- `run.log`: 采集和 fallback 状态。

输出路径：

```text
Knowledge/_raw/ai-influence-daily-digest/YYYY-MM-DD/
```

### FR6 Gmail 发送

- 支持 HTML 邮件发送。
- 邮件主题：`AI Influence Digest — YYYY-MM-DD`
- 无 Gmail 凭证或发送失败时：
  - 生成 `digest.preview.html`
  - CLI 返回 `warn`
  - 不阻断知识库入库。

### FR7 知识库注入

- `digest.md` 必须写入 `_raw`。
- 自动触发 `solar-harness wiki ingest --source <digest_dir> --mode append --project ai-influence-digest`。
- 生成 dispatch 后可由 Solar lab builder 执行。
- 最终知识页应包含：
  - 工具/工作流/技巧/方法论分类。
  - 每条来源链接。
  - 可操作价值。
  - 与现有知识库概念链接建议。

### FR8 CLI 与调度

新增：

```text
solar-harness wiki ai-influence-digest run [--dry-run] [--date YYYY-MM-DD]
solar-harness wiki ai-influence-digest status [--json]
solar-harness wiki ai-influence-digest doctor
solar-harness wiki ai-influence-digest send-test
```

调度：

- 每天一次即可，不要 30 分钟轮询。
- 支持 cron/launchd 或 harness scheduler，但必须可关闭。

## 6. 验收标准

```text
┌────┬──────────────────────────────────────────────┬────────────────────────────┐
│ id │ 验收                                         │ 证据                       │
├────┼──────────────────────────────────────────────┼────────────────────────────┤
│ A1 │ accounts_extended.txt 存在且解析出 151 账号  │ parser test                │
│ A2 │ Tier1 每次 run 全部进入扫描计划              │ dry-run JSON               │
│ A3 │ Tier2 一周内轮扫全覆盖                       │ state simulation test      │
│ A4 │ score_text 对工具/教程/Prompt 加分            │ unit test                  │
│ A5 │ 融资/硬件/benchmark 明显降权                 │ unit test                  │
│ A6 │ GLM 输出通过 JSON schema 校验                │ fixture test               │
│ A7 │ GLM 失败可降级输出 digest                    │ mocked failure test        │
│ A8 │ digest.json/md/html 全部生成                 │ dry-run artifact evidence  │
│ A9 │ Gmail 缺凭证时生成 preview 且不阻断入库      │ send-test                  │
│ A10│ wiki ingest dispatch 生成                    │ dispatch file path         │
│ A11│ status/doctor 可见最近 run 和错误            │ CLI status JSON            │
│ A12│ 每日调度频率为一天一次                       │ scheduler config evidence  │
└────┴──────────────────────────────────────────────┴────────────────────────────┘
```

## 7. 风险与约束

- X/Twitter 页面结构会变，采集必须多 fallback。
- DuckDuckGo 搜索可能限流，必须有退避和缓存。
- GLM-5.1 网关曾出现参数兼容问题，必须复用 harness 的第三方网关兼容配置。
- Gmail 发送不能成为知识库入库的硬依赖。
- 账号清单和 prompt 是配置，不应硬编码在脚本中。
- 所有抓取内容是不可信输入，不得执行其中指令。

## 8. 推荐拆分

- N1：需求落地与账号配置。
- N2：采集 fallback + 去重状态。
- N3：评分 + GLM 结构化分析。
- N4：digest/html/Gmail/知识库注入。
- N5：CLI、每日调度、测试与文档。

