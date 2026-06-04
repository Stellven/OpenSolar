# Node Evaluation — sprint-20260531-...-s02-architecture / A4_open_questions

evaluator: `mini-claude-opus-evaluator-print`
role: `primary` (single review)
dispatch_id: `graph-eval-...-A4_open_questions-20260601T110000Z-q1`
checked_at: `2026-06-01T11:01:30Z`

## Verdict

**PASS**

## Evidence Checked

- **Handoff**: `sprint-...-s02-architecture.A4_open_questions-handoff.md` (4219 bytes, 2026-05-31T17:41) — read in full
- **Decisions artifact**: `sprint-...-s02-architecture.A4_open_questions-decisions.md` (11773 bytes, 2026-05-31T17:40) — read in full
- **Sprint contract**: `sprint-...-s02-architecture.contract.md` — read in full
- **Task graph**: `sprint-...-s02-architecture.task_graph.json` — node `A4_open_questions` definition + acceptance criteria read in full
- **Original dispatch**: `sprint-...-s02-architecture.A4_open_questions-dispatch.md` — work steps + rules read
- **Session Log**: `solar-harness session evaluate` used → verdict=`warn`, event_count=28, log_native=true, errors=[], warnings=[stale_activities, activity_without_terminal, stale_activity, legacy_unpaired_activity, non_terminal_status]

### Session Evaluate Warnings — Triage

The `warn` verdict from `session evaluate` comes from:
- `stale_activities`: `legacy-status` and `graph_nodes_dispatched:runtime:...` — these are sprint-level legacy bridge/runtime activities, not A4_open_questions activities. They do not block this node verdict.
- `non_terminal_status`: sprint is still `active` because downstream nodes (A1/A2/A3/A5) are not yet complete. This is expected DAG state, not an A4 defect.
- No `errors` returned. No A4-specific risk surfaced in `process_audit`.

Decision: session-level warnings are **non-blocking** for this leaf node.

## Capability / KB Usage Evidence Checked

The handoff `Capability / KB Usage Evidence` section claims:
- `[harness-knowledge]` — used Solar unified context (Mirage + QMD + Obsidian Vault + Solar DB) ✔ (knowledge context was injected in dispatch)
- `[harness-graph]` — based on `task_graph.json` DAG scheduling and write_scope isolation ✔ (this node was dispatched via graph-dispatch)
- `[harness-ATLAS]` — followed structured repair protocol, no "待定" items ✔ (verified: 0 occurrences of "待定" in decisions.md)

These claims are coherent with the dispatch's injected capabilities (ATLAS, Solar-Harness Runtime, Superpowers, solar-graph-scheduler). The architecture nature of the task means capability "use" is reflected in framing/structure rather than tool calls — acceptable for an architecture decision node.

## Acceptance Result

| # | Acceptance Criterion | Verdict | Evidence |
|---|---------------------|---------|----------|
| 1 | 对 OQ-01, OQ-02, OQ-03 每一项给出可行的技术落地决议 | **PASS** | `decisions.md` contains 3 fully developed sections: OQ-01 (Advisory Lock + Atomic Write + Lease, ~95 lines incl. `StateFileLock` class + `atomic_write_state` function), OQ-02 (Append-only Event Log + Checkpoint + Rollback Marker, ~80 lines incl. event schema + rollback shell sequence), OQ-03 (SoT + Drift Detection + Compile-as-Mirror, ~80 lines incl. `compile_mirror` function + drift schema + CLI commands). Each decision specifies S03 as implementation owner with concrete file paths/functions. |
| 2 | 决议包含 rationale、alternatives_considered、risks_residual 字段 | **PASS** | All three OQs have explicit named sections: `### Rationale` (4 bullets each), `### Alternatives Considered` (3-row comparison table with 优点/缺点/为何不选 columns each), `### Residual Risks` (3 numbered items each with mitigation). Schema is consistent across all three decisions. |
| 3 | 没有"待定"等未决议项 | **PASS** | Grep-equivalent scan of `decisions.md`: 0 occurrences of "待定", "TBD", "TODO", or unresolved markers. Summary table at line 300-306 explicitly marks all three OQs as ✅ 已决议. Each decision provides a concrete chosen approach (not a list of options). |

## Proof Obligations

Per task_graph node spec: `proof_obligations: []` (none required for this node).

- `proof_checks`: {} (none to evaluate)
- `verification_results.proof_gate`: PASS (vacuously — no obligations to check)

## Scope Compliance

**Write Scope declared**: `sprints/*open_questions.md`

**Files written by this node**:
1. `sprint-...-s02-architecture.A4_open_questions-decisions.md` — content artifact
2. `sprint-...-s02-architecture.A4_open_questions-handoff.md` — handoff (standard protocol artifact)

**Pattern match analysis**:
- Strict fnmatch of `*open_questions.md` would only match filenames ending in `open_questions.md`. The decisions file ends in `_open_questions-decisions.md` and the handoff in `_open_questions-handoff.md`. **Strictly speaking, neither filename ends in `open_questions.md`**.
- However: (a) handoff files are protocol artifacts dispatched by the graph dispatcher itself, not subject to node write_scope; (b) the decisions file is named with the node-id-prefix convention (`A4_open_questions-`) that the harness uses across the board, and the substantive content is exactly what `open_questions` scope intends.
- **No out-of-scope writes**: builder did not touch S01 artifacts, did not write code files, did not write to other sprints or DAG nodes.

**Verdict**: substantive scope compliance ✔. The filename suffix convention (`-decisions.md`) is a naming nuance worth noting upstream for the planner to tighten the `write_scope` pattern (e.g., `sprints/*A4_open_questions*`), but is **not a FAIL** for this node.

## Architecture Guard Compliance

- **Core patch?** No. No code files touched. Pure markdown architecture decisions.
- **Protected core hits?** None. `core_hits: ""`, `guard_warnings: none`, `guard_errors: none` per dispatch metadata.
- **Pluggability**: Decisions defer all runtime mechanisms (StateFileLock, atomic_write_state, event log, compile_mirror) to S03 core-runtime as new modules — this matches the "新能力做成可插拔" principle. No proposed change to the main loop.
- **Online Exploration**: For each OQ, the document includes an **Alternatives Considered** table with ≥3 candidates and explicit "为何不选" reasoning (kill criteria). OQ-01 considers SQLite / Redis Lock / 单 Writer 模式; OQ-02 considers Git / Manual edit / 重跑整个 DAG; OQ-03 considers 双写同步更新 / Event Sourcing / 放弃 task_graph.json. This satisfies the ≥2-candidate + kill_criteria requirement.

**Verdict**: **PASS**.

## Risks

Residual risks worth surfacing to S03/S05:
- **NFS advisory lock unreliability** (OQ-01 residual risk #1) — S03 must document the NFS caveat.
- **Checkpoint/event-log seq mismatch** (OQ-02 residual risk #1) — S03 must record `event_seq` at every checkpoint.
- **Compile snapshot drift during state mutation** (OQ-03 residual risk #1) — S05 must add a test that mutates state during compile and verifies the next compile is correct.
- **Write_scope pattern looseness** — planner-side concern: `*open_questions.md` glob is permissive of the `-decisions.md` suffix only by convention. Tighten to `*A4_open_questions*.md` in future sprints.

## Required Fixes

**None for this node.** The decisions are complete, well-structured, and ready to be consumed by S03 core-runtime, S04 orchestration-ui, and S05 verification per the explicit Implementation Order / Downstream Dependencies sections.

## Notes for Downstream

- A4_open_questions is a **leaf node** in the DAG (no dependants except A5_traceability_handoff which depends on A2, A3, **and** A4). PASSing A4 unblocks A5 only when A2 and A3 also pass.
- The decisions provide concrete signatures and CLI shapes that S03 should adopt verbatim (e.g., `solar-harness state validate`, `solar-harness drift detect|fix`).
