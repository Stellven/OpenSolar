# Plan: AI Influence GitHub Project Intelligence Requirements Slice

epic_id: `epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade`
sprint_id: `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements`

## Execution Plan

1. Normalize the user design into six traceable outcomes: discovery, snapshot/delta ledger, local evidence compression, project intelligence cards, scoring/detectors, and AI Influence outputs.
2. Freeze P0/P1/P2 boundaries so implementation does not sprawl into unvalidated GH Archive, maintainer graph, or long-term prediction features.
3. Create a planner DAG that lets S02-S05 proceed with explicit contracts instead of a vague monolithic task.
4. Require all downstream code to preserve evidence IDs, cost ledger, provenance, and local-first model routing.
5. Validate graph-scheduler compatibility before handing off to Solar builders.

## Work Breakdown

| Node | Deliverable | Purpose |
|---|---|---|
| N1 | outcomes matrix | make scope measurable |
| N2 | data contract | define entities and evidence fields |
| N3 | scoring contract | define heat/potential/noise detectors |
| N4 | model/report contract | enforce ThunderOMLX first and report shape |
| N5 | traceability handoff | map S01 outcomes to S02-S05 |

## Acceptance Checklist

- `design.md` contains six outcomes with acceptance and risk boundaries.
- `task_graph.json` validates with `solar-harness graph-scheduler validate`.
- downstream slices have clear input expectations.
- no implementation is claimed complete by this requirements sprint.
- source PRD in `Knowledge/_raw` is referenced for knowledge closure.

## Stop Rules

- If graph validation fails, do not dispatch builders.
- If QMD cannot index the PRD, mark knowledge closure as degraded.
- If Solar pane is busy, keep files in sprint directory and let autopilot resume from artifacts.

