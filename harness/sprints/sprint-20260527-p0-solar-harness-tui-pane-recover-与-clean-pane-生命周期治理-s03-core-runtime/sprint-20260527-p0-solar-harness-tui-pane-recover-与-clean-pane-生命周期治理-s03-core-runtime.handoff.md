# Sprint Handoff — s03-core-runtime: TUI Pane Recover 与 Clean Pane 生命周期治理

## B1-B4 Phase Summaries

### B1 FSM Registry (passed)
- 6-state FSM: clean/running/dirty/cooling/needs_recover/needs_respawn
- 11 legal + 4 forbidden transitions
- PaneHygieneRegistry with atomic write (tmp→rename) + flock
- 5 error codes: PROCEED_PROMPT_STUCK, QUEUED_PROMPT_STUCK, PERMISSION_LOOP, CLEAR_FAILED_EXHAUSTED, RESPAWN_FAILED
- 41+ tests passing

### B2 Detection and Clear (passed)
- RecoverDetector: 3 regex (DET_PROCEED/DET_QUEUED/DET_PERMISSION) + 4 detect methods + capture_fn injection
- PaneClearManager: 3 methods (clear_pane/verify_clear_success/clear_with_retry) + three-signal verification + retry 5/10/15s backoff
- Exhausted path: dirty→cooling→needs_recover→needs_respawn (legal FSM)
- 41 tests passing (24 detector + 17 clear manager), mock-based

### B3 Reinject Ledger Scheduler (reviewing)
- PersonaReinjector: 4 methods + session-aware injection (OQ-03)
- LedgerWriter: dual-write JSONL + SQLite WAL with fallback file buffer
- DispatchScheduler: 4 methods + round-robin spillover + dedup + max-items 3
- PaneLifecycleJobs: archive 30d + TTL 90d + backup daily
- spillover_config.yaml: 5 pane (1 main + 4 lab)

### B4 Acceptance Gates (pending)
- Not yet dispatched; may discover integration issues

### B5 Traceability Handoff (current)
- Aggregating B1-B4 outputs into traceability.json + this handoff.md

## Acceptance Reports

| Report | Path |
|--------|------|
| B1 handoff | sprints/...B1_fsm_registry-handoff.md |
| B1 eval | sprints/...B1_fsm_registry-eval.md |
| B2 handoff | sprints/...B2_detection_and_clear-handoff.md |
| B2 eval | sprints/...B2_detection_and_clear-eval.md |
| B3 handoff | sprints/...B3_reinject_ledger_scheduler-handoff.md |
| B4 handoff | sprints/...B4_acceptance_gates-handoff.md |
| B4 eval | sprints/...B4_acceptance_gates-eval.md |
| B5 handoff | sprints/...B5_traceability_handoff-handoff.md |

Key numbers:
- 6 Python modules (1178 total lines)
- 4 schemas initialized
- 5 error codes defined
- B1+B2: 82+ tests passing (B3/B4 tests pending review)

## S04 Startup Checklist

1. Consume S04 dependencies from traceability.json → s04_dependencies
2. Implement orchestration UI for pane lifecycle visualization
3. Wire CLI commands to S03 Python API
4. Integration test: full lifecycle clean→running→dirty→clear→clean
5. Wire PersonaReinjector into dispatch flow (clean→running injection)

## S05 Startup Checklist

1. E2E verification with real tmux panes (not mocks)
2. Autopilot respawn trigger chain test
3. Ledger dual-write consistency under concurrent access
4. Coverage measurement with --cov (target ≥80% per module)
5. Integration test: DispatchScheduler spillover with real pane allocation

## Residual Risks

1. **B3 status**: Still in reviewing — tests not yet evaluator-verified
2. **B4 not dispatched**: May discover integration issues between modules
3. **Linter import instability**: Auto-modifies Python imports, may cause ImportError
4. **Coverage unmeasured**: B2 tests assumed >80% but not confirmed with --cov
5. **deprecated datetime.utcnow()**: 21 test warnings in recover_detector.py

## Declarations

**禁止乐观词**: 本 handoff 不使用 "done/complete/implemented" 描述未验证项。B3 仍为 reviewing 状态，B4 未派发。

**禁止 cooldown 当最终修复**: Cooldown (per OQ-02) 仅作为 retry 间等待，不是终态。Exhausted path 最终转入 needs_respawn，cooldown 不当作最终修复手段。
