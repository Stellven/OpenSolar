# Plan — S05 verification-release

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s05-verification-release`
Slice: verification-release

## Master Roadmap

```text
┌────────────┬─────────┬──────────────────────────────────────────────┬──────────────────────────────┐
│ Item       │ Status  │ Evidence                                     │ Next                         │
├────────────┼─────────┼──────────────────────────────────────────────┼──────────────────────────────┤
│ S01        │ ok      │ outcomes_ready=true                          │ N/A                          │
│ S02        │ ok      │ architecture_ready=true                      │ N/A                          │
│ S03        │ ok      │ core_runtime_ready=true; node_count=8 passed │ feed S05 e2e fixture         │
│ S04        │ ok      │ orchestration_ui_ready=true; node_count=6    │ feed S05 activation proof    │
│ S05        │ pending │ PRD/contract exist, graph missing before now │ execute verification-release │
└────────────┴─────────┴──────────────────────────────────────────────┴──────────────────────────────┘
```

## DAG

```text
N1 e2e-gate-chain      ─┐
N2 negative-controls   ─┤
N3 activation-proof    ─┤
N4 release-evidence    ─┴── N5 join-traceability-handoff
```

## Node Plan

| Node | Goal | Depends | Gate |
| --- | --- | --- | --- |
| N1 | Local fixture proves full survey quality gate chain and CLI view propagation | - | `e2e-gate-chain-pass` |
| N2 | Negative controls prove weak outputs are visibly failed/warned/degraded | - | `negative-controls-pass` |
| N3 | Runtime activation proof for view registry, status/hint, and attach-style hook | - | `activation-proof-pass` |
| N4 | Release evidence report with test commands, no-rewrite scan, raw knowledge archive | - | `release-evidence-pass` |
| N5 | Join node patches S05 traceability only and writes final handoff/eval | N1-N4 | `verification-release-pass` |

## Current-Round Actions

1. Generate this design/plan/task_graph locally because planner pane contains stale S04 prompt residue.
2. Validate graph and dispatch S05 ready nodes through `graph-dispatch dispatch-ready`.

## Acceptance

- Graph validates with no schema errors.
- First dispatch only emits N1-N4.
- N5 is not ready until N1-N4 are passed.
- No parent epic completion claim appears before N5.

## Risks

- Worker queue may still contain stale pane prompt residue; dispatch artifacts are the source of truth.
- Some evaluator panes may be unavailable; if so, local equivalent eval artifacts must include exact test evidence.
- Raw knowledge archive may be blocked by path permissions; if blocked, release evidence must say so rather than claim success.
