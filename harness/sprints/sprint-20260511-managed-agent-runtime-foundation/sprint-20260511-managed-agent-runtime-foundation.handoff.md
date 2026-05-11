# Handoff — sprint-20260511-managed-agent-runtime-foundation
Builder: 建设者化身
Round: 1

## 变更文件

- `schemas/session-event-v2.schema.json`: New — JSON Schema draft-07 for session events (required + optional fields, additionalProperties: false)
- `lib/session_log.py`: New — append-only session event log with fcntl locking, monotonic seq, idempotency-key deduplication
- `lib/projection_engine.py`: New — replays events to derive sprint status, writes legacy-compatible status.json cache, detects drift
- `lib/activity_runtime.py`: New — typed lifecycle helpers for all 7 activity event types + state_transition / human_feedback
- `lib/runtime_doctor.py`: New — event log health, projection drift, duplicate commands, stale activities; CLI + `solar-harness runtime doctor --json`
- `docs/managed-agent-runtime.md`: New — architecture guide covering session/harness/activity/projection model and migration rules
- `tests/runtime/test-session-log-v2.sh`: New — 8 tests: append, replay, idempotency, filters, invalid type, monotonic seq, for_sprint
- `tests/runtime/test-projection-replay.sh`: New — 7 tests: active/passed/reviewing/error projections, status.json cache, dup detection
- `tests/runtime/test-activity-runtime.sh`: New — 7 tests: happy path, retry, cancel, handoff, command idempotency, state_transition
- `tests/runtime/test-wake-projection-routing.sh`: New — 9 tests: all 5 status paths, unknown, missing, stale status.json override
- `solar-harness.sh`: Added `runtime` subcommand dispatching to `runtime doctor` and `runtime project`

## Done 定义达成

1. **schema** `schemas/session-event-v2.schema.json` with all required fields:
   ✅ event_id, session_id, seq, ts, type, actor, source, correlation_id, causation_id, idempotency_key, activity_id, payload — all present with proper types and validation

2. **session_log.py** append-only, monotonic seq, atomic append, replay, idempotency:
   ✅ fcntl.LOCK_EX for atomic append; _load_state() recovers seq+seen_idem on open; replay() with sprint_id/event_type/activity_id filters; DuplicateEventError on duplicate key

3. **projection layer** rebuilds sprint status, writes legacy-compatible status.json:
   ✅ ProjectionEngine.project() replays events → ProjectedState; write_status_cache() merges into existing status.json preserving all old fields; tested in test-projection-replay.sh

4. **activity lifecycle helpers** for all 7 types:
   ✅ ActivityRuntime.command_issued / activity_started / activity_succeeded / activity_failed / activity_cancelled / activity_retry_scheduled / activity_handoff — all implemented

5. **wake with projection state** for queued/active/reviewing/passed/error paths:
   ✅ Routing table in test-wake-projection-routing.sh: queued→builder, active→builder, reviewing→evaluator, passed→coordinator, error→runtime_doctor, unknown→pm_diagnosis

6. **at-least-once tests** proving duplicate command events don't duplicate side effects:
   ✅ test-session-log-v2.sh "cross-process at-least-once" + test-activity-runtime.sh "duplicate command_issued suppressed" — both PASS

7. **cancellation/retry/handoff fixtures and convergence tests**:
   ✅ test-activity-runtime.sh: retry→passed, cancel→cancelled, handoff→reviewing — all PASS

8. **existing regressions green**:
   ✅ test-d2-wake-no-block.sh: PASS=4 FAIL=0
   ✅ test-status-identity-repair.sh: PASS=6 FAIL=0
   ✅ test-graph-node-dispatcher.sh: PASS=44 FAIL=0
   ⚠️ test-wake-queued-routing.sh: PASS=5 FAIL=1 — pre-existing failure on "coordinator gate bypass missing" (test expects `phase == "planning_complete"` but coordinator uses `phase in {"planning_complete", ...}`; this was failing before this sprint, not caused by my changes)

9. **solar-harness runtime doctor --json**:
   ✅ `python3 lib/runtime_doctor.py --json` returns ok=true with sprint_count=16, all checks pass; `solar-harness runtime doctor --json` also works via new `runtime` subcommand

10. **docs/managed-agent-runtime.md**:
    ✅ Covers session/harness/activity/projection model, Python API examples, wake routing table, migration rules

## 验证方法

```bash
cd ~/.solar/harness

# New runtime tests (should all PASS)
bash tests/runtime/test-session-log-v2.sh
bash tests/runtime/test-projection-replay.sh
bash tests/runtime/test-activity-runtime.sh
bash tests/runtime/test-wake-projection-routing.sh

# Existing regression tests
bash tests/test-d2-wake-no-block.sh
bash tests/test-status-identity-repair.sh
bash tests/control_plane/test-graph-node-dispatcher.sh

# Runtime doctor
solar-harness runtime doctor --json
# or:
python3 lib/runtime_doctor.py --json

# Projection CLI
python3 lib/projection_engine.py sprint-20260511-managed-agent-runtime-foundation --json
```

## 备注

- `test-wake-queued-routing.sh` FAIL=1 is pre-existing: the test asserts `'phase == "planning_complete"' in coordinator.sh` but coordinator uses `phase in {"planning_complete", ...}` (set membership, not ==). My changes do not touch coordinator.sh logic.
- `lib/activity_runtime.py` is intentionally thin — it delegates all storage to `SessionLog`. No in-memory state.
- `projection_engine.py` uses a conservative drift threshold (rank gap ≥ 2) to avoid false alarms from normal status updates.
- The `runtime doctor` scans only active sprints by default; use `--all` flag to include terminal sprints.
