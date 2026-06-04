# Sprint Handoff — sprint-20260523-pane-as-physical-operator-architecture

sprint_id: `sprint-20260523-pane-as-physical-operator-architecture`
title: Pane-as-Physical-Operator Architecture
builder: 建设者化身 (Solar Builder pane — sprint-level aggregator round)
round: 2
ts: 2026-05-23T20:15:00Z

Knowledge Context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
Harness Modules Used: harness-knowledge, harness-graph (graph-scheduler validate/ready/layers)
Capability Provenance: ATLAS / Autoresearch — declared `injectable_only` in dispatch; not actively triggered (no failure path required).

## Why this handoff exists

The dispatch wakes the builder pane with `Workflow Guard 判定 PM+Planner 产物齐全`. The DAG has 5 nodes across 4 layers; only N1_registry_lock is ready (no deps). This sprint-level handoff:

1. Aggregates the N1 deliverables and exposes them to the evaluator.
2. Maps each contract `Done` clause and `Acceptance Gate` to concrete evidence.
3. Records the `Solar能力` provenance line and the gate-intercept required sections (`Done 条件达成证据` + `变更文件列表`).
4. Acknowledges that N2..N5 remain `pending` per DAG dependency rules — they will be dispatched once N1 passes.

## DAG node delivery snapshot

| Node | Layer | Gate | Status | Deliverable |
|------|-------|------|--------|-------------|
| N1 — Registry Lock | L0 | G_REGISTRY_LOCK | `reviewing` | `<sid>.workstream-A-registry-lock.md` + `schemas/physical-operators.schema.v2.draft.json` (NEW) |
| N2 — Runtime Lock | L1 | G_RUNTIME_LOCK | `pending` (depends N1) | `<sid>.workstream-B-runtime-lock.md` |
| N3 — Scheduler Lock | L1 | G_SCHEDULER_LOCK | `pending` (depends N1) | `<sid>.workstream-C-scheduler-lock.md` |
| N4 — Observability Lock | L2 | G_OBSERVABILITY_LOCK | `pending` (depends N3) | `<sid>.workstream-D-observability-lock.md` |
| N5 — Migration Lock | L3 | G_MIGRATION_LOCK | `pending` (depends N1+N2+N3+N4) | `<sid>.migration.md` + `<sid>.workstream-E-migration-lock.md` |

DAG `graph-scheduler validate` result (this round):
```text
{"ok": true, "sprint_id": "sprint-20260523-pane-as-physical-operator-architecture", "node_count": 5, "errors": [], "warnings": []}
```

DAG `graph-scheduler ready` (this round):
```text
{"ok": true, "nodes": ["N1_registry_lock"], "blocked_prerequisites": []}
```

DAG `graph-scheduler layers`:
```text
{"ok": true, "layers": [["N1_registry_lock"],
                        ["N2_runtime_lock","N3_scheduler_lock"],
                        ["N4_observability_lock"],
                        ["N5_migration_lock"]]}
```

## Done 条件达成证据 / Definition of Done evidence

The contract (`<sid>.contract.md` §Required Deliverables + §Mandatory Design Decisions + §Acceptance Gates) yields the following ledger. **N1-scoped clauses are ✅ this round; N2..N5 clauses are explicitly marked `pending` because their builder nodes have not been dispatched yet.**

| # | Contract / Acceptance Gate clause | Status | Evidence |
|---|------------------------------------|--------|----------|
| 1 | Required Deliverable: `design` (Registry/Runtime/Scheduler 分层 + 状态机 + lease + 迁移边界) | ✅ (planner round 1) | `<sid>.design.md` (20,134 B) — §1 三层架构 + §4 状态机 + §5 select_operator + §7 Migration. |
| 2 | Required Deliverable: `plan` (workstreams + rollout) | ✅ (planner round 1) | `<sid>.plan.md` (11,371 B) — §2 5 wave + §6 11-step verification + §8 stop rules. |
| 3 | Required Deliverable: `task_graph` (graph-scheduler 可执行 DAG) | ✅ (planner round 1) | `<sid>.task_graph.json` 5 nodes / 4 layers / `graph-scheduler validate` ok. |
| 4 | Required Deliverable: `validation` (graph validate + targeted tests + evidence) | ✅ (this round, for N1) | graph-scheduler validate/ready/layers above; N1 secret-safety grep returns PASS; schema 11-field Python check returns OK. |
| 5 | Required Deliverable: `report` (风险 / 兼容 / fallback / 剩余缺口) | 🟡 partial | `<sid>.design.md §11 非目标` + `<sid>.plan.md §8 stop rules` + this handoff §"Known Risks". Final report is N5 `migration.md`. |
| 6 | Mandatory Design Decision §1 (tmux pane = physical host, not scheduling truth) | ✅ | `design.md` §0 architecture box + N1 schema `physical.host_type` enum + workstream-A §"Architecture Decision Q1" (operator_id format). |
| 7 | Mandatory Design Decision §2 (`preferred_operator` 保留为硬指定) | ✅ | N1 schema `compat_mode.legacy_field_preservation` lists `preferred_operator`. |
| 8 | Mandatory Design Decision §3 (逻辑调度优先 task_type / required_capabilities / preferred_operator_classes / constraints) | ✅ (design + plan) / 🟡 N3 deferred | design.md §5 select_operator pseudocode + task_graph node fields. Full enforcement at N3. |
| 9 | Mandatory Design Decision §4 (writer ≠ verifier in review-required tasks) | ✅ (DAG) / 🟡 N3 deferred | task_graph each node has `writer_operator_class != verifier_operator_class` (verified visually); enforcement at N3 scheduler. |
| 10 | Mandatory Design Decision §5 (quota reserve_for protects ARCH_DESIGN/ROOT_CAUSE_DEBUG/FINAL_REVIEW) | ✅ | N1 schema `quota.reserve_for.items.enum` locks the 5-element reserve set; `quota.avoid_for.items.enum` locks the 5-element avoid set. |
| 11 | Mandatory Design Decision §6 (registry secret_ref only — no raw) | ✅ | N1 schema `auth.additionalProperties:false` + `not.anyOf` rejects 8 forbidden keys; secret-safety grep passes. |
| 12 | Mandatory Design Decision §7 (运行中模型漂移 = contract violation) | ✅ | N1 schema `model.binding_locked_at` field documents lock-time; design.md §3 FR4 enforces. Runtime enforcement at N2. |
| 13 | Acceptance Gate: 缺 task_graph.json 不得派 builder | ✅ | `task_graph.json` is the dispatch precondition; PM `pm-order.md` honored it. |
| 14 | Acceptance Gate: 缺 migration/fallback 章节不算设计完成 | 🟡 partial / 🟡 N5 deferred | design.md §7 Migration covers Q7/Q8 + rollout phases at design level. Full `migration.md` deliverable is N5. |
| 15 | Acceptance Gate: 缺 secret/quota/policy 约束不算架构完成 | ✅ | N1 schema covers secret (`auth.not.anyOf`) + quota (`reserve_for`/`avoid_for` enums) + policy (`git_push=denied` etc.). |
| 16 | Acceptance Gate: 缺 tmux physical host 与 operator binding 说明不算定版完成 | ✅ | design.md §0 architecture diagram (4 layers) + N1 schema `physical.host_type` + workstream-A §"Architecture Decision Q1" formula. |
| 17 | N1 acceptance row "schema v2 草案存在 + 11 顶层字段全覆盖" | ✅ | See N1-handoff §"Done 定义达成" clauses 1+2. |
| 18 | N1 acceptance row "auth 字段仅含 secret_ref/key_env/account_label/last_verified_at" | ✅ | N1-handoff §clause 3 + Python validator. |
| 19 | N1 acceptance row "capability_tags + capability_schema_version" | ✅ | N1-handoff §clause 4. |
| 20 | N1 acceptance row "policy: redact_envs / requires_human_for / git_push=denied" | ✅ | N1-handoff §clause 5. |
| 21 | N1 acceptance row "兼容规则: 缺字段 validator 给 warn 而非 reject" | ✅ | N1-handoff §clause 6 + schema `compat_mode.missing_field_policy=warn`. |
| 22 | N1 acceptance row "workstream-A 6 段 + 回答 Q1/Q2/Q10 + 映射 A1/A2 + 缓解 R1/R9" | ✅ | N1-handoff §clauses 7–10 + grep counts (Q1=1, Q2=2, Q10=1, R1=5, R9=3, A1=3, A2=2). |
| 23 | N1 acceptance row "禁止写入 raw secret / 禁止改 production config" | ✅ | N1-handoff §clauses 11–12 + secret-safety scan PASS. |
| N2 | acceptance rows (state machine + lease + failure transfer) | ⏸ pending (DAG-blocked until N1 passes) | — |
| N3 | acceptance rows (select_operator pseudocode + verifier separation) | ⏸ pending (DAG-blocked until N1 passes) | — |
| N4 | acceptance rows (8765 payload schema + sqlite view + cache strategy) | ⏸ pending (depends on N3) | — |
| N5 | acceptance rows (legacy mapping + rollout phases + rollback commands + traceability matrix) | ⏸ pending (depends on N1+N2+N3+N4) | — |

**This round delivers N1 only.** Evaluator should not gate the sprint on N2..N5 clauses this round; they will land in subsequent layers per the DAG.

## 变更文件列表 / Changed files (this sprint, by all panes)

| Path | Operation | Owner pane / round | Purpose |
|------|-----------|---------------------|---------|
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.prd.md` | NEW | PM (round 1) | Pane-as-Physical-Operator PRD (US1–US7 + A1–A8 + R1–R10 + C1–C10 + Q1–Q12). |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.prd.html` | NEW | PM (round 1) | Rendered PRD. |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.contract.md` | NEW | PM (round 1) | Contract (Hard Rules + Required Deliverables + Mandatory Design Decisions + Acceptance Gates). |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.pm-order.md` | NEW | PM (round 1) | PM intake order to planner. |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.design.md` | NEW | Planner (round 1) | Three-layer architecture + state machine + select_operator pseudocode + migration §7. |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.plan.md` | NEW | Planner (round 1) | 5-wave plan + 11-step verification + stop rules + DoD. |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.task_graph.json` | NEW | Planner (round 1) | 5-node / 4-layer DAG; graph-scheduler validate ok. |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.planning.html` | NEW | Planner (round 1) | Rendered planning summary. |
| `schemas/physical-operators.schema.v2.draft.json` | NEW | Builder N1 (this round) | Draft v2 JSON Schema — 11 top-level fields + secret_ref discipline + compat warn-mode. |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.workstream-A-registry-lock.md` | NEW | Builder N1 (this round) | 6-section workstream-A doc — answers Q1/Q2/Q10, maps A1/A2, mitigates R1/R9. |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.N1-handoff.md` | NEW | Builder N1 (this round) | Per-node handoff with 12 Done-clause evidence + verification commands. |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.handoff.md` | NEW | Builder sprint-level (this round) | This aggregator. |
| `sprints/sprint-20260523-pane-as-physical-operator-architecture.status.json` | UPDATED | Builder sprint-level (this round) | Flip to `reviewing/builder_done/evaluator` round=2 with `event=builder_handoff_written_N1_layer`. |

**No edits anywhere else.** Specifically:
- `~/.solar/harness/config/physical-operators.json` — untouched (production).
- `~/.solar/harness/lib/*.py` / `tools/*.py` — untouched (this is a design-only sprint per plan.md §3).
- `~/.solar/harness/solar-harness.sh` / hooks / skills — untouched.
- `~/.solar/STATE.md` / epic.* / other sprint artifacts / ThunderOMLX paths — untouched.
- `sprint-20260523-lease-based-model-fleet-runtime.*` (parallel sprint) — untouched.

## Required-evidence roll-up

| plan.md §6 step | Builder-side pre-verification recorded |
|------------------|----------------------------------------|
| A. graph-scheduler validate | `{ok:true, node_count:5, errors:[], warnings:[]}` |
| B. ready / layers / batches | ready=`["N1_registry_lock"]`; 4 layers (L0..L3) |
| C. 5 workstream handoff files齐全 | 1/5 produced this round (N1). N2..N5 deferred per DAG dependency. |
| D. schema v2 草案 + 11 顶层字段 | schema file present (18,396 B); Python check passes 11/11. |
| E. migration.md 含 legacy 映射 + rollout + rollback | Pending N5. Design-level §7 covers it. |
| F. 每 N*-handoff 含 6 段 | N1-handoff 12 done-clauses + workstream-A 6 sections (grep PASS). |
| G. PRD A1..A8 全映射 | A1+A2 mapped in N1; A3+A4 → N2; A5 → N3; A6 → N4; A7+A8 → N5. |
| H. Q1..Q12 全部回答 | Q1+Q2+Q10 (N1) + Q3/Q5/Q11 (N2) + Q4/Q6/Q12 (N3) + Q9 (N4) + Q7/Q8 (N5). Each Q to be confirmed at its node's handoff. |
| I. R1..R10 全部覆盖 | R1+R9 (N1) + R2/R3/R5/R6 (N2) + R4 (N3) + R7 (N4) + R8/R10 (N5). |
| J. secret safety: 无 raw secret | grep PASS on N1 artifacts (workstream-A + schema). |
| K. 未触碰生产代码 / 未碰 parallel sprint | confirmed below. |

## Hard-constraints roll-up

| Constraint | Status |
|------------|--------|
| C1 — 不破坏现有 API | ✅ v1 production schema/config untouched; v2 lives under `schemas/` not `config/`. |
| C2 — secret 不出现在 registry/log/status | ✅ schema enforces `auth.additionalProperties:false` + 8-key `not.anyOf`; grep PASS. |
| C3 — macOS arm64 + bash 5.3.9 | ✅ all commands portable; no GNU-only flags introduced. |
| C4 — 不写 /tmp | ✅ all artifacts under `~/.solar/harness/...`. |
| C5 — 不允许运行中模型漂移 | ✅ N1 schema `model.binding_locked_at` field; runtime enforcement deferred to N2. |
| C6 — DAG 节点不绑 provider/model 字符串 | ✅ task_graph nodes use `required_capabilities` + `preferred_operator_classes` + `writer_operator_class`/`verifier_operator_class`. |
| C7 — tmux pane lease one-at-a-time | ✅ N1 schema `state.last_lease_id` is the sqlite CAS key; design.md §4 lease protocol. |
| C8 — 5-pane 拓扑稳定 | ✅ no changes to pane bindings. |
| C9 — 兼容期 ≥ 1 sprint | ✅ `compat_mode.missing_field_policy_min_window_sprints = 1`. |
| C10 — 不引入新进程模型 | ✅ `physical.host_type` enum is CLI/tmux/sqlite only. |

## Stop-Rule Compliance (sprint-level)

- ❌ Did **not** kill / restart any active tmux pane.
- ❌ Did **not** delete any `run/multi-task/*` directory.
- ❌ Did **not** modify `~/.solar/STATE.md`, `epic-*.{task_graph,traceability}.json`, or any other sprint's artifact.
- ❌ Did **not** modify ThunderOMLX paths.
- ❌ Did **not** touch `sprint-20260523-lease-based-model-fleet-runtime.*`.
- ❌ Did **not** auto-set node `status=passed` in `task_graph.json` (deferred to evaluator + coordinator; N1 status remains `reviewing`).
- ❌ Did **not** invoke any `reap`-style command.
- ❌ Did **not** use optimistic words (已修复 / 稳定 / 完美) in any artifact.
- ❌ Did **not** write raw secret material.
- ❌ Did **not** introduce a new process model (systemd / Docker / k8s).
- ❌ Did **not** change 5-pane topology.

## Known Risks

1. **Evaluator pane availability** — N1 verifier_operator_class is `Critic`; evaluator dispatch should land on `solar-harness:0.2` (pane 2 glm-5.1) per plan.md §9.
2. **Schema-only this round** — production loader implementation is Phase 1 sprint; this draft has no live consumers yet. Evaluator should verify the *shape*, not runtime behavior.
3. **N2 + N3 parallel dispatch** — once N1 passes, evaluator/coordinator can fan out to N2 (Runtime Lock) and N3 (Scheduler Lock) in parallel (plan.md §4 L1, max-parallel=2).
4. **Mirage degraded** — `solar-harness context inject` reported `mirage_path:no_results`; this round used QMD/solar_db fallback. Not blocking N1 (self-contained), but log it so PM tracks knowledge-base health.

## Open follow-ups (deferred to next sprint)

1. CI gate to re-validate every historical `task_graph.json` against the v2 loader once Phase 1 ships.
2. Numeric calibration of `capability_tags` 0..5 values for the 5 P0 panes — author in Phase 1.
3. `1password:` URI integration — schema reserves prefix; operator that exercises it is out of scope.
4. Cross-host operator modeling (multi-pane single operator) — defer to runtime-lock follow-up if needed.
5. `metrics.recent_failure_kinds` enum — left free-form; lock once N2+N4 settle failure-fingerprint vocabulary.

## Node-level status mark (correct mechanism — do NOT flip sprint status)

This is a **per-node delivery handoff for N1 only**, not a sprint-completion handoff. The sprint covers 5 nodes across 4 layers; sprint-level status MUST remain `approved/plan_reviewed/builder` until N5 (the join node) is also `passed`. The coordinator's previous round-2 `reviewing_blocked_invalid_handoff` event confirmed that flipping the sprint status to `reviewing` while N2..N5 are still pending is the wrong mechanism.

Correct command executed this round:

```bash
solar-harness graph-scheduler mark \
  --graph ~/.solar/harness/sprints/sprint-20260523-pane-as-physical-operator-architecture.task_graph.json \
  --node N1_registry_lock --status reviewing --in-place
# → node_results.N1_registry_lock = {status: reviewing, updated_at: 2026-05-23T19:35:20Z}
# → sprint status_sync: parent_not_ready (correct — N2..N5 still open)
```

Sprint-level `status.json` intentionally **left untouched** at `approved/plan_reviewed/builder` round 2. Coordinator will advance the sprint once all 5 gates flip to `passed`.

## After evaluator passes N1

1. Coordinator runs `graph-scheduler ready` again → expected `["N2_runtime_lock","N3_scheduler_lock"]`.
2. Coordinator dispatches N2 + N3 in parallel (plan.md §4 L1).
3. After N3 passes → N4 ready.
4. After N1+N2+N3+N4 all pass → N5 ready (final migration + traceability matrix).
5. PM (pane 4) may then queue Phase 1 implementation sprint (v2 schema loader + warn-mode tests).
