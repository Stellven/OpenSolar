# Design — Operatord Runtime Submit Foundation

Sprint: `sprint-20260522-operatord-runtime-submit`
Author: Planner (solar-harness:0.1, opus 4.7)
Authored-At: 2026-05-29T06:45:00Z
Dispatch: `d-20260529T064203Z-50785c`

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph

> **Status note:** This sprint's 5 nodes (N1-N5) shipped and were evaluator-PASSED on 2026-05-22T21:00:56Z (file `<sid>.finalized`). N5 verdict snapshot: **50/50 tests pass · persona 10/10 · operator binding 12/12 · lint gate 275 files / 10 ALLOW / 0 DENY · 0 substantive secret-pattern hits**. The Planner artifacts in this turn are a **retrospective schema augmentation** triggered by `graph_parent_ready_revoked` on 2026-05-28T15:08:14Z. No new scope, no new code, no new builder dispatch is being proposed.

---

## 1. Architecture Overview

The shipped system is a **structured task delivery foundation** that replaces ad-hoc `tmux send-keys` with an envelope+lease+inbox pipeline, and gives every physical operator a uniform `operatord` daemon shell. Three layers participate:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          DAG dispatch caller                              │
│                                                                            │
│            operator_runtime.submit(task_envelope: dict) -> dict           │
│                       (Python API + CLI bridge)                            │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
                ▼                 ▼                 ▼
       ┌────────────────┐ ┌───────────────┐ ┌──────────────────┐
       │ Envelope       │ │ Operator      │ │ Lease            │
       │ validator      │ │ availability  │ │ acquisition       │
       │ (schema)       │ │ (disabled/    │ │ (lease broker)    │
       │                │ │  leased/      │ │                  │
       │                │ │  running/     │ │                  │
       │                │ │  quota/auth/  │ │                  │
       │                │ │  unknown)     │ │                  │
       └────────┬───────┘ └───────┬───────┘ └─────────┬────────┘
                │                 │                   │
                └─────────────────┼───────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │ Deterministic inbox path     │
                    │ (per-operator filesystem dir)│
                    │   write envelope file        │
                    │   return                     │
                    │     task_id / operator_id    │
                    │     lease_id / inbox_path    │
                    │     status                   │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                ┌─────────────────────────────────────────┐
                │  operatord run <operator_id>             │
                │  (long-running daemon in operator pane)   │
                │                                          │
                │  1. read operator registry              │
                │  2. resolve secret_ref (no raw logging)  │
                │  3. set canonical pane title              │
                │     [PROVIDER][MODEL][ROLE][CONFIG][IDX] │
                │  4. write heartbeat / state files         │
                │  5. poll operator inbox                   │
                │  6. load persona file                     │
                │     + evaluator-verification-protocol      │
                │       (when role=evaluator)              │
                │  7. launch backend in dry-run / smoke /   │
                │     real (real requires explicit allow)  │
                │  8. capture stdout/stderr → exec logs    │
                │  9. parse quota/auth/runtime errors      │
                │  10. write structured task result         │
                └─────────────────────────────────────────┘

           ┌─────────────────────────────────────────────────┐
           │  Lint gate (FR-7)                                 │
           │  scan ~/.solar/harness/{lib,tools,tests}          │
           │  ban direct tmux send-keys in DAG dispatch code   │
           │  whitelist: approved adapters / startup           │
           │  result: 275 files / 10 ALLOW / 0 DENY (N5)       │
           └─────────────────────────────────────────────────┘
```

### Components (shipped paths)

| Component | Path | Owner Node | Role |
|-----------|------|------------|------|
| Submit API + Python module | `~/.solar/harness/lib/operator_runtime.py` | N2 | `submit(task_envelope)`: validate → check operator availability → acquire lease → write to inbox → return metadata |
| Operatord daemon | `~/.solar/harness/tools/operatord.py` | N3 | `operatord run <operator_id>` — 10 minimum responsibilities (see diagram) |
| Operator naming helper | `~/.solar/harness/tools/operator_naming.py` | N3 | Canonical id parser + pane title canonicalizer |
| CLI wiring | `~/.solar/harness/solar-harness.sh` | N3 | `solar-harness operatord run` + `solar-harness operator-runtime submit` |
| Persona bank | `~/.solar/harness/personas/*.md` (10 files + evaluator-verification-protocol.md) | N1 design + N3 loader | pm, planner, builder, evaluator, architect, lab-builder, lab-evaluator, observer, second-builder, evaluator-verification-protocol |
| Operator registry | `~/.solar/harness/config/physical-operators.json` | N1 model + N5 audit | Each entry binds `persona` to operator; missing persona → `needs_human_review` |
| Submit unit tests | `~/.solar/harness/tests/runtime/test_operator_runtime.py` | N2 | Success + 5 rejection classes + persona-block |
| Naming unit tests | `~/.solar/harness/tests/test_operator_naming.py` | N3 | Canonical id + 4 vendor title examples |
| Lint gate test | `~/.solar/harness/tests/test_no_direct_tmux_send_keys.py` | N4 | Scan 275 files; allowlist approved adapters |
| Final report | `~/.solar/harness/monitor-reports/operatord-runtime-submit.md` | N5 | 11-section acceptance + migration follow-up |

### Data flow (per submit)

1. **Caller** builds a task envelope (YAML/JSON) per FR-3 schema: `task_id / sprint_id / node_id / task_type / objective / constraints / output_contract / verifier`.
2. **`submit()`** validates envelope shape; rejects malformed payload synchronously.
3. **Operator availability check** — rejects 6 states:
   - `disabled`, `leased`, `running`, `quota_exhausted`, `auth_expired`, `unknown`
   - Additionally rejects operators with **missing persona binding** (FR-4 enforcement).
4. **Lease acquisition** — uses lease broker (sibling sprint `sprint-20260523-lease-based-model-fleet-runtime`). On success: returns `lease_id`.
5. **Inbox write** — envelope file dropped at deterministic path under operator's own inbox dir; atomic write.
6. **Return** — `{task_id, operator_id, lease_id, inbox_path, status}` synchronous to caller.
7. **`operatord` polls inbox** — picks up envelope, loads persona file, runs backend (dry-run by default), captures stdout/stderr, writes structured result, releases lease.

### Hard invariants (from contract + PRD)

- `solar-harness multi-task` continues to function (FR-9) — operatord is an additive safe foundation, not a replacement.
- No raw secrets in logs: `secret_ref` resolved only inside daemon process memory; envelope/result/stdout never carry `sk-…`, `ghp_…`, `gho_…`, `gsk_…`, `api_key=…`, or `token=…` substrings (N5 grep: 0 substantive hits).
- Writer ≠ verifier: envelope `verifier.cannot_use_same_operator=true` enforced.
- Direct `tmux send-keys` is **banned** in normal DAG dispatch code; only allowlisted tmux adapter/startup code may use it (FR-7).
- Tmux title application is a no-op outside tmux contexts; safe inside tmux.
- `operatord` defaults to dry-run/smoke mode; real backend execution requires explicit permission.
- Existing `mini-*` operator aliases continue to resolve; canonical `op.*` ids are also accepted.

---

## 2. DAG (delivered)

```
        ┌──────┐
        │  N1  │  design: submit API + operatord contract + inbox layout
        │ ARCH │           + multi-task compat plan + persona bank model
        └──┬───┘
           │ depends_on
     ┌─────┴─────┐
     ▼           ▼
   ┌────┐     ┌────┐
   │ N2 │     │ N3 │   parallel:
   │subm│     │op- │   N2 owns lib/operator_runtime.py + submit tests;
   │ API│     │erd │   N3 owns tools/operatord.py + operator_naming.py
   │    │     │+nam│        + solar-harness.sh wiring + naming tests
   └─┬──┘     └─┬──┘
     └────┬─────┘
          ▼
        ┌────┐
        │ N4 │  lint gate: scan 275 files; allowlist 10
        │LINT│           regression pytest
        └─┬──┘
          ▼
        ┌────┐
        │ N5 │  final report (11 sections) + verdict + migration G1-G8
        │EVAL│
        └────┘
```

- **N1** is the serial root (design before code).
- **N2 ∥ N3** run in parallel: write-scopes are disjoint (`lib/operator_runtime.py` vs `tools/operatord.py` + `tools/operator_naming.py` + `solar-harness.sh` + naming tests).
- **N4** depends on `passed(N2) ∧ passed(N3)` because the lint regression must see the new files in place.
- **N5** is the final report node, joining on `passed(N2) ∧ passed(N3) ∧ passed(N4)`.

### Concurrency safety analysis

| Pair | Write overlap? | Safe? |
|------|----------------|-------|
| N2 ∥ N3 | `lib/operator_runtime.py` vs `tools/operatord.py + tools/operator_naming.py + solar-harness.sh` | ✅ Disjoint; only `solar-harness.sh` is touched by N3 (CLI wiring), N2 doesn't touch it |
| Any other pair | Sequential (depends_on chain) | n/a |

### Architecture guard alignment

- N1: design-only artifact (handoff markdown); no executable boundary required, marked `core_patch_allowed=false`.
- N3: explicit `architecture_policy.package_boundary = "harness/tools/;harness/tests/;solar-harness.sh"`, `core_patch_allowed=true` (CLI router was patched).
- Other nodes inherit boundaries via write_scope arrays.

---

## 3. Online exploration alternatives (and why rejected)

Per system rule "≥2 candidates + kill_criteria":

| Candidate | Idea | Kill criterion |
|-----------|------|----------------|
| **Picked: filesystem inbox + Python daemon** | Per-operator inbox dir; daemon polls; lease broker integration | Already shipped & PASS; minimal new infra (no message broker); compatible with existing `solar-harness` Python stack |
| SQLite-backed inbox queue | Single SQLite table per inbox; daemon `SELECT FOR UPDATE` | Killed for v1: bigger surface, lock semantics tricky on macOS APFS; tracked as OQ-03 for follow-up sprint |
| Redis/NATS broker | Real message queue | Killed: introduces an external service, contract Non-Goal "do not globally install packages" |
| Direct `tmux send-keys` (status quo) | Keep current behavior | Killed by PRD Problem PB-2 + Acceptance "Lint gate finds direct tmux send-keys" |
| Inline `subprocess.Popen` per task | No daemon, fire-and-forget child process | Killed: no persistent role identity (PB-1), no canonical pane title (PB-4), no `secret_ref` resolver boundary (PB-3) |

---

## 4. Requirement → Node coverage

| Requirement | N1 | N2 | N3 | N4 | N5 |
|-------------|:--:|:--:|:--:|:--:|:--:|
| FR-1 operatord CLI daemon | | | ● | | |
| FR-2 submit API + 6 rejections | | ● | | | ● |
| FR-3 task envelope schema | ● | ● | ● | | |
| FR-4 persona bank binding | ● | | ● | | ● |
| FR-5 canonical operator id | ● | | ● | | |
| FR-6 pane title canonicalizer | | | ● | | |
| FR-7 lint gate ban send-keys | | | | ● | ● |
| FR-8 secrets 0-leak | | ● | ● | ● | ● |
| FR-9 don't disturb multi-task | ● | | | | ● |
| FR-10 final report 11 sections | | | | | ● |
| FR-11 PRD schema | (PM/coordinator — not a node) |
| US-01 DAG author UX | ● | ● | | | |
| US-02 operator maintainer | | | ● | | |
| US-03 persona binding enforced | ● | | ● | | ● |
| US-04 pane title uniform | | | ● | | |
| US-05 security audit (lint) | | | | ● | ● |
| US-06 secrets compliance | | | | | ● |
| ACC-DESIGN / PERSONA-MODEL | ● | | | | |
| ACC-SUBMIT-* (4) | | ● | | | |
| ACC-OPERATORD-* (4) | | | ● | | |
| ACC-LINT-* (3) | | | | ● | |
| ACC-REPORT / PERSONA-COVERAGE / NO-SECRETS / NODE-PASSED | | | | | ● |

Every requirement is mapped to ≥1 node; every node carries an explicit `requirement_ids` array in `task_graph.json`. The map is non-trivial (no broadcast).

---

## 5. Risks and stop rules (planner view)

| Risk | Trigger | Stop rule |
|------|---------|-----------|
| Lint gate misfires on legitimate adapter code | Future refactor renames adapter file | Whitelist is data-driven; update allowlist instead of disabling lint |
| Inbox path race (two submits land same name) | High-throughput dispatch | Deterministic path = `<inbox>/<task_id>.envelope.yaml`; task_id includes timestamp+uuid suffix; atomic `tempfile + rename` write semantics |
| Lease broker unavailable | Sibling sprint regression | submit returns `status=unavailable`; does NOT silently dispatch; caller must retry |
| Persona file renamed/removed | Future restructuring | operatord reports structured blocker `needs_human_review`; does NOT dispatch; tracked as OQ-07 |
| `secret_ref` resolution leaks to stderr | Backend cmd prints token | Daemon scrubs known secret patterns before write; N5 §D3 grep verifies 0 hits — repeat as regression test |
| Old `multi-task` path breaks | Code touched outside FR-9 boundary | Lint gate + N5 G1-G8 follow-up plan; operatord is additive, not replacing |
| Tmux title apply throws outside tmux | dispatched on non-tmux host | FR-6 explicit no-op; verified by N3 acceptance |
| Real-mode operatord runs unintended backend | Configuration drift | Daemon defaults dry-run; real mode requires explicit env flag + N5 verification |
| Canonical id ↔ logical_operator namespace collision | Sibling sprint adds overlapping ids | OQ-06 follow-up; not in this sprint's blast radius |
| Verifier same-operator as writer | Configuration drift | Envelope `verifier.cannot_use_same_operator=true` enforced at submit time |

---

## 6. Anti-redo guard

This Planner artifact does **not** authorize a new Builder dispatch. Per PRD §架构交接 / Planner Handoff and §给 Coordinator 的明确指令, the coordinator should:

1. Re-run `validate.sh prd` → PASS (schema-gate flap is being closed via the augmented `task_graph.json` + this design + the new `plan.md`).
2. Re-recognize `<sid>.finalized` → return sprint to `passed`.
3. **Not advance to a fresh planner round**.

If the coordinator nevertheless dispatches Builder, the builder should observe: every node already `reviewing`, every gate already shipped (gate_results show `blocked` due to ready-check, but each gate has node-side evidence and N5 verdict PASS), and produce a no-op handoff that re-states the existing evidence rather than overwrite shipped code.

### G1-G8 migration follow-ups (NOT in this sprint)

Tracked in N5 §7 and PRD OQ-01..OQ-08:
- G1: existing pane migration to `operatord` (OQ-01)
- G2: cross-host inbox via SSH/Tailscale (OQ-04)
- G3: lint gate IDE integration (OQ-05)
- G4: canonical_id ↔ logical_operator namespace integration (OQ-06)
- G5: persona lifecycle / versioning (OQ-07)
- G6: evaluator-verification-protocol ↔ OperatorScore SameProviderVerifierPenalty integration (OQ-08)
- G7: asubmit (async) API (OQ-02)
- G8: inbox upgrade from filesystem to SQLite/queue (OQ-03)
