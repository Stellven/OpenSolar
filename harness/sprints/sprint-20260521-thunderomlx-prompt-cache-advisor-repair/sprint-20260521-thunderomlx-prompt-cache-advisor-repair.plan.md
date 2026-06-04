# Plan — sprint-20260521-thunderomlx-prompt-cache-advisor-repair (Round-2 Closure)

## Mission
Close the genuinely-unverified PRD acceptance gaps left open by Round-1 (N1–N4) so the autopilot no longer reopens the sprint, and bring the on-disk task_graph status into agreement with the gate_results. Round-1 already delivered the code fixes (server pre-flight 422 guard, retry loop, advisor importlib isolation, four-pane prewarm task); Round-2 is exclusively about live evidence + status reconciliation + the chat/completions reuse contract decision the PRD explicitly demands.

## Why a Round-2 is needed
Three concrete gaps from the N4 handoff drive this round:

1. **Live-server HTTP regression never ran.** The `prompt-cache-save-regression.sh` script exists and unit tests pass offline, but the omlx server was never running at `127.0.0.1:8002` during N2/N4 — so Tests 1–3 in the script have no live HTTP evidence and "save/list/load for a long knowledge-extraction prompt" (PRD Acceptance #1) is still asserted only from synthetic numpy fixtures.
2. **chat/completions cache reuse contract is undecided.** PRD Acceptance #2 explicitly says "explains and verifies how a loaded named prompt cache is reused by inference, **or clearly marks it unsupported with a follow-up contract**." N4 picked option B but never registered the follow-up sprint, so the requirement is unresolved.
3. **Node status drift keeps reopening the sprint.** All four nodes in `task_graph.json` show `status: reviewing` while `gate_results.*.status` say `passed`. The graph scheduler treats `reviewing` as open → `graph_parent_ready_revoked` → autopilot re-routes to planner. This has bounced twice (2026-05-26 and 2026-05-29) since finalization.

Round-2 explicitly does **not** redo N1–N4 work. It builds on top with new node IDs R1–R5 and treats prior handoffs as authoritative evidence inputs.

## Parallelization
- **R1 (status reconciliation)**, **R2 (advisor live re-run + repo cleanup)**, and **R3 (live server bring-up + cache API regression)** have no inter-dependencies and disjoint write_scope → coordinator may dispatch all three in the first wave.
- **R4 (long knowledge-extraction prompt + chat/completions reuse follow-up sprint)** requires the omlx server to be live; depends on **R3** so the server stays running.
- **R5 (final PRD acceptance evidence + sprint closure)** is the join node — depends on R1, R2, R3, R4. It produces the closure handoff that the autopilot will consume to mark the sprint terminal again.

## DAG (textual)
```
R1 ─┐
R2 ─┼──► R5
R3 ─┼──► R4 ───► R5
    │
    └─ (R5 join)
```

## Gates
| Gate | Owning Node | Pass Condition |
|------|-------------|----------------|
| `R-status-reconciled` | R1 | All N1–N4 node statuses + gate_results recorded as `passed` with evidence pointers; status.json no longer triggers `graph_parent_ready_revoked` |
| `R-advisor-live-clean` | R2 | `thunderomlx_cache_advisor_report.py` exits 0 under a freshly-spawned system-python process (no `KMP_DUPLICATE_LIB_OK`), JSON report under `monitor-reports/`; uncommitted Round-1 working-tree files either committed or formally stashed with note |
| `R-cache-api-live` | R3 | Live HTTP evidence: `POST /v1/cache/prompt/save` returns 422 for <256-token prompt, returns 200 for ≥256-token prompt; `GET /v1/cache/prompt/list` shows the saved entry; server PID + tail of stderr captured |
| `R-long-prompt-and-reuse-contract` | R4 | (a) ≥1024-token Chinese knowledge-extraction prompt save→list→load round-trip succeeds against the live server; (b) follow-up sprint `sprint-20260601-thunderomlx-chat-completions-cache-reuse` registered with its own PRD + contract describing the exact missing integration |
| `R-final-acceptance` | R5 | All seven PRD acceptance bullets re-verified with cited evidence files; sprint status.json updated to `passed/completed`; closure handoff written |

## Stop rules
- If R3 cannot start the omlx server (port 8002 already taken, model missing, mlx not importable) → R3 must publish a **partial-pass** handoff documenting blocker + exact remediation needed, and R4 is short-circuited to "reuse contract follow-up sprint only" (option B for the reuse decision). R5 still runs and produces a closure that names the live-test gap as a known-residual-risk rather than a regression.
- If R2 finds the advisor still aborts under fresh system python → escalate to PM; do **not** add `KMP_DUPLICATE_LIB_OK=TRUE` (contract prohibits).
- If any node tries to enable `partial_block_cache` / `full_skip` / `approximate_skip`, or move the SSD cache off `/Volumes/RAID0-Main/omlx-cache/ssd-qwen36`, or downgrade `--hot-cache-max-size 8GB` → fail immediately and roll back via the rollback recipe in `N4-handoff.md`.

## Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| Live server start fails on Mac mini | Medium | R3 stop rule above; partial-pass handoff still closes the round |
| Long Chinese prompt produces `bad_chars=true` despite fix | Low | R4 must run the verify step with `bad_chars` assertion; failure → no chat/completions wiring, only follow-up contract |
| Uncommitted Round-1 working-tree edits include unrelated breakage | Medium | R2 reviews diff first; if unrelated, `git stash` with named message rather than commit |
| Status reconciliation race with autopilot reopening loop | Low | R1 records both `node_results[*].status=passed` AND `task_graph_status=completed` atomically with explicit `gate_results` so `graph_parent_ready_check` returns `ready=true` |
