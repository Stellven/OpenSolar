# PRD: Operatord Daemon + Submit Production Cutover

Sprint: `sprint-20260522-operatord-daemon-submit-production`
Priority: P0
Owner: solar-harness control-plane
Target: Mac mini `/Users/lisihao/.solar/harness`

## Background

The previous sprint `sprint-20260522-operatord-runtime-submit` passed as an MVP foundation. It delivered `operator_runtime.submit`, `operatord` bootstrap, pane naming tests, persona bank coverage, and a no-direct-`tmux send-keys` lint gate. Its acceptance report explicitly left production migration gaps:

- G1: `operatord` is one-shot bootstrap, not a persistent daemon.
- G5: `multi_task_runner.py` does not route production dispatch through `operator_runtime.submit`.
- G2: persona resolution diverges between `submit()` and `operatord`.
- G3/G8: pane title and bridge status do not yet expose the canonical operator/persona runtime state.

This sprint turns the MVP into a production path while preserving rollback safety.

## Goal

Make `Pane-as-Physical-Operator` usable by real multi-task execution:

1. `operatord run <operator_id>` stays alive, heartbeats, polls inbox, leases tasks, executes task envelopes, writes results, and transitions state.
2. `multi_task_runner.py` can submit DAG nodes through `operator_runtime.submit` instead of directly injecting work into panes.
3. persona resolution is unified across submit, operatord, status, and tests.
4. bridge/status output shows the active operator, persona, lifecycle state, and last task evidence.

## Non-goals

- Do not remove all legacy direct pane dispatch in this sprint; keep an explicit feature flag or compatibility fallback.
- Do not introduce raw secrets into registry, inbox, stdout, stderr, logs, handoff, or reports.
- Do not enable unsafe ThunderOMLX cache features.
- Do not require Codex/Antigravity/Claude credentials to run tests; use fixtures and dummy/local operators for automated tests.

## Requirements

### R1 Persistent operatord daemon

`tools/operatord.py run --operator <id>` must support a persistent mode that:

- loads the physical operator registry and shared persona resolver;
- writes heartbeat/status under `run/operator-status/<operator_id>.json`;
- polls `run/operator-inbox/<operator_id>/*.json`;
- atomically claims one envelope at a time;
- transitions `idle -> leased -> running -> draining -> idle` or an explicit error state;
- writes task result artifacts under `run/operator-results/<operator_id>/<task_id>/`;
- records stdout/stderr tail with secret scrubbing;
- exits cleanly on `--once`, `--max-tasks`, or signal.

### R2 Production submit path

`multi_task_runner.py` must gain a controlled path that:

- builds a structured task envelope from a DAG node;
- selects a logical physical operator via existing task type/capability routing;
- calls `operator_runtime.submit`;
- records the returned inbox path, lease id, operator id, and state in task `status.json`;
- waits for an operator result when configured;
- falls back to legacy dispatch only if the feature flag says so or submit is unavailable.

### R3 Unified persona resolution

Create or consolidate a single resolver used by `submit()`, `operatord`, and status rendering:

- if `persona` is set, it is authoritative;
- otherwise derive from `role`;
- verify the persona file exists in `personas/`;
- evaluator operators must load `evaluator-verification-protocol.md`;
- tests must cover `persona != role`, missing persona, role fallback, and evaluator protocol loading.

### R4 Operator state observability

Bridge/status must expose, at minimum:

- `operator_id`
- provider/vendor
- model alias or configured model
- role
- resolved persona
- lifecycle state
- task id / sprint id / node id
- last heartbeat
- last result status
- quota/auth disabled reason if present

### R5 Safety and regression gates

- no-direct-`tmux send-keys` lint gate must fail if new production control-plane files add direct pane injection;
- no raw secret pattern may appear in new/changed artifacts;
- tests must run without hitting real model APIs;
- all write scopes must be listed in the handoff.

## Acceptance Criteria

- `python3 -m pytest tests/runtime/test_operator_runtime.py tests/test_operatord_daemon.py tests/test_operator_naming.py tests/test_no_direct_tmux_send_keys.py -v` passes.
- A dummy operator end-to-end smoke succeeds: submit envelope -> inbox -> operatord --once -> result artifact -> status transitions.
- A fake missing persona operator is rejected consistently by both submit and operatord.
- A DAG smoke can route one node through `operator_runtime.submit` without direct `tmux send-keys`.
- `solar-harness multi-task status --no-clear --renderer plain` includes operator/persona runtime fields.
- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/operatord-daemon-submit-production.md`.

## Risks

- The new submit path can strand tasks if lease/result timeouts are wrong.
- Long-running CLI tools may need backend-specific adapters, so the first production path should start with local/dummy and one verified CLI operator.
- Persona resolver changes can break existing implicit role behavior; tests must preserve backwards compatibility.

## Rollback

Keep legacy multi-task dispatch available behind a clearly named flag. If submit path fails, mark the affected node failed with evidence and leave legacy behavior untouched.
