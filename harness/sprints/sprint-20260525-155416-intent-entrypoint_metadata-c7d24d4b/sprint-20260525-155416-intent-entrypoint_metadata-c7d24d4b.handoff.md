# solar-harness Handoff — RawIntent Consumer Request - [entrypoint_metadata]

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
