# solar-harness Handoff — Agent Plan Optimizer Foundation

## Goal

Read compiled APO/AQO PRD / contract / task graph proposal once predecessor Requirement Compiler sprints pass, then produce planner artifacts without skipping governance.

## Read First

- .pm/requirement_ir.json
- .pm/prd.md
- .pm/Contracts.yaml
- .pm/task_dag.json
- .pm/handoff/solar_harness_handoff.md

## Constraints

- IR is source of truth.
- Markdown PRD / contract are compiled views.
- This sprint is blocked by:
  - sprint-20260523-pm-pane-requirement-compiler-backend-foundation
  - sprint-20260523-requirement-compiler-quality-loop
- No planner/builder wake until dependency gate clears.

## Acceptance

- Planner produces design.md and plan.md.
- Planner may refine task_graph.json but must preserve compiled governance constraints.
- No direct builder dispatch from raw request.
- APO must remain heuristic in P0.
- Explain Plan / rule engine / physical plan enumeration / cost model / enforcer contracts must be explicit.
