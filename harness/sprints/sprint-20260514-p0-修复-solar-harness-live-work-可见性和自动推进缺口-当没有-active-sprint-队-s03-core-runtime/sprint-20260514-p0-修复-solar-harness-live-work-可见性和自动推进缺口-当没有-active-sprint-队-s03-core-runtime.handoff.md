# S03 Core Runtime Handoff

Sprint: `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s03-core-runtime`
Status: ready_for_eval
evaluator_can_review: true
s04_can_start: true

## Summary

S03 delivered the live-work core runtime package under `harness/lib/livework` without modifying coordinator main loops, autopilot main loop, or status-server code. The package gives S04 a stable API surface for pane state aggregation, append-only live-work events, idle/deadlock detection, and PM-first requirement intake FSM.

## Outcome Matrix

| Outcome | Module | API | Evidence |
|---|---|---|---|
| O1 idle/no-active visibility | `state_aggregator.py` | `aggregate_pane_state(events)` | `test_state_aggregator.py` |
| O2 PM-first requirement flow | `intake_state_machine.py` | `intake_requirement(text)` | `test_intake_state_machine.py` |
| O3 append-only runtime facts | `events.py` | `emit_*` functions | `test_events.py` |
| O4 deadlock/heartbeat detection | `idle_detector.py` | `is_idle`, `detect_deadlock`, `should_emit_heartbeat` | `test_idle_detector.py` |
| O5 replayable integration | `test_integration_replay.py` | real `events.jsonl` replay | full livework pytest |

## Delivered Files

- `lib/livework/__init__.py`
- `lib/livework/schemas.py`
- `lib/livework/state_aggregator.py`
- `lib/livework/events.py`
- `lib/livework/idle_detector.py`
- `lib/livework/intake_state_machine.py`
- `tests/livework/test_schemas.py`
- `tests/livework/test_state_aggregator.py`
- `tests/livework/test_events.py`
- `tests/livework/test_idle_detector.py`
- `tests/livework/test_intake_state_machine.py`
- `tests/livework/test_integration_replay.py`
- `sprints/epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队.traceability.json`

## Verification

```text
PYTHONPATH=/Users/sihaoli/.solar/harness/lib python3 -m pytest tests/livework -q
81 passed in 0.07s

Assertion count across tests/livework/*.py: 198
Implementation hidden clock grep for idle_detector.py: 0 matches
Forbidden core diff for coordinator.sh / status-server: 0 files
```

## S04 Integration Checklist

- Use `aggregate_pane_state(events)` as the projection source for idle/no-active UI state.
- Use `emit_heartbeat`, `emit_deadlock_detected`, `emit_requirement_intake`, `emit_pm_drafted`, and `emit_role_transition` for append-only live-work telemetry.
- Use `detect_deadlock(dispatch_log, now, timeout)` with explicit time injection from the orchestration layer.
- Use `intake_requirement(text)` before PM/Planner dispatch to reject too-vague requests without creating sprint files.
- Keep all future S04 integration package-first; do not patch coordinator main loop directly.

## Boundaries

- This sprint intentionally does not claim epic completion.
- This sprint intentionally does not claim S04 or S05 readiness beyond `s04_can_start: true`.
- Evaluator lane was rate-limited, so N2-N6 used Codex fallback eval with explicit test evidence.
