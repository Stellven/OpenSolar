# Eval: Managed Agent Runtime Interfaces

Sprint: `sprint-20260512-managed-agent-runtime-interfaces`
Verdict: `PASS_WITH_WARN`
Evaluated: 2026-05-13T01:45Z

## Scope

This evaluation covers the managed-agent runtime interface layer:

- Session API pagination and filters
- HandRuntime adapters and activity event emission
- ContextProjection with provenance and secret redaction
- WorkerRuntime registration, heartbeat, and leases
- Runtime chaos suite
- Runtime doctor interface health
- Status UI `/status.runtime_interfaces`
- QMD IPv4 self-healing before KB probes

## Evidence

```text
test-session-get-events.sh: 14 passed, 0 failed
test-hands-runtime.sh: 30 passed, 0 failed
test-context-projection-policy.sh: 23 passed, 0 failed
test-worker-runtime.sh: 25 passed, 0 failed
test-runtime-interface-chaos.sh: PASS
test-session-log-v2.sh: PASS=8 FAIL=0
test-projection-replay.sh: PASS=7 FAIL=0
test-activity-runtime.sh: PASS=7 FAIL=0
test-wake-projection-routing.sh: PASS=9 FAIL=0
test-autopilot-kb-probe-no-pane-dispatch.sh: PASS
test-autopilot-kb-probe-starts-qmd-proxy.sh: PASS
test-knowledge-probe-coverage.sh: PROBES_PASSED=10 PROBES_FAILED=0
status /status.runtime_interfaces: ok 5/5
runtime doctor interface_health: 5/5 interfaces healthy
```

## Acceptance Trace

| Acceptance | Result | Evidence |
|---|---|---|
| Stable runtime interfaces | PASS | `lib/runtime_interfaces.py` |
| SessionLog.get_events | PASS | `test-session-get-events.sh` |
| HandRuntime mock/shell/pane/remote | PASS | `test-hands-runtime.sh` |
| Idempotency | PASS | duplicate command tests |
| provision/execute/dispose | PASS | hands runtime tests |
| ContextProjection provenance | PASS | context projection tests |
| No session rewrite by projection | PASS | context projection + chaos |
| Secret negative controls | PASS | context projection + shell redaction |
| Worker registry/heartbeat/lease | PASS | worker runtime tests |
| Chaos suite | PASS | 6/6 cases |
| Runtime doctor interface health | PASS | 5/5 dimensions |
| Status UI surface | PASS | `/status.runtime_interfaces` exposed |
| Existing runtime tests | PASS | session/projection/activity/wake all green |
| Knowledge raw mirror | PASS | repair/eval documents under `_raw/solar-harness/` |

## Done 条件逐条检查

| Done 条件 | 结论 | 证据 |
|---|---|---|
| D1 Session API pagination and filters are implemented and tested | PASS | `test-session-get-events.sh: 14 passed, 0 failed` |
| D2 HandRuntime adapters emit normalized activity events | PASS | `test-hands-runtime.sh: 30 passed, 0 failed` |
| D3 ContextProjection includes provenance and redacts secrets | PASS | `test-context-projection-policy.sh: 23 passed, 0 failed` |
| D4 WorkerRuntime registry, heartbeat, and leases are functional | PASS | `test-worker-runtime.sh: 25 passed, 0 failed` |
| D5 Chaos suite covers crash, duplicate, late, cancel, lease, compaction, and secret controls | PASS | `test-runtime-interface-chaos.sh: PASS` |
| D6 Existing foundation regressions remain green | PASS | session/projection/activity/wake tests all green |
| D7 Doctor and status UI expose interface health | PASS | `/status.runtime_interfaces: ok 5/5`; runtime doctor interface health `5/5` |
| D8 Knowledge mirror and KB probe remain usable | PASS | `_raw/solar-harness/` mirror present; `PROBES_PASSED=10 PROBES_FAILED=0` |

## Residual Warn

`runtime doctor` reports one historical seq gap in this active sprint event log:

```text
seq gaps at [34]
```

This is a hygiene warning on the sprint event stream, not a runtime interface failure. Interface health is `5/5`, projection drift is `no drift`, and all tests pass.

## Verdict

`PASS_WITH_WARN`: runtime interfaces are usable and integrated into doctor/status. Follow-up should clean the seq-gap hygiene and reduce legacy event/status drift, but this does not block the interface layer.
