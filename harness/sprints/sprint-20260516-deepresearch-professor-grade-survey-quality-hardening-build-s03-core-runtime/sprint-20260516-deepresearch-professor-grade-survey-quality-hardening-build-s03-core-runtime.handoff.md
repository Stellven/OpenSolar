# Handoff — sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s03-core-runtime

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s03-core-runtime`
Parent epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Status intent: core runtime package slice ready for S04 wiring, not an epic completion claim.

## Implementation Checklist D1-D7

| ID | Slice | Delivered package surface | Tests |
|----|-------|---------------------------|-------|
| D1 | schemas | Append-only survey quality dataclasses in `lib/research/survey/schemas.py`; existing dataclasses preserved | N1: 19 passed |
| D2 | gate registry | Pluggable `survey/gates/` registry, decorator, config defaults, duplicate/missing behavior | N2: 6 passed |
| D3 | source quality gate | `source_quality_distribution.py` with distribution and stuffing alert gate | N3: 12 passed |
| D4 | argument density gate | `argument_density.py` with five detector dimensions and applicability mapping | N4: 19 passed |
| D5 | controversy matrix gate | `controversy_matrix.py` with contradiction matrix, synthesis reference check, decorative-matrix detection | N5: 18 passed |
| D6 | exploration package | `survey/explorer/` package with deterministic scoring, elimination run, and JSONL log writer | N6: 28 passed |
| D7 | gate report/global hook | `compile_gate_report.py`, `global_consistency_pass.py`, and attach-style `runner_hook.py` | N7: 14 passed |

## S04 Cut-In Checklist

| Identifier | Required S04 action |
|------------|---------------------|
| s04_cli_gate_report_path | Add CLI/runtime field for emitted `gate_report.json` path |
| s04_cli_source_quality_verdict | Surface `gate_verdicts.source_quality.verdict` |
| s04_cli_argument_density_verdict | Surface `gate_verdicts.argument_density.verdict` |
| s04_cli_controversy_matrix_verdict | Surface `gate_verdicts.controversy_matrix.verdict` |
| s04_cli_exploration_log_verdict | Surface `gate_verdicts.exploration_log.verdict` and missing-plugin degradation |
| s04_cli_partial_verdicts | Surface `partial_verdicts` so degraded gate coverage is visible |
| s04_runner_attach_hook | Wire `attach_to_survey_continue(runner)` without editing frozen runner entrypoints |

## S05 Cut-In Checklist

| Identifier | Required S05 evidence |
|------------|----------------------|
| s05_e2e_fixture_full_gate_chain | End-to-end fixture producing source quality, argument density, controversy matrix, exploration log, and final gate report |
| s05_verdict_chain_trace | Verify per-gate verdicts propagate into `GateReport` and CLI/status output |
| s05_regression_no_frozen_rewrite | Verify frozen five survey modules and frozen harness runtime files were not rewritten |
| s05_determinism_scan | Verify no random, wall-clock, network, or mock-only behavior in S03 runtime paths |

## Runtime Flags

```yaml
s04_can_start: true
s05_blocked_until: [s04_passed]
epic_complete: false
s04_plus_ready_claimed: false
e2e_verified: false
```

## Verification Summary

| Node | Command summary | Result |
|------|-----------------|--------|
| N1 | `python3 -m pytest tests/research/survey/test_schemas.py -q` | 19 passed |
| N2 | `python3 -m pytest tests/research/survey/gates/test_registry.py -q` | 6 passed |
| N3 | `python3 -m pytest tests/research/survey/gates/test_source_quality_distribution.py -q` | 12 passed |
| N4 | `python3 -m pytest tests/research/survey/gates/test_argument_density.py -q` | 19 passed |
| N5 | `python3 -m pytest tests/research/survey/gates/test_controversy_matrix.py -q` | 18 passed |
| N6 | `python3 -m pytest tests/research/survey/explorer/ -q` | 28 passed |
| N7 | `python3 -m pytest tests/research/survey/gates/test_compile_gate_report.py tests/research/survey/gates/test_global_consistency_pass.py tests/research/survey/test_runner_hook.py -q` | 14 passed |

## Known Open Loops

- S04 must wire these packages into the survey-continue orchestration/UI path; S03 only supplies pluggable runtime packages and attach hook.
- S05 must perform end-to-end fixture verification; this handoff does not claim e2e verification.
- `exploration_log` is represented as a GateReport slot and degraded through `partial_verdicts`; S04/S05 must decide whether to register a dedicated gate plugin or consume N6 log artifacts directly.
- Existing evaluator pane availability remained degraded during S03; local-equivalent eval artifacts were used where no live evaluator was available.
- N2 introduced `tests/conftest.py` to work around the pre-existing `research.evaluator` import chain in tests; this is a test-scope support file and should be reviewed in S05 scope checks.

## Scope Boundary

- New functionality stays inside `lib/research/survey/gates/**`, `lib/research/survey/explorer/**`, append-only `lib/research/survey/schemas.py`, and `lib/research/survey/runner_hook.py`.
- Frozen survey modules were not intentionally rewritten: `source_authority`, `literature_mapping`, `controversy`, `chapter_review`, `chief_editor`.
- Frozen harness runtime files were not intentionally rewritten: coordinator, autopilot, dispatcher, phase-state-machine, `solar-harness`, and `survey/__init__.py`.
