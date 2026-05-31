# Design — RawIntent Consumer Smoke (entrypoint_metadata variant)

Sprint: `sprint-20260525-155416-intent-entrypoint_metadata-c7d24d4b`
Intent: `intent-20260525-155416-c7d24d4b84` (channel=`pm_dispatch`, device=`mac_mini_pm_dispatch`, smoke=`1779724456`)
Author: Planner (solar-harness:0.1, opus 4.7)
Authored-At: 2026-05-29T07:38:00Z
Dispatch: `d-20260529T073516Z-9e93f9`

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-intent (reusing existing intent capture)

> **Sprint nature:** This is a **PM dispatch entrypoint trusted-auto-planner-handoff smoke test**, not a real feature delivery. The RawIntent `[entrypoint_metadata]` is a placeholder verifying that `channel=pm_dispatch` can drive the full Solar-Harness compile chain end-to-end. 14 auto-generated artifacts already exist (raw_intent → requirement_ir → rewritten_intent → product-brief → PRD → contract → Contracts.yaml → task_graph → coverage_report → acceptance_verdict → handoff). PM has fixed PRD schema 4 sections in a prior pass. This Planner pass produces the **design / plan / planning.html** artifacts that the coordinator gate now expects from the planner role.

---

## 1. Architecture Overview

The unit-under-test is the **PM dispatch entrypoint** itself — a channel adapter that converts a user request into a fully compiled, dispatchable Solar-Harness work item. Validation is structural (does the chain produce all 14 artifacts? does each step pass its gate?), not functional (the intent text is placeholder).

```
┌───────────────────────────────────────────────────────────────────────────┐
│            pm_dispatch entrypoint (channel under test)                     │
│                                                                            │
│  user @ mac_mini_pm_dispatch ──▶  raw_intent.json                          │
│                                          │                                  │
│                                          ▼                                  │
│                                  requirement_ir.json (v1)                  │
│                                  schema_version=solar.requirement_ir.v1    │
│                                  source.channel=pm_dispatch                │
│                                          │                                  │
│                          ┌───────────────┼───────────────┐                  │
│                          ▼               ▼               ▼                  │
│              rewritten_intent.json  product-brief.md  requirement_trace.json│
│                          │               │               │                  │
│                          └───────┬───────┴───────┬───────┘                  │
│                                  ▼               ▼                          │
│                              prd.md  +  Contracts.yaml  +  contract.md      │
│                                  │                                          │
│                                  ▼                                          │
│                          task_graph.json (5-node template)                  │
│                                  │                                          │
│                                  ▼                                          │
│                          coverage_report.json                              │
│                                  │                                          │
│                                  ▼                                          │
│                          acceptance_verdict.json                          │
│                                  │                                          │
│                                  ▼                                          │
│                              handoff.md (solar-harness planner handoff)    │
└───────────────────────────────────────────────────────────────────────────┘
```

### Artifact inventory (read scope — do not mutate)

| Artifact | Purpose | Source-of-truth role |
|----------|---------|----------------------|
| `<sid>.raw_intent.json` | Captured user intent (redacted) | input |
| `<sid>.requirement_ir.json` | **Single source of truth** for all derived views | canonical |
| `<sid>.rewritten_intent.json` | Deterministic rewrite of objective | derived view |
| `<sid>.requirement_trace.json` | Traceability map intent ↔ requirements | derived view |
| `<sid>.product-brief.md` | PM-facing brief | derived view |
| `<sid>.prd.md` | PRD (PM-augmented to 11 schema sections) | derived view |
| `<sid>.prd.html` | PRD visual artifact | derived view |
| `<sid>.contract.md` | Compiled contract (markdown view) | derived view |
| `<sid>.Contracts.yaml` | Canonical structured contract | canonical (per contract.md note) |
| `<sid>.task_graph.json` | Standard 5-node template (S1-S5) | canonical execution plan |
| `<sid>.coverage_report.json` | Acceptance coverage check (REQ ↔ node) | gate input |
| `<sid>.acceptance_verdict.json` | PASS/FAIL verdict on coverage | gate output |
| `<sid>.handoff.md` | Planner handoff stub | input to Planner |
| `<sid>.dispatch.md` + `.intent.json` + `.runtime-context.json` | Dispatch metadata | telemetry |

### What this Planner pass adds (write scope)

| New artifact | Purpose |
|--------------|---------|
| `<sid>.design.md` (this file) | Architecture + smoke-test framing + read/write boundaries |
| `<sid>.plan.md` | Delivery slice / write scope / concurrency / verification / stop rules |
| `<sid>.planning.html` | Visual planning artifact (richer visual system, registered via html_artifact.py) |
| `<sid>.task_graph.json` (augmented in-place) | Added `write_scope`, `required_capabilities`, `required_skills`, `preferred_model`, `architecture_policy` to clear scheduler warnings; preserved upstream `requirement_ids`, `acceptance_ids`, `capsule_plan`, gate map |

### Hard invariants

- **Requirement IR is the only source of truth** (contract §Interface). PRD / contract / DAG / handoff are derived views; never modify in this Planner pass.
- **No raw secrets surface** anywhere in produced artifacts; raw_intent is already redacted upstream.
- **No bypass to builder**: handoff routes through planner explicitly (Acceptance: "No direct builder dispatch from raw request").
- **Acceptance coverage gate**: REQ-000..REQ-003 must map to at least one node each in `task_graph.nodes[*].requirement_ids` (already satisfied — see §4).
- **Planner write scope is closed**: only the 4 new artifacts above; existing 14 are read-only.

---

## 2. DAG (S1-S5 standard template)

```
        ┌────┐
        │ S1 │  DeepArchitect  — design / lock implementation approach
        │PLAN│  capsule: cap.requirement-compiler-planner
        └─┬──┘  preferred: mini-claude-opus-planner
          │
          ▼
        ┌────┐
        │ S2 │  ImplementationWorker — produce patch within declared write scope
        │IMPL│  capsule: cap.requirement-compiler-implementation
        └─┬──┘  preferred: mini-claude-sonnet-builder
          │
          ▼
        ┌────┐
        │ S3 │  TestRunner — run verification commands and collect evidence
        │TEST│  capsule: cap.requirement-compiler-verification
        └─┬──┘  preferred: mini-claude-opus-evaluator
          │
          ▼
        ┌────┐
        │ S4 │  Verifier — independent review + closeout decision
        │REV │  approval_gate=true; parallelizable=false
        └─┬──┘  preferred: mini-claude-opus-evaluator
          │
          ▼
        ┌────┐
        │ S5 │  Critic — migration / compatibility / rollout notes
        │RUN │  approval_gate=true; parallelizable=false
        └────┘  preferred: mini-claude-opus-evaluator
```

- **Strictly sequential**: every edge is `depends_on` linear. No parallel branches in this template — by design (each step's output feeds the next).
- **Gate alignment**: S1→`G_PLAN`, S2→`G_IMPL`, S3→`G_VERIFY`, S4+S5→`G_REVIEW`.
- **Approval gates**: S4 and S5 have `approval_gate=true` (rollout-adjacent steps need human sign-off).
- **Operator-level forbidden list**: every capsule_plan declares `forbidden=[mini-antigravity-gemini35-flash-high]` — consistent vendor exclusion across nodes (likely operator-quality policy from the requirement compiler).

### Concurrency boundary

- S1 / S2 / S3 are marked `parallelizable=true` at the **template** level, but `depends_on` makes them serial in *this* sprint. The flag means "these node types can be parallelized in larger DAGs that branch them"; here, the chain is linear because each step consumes the previous one's output.
- S4 / S5 are explicitly `parallelizable=false` (review/rollout must serialize).

### Capsule plan preserved

Each node carries an upstream-generated `capsule_plan` with `capability_capsule_id`, `selection_mode=logical_operator_default`, `required_guard_capsules=[guard.secret-leak-guard]`, `required_resource_capsules`, `selected_skills`, and `operator_constraints`. This Planner pass **did not modify** capsule_plan; it only added scheduler-required fields (write_scope, required_capabilities, etc.).

---

## 3. Online exploration alternatives (and why rejected)

Per system rule "≥2 candidates + kill_criteria":

| Candidate | Idea | Kill criterion |
|-----------|------|----------------|
| **Picked: preserve 5-node template + augment scheduler fields** | Don't reshape the auto-generated DAG; only fix what graph-scheduler warned about | Honors PM constraint "不动其他 14 份自动产物"; minimal blast radius; sustains smoke-test purpose |
| Collapse S4 + S5 into one review node | Faster | Killed: distinct capsule_plans + distinct gates `G_REVIEW` (S4=Verifier vs S5=Critic) — they're different operator profiles |
| Re-parallelize S1 + S2 + S3 (branch DAG) | More throughput | Killed: each step's `inputs` references previous step's `outputs`; would break data dependency |
| Replace placeholder requirement text with synthesized real intent | Make smoke test more lifelike | Killed: intent text is `[entrypoint_metadata]` deliberately — verification is structural, not semantic; synthesizing would mask real entrypoint bugs |
| Skip writing design/plan/planning.html since "nothing to do" | Save effort | Killed: PM handoff explicitly requires Planner to produce design.md + plan.md; coordinator gate expects them; this is the smoke test purpose |

---

## 4. Requirement → Node coverage

Source: `requirement_ir.json` declares 4 REQs (REQ-000..REQ-003 inferred from task_graph + coverage_report — REQ-000 is the meta requirement, REQ-001..REQ-003 derive from PRD §5 Functional Requirements).

| Requirement (from IR) | Description (from PRD §5) | S1 | S2 | S3 | S4 | S5 |
|------------------------|---------------------------|:--:|:--:|:--:|:--:|:--:|
| REQ-000 | PRD/contract/TaskDAG互相对齐 (alignment meta) | ● | | | ● | ● |
| REQ-001 | 实施、验证、兼容/发布路径已显式表达 | ● | ● | ● | ● | ● |
| REQ-002 | 每条验收标准都能追溯到验证或 gate | ● | ● | ● | ● | ● |
| REQ-003 | 与现有 PM→Planner→Builder 主链兼容 (§6) | ● | ● | ● | ● | ● |
| ACC-S1-1 (S1 acceptance) | Implementation path/constraints explicit | ● | | | | |
| ACC-S2-1 (S2 acceptance) | Patch within declared write scope | | ● | | | |
| ACC-S3-1 (S3 acceptance) | Verification evidence attached | | | ● | | |
| ACC-S4-1 (S4 acceptance) | Verifier decision machine-readable | | | | ● | |
| ACC-S5-1 (S5 acceptance) | Rollout notes explicit | | | | | ● |

**Explanation of REQ-001..REQ-003 broadcast**: REQ-001 to REQ-003 are pipeline-level requirements ("implementation/verification/release paths explicit"; "each acceptance traceable"; "compatible with main chain"). Every node in the standard template *must* satisfy them — they are not feature requirements but pipeline invariants. REQ-000 is the alignment meta-requirement, owned by the design phase (S1) and the review/rollout closeout (S4/S5). This is the **only** broadcast in the map; per-node acceptance ids (ACC-S*-1) provide the distinguishing per-node coverage.

This matches `coverage_report.json` which maps `REQ-000 → mapped_nodes: [S1, S4, S5]` (verified above).

---

## 5. Risks and stop rules (planner view)

| Risk | Trigger | Stop rule |
|------|---------|-----------|
| Planner writes outside scope (mutates 14 auto-generated artifacts) | Accidental file overwrite | Strict whitelist enforced; this pass only writes design.md / plan.md / planning.html and **in-place-augments** task_graph.json (preserving capsule_plan + requirement_ids) |
| Builder dispatched from raw request without Planner artifacts | DAG bypass | handoff.md acceptance: "No direct builder dispatch from raw request"; coordinator gate must require planner artifacts |
| Acceptance coverage regresses (REQ unmapped) | Future template change | `coverage_report.json` is gate input; verdict FAIL on coverage regression should block downstream |
| `acceptance_verdict.json` already FAIL | Coverage says missing=1 (REQ-000 partial since nodes pending) | Expected pre-builder; verdict will re-evaluate after S2/S3/S4 produce evidence. Do NOT manually mutate verdict to PASS |
| Operator forbidden list bypassed | Future quota fallback chooses `mini-antigravity-gemini35-flash-high` | Every capsule_plan declares forbidden array; runtime must honor it |
| Smoke test gets confused with real feature work | Planner reading `[entrypoint_metadata]` as a real product spec | This design + plan clearly mark the sprint as smoke test; downstream tools should detect and downgrade priority |
| Schema gate flap (PRD missing schema sections) | PM template emits PRD without 11 schema sections | OQ-entrypoint-01: future PM dispatch template must default to schema-complete PRD; tracked for follow-up sprint |
| Cross-entrypoint regression | New entrypoint added without smoke coverage | OQ-entrypoint-02: cross-entrypoint smoke matrix; tracked |

---

## 6. Anti-redo / smoke-test posture

This Planner pass produces real artifacts but does **not** authorize a real Builder code dispatch. The proper next step depends on whether the smoke test should continue mechanically through Builder:

- **If smoke includes Builder**: coordinator should dispatch S2 to `mini-claude-sonnet-builder`; Builder produces a smoke patch.diff (the diff content does not matter, only that the artifact path exists and the chain advances).
- **If smoke stops at Planner**: this Planner pass is the terminal step; coordinator should mark planner_plan_completed and close the sprint as smoke-passed without Builder dispatch.

The PRD §架构交接 directs coordinator to continue to Planner downstream (smoke test normal path), and the standard template assumes S2-S5 follow. This Planner pass writes status=`active` / phase=`planning_complete` / handoff_to=`builder_main` per dispatch step 10, so the smoke continues into Builder if coordinator chooses to dispatch.

### Follow-ups (out of scope)

- **OQ-entrypoint-01**: PM dispatch template default-includes PRD 11 schema sections to avoid gate flap (same root cause as `codex_bridge` OQ-bridge-01).
- **OQ-entrypoint-02**: cross-entrypoint smoke matrix covering all channels (pm_dispatch, codex_bridge, cli_intake, antigravity, claude_code, ...).
- **OQ-entrypoint-03**: versioning for `entrypoint_metadata` fields (`actor / device / thread_ref`).
