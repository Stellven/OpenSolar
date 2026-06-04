# Contract — Mac mini stale Python multi-task runner fix

Sprint: `sprint-20260520-multitask-stale-python-runner`

## Scope

Fix `solar-harness multi-task` so completed DAG scheduler processes do not remain as confusing long-running Python processes. Implement root-cause behavior first, then add safe observability and cleanup evidence.

## Required Work

1. Audit `lib/multi_task_runner.py` scheduler loop, status rendering, and any doctor/monitor entrypoints.
2. Implement auto-exit for graph-specific `start` loops when:
   - parent-check is ready,
   - no open nodes remain,
   - no active workers remain,
   - no ready nodes remain.
3. Add stale scheduler detection:
   - PID,
   - graph path,
   - sprint id,
   - elapsed time,
   - RSS,
   - log file path,
   - reason.
4. Add safe cleanup/report behavior:
   - default report only,
   - apply/repair mode may only terminate exact stale `multi_task_runner.py start --graph <completed graph>` processes after re-checking graph readiness.
5. Update status output so old completed task windows are not reported as current active work.
6. Produce handoff with before/after evidence.

## Constraints

- Do not kill unrelated Python processes.
- Do not delete task directories, graph files, or logs.
- Do not change ThunderOMLX runtime/cache settings.
- Do not hide errors by filtering all Python processes from status.
- Preserve `screen`/TUI behavior and active scheduler behavior.

## Verification

- Unit or fixture test: completed graph loop exits.
- Unit or fixture test: active graph with ready nodes does not exit before dispatch.
- Smoke: run stale detector against current Mac mini state and show it flags existing residual scheduler PIDs if still present.
- Smoke: after repair/apply or natural exit, `ps` no longer shows stale completed graph runners.
- Smoke: `multi-task status --no-clear` clearly separates active/running from historical completed workers.

## Deliverables

- Code changes under `/Users/lisihao/.solar/harness/lib/` and CLI wiring as needed.
- Report under `/Users/lisihao/.solar/harness/monitor-reports/`.
- Handoff at `/Users/lisihao/.solar/harness/sprints/sprint-20260520-multitask-stale-python-runner.N*-handoff.md`.

