# Contract: Lease-based Model Fleet Runtime

Sprint: `sprint-20260523-lease-based-model-fleet-runtime`
Target repo: `/Users/lisihao/.solar/harness`

## Scope

Design and implement the next abstraction layer above tmux panes: a lease-based `AgentActor` runtime where DAG scheduling targets actors, while tmux panes and other environments are only `ActorHost` carriers.

## Hard Constraints

- Keep tmux support; do not remove current working pane execution.
- DAG/scheduler code must not directly call `tmux send-keys`.
- `tmux send-keys` may only bootstrap `operatord run <actor_id>`; it must never carry task payloads or natural-language instructions.
- The primary task protocol must be machine-readable mailbox/queue based. P0 uses file mailbox; socket/SQLite are later-compatible transports.
- Do not use tmux pane index as a durable scheduler key.
- Do not use `idle/running` display state as scheduling authority; lease ownership and heartbeat state are authoritative.
- Every schedulable actor must have separate `capability_profile`, `risk_profile`, and `cost_profile`.
- DAG nodes must reference `logical_operator`; direct physical actor/operator/model ids are compatibility-only and must be linted/deprecated.
- The runtime must map `logical_operator -> candidate AgentActors` through data bindings, not hard-coded model names.
- Physical actor selection must use an explainable `OperatorScore`, not manual ordering alone.
- Runtime policy must enforce risk/cost gates before acquiring a lease; prompts alone are not sufficient.
- Critical DAG completion must require patch/artifact evidence, test or benchmark evidence, and independent verifier decision.
- Writer and verifier must not be the same actor; high-risk tasks should prefer cross-provider verification.
- Premium/high-effort actors must be reserved for high-value task classes and blocked from low-value batch work.
- Do not kill or restart existing panes during this sprint unless a later user explicitly approves.
- Do not print secrets, API keys, OAuth tokens, cookies, or raw provider credentials.
- Preserve compatibility aliases for existing physical operator ids.
- Do not block or rewrite the currently active `operatord-daemon-submit-production` and `claude-operator-billing-split` sprints.

## Required Evidence

Each node handoff must include:

- files changed;
- tests run and result;
- compatibility impact;
- whether tmux pane identity is used only as host metadata;
- proof that task payloads enter through mailbox/queue, not terminal keystrokes;
- proof that lease state includes owner, TTL, heartbeat timeout, renewability, and failure state;
- proof that capability/risk/cost profiles are schema-validated and used by routing tests;
- proof that all 16 P0 logical operator types are schema-validated and mapped to bindings;
- proof that changing a binding changes physical actor selection without changing the DAG node;
- proof that OperatorScore includes HistoricalSuccess and can be updated from local task evidence;
- proof that verifier decision files are machine-readable and gate DONE/PASS transitions;
- proof that policy blocks destructive actions, secret access, git push, payment/external actions, and unauthorized writes;
- evidence that secrets were not printed;
- remaining migration risk.

## Done

The sprint is done only when:

- all graph nodes are passed;
- final report exists;
- actor/host schema validates fixtures;
- actor lease submit path is covered by tests;
- file mailbox P0 path is covered by tests;
- stale lease and heartbeat timeout behavior is covered by tests;
- profile-aware selection and denial behavior is covered by tests;
- logical-operator selection and binding fallback behavior is covered by tests;
- operator scoring and penalty behavior is covered by tests;
- verifier-required DAG closure behavior is covered by tests;
- status/bridge expose actor/host/lease fields;
- no-direct-tmux-send-keys lint still passes.
