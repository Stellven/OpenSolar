# Sprint Contract: Managed Agent Runtime Interfaces

Priority: P0
Lane: reliability/control-plane
Owner: builder
Status: queued
Bypass PM: true
Handoff: builder_main
Parent: sprint-20260511-managed-agent-runtime-foundation
Source: Anthropic Engineering, "Scaling Managed Agents: Decoupling the brain from the hands", published 2026-04-08.

## Intent

Upgrade Solar-Harness from a working event-sourced foundation into a stable managed-agent runtime interface layer. The prior sprint implemented session log, projection, activity lifecycle, and runtime doctor. This sprint must make those foundations usable by real execution surfaces: pane dispatch, shell tools, MCP-like tools, remote Mac mini workers, context projection, and disposable hands/sandboxes.

The architectural target is:

```text
Session log = durable facts
Harness     = stateless control loop / policy
Hands       = disposable execution runtimes
Context     = materialized projection, not source of truth
```

## Source Insight

Anthropic's Managed Agents design makes three moves that Solar-Harness must adopt:

1. Harness assumptions rot as models improve. Workarounds must be isolated as policy, not embedded into the runtime ABI.
2. The session is not the context window. The session is an append-only event stream; context is a recoverable, auditable projection over that stream.
3. Brain/harness and hands/sandbox/tools must be decoupled. Hands are cattle: `provision(...)`, `execute(name, input)`, and `dispose(...)` are stable interfaces; the implementation behind them can change.

## Current Foundation

Already done by `sprint-20260511-managed-agent-runtime-foundation`:

- `schemas/session-event-v2.schema.json`
- `lib/session_log.py`
- `lib/projection_engine.py`
- `lib/activity_runtime.py`
- `lib/runtime_doctor.py`
- `docs/managed-agent-runtime.md`
- runtime tests for append/replay/idempotency/projection/activity/wake routing

## Gaps This Sprint Must Close

1. `SessionLog.replay()` exists, but there is no first-class `get_events(cursor/range/filter)` API for context projection and replay debugging.
2. Activity lifecycle exists, but real execution surfaces are not normalized behind `HandRuntime.execute(...)`.
3. Pane dispatch is still special natural-language tmux IO, not a hand adapter with command/result envelope.
4. Shell/MCP/remote/MinerU/QMD execution surfaces do not share one side-effect boundary or idempotency contract.
5. Context injection is still query/retrieval augmentation; it is not a projection policy over session events with provenance.
6. Secrets boundary is policy text, not runtime-enforced negative tests.
7. MacBook/Mac mini coordination exists, but worker registration/heartbeat/lease are not part of a stable Worker API.
8. Runtime doctor shows health, but does not yet certify the runtime interfaces under chaos/failure injection.

## Non-Goals

- Do not replace tmux panes or coordinator in this sprint.
- Do not introduce Kafka, Temporal, Redis, Celery, Docker Desktop, or any new always-on dependency.
- Do not move credentials into worker sandboxes or test fixtures.
- Do not claim deterministic LLM replay. Old model outputs are facts; only new decision boundaries call models.
- Do not migrate every old integration. Build the interface and prove four adapters: `mock`, `shell`, `pane`, `remote`.

## Required Deliverables

- `lib/runtime_interfaces.py`
- `lib/hands_runtime.py`
- `lib/context_projection.py`
- `lib/worker_runtime.py`
- `lib/runtime_chaos_suite.py`
- `schemas/runtime-hand-v1.schema.json`
- `schemas/context-projection-v1.schema.json`
- `docs/managed-agent-runtime-interfaces.md`
- `reports/managed-agent-runtime-interfaces/interface-inventory.{json,md}`
- `reports/managed-agent-runtime-interfaces/chaos-report.{json,md}`
- `/Users/sihaoli/Knowledge/_raw/solar-harness/managed-agent-runtime-interfaces-20260512.md`
- `/Users/sihaoli/Knowledge/_raw/solar-harness/managed-agent-runtime-interfaces-eval.md`
- tests:
  - `tests/runtime/test-session-get-events.sh`
  - `tests/runtime/test-hands-runtime.sh`
  - `tests/runtime/test-context-projection-policy.sh`
  - `tests/runtime/test-worker-runtime.sh`
  - `tests/runtime/test-runtime-interface-chaos.sh`

## Acceptance

1. `runtime_interfaces.py` defines typed protocols/data classes for Session, Harness, Hand, Worker, ContextProjection, CommandEnvelope, ResultEnvelope, and CapabilityPolicy.
2. `session_log.py` exposes `get_events(session_id, cursor=None, start_seq=None, end_seq=None, event_type=None, activity_id=None, limit=None)` and returns stable cursor metadata.
3. `hands_runtime.py` implements at least four adapters: `mock`, `shell`, `pane`, and `remote`. Each emits `command_issued`, `activity_started`, and exactly one terminal event.
4. Every `execute(...)` has an `idempotency_key`. Repeating the same key must not duplicate side effects.
5. `provision(...)` and `dispose(...)` exist for all adapters. For pane/remote they may be logical no-op, but must emit lifecycle events.
6. `context_projection.py` can build a model-visible context view from session events, with provenance listing included events, summarized events, dropped event ranges, and knowledge-context hits.
7. Context projection never deletes or rewrites session events. Compaction writes a new `context_injected` or `log_message` event with provenance only.
8. Secrets negative test proves env keys/tokens are redacted from hand result envelopes and context projections.
9. Worker runtime supports register/heartbeat/acquire_lease/release_lease for local and remote workers using existing state DB or files, with no new service dependency.
10. Runtime chaos suite covers: harness crash, hand crash, duplicate command, late result, cancelled activity, worker lease expiry, context compaction loss, and secret leak negative control.
11. `runtime doctor --json` or a new `runtime interfaces doctor --json` includes interface health: session_api, hands_runtime, worker_runtime, context_projection, chaos_suite.
12. Status UI can surface the new interface health without breaking `/status` and `/healthz`.
13. Existing runtime tests remain green:
    - `tests/runtime/test-session-log-v2.sh`
    - `tests/runtime/test-projection-replay.sh`
    - `tests/runtime/test-activity-runtime.sh`
    - `tests/runtime/test-wake-projection-routing.sh`
14. Every analysis/design/contract/eval artifact must be mirrored to `/Users/sihaoli/Knowledge/_raw/solar-harness/`.

## Stop Rules

- Stop if a builder tries to replace the coordinator instead of adding adapters.
- Stop if any adapter requires credentials in the sandbox environment.
- Stop if any test uses real user secrets, real Google Drive writes, or destructive shell commands.
- Stop if new runtime code exceeds 1400 net LOC before tests.
- Stop if chaos suite passes only by mocking all adapters; at least `shell` and `pane` must use real local integration paths in safe mode.
- Stop if UI changes break the existing loading/status tabs.

## Verification

Run:

```bash
bash tests/runtime/test-session-get-events.sh
bash tests/runtime/test-hands-runtime.sh
bash tests/runtime/test-context-projection-policy.sh
bash tests/runtime/test-worker-runtime.sh
bash tests/runtime/test-runtime-interface-chaos.sh
bash tests/runtime/test-session-log-v2.sh
bash tests/runtime/test-projection-replay.sh
bash tests/runtime/test-activity-runtime.sh
bash tests/runtime/test-wake-projection-routing.sh
solar-harness runtime doctor --json
solar-harness context inject --query "managed agent runtime interface smoke" --format markdown
```

Expected:

- All new interface tests pass.
- Existing foundation regressions remain green.
- Chaos report says `ok=true` or bounded `warn` with exact failed adapter.
- Runtime doctor includes the five interface health dimensions.
- Context projection report proves context is derived from events, not a replacement for session log.
- Knowledge raw contains design and eval summaries.

## Dispatch Policy

Use the DAG task graph. Builder nodes may run in parallel only when `write_scope` does not overlap. Evaluator must review per-node evidence and final parent readiness before the sprint can pass.
