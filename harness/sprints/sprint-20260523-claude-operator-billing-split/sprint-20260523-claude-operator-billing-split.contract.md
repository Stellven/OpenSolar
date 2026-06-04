# Contract: Claude Interactive vs Programmatic Physical Operator Split

Sprint: `sprint-20260523-claude-operator-billing-split`
Target repo: `/Users/lisihao/.solar/harness`

## Scope

Implement a first-class split between Claude interactive physical operators and Claude programmatic print/SDK operators, including registry schema, runtime detection, quota/billing-aware routing policy, status/bridge observability, and tests.

## Hard Constraints

- Do not kill, restart, or mutate existing user Claude panes.
- Do not print auth tokens, cookies, API keys, OAuth material, or raw credentials.
- Do not hard-code plan dollar amounts; make credit/budget configurable.
- Do not route low-value bulk/fanout/test work to Claude print reserve operators.
- Do not remove existing Claude operators until compatibility aliases are present.
- Do not disable the active `monitor-operatord-daemon-submit-production` sprint.

## Required Evidence

Each node handoff must include:

- live classification evidence from tmux/ps/wrapper inspection, with secrets scrubbed;
- files changed and why;
- tests run and summary;
- explicit note whether any real billing call was avoided;
- remaining risks.

## Done

The sprint is done only when:

- all graph nodes are passed;
- final report exists;
- `graph-scheduler ready` returns `ready=true`;
- status/bridge expose Claude `surface` and `billing_surface`.
