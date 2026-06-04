# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade`
sprint_id: `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements`
slice: `requirements`

## 用户原始需求

P0: AI Influence GitHub Project Intelligence System. Upgrade Tech Hotspot Radar GitHub module from basic repo snapshots/trending to an open-source project intelligence pipeline. Implement tracked/topic/trending/cross-source discovery, repo snapshots with 1h/6h/24h/7d/30d deltas, sudden-hot and early-potential detectors, ThunderOMLX local README/release/issues evidence atoms, why-hot attribution, project analysis cards, project planning briefs, alerts, model ledger, and AI Influence GitHub daily/weekly report. Source PRD: /Users/lisihao/Knowledge/_raw/tech-hotspot-radar/github-project-intelligence/20260524-github-project-intelligence-prd.md

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade.epic.md`、`epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade.traceability.json` 和父级 task_graph。
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

- `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements.design.md`
- `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements.plan.md`
- `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements.task_graph.json`
- `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements.handoff.md`
- `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements.eval.md` 或 `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements.eval.json`
