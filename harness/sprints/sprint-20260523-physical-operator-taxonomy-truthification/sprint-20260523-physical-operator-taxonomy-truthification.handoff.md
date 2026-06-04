# Sprint Handoff — sprint-20260523-physical-operator-taxonomy-truthification

sprint_id: `sprint-20260523-physical-operator-taxonomy-truthification`
title: Physical Operator Taxonomy Truthification — 10 类正式化为 schema/routing/policy/lifecycle 真值
parent_sprint: `sprint-20260523-pane-as-physical-operator-architecture` (read-only; **不回滚不重写**)
builder: 建设者化身 (Solar Builder pane — N1 layer round)
round: 1
ts: 2026-05-23T20:20:00Z

Knowledge Context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
Harness Modules Used: harness-knowledge, harness-graph (graph-scheduler validate/ready/layers/mark)
Capability Provenance: ATLAS / Autoresearch — declared `injectable_only`; not actively triggered (no failure path required).

## Why this handoff exists

The dispatch wakes the builder pane with `Workflow Guard 判定 PM+Planner 产物齐全`. The DAG has 6 nodes across 4 layers; only N1_taxonomy_lock is ready (no deps). This sprint-level handoff:

1. Aggregates the N1 deliverable into one evaluation-ready entry.
2. Maps every contract acceptance row and every applicable PRD acceptance / risk to concrete evidence.
3. Records the `Solar能力` provenance line and the gate-intercept required sections (`Done 条件达成证据` + `变更文件列表`).
4. Acknowledges that N2..N6 remain `pending` per DAG dependency rules — they will be dispatched once N1 passes.
5. Uses the correct per-node mark mechanism (`graph-scheduler mark --node ... --status reviewing`), NOT a sprint-level status flip (lessons learned from parent sprint's `reviewing_blocked_invalid_handoff` rejection).

## DAG node delivery snapshot

| Node | Layer | Gate | Status | Deliverable |
|------|-------|------|--------|-------------|
| N1 — Taxonomy Lock | L0 | G_TAXONOMY_LOCK | `reviewing` | `<sid>.workstream-A-taxonomy-matrix.md` (NEW) |
| N2 — Schema Truthification | L1 | G_SCHEMA_LOCK | `pending` (depends N1) | `<sid>.workstream-B-schema-truthification.md` |
| N4 — Runtime Lifecycle Lock | L1 | G_LIFECYCLE_LOCK | `pending` (depends N1) | `<sid>.workstream-D-runtime-lifecycle.md` |
| N5 — Safety Policy Lock | L1 | G_SAFETY_LOCK | `pending` (depends N1) | `<sid>.workstream-E-safety-policy.md` |
| N3 — Scheduler Mapping Lock | L2 | G_SCHEDULER_LOCK | `pending` (depends N1+N2) | `<sid>.workstream-C-scheduler-mapping.md` |
| N6 — Rollout/Repair Lock (JOIN) | L3 | G_ROLLOUT_REPAIR_LOCK | `pending` (depends N1+N2+N3+N4+N5) | `<sid>.workstream-F-rollout-repair.md` + `<sid>.parent-repair-addendum.md` |

DAG `graph-scheduler validate` (this round):
```text
{"ok": true, "sprint_id": "sprint-20260523-physical-operator-taxonomy-truthification",
 "node_count": 6, "errors": [], "warnings": []}
```

DAG `graph-scheduler ready` (before N1 mark):
```text
{"ok": true, "nodes": ["N1_taxonomy_lock"], "blocked_prerequisites": []}
```

DAG `graph-scheduler layers`:
```text
[["N1_taxonomy_lock"],
 ["N2_schema_truthification", "N4_runtime_lifecycle_lock", "N5_safety_policy_lock"],
 ["N3_scheduler_mapping_lock"],
 ["N6_rollout_repair_lock"]]
```

## Done 条件达成证据 / Definition of Done evidence

**N1-scoped clauses are ✅ this round; N2..N6 clauses are explicitly `pending` per DAG dependency.**

| # | Contract / Acceptance Gate clause | Status | Evidence |
|---|------------------------------------|--------|----------|
| 1 | Required Deliverable: `design` (taxonomy 真值化设计: class/matrix/policy/routing) | ✅ (planner round 1) | `<sid>.design.md` (22,018 B) — §1 10-class matrix + §3 schema + §4 scheduler mapping + §7 lifecycle + §8 safety + §10 parent repair + §13 Q1..Q11 answers. |
| 2 | Required Deliverable: `plan` (rollout / repair / compatibility) | ✅ (planner round 1) | `<sid>.plan.md` (11,990 B). |
| 3 | Required Deliverable: `task_graph` (taxonomy/schema/scheduler/safety/repair nodes) | ✅ (planner round 1) | `<sid>.task_graph.json` 6 nodes / 4 layers / validate ok. |
| 4 | Required Deliverable: `matrix` (10-class operator taxonomy 对照矩阵) | ✅ **THIS ROUND** | `<sid>.workstream-A-taxonomy-matrix.md` (18,984 B) — 10 rows × 7 columns. |
| 5 | Required Deliverable: `validation` (graph validate + parent gap mapping + residual risks) | 🟡 partial (this round for N1; N6 join for final) | graph-scheduler validate/ready/layers ok this round; N6 produces the parent-repair-addendum + traceability matrix. |
| 6 | Required Deliverable: `report` (P0 / Reservation / Follow-up) | 🟡 pending (N6 JOIN node) | Design.md §11 has the table; N6's `workstream-F-rollout-repair.md` materializes it as a deliverable. |
| 7 | Mandatory Design Decision §1 (一级 taxonomy 按执行角色 / 任务语义建模) | ✅ | N1 matrix — all 10 class names are role/task-semantic (DeepArchitect / Verifier) or domain (Browser/GoogleStack/LocalPrivacy); no provider-family names. |
| 8 | Mandatory Design Decision §2 (provider/model = implementation binding only) | ✅ | N1 matrix column 4 (Policy delta) and column 7 (Example operator ids) — provider/model appears only inside example operator id strings, never as a class name. |
| 9 | Mandatory Design Decision §3 (`task_type → preferred_operator_classes → fallback ladder` machine-readable) | 🟡 partial (N3 deferred) | Design.md §4 has the 20-task_type table; N3 will lock it as a workstream deliverable. |
| 10 | Mandatory Design Decision §4 (DAG nodes use `task_type / required_capabilities / constraints / preferred_operator_classes / verifier_required` — not `model=...`) | 🟡 partial (N3 deferred) | Design.md §5 has the YAML template; N3 enforces. |
| 11 | Mandatory Design Decision §5 (rule-based scoring / penalty) | 🟡 pending (N3 deferred) | Design.md §6 has the 10-factor model; N3 materializes it. |
| 12 | Mandatory Design Decision §6 (canonical lifecycle 6+7 = 13 states) | 🟡 pending (N4 deferred) | Design.md §7 + N4 deliverable. |
| 13 | Mandatory Design Decision §7 (异常状态显式定义) | 🟡 pending (N4 deferred) | Design.md §7 enumerates ERROR/QUOTA_EXHAUSTED/AUTH_EXPIRED/COOLDOWN/DISABLED/STALE_CONTEXT/NEEDS_HUMAN_REVIEW; N4 materializes. |
| 14 | Mandatory Design Decision §8 (`operatord run <operator_id>` 宿主) | 🟡 pending (N4 deferred) | Design.md §7 references; N4 codifies. |
| 15 | Mandatory Design Decision §9 (Task Envelope / Task Result 结构化 contract) | 🟡 pending (N3+N4 deferred) | Design.md §6 (scoring output contract) + §7 (DRAINING→IDLE result gate) hint. |
| 16 | Mandatory Design Decision §10 (Verifier ≠ generic reviewer; 与 taxonomy + policy + provider separation 对齐) | ✅ (N1 matrix) | Matrix row #6 column 6 codifies hard `verifier.operator_id ≠ writer` + high_risk `verifier.provider ≠ writer.provider`. |
| 17 | Mandatory Design Decision §11 (Browser / GoogleStack / LocalPrivacy 单列 policy 边界) | ✅ (N1 matrix) / 🟡 N5 deepens | Matrix rows #8/#9/#10 — independent rows with dedicated policy deltas. N5 produces the full safety policy doc. |
| 18 | Mandatory Design Decision §12 (旧角色桶 → 新 taxonomy 兼容映射) | 🟡 pending (N2 deferred) | Design.md §3 has the 6-bucket map; N2 materializes. |
| 19 | Mandatory Design Decision §13 (父 sprint 消费 follow-up 结果说明) | 🟡 pending (N6 JOIN deferred) | Design.md §10 (Q11 answer: addendum injection); N6 produces the addendum. |
| 20 | Acceptance Gate: 缺 taxonomy matrix 不得算完成 | ✅ THIS ROUND | N1 deliverable. |
| 21 | Acceptance Gate: 缺 `task_type → operator_class ladder` 不得算完成 | 🟡 N3 deferred | — |
| 22 | Acceptance Gate: 缺 "DAG 不直写模型" 规则不算完成 | 🟡 N3 deferred | — |
| 23 | Acceptance Gate: 缺 score-based selection 规则不算完成 | 🟡 N3 deferred | — |
| 24 | Acceptance Gate: 缺 canonical lifecycle 与异常状态定义不算完成 | 🟡 N4 deferred | — |
| 25 | Acceptance Gate: 缺每个状态对应 dispatch 动作不算完成 | 🟡 N4 deferred | — |
| 26 | Acceptance Gate: 缺 `operatord run <operator_id>` 宿主契约不算完成 | 🟡 N4 deferred | — |
| 27 | Acceptance Gate: 缺结构化 task envelope / result contract 不算完成 | 🟡 N3+N4 deferred | — |
| 28 | Acceptance Gate: 缺 Browser / GoogleStack / LocalPrivacy 专门 policy 不算完成 | 🟡 N1 partial / N5 final | N1 matrix introduces the rows + policy delta cells; N5 writes the full safety policy doc. |
| 29 | Acceptance Gate: 缺旧角色桶兼容映射不算完成 | 🟡 N2 deferred | — |
| 30 | Acceptance Gate: 缺 parent repair / adoption 说明不算完成 | 🟡 N6 JOIN deferred | — |
| 31 | N1 acceptance row "新文件 + 10 行 + 7 列 + Q1..Q5 + Browser/GoogleStack/LocalPrivacy 一级 + A1 + R1+R2 + 6 段 + 不改父 sprint" | ✅ | See N1-handoff (all 10 contract clauses). |

**This round delivers N1 only.** Evaluator should NOT gate the sprint on N2..N6 clauses this round; they will land in subsequent DAG layers.

## 变更文件列表 / Changed files (this sprint, by all panes)

| Path | Operation | Owner pane / round | Purpose |
|------|-----------|---------------------|---------|
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.prd.md` | NEW | PM (round 1) | Taxonomy Truthification PRD. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.prd.html` | NEW | PM (round 1) | Rendered PRD. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.contract.md` | NEW | PM (round 1) | Contract (Hard Rules + Required Deliverables + 13 Mandatory Design Decisions + 11 Acceptance Gates). |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.pm-order.md` | NEW | PM (round 1) | PM intake order. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.design.md` | NEW | Planner (round 1) | 10-class matrix + scheduler mapping + lifecycle + safety + parent repair + Q1..Q11 answers. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.plan.md` | NEW | Planner (round 1) | Rollout / repair / compatibility plan. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.task_graph.json` | NEW | Planner (round 1) | 6-node / 4-layer DAG; graph-scheduler validate ok. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.planning.html` | NEW | Planner (round 1) | Rendered planning summary. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.workstream-A-taxonomy-matrix.md` | NEW | Builder N1 (this round) | 10×7 taxonomy matrix + Q1–Q5 answers + 6-section contract. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.N1-handoff.md` | NEW | Builder N1 (this round) | Per-node handoff with 10 Done-clause evidence + verification commands. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.handoff.md` | NEW | Builder sprint-level (this round) | This aggregator. |
| `sprints/sprint-20260523-physical-operator-taxonomy-truthification.task_graph.json` | UPDATED (via `graph-scheduler mark`) | Builder N1 (this round) | `node_results.N1_taxonomy_lock = {status: reviewing, ...}`. |

**No edits anywhere else.** Specifically:
- Parent sprint `sprint-20260523-pane-as-physical-operator-architecture.*` — untouched.
- Parallel sprint `sprint-20260523-lease-based-model-fleet-runtime.*` — untouched.
- `~/.solar/harness/config/physical-operators.json` — untouched (production).
- `~/.solar/harness/lib/*.py` / `tools/*.py` / `solar-harness.sh` / hooks / skills — untouched (design-only sprint).
- `~/.solar/STATE.md` / epic.* / ThunderOMLX paths — untouched.

## Required-evidence roll-up (parallel to contract Acceptance Gates)

| Plan §6 verification step | Builder-side pre-verification |
|---------------------------|--------------------------------|
| A. graph-scheduler validate | `{ok:true, node_count:6, errors:[], warnings:[]}` |
| B. ready / layers | ready=`["N1_taxonomy_lock"]` (before mark); 4 layers (L0..L3) |
| C. workstream handoff files齐全 | 1/6 produced this round (N1). N2..N6 deferred per DAG dependency. |
| D. matrix file present + 10 rows × 7 cols | ✅ awk row count = 10; header row column count = 7. |
| E. 10 class names verbatim | ✅ grep -E "`(DeepArchitect|...)`" each present. |
| F. Q1..Q5 answered | ✅ each subsection labeled `### Q1 — ...` through `### Q5 — ...`. |
| G. PRD A1 mapped | ✅ "Inputs From PRD" table. |
| H. R1 + R2 mitigated | ✅ explicit rows in "Inputs From PRD" + Q1/Q3/Q4/Q5 rationale. |
| I. parent sprint untouched | ✅ ls -lT shows parent design.md / task_graph.json mtime unchanged. |
| J. no raw secrets | ✅ grep -nE 'sk-...' / 'Bearer...' / 'ANTHROPIC...=' → only false positive on "ta**sk-s**emantic"; no real raw secret strings. |
| K. 6-section contract | ✅ grep PASS for all 6 sections. |

## Hard-constraints roll-up

| Hard Rule | Compliance evidence |
|-----------|---------------------|
| 不允许把 taxonomy 简化回 `planner/builder/evaluator/architect/external` | Matrix has 10 first-class rows; none use legacy bucket names. |
| 不允许直接篡改父 sprint 已完成的 planner artifacts | Parent design.md / task_graph.json mtime unchanged. |
| 不允许把 provider/model 枚举伪装成 taxonomy 主轴 | All 10 class names are role/task-semantic or domain, not provider-family. |
| 不允许在 DAG 节点直写 `model/provider/profile` | This sprint is design-only; the rule is materialized in design.md §5 + N3 lock. |
| 不允许忽略 Browser / Google-stack / Local Privacy 的专门 policy 边界 | Matrix rows #8/#9/#10 each have dedicated policy delta cells; N5 deepens with full sections. |
| 不允许让 writer/verifier separation 脱离 taxonomy 单独存在 | Matrix row #6 column 6 codifies the rule; every row's column 6 names its verifier constraint. |
| 不允许继续使用含糊 runtime state | Design.md §7 + N4 deliverable. |
| 不允许 pane 直接裸跑底层 CLI | Design.md §7 references `operatord run <operator_id>`; N4 lock. |
| 不允许直接给 pane 塞自然语言任务 | Design.md §6 references the scoring output contract; N3+N4 lock the task-envelope contract. |
| 不允许写入 raw secret | Grep PASS (only false positive on substring); workstream-A doc contains zero raw secret literals. |

## Stop-Rule Compliance (sprint-level)

- ❌ Did **not** modify parent sprint design.md / task_graph.json (mtime unchanged).
- ❌ Did **not** modify parallel sprint `sprint-20260523-lease-based-model-fleet-runtime.*`.
- ❌ Did **not** kill / restart any active tmux pane.
- ❌ Did **not** delete any run directory.
- ❌ Did **not** modify ThunderOMLX paths.
- ❌ Did **not** modify `~/.solar/STATE.md` / epic.*.
- ❌ Did **not** auto-set node `status=passed` (used the correct `graph-scheduler mark --status reviewing` mechanism; evaluator advances to `passed`).
- ❌ Did **not** invoke any `reap`-style command.
- ❌ Did **not** use optimistic words.
- ❌ Did **not** write raw secret material.
- ❌ Did **not** introduce a new process model.
- ❌ Did **not** change 5-pane topology.
- ❌ Did **not** flip sprint-level `status.json` to `reviewing` (correct mechanism per parent sprint's earlier `reviewing_blocked_invalid_handoff` lesson).

## Known Risks

1. **N2 + N4 + N5 parallel dispatch** — once N1 passes, evaluator/coordinator can fan out to all three (plan.md §4 L1). Builder pane must be ready for 3-wide concurrency.
2. **N3 depends on N1+N2** — different from parent sprint where N2/N3 were both L1; here N3 waits for N2 to ship the schema enum. Coordinator must respect this.
3. **N6 is JOIN node** — depends on all 5 predecessors. Late delivery from any of N2/N3/N4/N5 blocks the final addendum.
4. **Parent sprint adoption pathway** — N6 produces `<sid>.parent-repair-addendum.md` AND a target file under the parent sprint id (per design.md §10 `artifact_path: ~/.solar/harness/sprints/sprint-20260523-pane-as-physical-operator-architecture.taxonomy-addendum.md`). That cross-sprint write is the only legal touch of a parent-prefixed file; it is an addendum, NOT a mutation. Evaluator must confirm N6 honors this distinction.
5. **Mirage VFS degraded** — `solar-harness context inject` reported `mirage_path:no_results`; QMD/Obsidian/solar_db fallback used. Not blocking; log so PM tracks KB health.

## Open follow-ups (deferred beyond this sprint)

1. Real operator id registration for FastSubagent / ParallelExplorer / ResearchSynthesizer / BrowserOperator / GoogleStackOperator / LocalPrivacyOperator — these are P0 routing reservations only; concrete operators land in follow-up sprint.
2. `routing_tags` value calibration (multimodal / gpu_required / long_context_v2 / browser_session / google_workspace / air_gapped / sub_2s_latency) — vocabulary draft only.
3. Antigravity / Codex Bridge / ThunderOMLX real integration — `binding_locked_at` field available, but real-runtime ATLAS/operatord adapters are future work.
4. Failure-fingerprint taxonomy alignment (cross-sprint with `lease-based-model-fleet-runtime`).

## Node-level status mark (correct mechanism)

This is a **per-node delivery handoff for N1 only**, not a sprint-completion handoff. Sprint-level status MUST remain at `approved/plan_reviewed/builder` (or equivalent planning_complete state) until N6 (the join node) also reaches `passed`. The coordinator's prior `reviewing_blocked_invalid_handoff` event (on the parent sprint) confirmed that flipping the sprint status to `reviewing` while later nodes are still pending is the wrong mechanism.

Correct command executed this round:

```bash
solar-harness graph-scheduler mark \
  --graph ~/.solar/harness/sprints/sprint-20260523-physical-operator-taxonomy-truthification.task_graph.json \
  --node N1_taxonomy_lock --status reviewing --in-place
# → node_results.N1_taxonomy_lock = {status: reviewing, updated_at: <now>}
# → sprint status_sync: parent_not_ready (correct — N2..N6 still open)
```

Sprint-level `status.json` intentionally **left untouched**. Coordinator will advance the sprint once all 6 gates flip to `passed`.

## After evaluator passes N1

1. Coordinator runs `graph-scheduler ready` → expected `["N2_schema_truthification", "N4_runtime_lifecycle_lock", "N5_safety_policy_lock"]` (3-wide).
2. Coordinator dispatches L1 in parallel (max-parallel ≥ 2; ideally 3 if pane capacity allows).
3. After N2 passes → N3 ready.
4. After all of N1+N2+N3+N4+N5 pass → N6 (JOIN) ready.
5. N6 produces `<sid>.parent-repair-addendum.md` + a sibling file under the parent sprint id (legal cross-sprint addendum injection, per Hard Rule "不允许直接篡改父 sprint" — addendum ≠ mutation).
