# PRD: Operatord Runtime Submit Foundation

Sprint: `sprint-20260522-operatord-runtime-submit`
Priority: P0
Owner host: `lisihao@100.122.223.55`

## Background

The Model Fleet Operator Runtime now has a registry, selector, quota-aware fallback policy, and monitor bridge visibility. The next gap is the physical execution layer: panes still behave like ad hoc task runners. The target architecture requires every physical operator pane to run the same daemon shell:

```text
operatord run <operator_id>
```

Normal DAG execution must submit structured task envelopes through runtime APIs, not directly send instructions to tmux panes.

## Goals

1. Implement a first-version `operatord` CLI for running physical operator panes.
2. Add `operator_runtime.submit(task)` or equivalent API to create task envelopes, acquire leases, and route tasks to an operator-owned inbox.
3. Add canonical pane-title generation and application for tmux operators.
4. Add a lint/test gate that prevents normal DAG nodes from using direct `tmux send-keys` dispatch.
5. Preserve existing `solar-harness multi-task` behavior while adding the new runtime path as a safe foundation.

## Non-Goals

- Do not migrate every active pane to `operatord` in this sprint.
- Do not kill existing tmux panes.
- Do not print or persist raw API keys, OAuth tokens, or cookies.
- Do not globally install packages.
- Do not re-enable unsafe ThunderOMLX cache features.

## Required Interfaces

### Persona Bank Binding

Every physical operator must bind to the local persona bank under `personas/`. The binding is part of the operator contract, not just display metadata.

Required persona files:

```text
┌────────────────────────────────────────────┬────────────────────────────────────────────┐
│ Persona                                    │ Responsibility                             │
├────────────────────────────────────────────┼────────────────────────────────────────────┤
│ personas/pm.md                             │ Product brief, scope, clarification         │
│ personas/planner.md                        │ Task graph decomposition and dependencies   │
│ personas/builder.md                        │ Real code/test implementation               │
│ personas/evaluator.md                      │ Contract done-list validation and red-team   │
│ personas/architect.md                      │ Second-stage architecture/final gate         │
│ personas/evaluator-verification-protocol.md│ Executor verification protocol               │
│ personas/lab-builder.md                    │ Experimental implementation                 │
│ personas/lab-evaluator.md                  │ Experimental validation                     │
│ personas/observer.md                       │ Static observation and log recording         │
│ personas/second-builder.md                 │ Backup or parallel implementation           │
└────────────────────────────────────────────┴────────────────────────────────────────────┘
```

Required behavior:

- `physical-operators.json` entries must include `persona` or a canonical persona binding.
- `operatord run <operator_id>` must load the referenced persona file and include it in the task envelope context.
- Missing persona files must make the operator `needs_human_review` or not dispatchable.
- The evaluator role must also load `evaluator-verification-protocol.md` when present.
- Bridge/status output must expose persona binding so a human can see not only the model, but the working role contract.

### Canonical Operator ID

```text
op.<surface>.<provider>.<model>.<role>.<config>.<index>
```

### Pane Title

```text
[CLAUDE][OPUS47][ARCH][XHIGH][01]
[CODEX][GPT55][IMPL][01]
[AG][G35FLASH][PAR][03]
[LOCAL][MLX][SCAN][01]
```

### Operator Daemon

```text
solar-harness operatord run <operator_id>
```

Minimum daemon responsibilities:

- Read operator registry.
- Resolve `secret_ref` without logging raw secrets.
- Set canonical pane title when running under tmux.
- Write heartbeat/state files.
- Receive task envelope files from an operator inbox.
- Launch the configured backend command in dry-run/smoke mode or real mode when explicitly permitted.
- Capture stdout/stderr into execution logs.
- Parse quota/auth/runtime errors into structured status.
- Write a structured task result.

### Runtime Submit API

Python API:

```python
operator_runtime.submit(task_envelope: dict) -> dict
```

CLI:

```text
solar-harness operator-runtime submit --operator <operator_id> --task-envelope <path>
```

Submit must:

- Validate envelope shape.
- Validate operator availability.
- Acquire lease.
- Write envelope to operator inbox.
- Return task id, operator id, lease id, inbox path, and status.

### Task Envelope

```yaml
task_id: dag-20260522-node-03
sprint_id: sprint-...
node_id: N3
task_type: CODE_IMPL
objective: Implement operator runtime submit.
constraints:
  write_files: true
  run_tests: true
  git_commit: false
output_contract:
  required_artifacts:
    - execution_summary.md
    - result.json
verifier:
  required: true
  cannot_use_same_operator: true
```

## Acceptance Criteria

- `solar-harness operatord run --help` or equivalent CLI exists.
- `operator_runtime.submit(task)` exists and has unit tests.
- Submit rejects disabled, leased, running, quota-exhausted, auth-expired, and unknown operators.
- Submit writes a task envelope to a deterministic operator inbox path.
- Pane title canonicalizer maps registry/model aliases to `[PROVIDER][MODEL][ROLE][CONFIG][INDEX]`.
- Tmux title apply is no-op outside tmux and safe inside tmux.
- Lint/test gate finds direct `tmux send-keys` in normal DAG dispatch code and allows only approved tmux adapter/startup code.
- No raw secrets are logged.
- Persona bank binding is validated for pm/planner/builder/evaluator/architect/lab-builder/lab-evaluator/observer/second-builder and evaluator verification protocol.
- Operatord loads the persona file for the selected operator or reports a structured blocker.
- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/operatord-runtime-submit.md`.

## Evidence Required

- Changed files.
- Unit test commands and results.
- Submit smoke with a safe local/dummy operator.
- Pane title canonicalizer examples.
- Lint gate result.
- Remaining gaps for full pane migration.
