---
sprint_id: sprint-20260508-data-plane-closeout
title: Solar Data Plane Closeout
priority: P1
lane: reliability
owner: planner
created_at: 2026-05-08T08:45:00Z
status: contract_ready
handoff_to: planner
---

# Sprint Contract — Solar Data Plane Closeout

## Intent

Close the remaining gaps in Solar's data infrastructure so the system is not just "rich in components" but operationally complete:

1. `solar-harness` runtime, bridge ledger, status server, Obsidian/wiki sync, and `~/.solar/solar.db` must agree on the same truth.
2. `solar` CLI must stop being an isolated local-flow toy and either connect into the shared data plane or be explicitly downgraded/documented as separate.
3. data freshness, lock contention, malformed state rows, and dead tables/views must become visible and repairable.

This sprint is about **closing broken joins** between existing systems, not rebuilding the architecture.

## Current Evidence

- `solar-harness` is actively running in tmux with live `coordinator.sh` and `coordinator-watchdog.sh`.
- `~/.solar/codex-bridge/bridge-ledger.jsonl` contains fresh 2026-05-08 reviewed events, proving the harness workflow is actually used.
- `~/.solar/harness/sprints/` contains fresh PRD / contract / design / plan / handoff / eval / events artifacts on 2026-05-08.
- `~/.solar/solar.db` is large and broad, but some core data is stale:
  - `sys_data_ledger.last_checked` is still 2026-02-06.
  - `sys_resources.updated_at` latest is 2026-02-23.
  - `knowledge_records` latest is 2026-02-27.
  - `solar_kb_entries` latest is 2026-03-06.
  - `cortex_passages` latest is 2026-02-16.
- `state` table contains malformed JSON (`key=test_pragma value=test`), so state is not schema-clean.
- `sqlite3` already hit `database is locked`, so write/read concurrency is not fully controlled.
- `v_solar_resources` returns 99 resources, but `access_count=0` and `last_accessed_at IS NULL` for all checked rows, suggesting the resource layer exists but is not feeding actual retrieval telemetry.
- `solar` CLI currently shells into `/Users/sihaoli/.agents/skills/solar/scripts/run.sh` and writes only local `.solar/flow-state.json`, not the shared Solar DB / harness control plane.
- `cortex_task_capsules` has only 1 row and `sys_capsule_executions` has 0 rows, so the capsule execution branch looks architecturally present but operationally dead.

## Non-Goals

- Do not redesign the entire database schema.
- Do not migrate away from SQLite in this sprint.
- Do not break current `solar-harness` production workflow in order to clean up abstractions.
- Do not silently delete historical data to "make metrics look healthy".

## Deliverables

1. **Data Plane Health Audit command**
   - Add a first-class command and/or script:
     - `solar-harness data-plane audit`
   - Must report:
     - freshness by critical table/view
     - malformed JSON rows
     - locked DB / busy timeout symptoms
     - stale ledgers/manifests
     - dead branches (tables/views with zero real executions)

2. **State Integrity Repair**
   - Add validation + repair path for `state` table malformed JSON.
   - Invalid rows must be surfaced, backed up, and repaired or quarantined.
   - No silent ignore.

3. **SQLite Concurrency Hardening**
   - Standardize DB open settings for all Solar/harness writers:
     - `busy_timeout`
     - WAL mode if safe for current workload
     - retry/backoff where needed
   - Add at least one regression test that simulates concurrent readers/writers.

4. **Runtime Usage Telemetry That Matches Reality**
   - Resource retrieval / context injection must update real access telemetry.
   - `v_solar_resources` or successor status view must stop showing an all-zero ghost layer if retrieval is active.
   - If the layer is not truly used, mark it dormant in status instead of pretending.

5. **`solar` CLI Integration Decision**
   - Choose one and implement/document clearly:
     - Option A: connect `solar start/status/stop` to shared Solar DB + harness status plane
     - Option B: declare `solar` as local lightweight flow only, and expose that status clearly so users do not confuse it with `solar-harness`
   - Current ambiguous middle state is not acceptable.

6. **Accepted/Passed Artifact Ingestion Hook-up**
   - Ensure accepted harness artifacts can actually reach searchable knowledge, not just stay in sprint files and wiki raw export.
   - If another active sprint already covers this, integrate with it rather than duplicating.

7. **Operator Runbook**
   - Add a short operational doc:
     - what is production truth
     - what is derived cache
     - how to audit freshness
     - how to repair malformed state
     - how to tell whether `solar` or `solar-harness` is the active runtime

## Acceptance Criteria

### A1 — Health Audit Is Concrete

Required:
- `solar-harness data-plane audit` prints a machine-parseable summary.
- Summary covers at least:
  - `state`
  - `sys_data_ledger`
  - `sys_resources` / `v_solar_resources`
  - `cortex_sources`
  - `cortex_passages`
  - `solar_kb_entries`
  - bridge ledger
  - sprint artifacts freshness

Verify:

```bash
solar-harness data-plane audit --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "checks" in d and "overall_status" in d'
```

### A2 — Malformed State Is Detectable And Repairable

Required:
- audit must flag invalid `state.value` JSON rows
- repair command must back up and fix or quarantine them
- post-repair `json_valid(value)=0` count is zero or explicitly quarantined out of hot path

Verify:

```bash
sqlite3 ~/.solar/solar.db "select count(*) from state where json_valid(value)=0;"
```

### A3 — DB Lock Risk Is Reduced

Required:
- common DB entry points use consistent busy timeout
- at least one concurrency test passes without `database is locked`
- docs explain any remaining lock caveats

Verify:

```bash
bash ~/.solar/harness/test-data-plane-db-concurrency.sh
```

### A4 — Resource Usage Telemetry Is Honest

Required:
- if retrieval is active, `last_accessed_at` and/or access counters move
- if retrieval is inactive, audit reports the layer as dormant/stale instead of healthy

Verify:

```bash
solar-harness data-plane audit --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "resource_usage" in d'
```

### A5 — `solar` And `solar-harness` Relationship Is Explicit

Required:
- user can run one command and know:
  - which runtime is active
  - whether `solar` writes shared state or local-only state
  - whether the two systems are bridged

Verify:

```bash
solar status
solar-harness status
```

### A6 — Accepted Knowledge Path Is Not A Dead End

Required:
- accepted sprint artifacts have an auditable path toward searchable knowledge
- if blocked by current P0/P1 sprint dependencies, audit must say so explicitly

Verify:

```bash
solar-harness data-plane audit --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "accepted_artifact_path" in d'
```

### A7 — Runbook Exists

Required:
- concise operator doc checked into harness docs
- includes repair and rollback steps

Verify:

```bash
test -f ~/.solar/harness/docs/data-plane-closeout.md
```

## Planner Instructions

1. Read this contract first, then inspect the live runtime before proposing refactors.
2. Keep one P0 mainline: **truth alignment between runtime, DB, and ledgers**.
3. Split implementation into 3 slices:
   - S1: audit + state integrity + DB concurrency
   - S2: resource usage telemetry + accepted artifact path
   - S3: `solar` vs `solar-harness` relationship + docs/status UX
4. Do not propose a rewrite-first plan. Prefer measurable closure of real gaps.
5. If a branch is effectively abandoned (`capsule executions`, stale ledgers, dead telemetry), either reconnect it or explicitly downgrade it in status/docs.

## Definition Of Done

- We can answer, from commands and status alone:
  - what is the source of truth
  - what is stale
  - what is actually used in production
  - what is dormant/dead
- malformed state rows are no longer silently sitting in the hot path
- SQLite lock risk is reduced and tested
- `solar` is no longer ambiguously half-integrated
- accepted harness outputs no longer end at raw artifacts with no observable knowledge ingestion path
