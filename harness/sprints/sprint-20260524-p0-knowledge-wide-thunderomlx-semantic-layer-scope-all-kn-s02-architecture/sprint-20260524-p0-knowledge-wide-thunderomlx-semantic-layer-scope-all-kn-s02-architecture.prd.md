# PRD: 架构设计与接口契约

epic_id: `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn`
sprint_id: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s02-architecture`
slice: `architecture`

## 用户原始需求

P0: Knowledge-wide ThunderOMLX semantic layer. Scope: all knowledge sources, not only YouTube transcript. Implement single knowledge_ingest_dispatcher/state registry; accepted, Obsidian, ChatGPT, Web, GitHub, PDF/manual raw, Solar artifacts must flow raw/vault -> QMD raw/vault embed -> ThunderOMLX JSON-first semantic extraction -> validator/repair/quarantine -> semantic.md -> QMD extracted embed. Contract source: /Users/lisihao/Knowledge/_raw/solar-harness/intake/20260524t132500z-knowledge-wide-thunderomlx-semantic-layer.md

## 本切片目标

基于需求矩阵产出系统分层、接口、数据模型、兼容策略和迁移方案。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn.epic.md`、`epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn.traceability.json` 和父级 task_graph。
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

- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s02-architecture.design.md`
- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s02-architecture.plan.md`
- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s02-architecture.task_graph.json`
- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s02-architecture.handoff.md`
- `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s02-architecture.eval.md` 或 `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s02-architecture.eval.json`
