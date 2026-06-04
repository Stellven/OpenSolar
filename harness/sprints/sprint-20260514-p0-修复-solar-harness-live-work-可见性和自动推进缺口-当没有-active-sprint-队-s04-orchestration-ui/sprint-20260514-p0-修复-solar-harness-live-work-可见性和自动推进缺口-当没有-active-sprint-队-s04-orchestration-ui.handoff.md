# Handoff — sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s04-orchestration-ui / N5

Sprint: `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s04-orchestration-ui`
Node: N5
Date: 2026-05-14
Knowledge Context: solar-harness context inject used

## Summary

Integration smoke test + S04 handoff + parent traceability patch. 13 integration tests verify all 5 Flask routes return 2xx via real test client, plus 4 UI template assertions. Total livework suite: 136 tests, 322 assertions. Parent traceability patched with `orchestration_ui_ready=true`.

evaluator_can_review: true
s05_can_start: true

## Changed Files

| File | Action | Description |
|------|--------|-------------|
| `harness/tests/livework/test_integration_s04.py` | created | 13 integration tests: 9 route tests (5 routes, all 2xx) + 4 UI template tests |
| `sprints/sprint-20260514-p0-…-s04-orchestration-ui.handoff.md` | created | This file |
| `sprints/epic-20260514-p0-…-traceability.json` | modified | Patched children[3].orchestration_ui_ready=true |

## Verification Evidence

```bash
cd /Users/lisihao/.solar

# N5 integration tests
python3 -m pytest harness/tests/livework/test_integration_s04.py -v
# Result: 13 passed in 0.11s, exit code 0

# Full livework suite
python3 -m pytest harness/tests/livework/ -v
# Result: 136 passed in 0.40s

# Total assertions
grep -rc 'assert ' harness/tests/livework/ | awk -F: '{s+=$2} END {print s}'
# Result: 322 (>= 90)
```

## 5 curl Examples

```bash
# 1. O1: Check idle state
curl -s http://localhost:8765/api/idle-state | jq .
# Expected: {"is_idle": true, "active_panes": [], "queue_depth": 0, ...}

# 2. O2: Heartbeat config
curl -s http://localhost:8765/api/heartbeat-config | jq .
# Expected: {"interval_seconds": 300, "should_emit_now": true, ...}

# 3. O2/O3: Deadlock alerts
curl -s http://localhost:8765/api/deadlock-alerts | jq .
# Expected: {"active_deadlocks": [], "deadline_seconds": 600, ...}

# 4. O3/O4: Submit requirement
curl -s -X POST http://localhost:8765/api/requirements \
  -H 'Content-Type: application/json' \
  -d '{"raw_requirement":"Fix status page to show idle state when no sprint is active"}'
# Expected: {"status":"created","sprint_id":"...","phase":"dispatched"}

# 5. O5: Sprint next step
curl -s http://localhost:8765/api/sprints/my-sprint/next-step | jq .
# Expected: {"sprint_id":"my-sprint","phase":"unknown","next_action":"..."}
```

## 4 DOM IDs

- `#no-active-work-card` — O1 idle/no-active-work display
- `#role-next-step-card` — O5 role next-step display
- `#deadlock-alerts-card` — O2/O3 deadlock alerts
- `#events-tail-card` — recent events tail

## Autopilot 1-line Integration

```bash
# Add to autopilot schedule (crontab or coordinator loop):
*/5 * * * * $HOME/.solar/harness/autopilot/hooks/livework_heartbeat_hook.sh
```

## S05 Integration Checklist

- [ ] Run full regression: `pytest harness/tests/livework/ -v` (must stay 136+ pass)
- [ ] Verify traceability `children[3].orchestration_ui_ready == true`
- [ ] Verify traceability `children[4].status` transitions to `active`
- [ ] Start status-server: `python3 harness/status-server/app.py` (or Flask dev server)
- [ ] curl all 5 routes from S05 environment to confirm HTTP connectivity
- [ ] Load `http://localhost:8765/` in browser, verify 4 cards render
- [ ] Confirm autopilot heartbeat hook exits 0 on runner failure (fail-open)
- [ ] Final acceptance: all S04 gates (routes-pass, hook-pass, visibility-pass, ui-pass, integration-pass) marked passed

## Capability / KB Usage Evidence

- **harness-knowledge**: context inject used at dispatch start. Standard KB hits.
- **harness-graph**: Task graph and traceability read for N5 node details.
- Not used: harness-intent, harness-skills, harness-ATLAS, harness-autopilot, gstack.

## Scope Compliance

- `harness/tests/livework/test_integration_s04.py` — within write scope
- `sprints/...s04-orchestration-ui.handoff.md` — within write scope
- `sprints/epic-...traceability.json` — within write scope
- No files outside write scope were modified.

## Known Risks

1. **No running server tested**: Tests use Flask test client, not a real HTTP server. S05 should verify with a live server.
2. **/api/events/tail route missing**: JS fetches this route but N1 doesn't implement it. Graceful fallback to "unknown" in UI.
3. **Autopilot hook integration untested**: `livework_heartbeat_hook.sh` exists but the Python runner (`livework_heartbeat_runner.py`) doesn't exist yet. Hook exits 0 (fail-open) when runner is absent.

## Not Done

Nothing within N5 scope remains undone. All acceptance criteria met.
