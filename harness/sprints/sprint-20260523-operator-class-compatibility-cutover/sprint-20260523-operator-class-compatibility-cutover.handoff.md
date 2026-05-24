# Sprint Handoff — sprint-20260523-operator-class-compatibility-cutover

sprint_id: `sprint-20260523-operator-class-compatibility-cutover`
title: Operator Class Compatibility Cutover — legacy role 到 canonical operator class 的兼容桥 + staged rollout
parent_sprint_chain: `sprint-20260523-pane-as-physical-operator-architecture` → `sprint-20260523-physical-operator-taxonomy-truthification` → (this sprint)
builder: 建设者化身 (Solar Builder pane — N1 layer round)
round: 1
ts: 2026-05-23T20:44:00Z

Knowledge Context: solar-harness context inject used (mirage timeout → qmd/obsidian/solar_db fallback)
Harness Modules Used: harness-knowledge, harness-graph (graph-scheduler validate/ready/layers/mark)
Capability Provenance: ATLAS — declared `injectable_only` in dispatch; not actively triggered.

## Why this handoff exists

The dispatch wakes the builder pane with `Workflow Guard 判定 PM+Planner 产物齐全`. The DAG has 6 nodes across 4 layers; only N1_audit is ready (no deps). This sprint-level handoff:

1. Aggregates the N1 deliverable (read-only 6-component audit).
2. Maps every applicable contract acceptance row to concrete evidence.
3. Records the `Solar能力` provenance line and the gate-intercept required sections (`Done 条件达成证据` + `变更文件列表`).
4. Acknowledges that N2..N6 remain `pending` per DAG dependency rules — they will be dispatched once N1 passes.
5. Uses the correct per-node mark mechanism (`graph-scheduler mark --node ... --status reviewing`), NOT a sprint-level status flip.

## DAG node delivery snapshot

| Node | Layer | Gate | Status | Deliverable |
|------|-------|------|--------|-------------|
| N1 — Compatibility Audit Lock | L0 | G_AUDIT | `reviewing` | `<sid>.workstream-A-audit.md` (NEW) |
| N2 — Canonical Mapping Lock | L1 | G_CANONICAL_MAPPING | `pending` (depends N1) | `<sid>.workstream-B-canonical-mapping.md` + `<sid>.canonical-mapping.md` |
| N4 — In-flight Safety Lock | L1 | G_INFLIGHT_SAFETY | `pending` (depends N1) | `<sid>.workstream-D-inflight-safety.md` |
| N5 — Observability Three-View | L1 | G_OBSERVABILITY_THREE_VIEW | `pending` (depends N1) | `<sid>.workstream-E-observability.md` |
| N3 — Scheduler Bridge Lock | L2 | G_SCHEDULER_BRIDGE | `pending` (depends N1+N2) | `<sid>.workstream-C-scheduler-bridge.md` |
| N6 — Rollout / Rollback Lock (JOIN) | L3 | G_ROLLOUT_ROLLBACK | `pending` (depends N1+N2+N3+N4+N5) | `<sid>.workstream-F-rollout-rollback.md` + `<sid>.rollout-runbook.md` |

`graph-scheduler validate` (this round):
```text
{"ok": true, "sprint_id": "sprint-20260523-operator-class-compatibility-cutover",
 "node_count": 6, "errors": [], "warnings": []}
```

`graph-scheduler ready` (before mark):
```text
{"ok": true, "nodes": ["N1_audit"], "blocked_prerequisites": []}
```

`graph-scheduler layers`:
```text
[["N1_audit"],
 ["N2_canonical_mapping", "N4_inflight_safety", "N5_observability_three_view"],
 ["N3_scheduler_bridge"],
 ["N6_rollout_rollback"]]
```

## Done 条件达成证据 / Definition of Done evidence

**N1-scoped clauses are ✅ this round; N2..N6 clauses are explicitly `pending` per DAG dependency.**

| # | Contract / Acceptance Gate clause | Status | Evidence |
|---|------------------------------------|--------|----------|
| 1 | Required Deliverable: `design` | ✅ (planner round 1) | `<sid>.design.md` (20,955 B). |
| 2 | Required Deliverable: `plan` | ✅ (planner round 1) | `<sid>.plan.md` (12,291 B). |
| 3 | Required Deliverable: `task_graph` (audit/mapping/scheduler/safety/observability/rollout) | ✅ (planner round 1) | `<sid>.task_graph.json` 6 nodes / 4 layers / validate ok. |
| 4 | Required Deliverable: `mapping` (legacy → canonical class matrix) | 🟡 pending (N2 deferred) | Audit §1 + Architecture Decision §1 sets up the input; N2 produces `<sid>.canonical-mapping.md`. |
| 5 | Required Deliverable: `validation` (in-flight safety proof + no-breaking evidence) | 🟡 partial (N1 part done; N4+N6 finalize) | Audit Finding 4A proves **zero LEASED/RUNNING/DRAINING** = no current in-flight risk; N4 produces 13-state matrix; N6 produces non-breaking guarantees list. |
| 6 | Required Deliverable: `report` (strict mode entry criteria / remaining gaps) | 🟡 pending (N6 JOIN node) | Audit Findings 3A + 5A + 6A quantify the gap; N6 produces the strict-mode entry criteria runbook. |
| 7 | Mandatory Design Decision §1 (引入 `canonical_operator_class` 中间层) | 🟡 pending (N2 deferred) | Audit confirms it's a greenfield addition (Finding 5A: 0 references in any status code). |
| 8 | Mandatory Design Decision §2 (legacy role 只作 alias / compatibility input) | 🟡 pending (N2+N3 deferred) | Audit Finding 1A: 100% legacy role today; N2 designs alias table; N3 enforces "alias resolve first, never as long-term truth". |
| 9 | Mandatory Design Decision §3 (LEASED/RUNNING/DRAINING 不允许 online re-classify) | ✅ Foundation set | Audit Finding 4A confirms zero such nodes currently; N4 codifies the 13-state matrix that protects them prospectively. Audit itself is read-only — does not violate. |
| 10 | Mandatory Design Decision §4 (scheduler 先 alias resolve → canonical → strict mode) | 🟡 pending (N3 deferred) | Audit Finding 3A confirms dispatcher has zero such infrastructure (greenfield); N3 designs the 4-step resolve. |
| 11 | Mandatory Design Decision §5 (observability 同时展示 legacy / canonical / selected_binding) | 🟡 pending (N5 deferred) | Audit Finding 5A: zero canonical fields in status payload today; N5 designs 3-view schema. |
| 12 | Mandatory Design Decision §6 (rollout 可回退，不得停机) | 🟡 pending (N6 JOIN deferred) | Audit Finding 4A removes the stop-machine risk for Phase 0-1; N6 designs Phase 2-5 rollback commands. |
| 13 | Acceptance Gate: 缺 canonical mapping 不得算完成 | 🟡 N2 deferred | — |
| 14 | Acceptance Gate: 缺 RUNNING/LEASED/DRAINING 安全规则不算完成 | 🟡 N4 deferred | — |
| 15 | Acceptance Gate: 缺 scheduler alias resolve 顺序不算完成 | 🟡 N3 deferred | — |
| 16 | Acceptance Gate: 缺 rollout/rollback 不算完成 | 🟡 N6 JOIN deferred | — |
| 17 | N1 acceptance row: workstream-A-audit.md 含 6 段 | ✅ | grep PASS for all 6 sections (已完成 / Inputs From PRD / Architecture Decision / Acceptance 映射 / In-flight Safety / Stop-Rule). |
| 18 | N1 acceptance row: 6 组件盘点全集 | ✅ | Audit §1–§6: registry / sqlite / dispatcher / in-flight nodes / 8765 / evaluator scripts — each populated with concrete numbers. |
| 19 | N1 acceptance row: physical-operators.json 报告 entry 数 + legacy/canonical ratios | ✅ | Audit Finding 1A: 15 entries, 15/15 legacy role, 0/15 new 10-class taxonomy, 6/15 v1 enum. |
| 20 | N1 acceptance row: in-flight 状态盘点 LEASED+RUNNING+DRAINING + binding | ✅ | Audit Finding 4A: 0/0/0 active; binding N/A; 11 `reviewing` nodes are evaluator-blocked, not running. |
| 21 | N1 acceptance row: dispatcher alias / canonical / strict mode 现状 | ✅ | Audit Finding 3A: zero canonical infrastructure; only `_normalize_model_alias` (model-only). |
| 22 | N1 acceptance row: audit 仅 read-only | ✅ | Audit doc + N1-handoff + sprint-level aggregator are the only 3 writes this round. `config/physical-operators.json` mtime unchanged at 2026-05-23T00:53Z. |
| 23 | N1 acceptance row: 映射 PRD A6 + G4 | ✅ | Audit "Inputs From PRD" table maps A6 (no_matching_worker root-cause) + G4 (3-view observability baseline). |

**This round delivers N1 only.** Evaluator should NOT gate the sprint on N2..N6 clauses this round.

## 变更文件列表 / Changed files (this sprint, by all panes)

| Path | Operation | Owner pane / round | Purpose |
|------|-----------|---------------------|---------|
| `sprints/sprint-20260523-operator-class-compatibility-cutover.prd.md` | NEW | PM (round 1) | Compatibility Cutover PRD. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.prd.html` | NEW | PM (round 1) | Rendered PRD. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.contract.md` | NEW | PM (round 1) | Contract (Hard Rules + 6 Mandatory Design Decisions + 4 Acceptance Gates). |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.pm-order.md` | NEW | PM (round 1) | PM intake order. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.design.md` | NEW | Planner (round 1) | Compatibility bridge / canonical mapping / 6-phase rollout / Q1..Q5 answers. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.plan.md` | NEW | Planner (round 1) | Staged migration + rollback plan. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.task_graph.json` | NEW | Planner (round 1) | 6-node / 4-layer DAG; graph-scheduler validate ok. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.planning.html` | NEW | Planner (round 1) | Rendered planning summary. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.workstream-A-audit.md` | NEW | Builder N1 (this round) | 6-component read-only audit with concrete numbers and findings. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.N1-handoff.md` | NEW | Builder N1 (this round) | Per-node handoff with 7 Done-clause evidence + verification commands. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.handoff.md` | NEW | Builder sprint-level (this round) | This aggregator. |
| `sprints/sprint-20260523-operator-class-compatibility-cutover.task_graph.json` | UPDATED (`graph-scheduler mark`) | Builder N1 (this round) | `node_results.N1_audit = {status: reviewing, …}`. |

**No edits anywhere else.** Specifically:
- `~/.solar/harness/config/physical-operators.json` — untouched (mtime 2026-05-23T00:53Z).
- `~/.solar/harness/lib/*.py` / `tools/*.py` / `solar-harness.sh` / hooks / skills — untouched (read-only audit).
- Parent sprint chain (`pane-as-physical-operator-architecture`, `physical-operator-taxonomy-truthification`) — untouched.
- Parallel `sprint-20260523-lease-based-model-fleet-runtime.*` — untouched.
- `~/.solar/STATE.md` / epic.* / ThunderOMLX paths — untouched.

## Required-evidence roll-up

| Plan-side verification | Builder-side result this round |
|------------------------|--------------------------------|
| graph-scheduler validate | `{ok:true, node_count:6, errors:[], warnings:[]}` |
| ready / layers | ready=`["N1_audit"]` (before mark); 4 layers |
| audit doc present + 6 sections | ✅ grep PASS for all 6 sections |
| 6 components addressed | ✅ each component (registry / sqlite / dispatcher / in-flight / 8765 / evaluator) present |
| numerical findings (1A / 3A / 4A / 5A / 6A) | ✅ entry 15 / legacy 100% / canonical 0% / dispatcher 0-refs / in-flight 0+0+0 / 8765 0-canonical-fields / lib 16-of-115 legacy files |
| no raw secrets | ✅ grep PASS |
| read-only invariant | ✅ `config/physical-operators.json` mtime unchanged; `lib/graph_node_dispatcher.py` not edited |

## Hard-constraints roll-up

| Hard Rule | Compliance evidence |
|-----------|---------------------|
| 不允许停掉 LEASED / RUNNING / DRAINING 的 operator | None existed (Finding 4A) AND audit was read-only — neither condition activated. |
| 不允许强制重启全部 pane | No pane restart commands invoked; no `tmux send-keys`. |
| 不允许回滚父 sprint 或 taxonomy sprint planner 真值 | Zero writes under those sprint ids (mtimes unchanged on parent + grandparent design.md / task_graph.json). |
| 不允许 legacy role 继续作为长期调度真值 | Audit only inventories; design-decision artifact is N2/N3, not this audit. |
| 不允许 strict canonical mode 抢跑 | Audit Finding 3A confirms dispatcher has zero strict-mode infrastructure — strict mode cannot accidentally activate from this artifact. |
| 不允许无观测切换 | Audit produces visibility data; no switching performed. |

## Stop-Rule Compliance (sprint-level)

- ❌ Did **not** modify `config/physical-operators.json` (production registry).
- ❌ Did **not** modify any `lib/*.py` / `tools/*.py` / shell scripts.
- ❌ Did **not** kill / restart any tmux pane.
- ❌ Did **not** stop any LEASED/RUNNING/DRAINING operator (none existed; audit was read-only anyway).
- ❌ Did **not** activate strict canonical mode.
- ❌ Did **not** roll back any parent / grandparent / parallel sprint.
- ❌ Did **not** write raw secret strings.
- ❌ Did **not** introduce a new process model.
- ❌ Did **not** change 5-pane topology.
- ❌ Did **not** write under `/tmp`.
- ❌ Did **not** modify `~/.solar/STATE.md` / epic.* / `sprint-20260523-lease-based-model-fleet-runtime.*`.
- ❌ Did **not** auto-set node `status=passed` (correct `graph-scheduler mark --status reviewing` mechanism used).
- ❌ Did **not** flip sprint-level `status.json` to `reviewing` (correct mechanism per parent-sprint earlier lesson).
- ❌ Did **not** use optimistic words.

## Known Risks

1. **L1 fan-out is 3-wide (N2 + N4 + N5)** — coordinator must dispatch with `max-parallel ≥ 2` to avoid serialization.
2. **N6's rollout runbook needs shell-side coverage** — audit found legacy literals in `persona-config.sh` (5) + `state-mapper.sh` (17). N6 cannot scope its rollback commands to Python only.
3. **Field-name collision with parallel sprint** — `sprint-20260523-lease-based-model-fleet-runtime` already shipped `monitor_bridge.py v2` with `actor_id / host_id / lease_state / billing_pool`. N5 should pick distinct field names (`legacy_role / canonical_operator_class / selected_binding / resolved_via` per task_graph) — audit flags the collision risk for evaluator review.
4. **Multi-sprint dependency on taxonomy sprint** — N2's mapping table references the new 10-class enum that is itself only `reviewing` in the taxonomy sprint. If the taxonomy sprint's evaluator rejects any class name, N2 must wait.
5. **Mirage VFS timeout** — `solar-harness context inject` returned `mirage:timeout` this round (different from earlier `no_results`); QMD/Obsidian/solar_db fallback used. Not blocking; PM should track KB health if this recurs.

## Open follow-ups (deferred beyond this sprint)

1. **Actual code changes** — this sprint is design-only. The real cutover work (alias-table loader, dispatcher 4-step resolve, 3-view payload writer, shell-side env-var) lands in a Phase 1+ implementation sprint authorized by N6's rollout runbook.
2. **Shell script alignment** — `persona-config.sh` / `state-mapper.sh` legacy-literal removal is on the rollout runbook's Phase 4+ checklist.
3. **`worker_state.sqlite` decision** — audit found no such file; either (a) keep in-flight state in `task_graph.json` `node_results` forever, or (b) build a real sqlite lease table when fleet size grows. N6 should call this out.

## Node-level status mark (correct mechanism)

This is a **per-node delivery handoff for N1 only**, not a sprint-completion handoff. Sprint-level status MUST remain at `active/planning_complete/builder_main` until N6 (the join node) reaches `passed`.

Correct command executed this round:

```bash
solar-harness graph-scheduler mark \
  --graph ~/.solar/harness/sprints/sprint-20260523-operator-class-compatibility-cutover.task_graph.json \
  --node N1_audit --status reviewing --in-place
# → node_results.N1_audit = {status: reviewing, updated_at: <now>}
# → sprint status_sync: parent_not_ready (correct — N2..N6 still open)
```

Sprint-level `status.json` intentionally **left untouched**. Coordinator advances the sprint only when all 6 gates flip to `passed`.

## After evaluator passes N1

1. Coordinator runs `graph-scheduler ready` → expected `["N2_canonical_mapping", "N4_inflight_safety", "N5_observability_three_view"]` (3-wide L1).
2. Coordinator dispatches L1 in parallel (max-parallel ≥ 2).
3. After N2 passes → N3 ready.
4. After all 5 predecessors pass → N6 (JOIN) ready.
5. N6 produces the 6-phase rollout runbook + parent-sprint adoption brief (taxonomy-truthification consumes this cutover as its physical-landing path).
