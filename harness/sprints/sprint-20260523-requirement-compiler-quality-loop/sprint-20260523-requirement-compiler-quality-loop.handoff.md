# solar-harness Handoff — 为 PM pane / Requirement Compiler 建立 Quality Loop：以 Requirement IR 为唯一事实源，补齐 gold

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
- Planner may refine task_graph.json but must preserve compiled governance constraints.
- No direct builder dispatch from raw request.
