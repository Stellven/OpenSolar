# Operator Health Watchdog: Cooldown / Quota / Graph Recovery

Status: P0 requirement package
Owner: Solar Harness
Created: 2026-06-05
Source request: repeated live stalls caused by provider quota/cooldown failures, expired cooldowns, and DAG nodes left in dispatched/reviewing limbo.

## 1. Problem Statement

Solar-Harness already has partial mechanisms for quota/cooldown handling:

- `operator_flow_control.py` classifies rate-limit, quota, auth, and reset-time text.
- `operator_runtime.py` stores dynamic operator status and expires status files on read.
- `pm_dispatch.py prune-rate-limits` clears expired operator config blocks.
- `pm_dispatch.py fail` can release transient quota/cooldown builder/evaluator graph assignments.
- `quota_refresh.py` writes quota/capacity snapshots and recommends concurrency.
- `builder-pool-status` surfaces rate-limit blocks and available capacity.

The gap is that these parts are not composed into a single periodic, idempotent health loop. As a result, humans still need to notice that a failure was quota/cooldown, manually inspect PM records, manually check task_graph assignment state, and manually trigger drain/retry. That creates the recurring perception that tasks are "stuck" even when the real cause is expired cooldown, provider runout, stale lease, or a graph assignment that was not released.

## 2. Goal

Build an `operator-health-watchdog` that continuously reconciles operator capacity, cooldown expiry, PM failure records, graph assignments, and backlog draining.

The watchdog must turn provider quota/cooldown events into safe automatic recovery:

```text
provider failure / cooldown
  -> operator flow-control block
  -> expired block pruned
  -> PM failed transient task reconciled
  -> matching graph assignment released
  -> capacity snapshot refreshed
  -> eligible backlog safely drained
```

## 3. Non Goals

- Do not bypass real provider cooldowns before reset time.
- Do not retry business failures as quota failures.
- Do not overwrite user or worker artifacts.
- Do not mark tasks complete without required handoff/eval sidecars.
- Do not dispatch to Gemini/Antigravity as a recovery fallback unless policy explicitly allows it.
- Do not change model selection semantics except through explicit policy knobs.

## 4. Watchdog Loop Contract

Add a command:

```bash
solar-harness operator-health-watchdog run --once --json
solar-harness operator-health-watchdog run --loop --interval 120
solar-harness operator-health-watchdog install-launchagent
solar-harness operator-health-watchdog status --json
```

Each loop must run these phases under a single file lock:

1. `prune_expired_blocks`
   - Clear expired `quota_guard_state`, `quota_refresh_at`, `state.runtime_state=cooldown|quota_exhausted|auth_expired`, and dynamic operator status files.
   - Preserve active non-expired blocks.

2. `refresh_capacity_snapshot`
   - Run `quota_refresh.py --json --apply`.
   - Recompute builder/evaluator/planner capacity.

3. `reconcile_pm_failures`
   - Scan recent PM records with `failed`, `failed_submit_exception`, `failed_no_dispatchable_operator`, `failed_contract_closeout`, and failure text matching transient operator failure.
   - For transient provider failures only, release the matching graph dispatch/eval assignment if and only if `task_id` matches graph assignment.
   - Record `graph_requeue` or `graph_eval_requeue`.

4. `reconcile_stale_leases`
   - Release leases with dead PID or expired lease TTL.
   - Do not release active PID leases.

5. `repair_status_projection`
   - If PM record says submitted/running but operator result says quota/cooldown failed, call the safe PM failure path.
   - If builder handoff exists and graph is still dispatched for the same task, move node to reviewing.
   - If evaluator eval sidecar exists and graph assignment is still active, clear eval assignment and surface for closeout.

6. `drain_if_capacity_available`
   - If available builder/planner/evaluator capacity exists, trigger existing safe drain paths.
   - Respect role policy and provider preference:
     - planner/prd: Opus/GPT-5.5 preferred.
     - builder: GPT-5.5/Spark preferred.
     - evaluator/gate fixture: Opus or low-risk deepseek-v4-pro if policy allows.
     - Gemini/Antigravity minimum.

7. `write_health_report`
   - Write JSON report and append JSONL history.
   - Include actions taken, skipped reasons, blockers, next retry times, and backlog deltas.

## 5. Required Artifacts

```text
~/.solar/harness/run/operator-health-watchdog/latest.json
~/.solar/harness/run/operator-health-watchdog/history.jsonl
~/.solar/harness/run/operator-health-watchdog/lock
~/.solar/harness/logs/operator-health-watchdog.out.log
~/.solar/harness/logs/operator-health-watchdog.err.log
```

## 6. Idempotency Rules

- Every action must carry an idempotency key:
  - `operator_id + expires_at` for cooldown prune.
  - `task_id + graph_path + node_id` for graph requeue.
  - `lease_id + operator_id` for lease release.
  - `sprint_id + node_id + role` for dispatch attempts.
- Re-running the watchdog must not double-dispatch the same node.
- Re-running must not clear a newly refreshed cooldown with a later `expires_at`.
- Re-running must not release an assignment whose `dispatch_id` no longer matches the failed PM task.

## 7. Safety Gates

The watchdog may auto-apply only these safe actions:

- Clear expired cooldown/auth/quota blocks.
- Release stale dead-PID leases.
- Release graph assignments for transient provider failures with exact dispatch id match.
- Move builder node from `dispatched` to `reviewing` only when required handoff exists and exact PM task id matches.
- Trigger existing `drain-builder-ready` and planner/evaluator submit paths only if existing duplicate checks pass.

The watchdog must not auto-apply:

- Business failure retries without explicit repair task.
- Eval verdict changes.
- Completion status changes without sidecars.
- Destructive git or file operations.

## 8. Status Surface

`builder-pool-status --json` and status UI must surface:

```json
{
  "operator_health_watchdog": {
    "installed": true,
    "launchd_loaded": true,
    "last_run_at": "...",
    "last_exit_code": 0,
    "last_actions": {
      "expired_blocks_pruned": 3,
      "pm_failures_reconciled": 2,
      "graph_nodes_released": 2,
      "stale_leases_released": 1,
      "drain_submitted": 4
    },
    "blockers": [
      "spark cooldown until 2026-06-05T01:25:00Z",
      "thunderomlx health_check_failed: Unauthorized"
    ]
  }
}
```

## 9. Acceptance Criteria

P0 acceptance:

- A synthetic expired cooldown block is cleared by `operator-health-watchdog run --once`.
- A non-expired cooldown block is not cleared.
- A PM record failed with quota/cooldown releases the matching builder graph node back to `pending`.
- A PM evaluator record failed with quota/cooldown clears the matching `eval_dispatch_id/eval_assignments`.
- A failed PM record with business failure text does not release graph assignment.
- A stale lease with dead PID is released; active PID lease is preserved.
- Watchdog writes latest.json/history.jsonl.
- `builder-pool-status --json` includes watchdog status.
- The loop can be run twice without duplicate dispatch/requeue.

P1 acceptance:

- LaunchAgent install/status works.
- Watchdog integrates with quota_refresh and dynamic concurrency.
- Watchdog can safely submit eligible drain work when capacity becomes available.

## 10. Test Plan

Add tests:

- `test_watchdog_prunes_expired_cooldown`
- `test_watchdog_preserves_future_cooldown`
- `test_watchdog_requeues_transient_builder_failure`
- `test_watchdog_releases_transient_evaluator_assignment`
- `test_watchdog_ignores_business_failure`
- `test_watchdog_releases_dead_pid_lease`
- `test_watchdog_idempotent_second_run`
- `test_builder_pool_status_surfaces_watchdog_status`

Run:

```bash
python3 -m pytest -q harness/tests/test_operator_health_watchdog.py harness/tests/test_pm_dispatch.py
python3 -m py_compile harness/tools/operator_health_watchdog.py harness/tools/pm_dispatch.py
```

## 11. Dispatch Guidance

Recommended split:

- S01 requirements/architecture: finalize watchdog loop contract, state model, and safety gates.
- S02 core runtime: implement `operator_health_watchdog.py`.
- S03 orchestration/status: LaunchAgent, `solar-harness` command, status UI and builder-pool-status surface.
- S04 verification-release: idempotency, synthetic fixtures, live dry-run proof.

Preferred routing:

- Planner: Opus/GPT-5.5.
- Builder: GPT-5.5/Spark.
- Evaluator: Opus or deepseek-v4-pro for low-risk fixture review.

Do not use:

- Gemini/Antigravity as primary implementation route.
- Deepseek as primary complex builder.

## 12. Product Principle

Cooldown/rate-runout should be a normal runtime state, not a human debugging event. If a provider says "try again later", Solar must know when later arrives, clear the block, release stale graph assignments, and resume safe dispatch automatically.
