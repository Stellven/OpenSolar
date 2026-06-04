# Contract: Operatord Daemon + Submit Production Cutover

Sprint: `sprint-20260522-operatord-daemon-submit-production`
Target repo: `/Users/lisihao/.solar/harness`
Mode: `solar-harness multi-task`

## Scope

Implement the next production step after `sprint-20260522-operatord-runtime-submit`: persistent operatord daemon, submit-path production routing, unified persona resolver, and bridge observability.

## Hard Constraints

- Do not kill existing user processes.
- Do not delete task directories.
- Do not print secrets or tokens.
- Do not re-enable unsafe ThunderOMLX cache features.
- Do not remove legacy dispatch until a tested feature flag/fallback exists.
- Do not make DAG nodes depend on concrete model names; route through task type, required capabilities, and operator classes.
- Do not use real external API calls in automated tests.

## Required Evidence

Each node handoff must include:

- files changed;
- commands run;
- test output summary;
- any skipped verification with reason;
- safety checks for secrets and direct `tmux send-keys`;
- next action.

Final report must include:

- node-by-node acceptance;
- test matrix;
- smoke evidence;
- remaining migration gaps;
- exact artifact paths.

## Done

The sprint is complete only when:

- all graph nodes are `passed`;
- `graph-scheduler ready` returns `ready=true`;
- final report exists;
- no open failed nodes remain.
