# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w`
sprint_id: `sprint-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w-s01-requirements`
slice: `requirements`

## 用户原始需求

P0: AI Influence YouTube 报告流质量增强 — Report IR + 逐章写作 + Deep Writer + Verifier + Synthesizer

背景：
当前 AI Influence YouTube 报告流已经具备 transcript quality gate、video catalog、semantic grouping、Browser Agent / ChatGPT Thinking high report planner、evidence pack、一次性 report writer、validation/render/archive。但主链路仍是“整份报告一次写完”，导致 Planner 规划粒度被 Writer 压扁，章节浅、散、漏，Deep Writer 没进入默认路径，缺章直接 blocked，缺少逐章 evidence、claim-level verifier、repair loop、global synthesizer 和可复盘质量分。

核心判断：
这不是再调 prompt 的问题，而是报告控制面缺失。必须把报告生成改造成可追踪、可重试、可验证、可合成的多阶段流水线：Planner 决定写什么；Chapter Writer 写清楚；Deep Writer 写深；Verifier 防瞎写；Repair Loop 自动补弱章/缺章；Synthesizer 把章节编成完整报告；Copy Editor 做最终可读性和内部字段清理。

目标架构：
Video Pool
  -> Transcript Quality Gate
  -> Video Catalog
  -> Semantic Grouping
  -> Report Planner
  -> Report IR / report-ir.json
  -> Chapter Job Builder
  -> Per-Chapter Evidence Pack
  -> Chapter Writer
  -> Deep Writer
  -> Chapter Verifier
  -> Repair Loop
  -> Report Synthesizer
  -> Figure Spec Builder
  -> TechnologyDiagramPainter
  -> Figure Grounding Gate
  -> Global Verifier
  -> Copy Editor
  -> Markdown / HTML / Knowledge Raw

P0 实现目标：
1. 把 report-plan.json 升级为 Report IR，作为执行契约，不再只是规划文本。
2. cmd_run_ai_influence_planned_reports 不再默认一次性写整篇报告，改为逐章执行。
3. 每个章节有 chapter_job、chapter_spec、chapter_evidence_pack、draft/deep/final/verification 产物。
4. P0/P1 或 deep_writer_required=true 的章节默认进入 Deep Writer。
5. 每章必须经过 Chapter Verifier，缺章、弱证据、unsupported claim、内部字段泄露必须触发 repair，而不是整份报告直接 blocked。
6. 所有章节通过后由 Synthesizer 合成整篇报告，再由 Global Verifier + Copy Editor 生成 final/report.md 和 final/report.html。
7. 质量结果必须落盘：quality-score.json、claim-verification.json、chapter-validation-summary.json、report-validation-result.json。
8. 在证据充分时，调用 `TechnologyDiagramPainter` 产出 1-3 张架构图 / 流程图 / 技术堆栈图，并把图片、caption、evidence 绑定嵌入 final report。
9. 保留 Browser Agent / ChatGPT 项目“杂项”归档要求，账号、profile、secret 必须走环境变量，不得写入仓库。

Report IR 要求：
- 新增 compile_report_ir(report_plan, catalog, video_groups, config) -> dict。
- report-ir.json 必须包含：report_id、report_title、report_type、date_range、global_thesis、target_audience、tone、chapters、quality_targets。
- 每个 chapter 必须包含：chapter_id、title、chapter_type、priority、deep_writer_required、expected_words、required_questions、required_evidence、selected_video_refs、evidence_pack_id、status。
- Report IR 必须兼容旧 report-plan.json，但执行时以 report-ir.json 为准。

Chapter Jobs 要求：
- 新增 create_chapter_jobs(report_ir) -> list[dict]。
- job 状态：queued | writing | deepening | verifying | repair_needed | passed | failed。
- 输出路径：chapters/ch_XX.draft.md、chapters/ch_XX.deep.md、chapters/ch_XX.final.md、chapters/ch_XX.verification.json。
- chapter_type 至少支持：executive_summary、core_trend、technical_deep_dive、big_name_viewpoints、project_implications、video_digest、watchlist、noise_and_risk、appendix。
- 默认 deep_writer_required=true 的类型：executive_summary、core_trend、technical_deep_dive、big_name_viewpoints、project_implications、noise_and_risk。

Chapter Evidence Pack 要求：
- 新增 build_chapter_evidence_pack(report_ir, chapter_spec, report_evidence_pack, db) -> dict。
- 每章 evidence pack 必须包含：selected_videos、transcript_segments、semantic_packets、cross_source_links、counter_evidence、must_use_evidence_ids、optional_evidence_ids。
- T0/T1 transcript 可作为核心证据；T2 只能 support_only；T3/failed 只能 metadata_only。
- 核心趋势章节默认要求 min_videos>=2，min_transcript_segments>=4，必须尝试 counter_evidence。
- 证据不足时不能硬写，章节降级为 weak/watchlist 或进入 repair_needed。

Browser Agent Operator 使用规则：
- PlannerOperator：只做语义分组和 Report IR 规划，不写正文。
- ChapterWriterOperator：只写单章，不写整篇报告；必须使用 Thinking high，并产生 UI mode proof。
- DeepWriterOperator：只增强 P0/P1 深度章节；必须使用 Pro / Deep Research，并产生 deep-research-state proof；不能用普通 ChatGPT 输出冒充。
- VerifierOperator：检查证据、结构、内部字段、缺章、unsupported claim；可先用 deterministic verifier + 可选 high model verifier。
- SynthesizerOperator：合并章节，统一叙事，不新增事实。
- CopyEditorOperator：只清理语言、重复、内部字段、标题密度，不新增事实。
- TechnologyDiagramPainter：只根据结构化 `figure-spec` 生成正式 Figure 风格图；必须保留 image/result/proof；证据不足时必须 `skipped/warn`，不得硬画。

Chapter Writer 验收：
- 每章必须有一句话判断。
- 不得按视频流水账写。
- 每个核心判断必须绑定 evidence_id 或 video_ref/timestamp。
- 证据不足必须明确降级，不得强行下结论。
- 不得泄露内部字段名、JSON key、调度信息、raw video_id、transcript_status。

Deep Writer 验收：
- P0/P1 章节默认执行 Deep Writer。
- Deep Writer 输出必须包含 improved_markdown、key_claims、new_insights、counterarguments、watch_next。
- 每个新增判断必须绑定 evidence_ids。
- 如果证据弱，必须降级结论，不得拔高。
- Deep Writer 必须使用真实 Browser Agent Deep Research proof；缺 proof 视为失败。

Verifier 验收：
- 新增 run_chapter_verifier(chapter_job, markdown, evidence_pack) -> dict。
- 检查项至少包括：has_clear_thesis、uses_required_evidence、grounded_claim_ratio、has_counter_evidence、has_actionable_insight、no_internal_field_leak、no_unsupported_claim、not_video_by_video_summary。
- 生成 claim-verification：claim_text、claim_type、evidence_ids、verification_status、confidence。
- status 为 passed | repair_needed | failed。
- grounded_claim_ratio 默认目标 >= 0.90。

Repair Loop 验收：
- 新增 run_chapter_repair_loop(chapter_job, verification, max_attempts=3)。
- 缺章 -> 重新调用 Chapter Writer。
- 章节浅/无洞察 -> 调用 Deep Writer。
- unsupported claim -> 删除或降级为 weak/watchlist。
- 内部字段泄露 -> Copy Editor 修复。
- 反证缺失 -> 尝试从 evidence pack 补 counter_evidence；没有则明确写证据缺口。
- Repair 最多 2-3 轮；失败后整份报告可 internal_only，但不得伪装 publish。

Synthesizer / Copy Editor 验收：
- 新增 synthesize_report(report_ir, chapter_outputs) -> markdown。
- Synthesizer 负责：开头核心判断、章节顺序、过渡、去重、统一 global thesis、结尾观察指标。
- Synthesizer 不得新增 evidence pack 之外的事实。
- Copy Editor 只做可读性、术语统一、内部字段清理、标题信息密度优化。

质量评分：
- 新增 report_quality_score：
  0.20 evidence_grounding_score
+ 0.15 thesis_clarity_score
+ 0.15 insight_density_score
+ 0.15 cross_source_score
+ 0.10 technical_accuracy_score
+ 0.10 actionability_score
+ 0.05 counterargument_score
+ 0.05 readability_score
+ 0.05 structure_completeness_score
- 等级：A>=85 可发布；B 75-84 可发布但带注；C 60-74 internal_only；D<60 repair/blocked。
- 质量结果必须写 validation/quality-score.json。

文件产物结构：
reports/<report_id>/
  report-plan.json
  report-ir.json
  catalog/video-catalog.json
  catalog/video-groups.json
  evidence-packs/report-evidence-pack.json
  evidence-packs/ch_01.evidence.json
  chapters/ch_01.draft.md
  chapters/ch_01.deep.md
  chapters/ch_01.final.md
  chapters/ch_01.verification.json
  repairs/repair_ch_01_attempt_1.json
  synthesis/report.synthesized.md
  synthesis/report.copyedited.md
  validation/chapter-validation-summary.json
  validation/report-validation-result.json
  validation/claim-verification.json
  validation/quality-score.json
  figures/fig_01.spec.json
  figures/fig_01.result.json
  figures/figure-manifest.json
  final/report.md
  final/report.html
  final/transcripts.txt
  final/evidence-map.json

代码改造建议：
- 重点修改 scripts/tech_hotspot_radar.py 的 cmd_run_ai_influence_planned_reports。
- 新增函数：
  compile_report_ir
  create_chapter_jobs
  build_chapter_evidence_pack
  run_chapter_writer
  run_deep_writer
  run_chapter_verifier
  run_chapter_repair_loop
  synthesize_report
  compile_report_figure_specs
  run_technology_diagram_painter
  validate_report_figures
  render_report_with_figures
  run_global_report_verifier
  run_copy_editor
- tools/chatgpt_report_operator.py 已有 planner/chapter_writer/deep_writer 基础能力，本单重点是把它们接入 YouTube 报告主链路，并补 verifier/synthesizer/copy editor operator policy。
  `TechnologyDiagramPainter` 则作为 figure-stage browser operator 接到最终渲染链路。

硬性禁止：
- 禁止用 Codex/direct GPT/local Qwen 替代最终 Planner/Chapter/Deep Writer。
- 禁止把普通 ChatGPT 输出冒充 Deep Research。
- 禁止报告正文泄露 video_id、chapter_id、evidence_pack_id、JSON key、planner/backend/token/validation 内部字段。
- 禁止 T3/failed transcript 支撑核心结论。
- 禁止缺章时直接整份 blocked 而不尝试 repair。
- 禁止一次性整篇写作继续作为默认路径；只能保留为 legacy fallback，且默认关闭。

分阶段交付：
S01 Requirements：冻结 Report IR、Chapter Job、Evidence Pack、Verifier、Quality Score 规约与 traceability。
S02 Architecture：设计执行器状态机、文件布局、Browser Agent operator policy、repair loop、quality gate。
S03 Core Runtime：实现 Report IR、chapter jobs、per-chapter evidence pack、Chapter Writer、Synthesizer 基础链路。
S04 Deep/Verifier/Repair：接入 Deep Writer、Chapter Verifier、Claim Verifier、Repair Loop、Quality Score。
S05 Orchestration/UI：CLI、status surface、artifacts、Knowledge raw 入库、validation/report paths、旧链路兼容。
S06 Verification：用 W21/W22 新 transcript fixture 跑端到端，不使用 legacy ASR，不使用 premium ASR，不花钱；证明缺章能 repair，弱章能 deep repair，T3 不进核心证据，最终生成 A/B/C/D 质量分。

验收标准：
1. plan-ai-influence-reports 仍负责 catalog/grouping/planning，但输出 report-ir.json。
2. run-ai-influence-planned-reports 默认逐章执行，不再一次性整篇写。
3. 每个章节都有 evidence pack、draft/deep/final/verification 产物。
4. P0/P1 章节有 Deep Writer proof；没有 proof 不能通过。
5. 缺章、弱章、内部字段泄露、unsupported claim 会进入 repair loop。
6. 最终 report.md/report.html 来自 Synthesizer + Copy Editor，不是单次 writer 直出。
7. `figures/figure-manifest.json` 存在，并记录 `painted/skipped/failed` 与 evidence 绑定。
8. 最终 report.md/report.html 在证据充分时包含至少 1 张 `TechnologyDiagramPainter` 生成图及 caption。
9. W21/W22 fixture 端到端通过：只使用 T0/T1/T2 新 transcript；T3/legacy ASR 不进入核心证据。
10. pytest/py_compile 通过，新增测试覆盖 Report IR、chapter evidence selection、deep proof enforcement、repair loop、quality scoring、figure grounding、final validation。

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w.epic.md`、`epic-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w.traceability.json` 和父级 task_graph。
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

- `sprint-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w-s01-requirements.design.md`
- `sprint-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w-s01-requirements.plan.md`
- `sprint-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w-s01-requirements.task_graph.json`
- `sprint-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w-s01-requirements.handoff.md`
- `sprint-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w-s01-requirements.eval.md` 或 `sprint-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w-s01-requirements.eval.json`
