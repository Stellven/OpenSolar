# Sprint Contract: Managed Agent Runtime Foundation

Priority: P0
Lane: reliability/control-plane
Owner: builder
Status: active
Bypass PM: true
Handoff: builder_main

## Intent

Turn Solar-Harness from a pane-driven coordinator with several competing state files into an event-sourced, async-capable agent workflow runtime. This sprint must keep the existing tmux/Solar workflow working, but introduce a durable session log as the source of truth and make `status.json`, UI state, pane assignments, and context windows derived projections instead of independent writable truth.

## Source Insight

The "Scaling Managed Agents" runtime model maps directly to Solar-Harness:

- `session` is not the context window; it is the durable append-only event log.
- `harness` should be mostly stateless; it reconstructs execution state from session events.
- `sandbox/tools/MCP/pane/model calls` are activities with explicit side-effect boundaries.
- `wake(session_id)` should replay/project known facts and continue from the next decision boundary, not re-run old LLM reasoning.
- LLM outputs, tool calls, tool results, errors, human feedback, leases, handoffs, cancels, and retries must be recorded as facts.
- Long-running work should be async: command event out, result event back, any worker can resume.

## Current Gaps

1. `status.json`, queue files, dispatch ledger, `state.db`, pane state, and event files can disagree; no single fact source exists.
2. Existing events lack a strict envelope with `event_id`, monotonic `seq`, `session_id`, `correlation_id`, `causation_id`, and `idempotency_key`.
3. `wake` still relies on status heuristics and can fall back to the wrong role when state is ambiguous.
4. Tool/model/pane work is dispatched as natural-language tmux text, but lifecycle facts are not normalized as `command_issued -> activity_started -> activity_succeeded|failed|cancelled`.
5. Duplicate dispatch and at-least-once delivery are only partially guarded by pane lease files, not by idempotent command/result semantics.
6. Cancellation, retry, handoff, remote worker takeover, and human intervention are not first-class event types.
7. Context injection is retrieval augmentation, not a projection policy over session history.
8. Mac mini remote execution is available, but it is not yet a durable worker pool over the same event log.
9. Secrets and sandbox boundaries exist in pieces; activity credentials policy is not represented in runtime events.

## Non-Goals

- Do not replace tmux panes or the current coordinator in this sprint.
- Do not introduce Kafka, Temporal, Redis, or any external runtime dependency.
- Do not remove legacy `status.json`; it must remain as a projection cache for compatibility.
- Do not move secrets into worker sandboxes.
- Do not fabricate deterministic replay of old LLM inference. Old model outputs are facts; only new decision boundaries call models.

## Acceptance

1. Define `schemas/session-event-v2.schema.json` with at least: `event_id`, `session_id`, `seq`, `ts`, `type`, `actor`, `source`, `correlation_id`, `causation_id`, `idempotency_key`, `activity_id`, `payload`.
2. Implement `lib/session_log.py` with append-only writes, monotonic `seq`, atomic append, read replay, and idempotency-key duplicate suppression.
3. Implement a projection layer that can rebuild sprint status from events and write legacy-compatible `status.json` as a cache.
4. Add activity lifecycle helpers for `command_issued`, `activity_started`, `activity_succeeded`, `activity_failed`, `activity_cancelled`, `activity_retry_scheduled`, and `activity_handoff`.
5. Integrate `wake` with projection state for at least queued/active/reviewing/passed/error paths; unknown state must route to PM diagnosis or runtime doctor, never generic builder fallback.
6. Add at-least-once tests proving duplicate command events do not duplicate side effects when `idempotency_key` matches.
7. Add cancellation/retry/handoff fixtures and tests proving downstream projections converge.
8. Keep existing regressions green: `test-wake-queued-routing.sh`, `test-d2-wake-no-block.sh`, `test-status-identity-repair.sh`, and `test-graph-node-dispatcher.sh`.
9. Add `solar-harness runtime doctor --json` or equivalent report that shows event log health, projection drift, duplicate commands, stale activities, and pane/session ownership.
10. Add `docs/managed-agent-runtime.md` explaining the new session/harness/activity/projection model and migration rules.
11. Every analysis, design, contract summary, evaluation summary, and accepted architecture artifact produced by this sprint must also be written as Markdown under `/Users/lisihao/Knowledge/_raw/solar-harness/` so the Obsidian/QMD knowledge pipeline can extract it.

## Required Files

- `schemas/session-event-v2.schema.json`
- `lib/session_log.py`
- `lib/projection_engine.py`
- `lib/activity_runtime.py`
- `lib/runtime_doctor.py`
- `docs/managed-agent-runtime.md`
- `/Users/lisihao/Knowledge/_raw/solar-harness/managed-agent-runtime-foundation-20260511.md`
- `tests/runtime/test-session-log-v2.sh`
- `tests/runtime/test-projection-replay.sh`
- `tests/runtime/test-activity-runtime.sh`
- `tests/runtime/test-wake-projection-routing.sh`

## Stop Rules

- Stop and split if implementation exceeds 1200 net new LOC before tests.
- Stop if any change requires deleting existing sprint status files or historical event logs.
- Stop if projection cannot preserve current status UI and coordinator compatibility.
- Stop if a worker tries to solve this by adding only more status flags without a session event source.
- Stop if remote Mac mini is used as the only evidence; local tests must pass first.

## Verification

Run:

```bash
bash tests/runtime/test-session-log-v2.sh
bash tests/runtime/test-projection-replay.sh
bash tests/runtime/test-activity-runtime.sh
bash tests/runtime/test-wake-projection-routing.sh
bash tests/test-wake-queued-routing.sh
bash tests/test-d2-wake-no-block.sh
bash tests/test-status-identity-repair.sh
bash tests/control_plane/test-graph-node-dispatcher.sh
solar-harness runtime doctor --json
```

Expected:

- session log append/replay/idempotency tests pass
- projection rebuilds legacy status exactly in fixture cases
- activity lifecycle events converge to expected states
- wake no longer uses ambiguous builder fallback
- runtime doctor returns `ok=true` or a bounded `warn` list with actionable drift
