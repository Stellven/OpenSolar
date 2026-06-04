# solar-harness Handoff — 对 Solar Harness 做一轮架构收口，目标是降低接入新大模型供应商和新型号时的边际成本。必须把统一 selector、provider adapter

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

## Acceptance

- Planner produces design.md and plan.md.
- Planner may refine task_graph.json but must preserve compiled governance constraints and explicit requirement_ids mapping.
- No direct builder dispatch from raw request.
