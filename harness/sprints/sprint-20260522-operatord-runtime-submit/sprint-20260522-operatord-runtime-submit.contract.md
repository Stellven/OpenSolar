# Contract: Operatord Runtime Submit Foundation

Sprint: `sprint-20260522-operatord-runtime-submit`

## Execution Rules

- Work on Mac mini under `/Users/lisihao/.solar/harness`.
- Preserve existing multi-task behavior.
- Do not kill panes or delete task directories.
- Do not leak secrets.
- Do not make `operatord` the default path until tests pass.
- Use a safe local/dummy operator for submit smoke unless a real operator is explicitly verified as safe.

## Deliverables

### Code

- Persona bank binding:
  - validate `personas/pm.md`
  - validate `personas/planner.md`
  - validate `personas/builder.md`
  - validate `personas/evaluator.md`
  - validate `personas/architect.md`
  - validate `personas/evaluator-verification-protocol.md`
  - validate `personas/lab-builder.md`
  - validate `personas/lab-evaluator.md`
  - validate `personas/observer.md`
  - validate `personas/second-builder.md`
  - add helper to resolve an operator's `persona` to a file path.
  - `operatord` must load the persona file and include it in task context.
  - evaluator operators should also load `evaluator-verification-protocol.md`.
- `lib/operator_runtime.py`
  - add `submit(task_envelope)` or a small companion module if cleaner.
  - add envelope validation, lease acquisition, inbox write, and result metadata.
- `tools/operatord.py` or equivalent CLI module.
  - implement `run <operator_id>` and heartbeat/inbox processing foundation.
- `tools/operator_naming.py` or equivalent helper.
  - canonical id parsing/validation.
  - pane title canonicalization.
- CLI wiring in `solar-harness.sh` / command router, following existing project conventions.
- Lint or test helper for direct `tmux send-keys` usage.

### Tests

- Unit tests for submit success and rejection cases.
- Unit tests for persona binding resolution and missing-persona blocker.
- Unit tests for canonical pane titles.
- Unit tests for lint gate.
- Smoke test for `solar-harness operatord run --help`.
- Smoke test for `solar-harness operator-runtime submit ...` or equivalent.

### Report

- `/Users/lisihao/.solar/harness/monitor-reports/operatord-runtime-submit.md`

## Required Safety

- No raw `secret_ref` resolved value in logs.
- Existing `mini-*` aliases continue to work.
- Canonical `op.*` ids are supported or validated as target ids.
- Operators without valid persona binding are not silently dispatched.
- Direct `tmux send-keys` is not used for normal DAG dispatch in new code.

## Done Definition

Every node must write handoff with:

- Changed files.
- Verification commands.
- Acceptance status.
- Remaining gaps.
- Next action.
