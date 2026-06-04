# PRD: 架构设计与接口契约

epic_id: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
sprint_id: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture`
slice: `architecture`

## 用户原始需求

DeepResearch professor-grade survey quality hardening: build pluggable package-local gates under harness/lib/research/survey only. Goal: reports must support 50k-100k word professor-level survey quality, not generic stitched summaries. Requirements: (1) source quality gate beyond URL count: canonical/high-authority distribution, primary source ratio, paper/code/official/benchmark balance, no generic example/web stuffing; (2) argument density gate: every section must contain mechanism comparison, method taxonomy, evaluation protocol, failure/negative evidence, and engineering implication where applicable; (3) controversy/反证 gate: final report must include contradiction/negative evidence matrix and use it in chapter synthesis; (4) no main architecture rewrite; everything must be package-first and pluggable; (5) agent online exploration should try multiple research directions quickly and eliminate weak directions, recording why; (6) end-to-end verification must include solar-harness runtime survey-continue sample, strict tests, and evidence artifact. Do not mark done without tests and runtime evidence.

## 本切片目标

基于需求矩阵产出系统分层、接口、数据模型、兼容策略和迁移方案。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build.epic.md`、`epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build.traceability.json` 和父级 task_graph。
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

- `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture.design.md`
- `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture.plan.md`
- `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture.task_graph.json`
- `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture.handoff.md`
- `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture.eval.md` 或 `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture.eval.json`
