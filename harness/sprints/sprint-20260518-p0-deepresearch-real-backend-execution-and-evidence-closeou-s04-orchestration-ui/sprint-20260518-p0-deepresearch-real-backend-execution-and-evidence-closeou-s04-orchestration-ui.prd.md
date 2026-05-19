# PRD: 调度、自动化与可视化

epic_id: `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou`
sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui`
slice: `orchestration-ui`

## 用户原始需求

P0: DeepResearch real-backend execution and evidence closeout

背景：Codex 已直接在 Solar repo 中实现了 DeepResearch report execution metrics 与 model_usage.jsonl ledger 支持，但这不是完整的 solar-harness 四 pane 执行闭环。请 solar-harness 自己按 PM -> Planner -> DAG Builder -> Evaluator 路径验证并收口，不允许只依赖 Codex 手工改动结论。

目标：让 DeepResearch 能用高质量搜索与真实 writer/chief_editor backend 生成可审阅报告，并在报告与 JSON artifact 中明确写出本次执行总 token 消耗数和产生的文档字数。

必须完成：
1. PM 输出 PRD，并生成 prd.html。
2. Planner 输出 design.md、plan.md、task_graph.json，并生成 planning.html。
3. Builder 基于当前 /Users/sihaoli/Solar 代码验证以下链路：
   - Serper 搜索能被 DeepResearch 使用，并记录 usage meter。
   - survey writer/chief_editor backend 会写 model_usage.jsonl。
   - 如果 backend 返回真实 usage JSON/stream-json/stdout/stderr，final metrics 使用 provider_usage_ledger。
   - 如果 backend 不返回真实 usage，只能标记 estimated，不能伪装为真实 token。
   - final.md / human_final.md / research_eval.json / report_ast.json 包含 execution_metrics。
4. 必须运行一个受控 DeepResearch 样例，不要消耗大额度；max_results <= 3。
5. 如果可用，跑 survey-chief-editor --backend claude-cli --model opus 的小样；若 Claude CLI 或账户限制导致无法拿真实 usage，必须把错误、fallback 与估算标记写入 handoff。
6. Evaluator 必须检查报告末尾是否包含 Document word count、Total token consumption、Token usage source、Token usage estimated。

验收标准：
- status.json artifacts 里可追踪 prd_html/planning_html。
- 产物目录包含 final.md、research_execution_metrics.json 或 survey_execution_metrics.json、model_usage.jsonl（真实 backend 路径可用时）。
- 至少一个测试或样例证明 provider_usage_ledger 能被 report_metrics 读取；如果真实 Claude CLI 不提供 usage，则用受控 local-command JSON fixture 验证真实 usage 读取路径，并明确标注真实模型 usage 未返回。
- 不要把 API key、OAuth token、usage ledger 私密内容提交到 GitHub。
- 最终 handoff.md 用中文给出证据表：搜索次数、来源数、token 来源、文档字数、报告路径、测试命令、失败/降级原因。

## 本切片目标

把核心能力接入 autopilot、DAG 调度、status UI、pane 可视化和运行时证据。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou.epic.md`、`epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- ready 子任务能自动激活并派到正确角色
- UI 显示 epic、child sprint、能力使用和阻塞原因
- pane 输出不再只靠自然语言声称完成

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui.design.md`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui.plan.md`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui.task_graph.json`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui.handoff.md`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui.eval.md` 或 `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui.eval.json`
