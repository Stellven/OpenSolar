# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收`
sprint_id: `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s01-requirements`
slice: `requirements`

## 用户原始需求

P0: AI Influence YouTube 报告流默认流程固化与验收

背景：
YouTube Transcript 新架构 S01-S04 已落地，S05 正在验证 transcript acquisition ladder / quality gate / renderers / cleanup / premium fallback。AI Influence YouTube 报告流此前需求已固化，但没有独立闭环 sprint，且受 transcript 质量阻塞。

目标：
1. 将 AI Influence YouTube 报告流固化为默认流程：视频分组 → 高质量 transcript gate → Browser Agent ChatGPT 5.5 Thinking high 规划 → 趋势/章节/小结分层 → 逐章节 high model 写作 → 综合报告 → SVG 图表 → source mapping → email/report archive。
2. 默认排除 T3/unusable transcript；T2 只能作为 weak evidence；T0/T1 可作为核心证据。
3. 报告不得泄漏内部处理字段/video_id/raw refs；素材映射必须面向读者显示“频道/标题/发布时间/可信度/引用段”。
4. 所有 report claim 必须能回源到 transcript segment 或 metadata；低质量 ASR 不得作为硬证据。
5. 报告产物默认生成 markdown/html/json evidence map，并归档到 Knowledge/_raw/tech-hotspot-radar/ai-influence-planned/<date>/reports。
6. Browser Agent ChatGPT 会话完成后归档到 ChatGPT 项目“杂项”。
7. 增加 smoke/eval：用 2026-W21 fixture 跑一次 report plan + one report render，验证无内部用语、无裸 video_id、无截断、SVG 存在且嵌入 HTML。

实现要求：
- plan-ai-influence-reports 默认接入 transcript quality gate；低质量 transcript 自动排除或降级。
- 分组必须识别 event/conference/keynote/interview/tutorial/product_update/other，不允许只靠关键词和时间窗口。
- 调用 Browser Agent ChatGPT 5.5 Thinking high 的规划输出必须是结构化 JSON：trend -> chapter -> subsection -> evidence_refs。
- 写作阶段必须逐章节调用 Browser Agent ChatGPT 5.5 Thinking high，不允许用本地 ThunderOMLX/Qwen 代替最终趋势判断和正文写作。
- 输出报告必须包含读者友好的素材映射，不暴露内部 video_id、V00x、raw refs、处理日志、pipeline 字段。
- 架构图默认生成 SVG，并嵌入 HTML；禁止 ASCII 图作为最终图表。
- report validator 必须检查：无内部用语、无裸 video_id、无截断尾巴、SVG 存在、evidence_map 完整、T3 未进入核心证据。

验收标准：
1. 新 CLI 或现有 plan-ai-influence-reports 支持上述默认 gate。
2. 低质量 transcript 被拒绝或降级。
3. report plan 包含 group_type: conference/keynote/interview/tutorial/product_update/other。
4. report hierarchy 支持 trend -> chapter -> subsection。
5. 输出 HTML 中 SVG 图可见，不是 ASCII。
6. evidence_map.json 完整。
7. 至少一份 2026-W21 fixture 报告通过 validator。

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收.epic.md`、`epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收.traceability.json` 和父级 task_graph。
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

- `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s01-requirements.design.md`
- `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s01-requirements.plan.md`
- `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s01-requirements.task_graph.json`
- `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s01-requirements.handoff.md`
- `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s01-requirements.eval.md` 或 `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s01-requirements.eval.json`
