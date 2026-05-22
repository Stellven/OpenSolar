# Contract: GEPA optimize_anything Integration Design

Created: 2026-05-22T15:07:46Z
Status: drafting
Sprint: sprint-20260522-gepa-optimize-anything-integration
Project: /Users/lisihao/.solar/harness

## Summary

Research and design how Solar-Harness should integrate GEPA `optimize_anything` as a controlled optimizer plane for text-serializable artifacts. The output is a concrete implementation contract, not a production enablement.

## Scope

### In Scope

- Review GEPA `optimize_anything` official blog/docs/API enough to identify integration primitives.
- Map GEPA to Solar-Harness: physical operators, DAG tasks, evaluator gates, status artifacts, monitor bridge, and reports.
- Define a safe CLI/API proposal, e.g. `solar-harness optimizer gepa ...`.
- Define evaluator adapter contract and ASI storage model.
- Define budget/stopper/dry-run/approval rules.
- Define first implementation sprint with file boundaries and tests.

### Out of Scope

- Installing GEPA globally or mutating Python environments without explicit approval.
- Running expensive optimization loops.
- Applying optimized artifacts to production configs, hooks, skills, prompts, code, or operator registry.
- Printing tokens, API keys, OAuth material, or private prompts.

## Constraints

- Default mode must be `dry-run` / proposal-only.
- Any real GEPA run must require explicit `--execute` plus budget caps.
- Candidate artifacts must be written to isolated run directories with lineage metadata.
- Optimized output can be promoted only via a separate review/approval command.
- Cloud model use must prefer low-cost operators when adequate; expensive Claude is reserved for complex architecture/debug or evaluator review.
- Visual/multimodal optimization must only run on an operator with `input_modalities` including image.

## Required Artifacts

- `N1-handoff.md`: GEPA source/API audit.
- `N2-handoff.md`: Solar integration architecture.
- `N3-handoff.md`: safety, budget, and data model.
- `N4-handoff.md`: implementation backlog and tests.
- `N5-handoff.md`: final evaluation.
- `/Users/lisihao/.solar/harness/monitor-reports/gepa-optimize-anything-integration.md`: final report.

## Definition of Done

- `solar-harness graph-scheduler validate --graph /Users/lisihao/.solar/harness/sprints/sprint-20260522-gepa-optimize-anything-integration.task_graph.json` passes.
- All DAG nodes are passed.
- Final report includes "current problem" and "next action".
- No production GEPA loop executed.
- No secrets printed.

## Evaluation Dimensions

1. Source fidelity: GEPA claims are distinguished from Solar design assumptions.
2. Safety: no auto-apply path; bounded budgets and sandboxing are explicit.
3. Implementability: file paths, CLI shape, tests, and rollout are concrete.
4. Operator fit: physical operator routing is modeled, including multimodal support.

