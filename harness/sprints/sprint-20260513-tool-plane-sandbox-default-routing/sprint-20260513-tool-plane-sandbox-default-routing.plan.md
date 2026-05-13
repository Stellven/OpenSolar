# Plan — Tool Plane Sandbox Default Routing

Sprint: `sprint-20260513-tool-plane-sandbox-default-routing`
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

> Use this plan with `design.md` (architecture) and the PRD (acceptance). Plan = execution; design = why; PRD = what.

## 1. DAG

```text
R0 inventory  ──┬── R1 QMD / data-search route       ──┐
                └── R2 Document extraction route     ──┴── R3 activation proof + status + regression ── R4 closeout
```

Five nodes, two gates run in parallel, single join at R3, doc-only tail at R4.

## 2. Node-by-Node Execution

| Node | Goal | Depends | Preferred Model | Cost | Gate |
|------|------|---------|-----------------|------|------|
| R0 | Inventory + classify all `subprocess.run` call sites | — | glm | 1.0 | inventory-pass |
| R1 | Migrate QMD/data-search CLI path or prove excluded | R0 | glm | 2.0 | qmd-tool-pass |
| R2 | Migrate document-extraction smoke or prove excluded | R0 | anthropic-sonnet | 2.0 | document-tool-pass |
| R3 | Activation proof + status UI + 5 regression tests | R1, R2 | glm | 1.5 | activation-pass |
| R4 | Closeout docs + parent readiness report | R3 | anthropic-sonnet | 1.0 | docs-pass |

Total estimated cost: 7.5 units.

## 3. Parallelism

- **R1 ∥ R2** after R0. Write scopes are disjoint:
  - R1 writes `lib/qmd_adapter.py`, `lib/mirage_search.py`, `tests/storage/test-s3-storage.sh`, `tests/test-solar-kb-qmd-fallback.sh`.
  - R2 writes `lib/wiki-upload-extract.py`, `lib/wiki-upload-backfill.py`, `tests/test-wiki-upload-ingest-closure.sh`.
- **R3 join** requires both R1 and R2 to emit a verdict (`migrated` or `excluded`). One node stuck `pending` → R3 holds.
- **R4** is closeout only; cannot start until R3 emits an honest activation-proof verdict (`pass` or explicit `warn/pending` with reasons).

## 4. Dispatch Batches

Current `dispatch_batches.json` only declares batch-1 (R0). After R0 closes:

- `batch-2` should declare `nodes: [R1, R2]` with `join_gate: [qmd-tool-pass, document-tool-pass]`.
- `batch-3` should declare `nodes: [R3]` with `join_gate: [activation-pass]`.
- `batch-4` should declare `nodes: [R4]` with `join_gate: [docs-pass]`.

Graph scheduler is expected to expand batches as upstream gates close; if expansion does not happen automatically, planner appends batches via `solar-harness dag schedule --append` (or equivalent) before each transition.

## 5. Routing Policy

- **Tool/data-plane user commands** → prefer `SandboxHand` argv mode.
- **Control-plane side effects** (tmux/ssh/rsync/launchctl/status-server lifecycle/test-runner orchestration) → host-direct; document why in `inventory.md`.
- **Long-running background workers** (QMD embed) → sandbox the smoke/control path only, never the full embed run.

## 6. Honest Activation Proof (Hard Rule)

Every migrated path must emit `executor=sandbox`, `execution_mode=argv`, `evidence_file=<path>`. Activation proof gate must:

- `ok` only when all three present and `evidence_file` exists, non-empty.
- `warn` when path is migrated but evidence is partial.
- `pending` when path is intentionally not migrated yet (with reason).
- **fail** when a previously-migrated path regressed to host execution.

No fake `ok`. R3 acceptance hardcodes this.

## 7. Regression Test Pinning (D6 Gap Fix)

PRD D6 lists 5 regression tests but they live in §Required Verification, not as an explicit node gate. **Plan pins them as R3 join-gate requirements**:

```bash
bash ~/.solar/harness/tests/runtime/test-hands-runtime.sh
bash ~/.solar/harness/tests/test-status-capability-health-projection.sh
bash ~/.solar/harness/tests/test-mirage-substrate.sh
bash ~/.solar/harness/tests/test-mirage-unified-vfs.sh
bash ~/.solar/harness/tests/plugins/test-ruflo-integration.sh
```

All five must exit 0 before R3 closes. Evaluator must cite each test's exit status in the eval report.

## 8. Exit Criteria

- All 5 task_graph gates pass: `inventory-pass`, `qmd-tool-pass`, `document-tool-pass`, `activation-pass`, `docs-pass`.
- `solar-harness integrations activation-proof --json` reports honest verdict (no fake `ok`).
- All 7 PRD deliverables present:
  - `reports/tool-plane-sandbox-routing/inventory.{json,md}`
  - `reports/tool-plane-sandbox-routing/qmd-route.{json,md}`
  - `reports/tool-plane-sandbox-routing/document-route.{json,md}`
  - `reports/tool-plane-sandbox-routing/closeout.{json,md}`
  - `reports/capability-activation-proof-latest.json` (updated)
  - `_raw/solar-harness-local-disposable-sandbox-assessment-20260513.md` (appended)
  - `_raw/tool-plane-sandbox-default-routing-closeout-20260513.md` (new)
- Parent readiness report ends with `evaluator_can_review: yes`.

## 9. Stop Rules (inherited from PRD)

- Any `tmux`/`ssh`/`rsync`/`launchctl`/status-server-lifecycle/test-runner-orchestration routed through `SandboxHand` → stop.
- Foreground QMD embedding → stop.
- Claim of "full kernel isolation" → stop.
- `write_scope` exceeded without scope-change note → stop.

## 10. Handoff

This plan closes the Planner phase. Next handoff: **graph scheduler** dispatches batch-1 (R0) to the builder pane. Contract `Bypass_PM` and `Handoff_to` fields must be reconciled (see contract update) before dispatch fires.
