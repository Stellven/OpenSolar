# PRD: Lease-based Model Fleet Runtime

Sprint: `sprint-20260523-lease-based-model-fleet-runtime`
Priority: P0
Target: Mac mini `/Users/lisihao/.solar/harness`

## Summary

Upgrade the current Pane-as-Physical-Operator design into a lease-based Agent Actor runtime.

The core shift:

```text
old: DAG -> tmux pane / physical operator
new: DAG -> AgentActor lease -> ActorHost
```

`tmux` remains a useful local long-running process host, but it must not be the scheduling endpoint or RPC protocol. Pane indexes and layouts can drift, process titles can be stale, and direct `tmux send-keys` is not a reliable control plane. The runtime must schedule typed Agent Actors with lease, state, capability, quota, policy, and evidence records, then bind each actor to an ActorHost such as tmux, Codex worktree, Antigravity managed environment, Claude Code session, local MLX process, SSH devbox, or sandbox container.

## Problem

The current operator design still leaks host details into scheduling decisions:

- tmux pane identity is treated as if it were stable enough to schedule directly;
- operator status mixes process/container state with logical actor state;
- quota, lease, policy, and evidence are not uniformly attached to the dispatch object;
- future hosts like Codex cloud worktrees or Antigravity managed environments cannot be represented cleanly;
- direct terminal control remains a recurring risk unless the runtime owns communication.

## Goal

Introduce first-class `AgentActor` and `ActorHost` abstractions:

```yaml
AgentActor:
  actor_id: actor.claude.opus47.architect.01
  operator_class: DeepArchitect
  host_id: host.tmux.solar-aiops.claude-arch.01
  lease:
    state: idle | leased | running | draining | cooldown | error
    lease_id: null
    ttl_sec: 2700
  capability:
    planning: 5
    coding: 4
    debugging: 5
    review: 5
    multimodal: false
  quota:
    billing_pool: anthropic_subscription_interactive
    reserve_for: [ARCH_DESIGN, ROOT_CAUSE_DEBUG, FINAL_REVIEW]
  policy:
    write_files: ask_or_patch_only
    secrets_access: denied
    network: restricted
  evidence:
    task_log_dir: run/agent-actors/<actor_id>/
    ledger_path: run/agent-actors/ledger.jsonl

ActorHost:
  host_id: host.tmux.solar-aiops.claude-arch.01
  host_type: tmux_pane
  lifecycle: created | warming | alive | degraded | offline
  address:
    session: solar-aiops
    window: claude_arch
    pane_id: "%12"
```

## Required Host Types

The first registry version must support these host types, even if some are initially stubbed:

- `tmux_pane`
- `codex_worktree`
- `codex_cloud`
- `antigravity_managed_env`
- `claude_code_session`
- `local_mlx_process`
- `ssh_devbox`
- `docker_sandbox`

## Requirements

### R1 AgentActor schema

Add schema/config support for:

- `actor_id`
- `operator_class`
- `host_id`
- `host_type`
- `lease`
- `capability_profile`
- `risk_profile`
- `cost_profile`
- `quota`
- `policy`
- `evidence`
- `fallback_ladder`
- `persona_binding`

No DAG node should need a raw tmux pane, raw model string, or raw CLI command to select an executor.

### R1a Three Profile Model

Every schedulable `AgentActor` must expose three separate profiles. A single vague `capability` object is not enough for safe automatic routing.

Capability profile:

```yaml
capability_profile:
  architecture_reasoning: 5
  code_impl: 4
  root_cause_debug: 5
  test_generation: 4
  test_execution: 3
  research_synthesis: 4
  academic_critique: 5
  browser_use: 2
  gui_use: 2
  long_context: 5
  multi_agent_coordination: 3
  speed: 3
```

Risk profile:

```yaml
risk_profile:
  allowed_write_scope: patch_only
  allowed_shell_scope: repo_local
  allowed_network: docs_only
  allowed_secrets: none
  destructive_actions: denied
  git_commit: denied
  git_push: denied
  payment_or_external_action: denied
  requires_human_for:
    - delete_files
    - modify_ci
    - change_auth
    - touch_secrets
```

Cost profile:

```yaml
cost_profile:
  cost_tier: premium
  token_budget_class: expensive
  quota_period: monthly
  reserve_ratio: 0.25
  effort: xhigh
  prefer_for:
    - ARCH_DESIGN
    - ROOT_CAUSE_DEBUG
    - FINAL_REVIEW
  avoid_for:
    - BULK_DOC_EDIT
    - TRIVIAL_RENAME
    - GREP_SCAN
```

Effort level is part of cost/routing policy, not an ad hoc runtime switch. Premium reasoning modes must be reserved for high-value nodes.

### R1b Logical Operator Type System

DAG nodes must reference logical operator types, not physical actor ids, model ids, tmux panes, or provider CLI names.

Wrong:

```yaml
operator: op.claude.opus47.architect.01
```

Right:

```yaml
logical_operator: DeepArchitect
```

P0 logical operator taxonomy:

| Logical Operator | Purpose | Default physical binding |
|---|---|---|
| `DeepArchitect` | architecture design, option analysis | Claude Opus 4.7 xhigh/max |
| `RootCauseDebugger` | root cause analysis, log reading | Claude Opus 4.7 xhigh |
| `ImplementationWorker` | multi-file implementation | Codex GPT-5.5 |
| `PatchWorker` | small patches | Codex mini / Gemini Flash |
| `TestDesigner` | unit/integration test design | Claude / Codex |
| `TestRunner` | run tests and collect logs | Codex / local shell |
| `BenchmarkRunner` | performance experiments | Codex / local |
| `ParallelExplorer` | parallel solution exploration | Antigravity / Codex subagents |
| `ResearchScout` | source search and evidence collection | Codex / Gemini Flash |
| `ResearchSynthesizer` | synthesis reports | GPT-5.5 / Claude |
| `Critic` | critique, rebuttal, review | Claude Opus |
| `Verifier` | independent verification | Claude + local check |
| `SecurityGate` | permission/security review | local rules + Claude |
| `QuotaBroker` | quota arbitration | local runtime |
| `ContextCompressor` | context compression | local / cheap model |
| `ArtifactCurator` | artifact organization | Codex / local |

Bindings are data, not DAG logic:

```yaml
bindings:
  ParallelExplorer:
    primary: actor.antigravity.gemini35flash.parallel.01
  DeepArchitect:
    candidates:
      - actor.claude.opus47.architect.01
      - actor.google.gemini35pro.architect.01
```

When models change, update bindings and actor profiles; do not rewrite DAGs.

### R2 ActorHost schema

Add host registry support for:

- stable `host_id`
- `host_type`
- host lifecycle state
- host address metadata
- heartbeat path
- attach/reconnect instructions
- host-specific health probes

For tmux, prefer stable pane IDs and actor heartbeat files over pane index. Pane index may be displayed, but it must not be the durable scheduler key.

### R3 Lease broker

Create a lease broker that grants a node a lease on an `AgentActor`, not directly on a host.

Required states:

```text
CREATED -> WARMING -> IDLE -> LEASED -> RUNNING -> DRAINING -> IDLE
ERROR | QUOTA_EXHAUSTED | AUTH_EXPIRED | COOLDOWN | DISABLED | STALE_CONTEXT | NEEDS_HUMAN_REVIEW
```

The broker must persist lease state, TTL, task id, sprint id, node id, actor id, and evidence path.

### R3a Profile-aware routing and policy gates

The actor selector must use all three profiles:

- `logical_operator` chooses the logical role class first.
- `capability_profile` decides whether an actor can do the task well enough.
- `risk_profile` decides whether the actor is allowed to take the task safely.
- `cost_profile` decides whether the task is valuable enough to spend the actor's model/quota budget.

An actor that passes capability but fails risk or cost constraints must not receive the lease. This is a runtime gate, not just a prompt instruction.

### R3b Operator Score

Physical actor selection must use a dynamic score after logical operator binding and profile gates:

```text
OperatorScore =
  TaskFit * 0.30
+ HistoricalSuccess * 0.20
+ FreshQuota * 0.15
+ LatencyFit * 0.10
+ ContextAffinity * 0.10
+ RiskFit * 0.10
+ CostFit * 0.05
- RecentFailurePenalty
- SameProviderVerifierPenalty
- StaleContextPenalty
```

Initial model/provider priors may come from official positioning, but `HistoricalSuccess` must be learned from Solar task evidence:

- success rate in FlashMLX;
- success rate in Solar-harness;
- Metal/debug reliability;
- long-document evidence quality;
- test-generation honesty;
- quota pressure behavior;
- review/verifier disagreement history.

The score must persist enough data to explain why an actor won or lost a lease.

### R3c Verification as DAG Structure

Critical DAGs must not let the writer self-certify completion. Required evidence classes:

1. Patch or artifact.
2. Test, benchmark, or validation evidence.
3. Independent verifier decision.

Verifier decisions must be machine-readable:

```yaml
decision: PASS_WITH_WARNINGS
confidence: 0.82
must_fix: []
should_fix:
  - "Add one regression test for empty expert set"
evidence:
  tests_passed: true
  benchmark_delta_verified: true
  no_secret_leak: true
  scope_ok: true
```

Rules:

- no verifier output, no DAG DONE;
- no test/benchmark evidence, no code-task PASS;
- writer and verifier cannot be the same actor/operator;
- high-risk tasks should prefer cross-provider verification.

### R4 Submit protocol boundary

DAG code must call:

```python
actor_runtime.submit(task_envelope)
```

It must not directly call `tmux send-keys`, Claude, Codex, Antigravity, or a provider-specific CLI.

The runtime may use tmux, SDK calls, or managed environments internally, but the DAG sees only actor leases and result artifacts.

### R4a No `tmux send-keys` as task protocol

`tmux send-keys` is permitted only for host bootstrap:

```bash
tmux send-keys -t solar:claude_arch.0 \
  'operatord run actor.claude.opus47.architect.01' C-m
```

After `operatord` is alive, no DAG node, scheduler, router, or task dispatcher may send natural-language task payloads directly into a pane. The primary task channel must be a machine-readable queue:

```text
~/.solar/operators/<actor_id>/
  inbox/
    task-0001.yaml
  outbox/
    task-0001.result.yaml
  logs/
    task-0001.stdout.log
    task-0001.stderr.log
  state.json
  heartbeat.json
```

P0 should implement a file mailbox first. Unix socket or SQLite queue can be later host transports, but they must preserve the same `task_envelope -> result.json -> evidence ledger` contract.

### R5 Evidence ledger

Every actor execution must emit:

- task envelope snapshot with secrets scrubbed;
- lease grant/release events;
- host heartbeat evidence;
- stdout/stderr or equivalent provider output with secret scrub;
- result artifact path;
- verifier decision when present.

### R5a Lease is the source of truth

The runtime must not decide availability from `idle/running` text alone. Availability is derived from lease ownership and heartbeat state:

```yaml
lease:
  lease_id: lease-20260522-173001-opus47-001
  task_id: dag-017-node-03
  actor_id: actor.claude.opus47.architect.01
  acquired_at: "2026-05-22T17:30:01-04:00"
  expires_at: "2026-05-22T18:10:01-04:00"
  renewable: true
  preemptible: false
  heartbeat_timeout_sec: 90
```

The canonical state machine for actors is:

```text
UNREGISTERED -> BOOTING -> READY -> LEASED -> RUNNING -> FINALIZING -> READY

exception states:
  STALE
  QUOTA_BLOCKED
  AUTH_BLOCKED
  POLICY_BLOCKED
  HUMAN_REQUIRED
  CRASHED
  DRAINING
  DISABLED
```

The older `idle/running` labels may remain as display summaries, but they are not scheduling authority.

### R6 Compatibility migration

Existing `physical-operators.json` and previous Pane-as-Physical-Operator config must remain loadable through compatibility adapters. The migration must be additive first:

- current operators become `AgentActor` entries;
- current pane metadata becomes `ActorHost` entries;
- old operator ids become aliases;
- status output shows both old operator id and new actor id during transition.

## Non-goals

- Do not remove existing tmux-based execution.
- Do not rewrite every provider adapter in one sprint.
- Do not enable direct tmux send-keys from DAG code.
- Do not print secrets or raw credentials.
- Do not force cloud-host support to be fully functional in P0; schema + stub probe is enough.

## Acceptance

- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/lease-based-model-fleet-runtime.md`.
- Docs define `AgentActor`, `ActorHost`, lease state machine, and migration rules.
- Schema/config supports actor and host registries.
- Runtime can lease an actor and submit a task envelope without exposing tmux as scheduler endpoint.
- Tests prove tmux pane index is not the durable key.
- Tests prove `tmux send-keys` is used only for bootstrap and never for task payloads.
- Tests prove a stale lease can be detected and released/degraded without relying on pane text.
- Tests prove risk profile denies destructive, external-payment, secret-touching, git-push, and out-of-scope writes before dispatch.
- Tests prove cost profile reserves premium/high-effort actors for high-value task types and avoids low-value batch work.
- Tests prove DAG nodes can select by `logical_operator` and bindings can change physical actors without changing the DAG.
- Tests prove `OperatorScore` uses historical success, quota, latency, context, risk, cost, and penalties with explainable output.
- Tests prove critical DAGs require patch/artifact, test/benchmark evidence, and independent machine-readable verifier decision before DONE.
- Status/bridge output includes `actor_id`, `host_id`, `host_type`, `lease_state`, `quota/billing_pool`, and evidence path.

## Source Notes

- User design input treats tmux as a long-running local process container, not an RPC/control plane.
- Existing Solar direction already includes `operator_runtime.submit`, `operatord` daemon, no-direct-tmux-send-keys lint, persona binding, and physical operator registry work.
- Official source verification for tmux pane stability and managed-agent host claims should be captured in N1 before implementation.
