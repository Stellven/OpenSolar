# Plan — capability/risk/cost runtime constraints S01

Knowledge Context: solar-harness context inject used

## Objective

Produce the requirements-level contract that lets downstream slices upgrade capability/risk/cost profiles into runtime scheduling, risk, lease, quota, fallback, and audit constraints.

## DAG Strategy

```text
R1 baseline + gaps
        |
        v
R2 target requirement contract
        |
        v
R3 traceability + migration boundary
        |
        v
R4 handoff + evidence closeout
```

This requirements slice is intentionally serial because each node depends on the previous node's terminology and acceptance map. Parallel dispatch would risk conflicting edits to the same requirements artifacts.

## Nodes

| Node | Gate | Goal | Write scope |
| --- | --- | --- | --- |
| R1 | G_REQ_BASELINE | Confirm source inputs, missing artifacts, current gaps, and upstream/downstream dependencies. | S01 handoff / requirement trace addenda only |
| R2 | G_REQ_CONTRACT | Finalize target capability/risk/cost taxonomy and logical operator request contract. | S01 requirements artifacts only |
| R3 | G_REQ_TRACE | Map outcomes to S02-S05, migration constraints, and non-builder/direct-builder boundaries. | S01 traceability / handoff artifacts only |
| R4 | G_REQ_READY | Produce builder handoff evidence and mark readiness for evaluator path. | S01 handoff / PM result only |

## Acceptance Gates

| Gate | Required evidence |
| --- | --- |
| G_REQ_BASELINE | Inputs read, missing `product-brief.md` and sprint-local `requirement_ir.json` documented, no hardcoded implementation choices. |
| G_REQ_CONTRACT | Capability/risk/cost fields and operator fields are explicit; risk/cost gates are defined as runtime hard constraints. |
| G_REQ_TRACE | Parent epic to child-sprint mapping exists; S01 states what cannot be implemented directly in requirements. |
| G_REQ_READY | `task_graph.json` validates; status is moved to `planning_complete`; PM result records command evidence. |

## Builder Boundaries

The builder for this requirements slice may refine or add requirements/handoff artifacts under the declared write scope. It must not implement runtime modules, schema changes, router changes, or UI changes in S01. Those are owned by S02-S05.

## Verification Commands

Planned verification:

- `solar-harness context inject --query "<summary>" --format markdown`
- `python3 -m json.tool <task_graph.json>`
- `solar-harness graph-scheduler validate --graph <task_graph.json>`
- `python3 tools/pm_dispatch.py complete --task-id <task-id>`

## Risks

| Risk | Mitigation |
| --- | --- |
| Missing sprint-local product brief / requirement IR | Record as planning gap; use PRD, contract, epic spec, and epic traceability as authoritative inputs. |
| Requirements slice accidentally expands into implementation | Enforce write scope to sprint artifacts only; runtime/schema source edits move to S02-S05. |
| Prompt-only safety language mistaken for enforcement | Acceptance requires runtime policy, router, and lease/submit hard gates downstream. |
| Premium actor policy remains advisory | S03/S05 acceptance must prove low-value avoidance and high-value reservation. |

## Status Transition

When this plan and task graph validate, set:

- `status`: `active`
- `phase`: `planning_complete`
- `handoff_to`: `builder_main`
- `target_role`: `builder_main`

