# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa`
sprint_id: `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s01-requirements`
slice: `requirements`

## 用户原始需求

P0: 将 5 条 AI Influence 算子固化为 solar-harness 默认接入，并将其余实现降级为 fallback 或对照组

背景：
当前 Solar 仓库中已经存在多条成熟的 X / GitHub / Hugging Face / Gemini Deep Research / YouTube 相关能力，但入口、角色和状态展示存在潜在重复。现要求在 solar-harness 这唯一执行宿主内，明确 5 条默认接入主线，其余实现只作为 fallback、底层执行器或短期对照组，不再形成重复功能。

目标：
1. 固化以下默认主入口：
   - X / 社交大咖动态默认主线：`/Users/lisihao/Solar/harness/scripts/ai_influence_daily.py`
   - X 无头浏览器抓取默认执行器：`/Users/lisihao/Solar/harness/tools/playwright_twitter_scraper.py`
   - GitHub 趋势洞察默认新主线：`/Users/lisihao/Solar/harness/scripts/github_trends_pipeline.py`
   - Hugging Face 每日论文默认主线：`/Users/lisihao/Solar/harness/scripts/tech_hotspot_radar.py`
   - HF 辅助调度脚本：`/Users/lisihao/Solar/harness/scripts/run_tech_hotspot_radar.sh`
   - Gemini Deep Research 正式接入点：`/Users/lisihao/Solar/harness/tools/gemini_deep_research_operator.py`
   - Gemini 浏览器执行器：`/Users/lisihao/Solar/harness/scripts/browser_agent_gemini_deep_research_wrapper.py`
   - YouTube 最终报告默认主线：`/Users/lisihao/Solar/harness/scripts/youtube_influence_digest.py`
   - YouTube transcript 无头抓取器：`/Users/lisihao/Solar/harness/scripts/browser_agent_youtube_transcript_wrapper.py`

2. 明确职责边界，禁止重复：
   - `ai_influence_daily.py` 是 X 社交情报的唯一最终分析/日报入口；`playwright_twitter_scraper.py` 只负责抓取，不再独立承担最终报告职责。
   - `github_trends_pipeline.py` 作为 GitHub 新默认主线；旧 `github_intelligence` 先保留并行几天，对比效果后再决定是否退役。旧版这段时间必须继续正常产出报告，并在状态页与新版并排展示。
   - `tech_hotspot_radar.py` 作为 HF 默认主线，不再额外开辟第二套 HF 论文最终流程。
   - `gemini_deep_research_operator.py` 是 Gemini 正式入口；browser wrapper 仅作为内部执行器，不再暴露为第二正式入口。
   - `browser_agent_youtube_transcript_wrapper.py` 只负责 transcript 获取；`youtube_influence_digest.py` 负责最终多层写作、总结、架构图和最终报告，不能再形成第二套 YouTube 最终报告流。

3. 统一 `/ai-influence` 页面展示：
   - 增加至少 6 个清晰区块或卡片：
     - X / Social
     - GitHub New
     - GitHub Legacy
     - HF Papers
     - YouTube
     - Gemini Deep Research
   - 每个区块至少展示：最近运行状态、主要产物链接、核心统计、错误/阻塞摘要。
   - GitHub New / Legacy 必须支持并排对比查看报告，方便观察几天效果。

4. 默认 / fallback 机制：
   - 在配置或调度入口中写明 primary / fallback 关系。
   - fallback 不得与 primary 重复产出同类最终报告，除 GitHub 新旧对照组外。
   - 新实现或底层执行器若保留，仅能作为内部依赖、回退路径或短期对照实验。

5. 统一产物口径：
   - 五条主线都要能稳定输出可被状态页消费的产物元数据。
   - 至少统一到 `report + raw + metadata/status + log/diagnostic` 这一层级。
   - 对于 transcript / external article / planning brief / deep research 等中间产物，要在最终展示中可定位，但不能各自发展成新的最终报告入口。

6. 不要引入新的重复系统名词或第二宿主：
   - 本次整合默认假设执行宿主只有 `solar-harness`。
   - 某些算子虽然可能是借助其他工具或研发方式开发出来的，但整合后都必须体现为 `solar-harness` 内部默认接入或 fallback，而不是平行运行系统。

建议分解：
A. 配置与路由层：primary/fallback 关系、默认入口、调度绑定
B. 状态页与展示层：`/ai-influence` 六区块、GitHub 新旧对照展示
C. X / YouTube / Gemini 职责收敛：避免抓取器与最终报告器重叠
D. GitHub 新旧双跑对照：至少支持短期双跑与报告对照
E. 回归与验收：验证无重复主入口、无重复最终报告、状态页信息可读

验收标准：
- X / GitHub / HF / Gemini / YouTube 五条默认主线在代码、配置或文档层面都有唯一明确的默认入口。
- 除 GitHub 新旧对照外，不存在两套并行最终报告主线。
- `/ai-influence` 页面能同时看到六个分区，并且每区可点开对应产物。
- GitHub 新旧两版都能在状态页看到并排对照结果。
- YouTube transcript wrapper 不再被视作最终报告主线，Gemini wrapper 不再被视作正式接入点。
- 至少有定向测试或 smoke 证明 primary/fallback 与页面展示生效。

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa.epic.md`、`epic-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa.traceability.json` 和父级 task_graph。
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

- `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s01-requirements.design.md`
- `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s01-requirements.plan.md`
- `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s01-requirements.task_graph.json`
- `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s01-requirements.handoff.md`
- `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s01-requirements.eval.md` 或 `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s01-requirements.eval.json`
