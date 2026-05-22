# Dispatch — sprint-20260521-physical-operator-registry

## Mission

Implement the Solar-Harness physical operator registry model for Mac mini headless tmux panes.

## Source Files

- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-physical-operator-registry.prd.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-physical-operator-registry.contract.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-physical-operator-registry.task_graph.json`

## Execution

Run through `solar-harness multi-task` using the graph. Each node must write its handoff and move to reviewing/passed through graph-scheduler.

## Rules

- Do not print tokens, OAuth codes, or API keys.
- Do not delete task directories.
- Do not kill unrelated tmux panes.
- Keep existing `preferred_profile` behavior working.
- Antigravity is gated unless smoke returns `AGY_OK`.
- ThunderOMLX unsafe cache features stay disabled.

