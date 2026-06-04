# solar-harness Handoff — 对 Solar Harness 正式下单一轮 skill-to-capsule/operator auto-productization full PRD。目标

## Goal

Read compiled PRD / contract / task graph proposal, then produce planner artifacts without skipping governance.

## Read First

- .pm/requirement_ir.json
- .pm/prd.md
- .pm/Contracts.yaml
- .pm/task_dag.json
- .pm/handoff/solar_harness_handoff.md

## Constraints

- IR is source of truth.
- Markdown PRD / contract are compiled views.
- understand-anything 代表性 case 必须保留插件内置 deterministic 扫描/解析链。
- understand-anything 所有 semantic LLM analysis phase 必须显式使用 ThunderOMLX，并在 handoff 写明 backend 证据。

## Acceptance

- Planner produces design.md and plan.md.
- Planner may refine task_graph.json but must preserve compiled governance constraints and explicit requirement_ids mapping.
- No direct builder dispatch from raw request.
- Planner must make `semantic_backend=ThunderOMLX` a hard requirement for understand-anything case, not a soft preference.
