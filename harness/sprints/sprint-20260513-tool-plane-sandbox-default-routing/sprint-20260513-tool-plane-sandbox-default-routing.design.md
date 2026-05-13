# Design — Tool Plane Sandbox Default Routing

Sprint: `sprint-20260513-tool-plane-sandbox-default-routing`
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

## 1. Problem Framing

Local disposable runtime v2 (`SandboxHand`) already wraps two user-triggered entry points: `solar-harness mirage exec` and Ruflo runtime smoke. Activation proof reports 11/11 PASS. The remaining `subprocess.run` call sites inside `lib/`, `tools/`, `tests/` are unclassified — we cannot tell which are safe to route through `SandboxHand`, which are control-plane side effects (tmux/ssh/rsync), and which are long-running background workers (QMD embed) that must not be foregrounded.

This sprint is an inventory + selective migration, not a sweeping rewrite. It deliberately does **not** introduce kernel-level isolation, network egress policy, or any new sandbox primitive.

## 2. Design Goals

- **Classify before migrating.** Every `subprocess.run` call site gets one of five tags: `tool_plane`, `data_plane`, `control_plane`, `test_only`, `background_worker`.
- **Migrate only the safe cuts.** `tool_plane` and `data_plane` user-triggered paths route through `SandboxHand`. `control_plane` and `background_worker` stay host-direct with documented reasons.
- **Honest activation proof.** Migrated paths emit `executor=sandbox`, `execution_mode=argv`, and `evidence_file`. Paths intentionally excluded or not yet migrated must show as `warn` or `pending` — never fake `ok`.
- **Reversibility-aware.** If a migrated path regresses to naked host execution, activation proof must fail loudly.

## 3. Non-Goals (carried over from PRD §Scope/Out of Scope)

- No tmux / ssh / rsync / launchctl / status-server-lifecycle / test-runner-orchestration routing.
- No foreground QMD embedding.
- No chroot, sandbox-exec/seatbelt, Docker, or OS-level FS isolation.
- No network egress allow/deny list.

These are explicitly v3 concerns.

## 4. Classification Taxonomy

| Tag | Meaning | Sandbox Policy |
|-----|---------|----------------|
| `tool_plane` | User-triggered command that runs an external CLI (search, extraction, conversion) | **Migrate to SandboxHand argv mode** |
| `data_plane` | User-triggered command that reads/writes data assets (QMD search, status, doc upload smoke) | **Migrate to SandboxHand argv + write_guard_roots** |
| `control_plane` | Infra-side effect: tmux pane dispatch, SSH/rsync, launchctl, status server lifecycle, test runner orchestration | **Stay host-direct; document why** |
| `test_only` | Inside `tests/` directory, used only by harness regression | Stay as-is; sandboxing test infrastructure is out of scope |
| `background_worker` | Long-running embed/index jobs (QMD embed) | Smoke/control path only via sandbox; full run stays as background process |

## 5. Evidence Contract

Every migrated path **must** produce three pieces of evidence written to `reports/hands-sandbox-evidence/`:

1. `executor=sandbox` (string) — confirms `SandboxHand` was the runtime.
2. `execution_mode=argv` (string) — confirms argv mode, not shell-string passthrough.
3. `evidence_file=<path>` (string) — points to the per-invocation artifact under sandbox evidence dir.

`capability_activation_proof.py` validates all three on every migrated path. Missing any one → activation proof fails. No `executor` field at all → activation proof reports the path as `regressed_to_host` and fails the gate.

## 6. Migration Strategy per Node

### R0 — Inventory (`gate: inventory-pass`)

Walk `lib/`, `tools/`, `tests/`. For each `subprocess.run` (and `subprocess.Popen`, `os.system` if any), record:

- file:line
- argv pattern (first token + role)
- one of the five tags
- migration verdict: `migrate_now` / `excluded_with_reason` / `pending_with_next_step`

Output three artifacts:

- `reports/tool-plane-sandbox-routing/inventory.json` (machine-readable for downstream nodes)
- `reports/tool-plane-sandbox-routing/inventory.md` (human-readable, sorted by tag)
- `_raw/tool-plane-sandbox-routing-inventory-20260513.md` (mirror to Knowledge for evaluator)

### R1 — QMD / data-search route (`gate: qmd-tool-pass`)

Two acceptable outcomes:

- **Migrated**: at least one CLI/search/status path in `lib/qmd_adapter.py` or `lib/mirage_search.py` switches to `SandboxHand` argv. Evidence file generated. Existing tests in `tests/storage/test-s3-storage.sh` and `tests/test-solar-kb-qmd-fallback.sh` still green.
- **Not safe to migrate**: write `reports/tool-plane-sandbox-routing/qmd-route.{json,md}` explaining the blocker. Add a `warn` or `pending` entry to activation proof, never a fake `ok`.

**Hard line**: no foreground call to `qmd-embed-runner.sh` from inside the sandbox. Embed remains a background worker.

### R2 — Document extraction route (`gate: document-tool-pass`)

Same pattern as R1, applied to `lib/wiki-upload-extract.py` and `lib/wiki-upload-backfill.py`:

- Migrate smoke (small text/markdown fixture) through `SandboxHand` if feasible.
- Otherwise document as `not applicable`. MarkItDown capability remains injectable but never falsely reported as executed.

**Secrets guardrail**: any external-API path must use `secret_refs` + redact. The evidence file must not contain plaintext credentials. Spot-check during evaluator review.

### R3 — Activation proof + status UI (`gate: activation-pass`)

- Extend `capability_activation_proof.py` to validate the evidence contract (§5) on every R1/R2 migrated path.
- Update `lib/symphony/status-server.py` so `/status` exposes the migrated tool sandbox route status.
- Pin the 5 regression tests from PRD §Required Verification as a join-gate before transition to R4:
  - `tests/runtime/test-hands-runtime.sh`
  - `tests/test-status-capability-health-projection.sh`
  - `tests/test-mirage-substrate.sh`
  - `tests/test-mirage-unified-vfs.sh`
  - `tests/plugins/test-ruflo-integration.sh`

### R4 — Closeout (`gate: docs-pass`)

Three-column closeout document with explicit `migrated / excluded-with-reason / pending-with-next-step` tables. Parent readiness report ends with a binary line: `evaluator_can_review: yes|no`.

## 7. Parallelism & Sequencing

```
R0 ──┬── R1 (QMD)        ──┐
     └── R2 (Document)   ──┴── R3 (activation + status + regression) ── R4 (closeout)
```

- R1 ∥ R2 because write scopes are disjoint (`qmd_adapter.py + mirage_search.py` vs `wiki-upload-*.py`).
- R3 joins both; cannot start until R1 and R2 both report a verdict (migrated or excluded). One pending → R3 waits.
- R4 is documentation only; starts once R3 activation proof emits a non-fake verdict.

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Builder marks a not-actually-migrated path as `ok` to pass the gate | R3 acceptance hardcodes "honest verdict"; evaluator spot-checks evidence files exist and are non-empty |
| Migration breaks original env/cwd contract | R1/R2 acceptance requires the existing regression test (storage/fallback/ingest-closure) still green |
| QMD embed gets accidentally foregrounded inside sandbox | R1 acceptance bullet #1 is "no foreground qmd embed is run"; evaluator greps for `qmd-embed-runner.sh` in sandbox argv logs |
| Document path leaks plaintext credentials | R2 acceptance requires `secret_refs + redact`; evaluator spot-checks evidence file for token strings |
| Builder edits outside `write_scope` | task_graph nodes enforce `write_scope`; any expansion needs a scope-change note in node handoff (not silent edit) |

## 9. Rollback / Stop Conditions

If any stop rule in PRD §Stop Rules fires:

1. Builder pauses, writes `handoff.note` describing what tripped the stop rule.
2. Planner re-evaluates whether to descope (move that path to `excluded_with_reason`) or split into a follow-up sprint.
3. No silent rollback — activation proof state must reflect the partial migration honestly.

## 10. Open Decisions Deferred to v3

- OS-level FS isolation (chroot/sandbox-exec/Docker).
- Network egress policy (allowlist/denylist).
- Migrating control-plane paths (tmux/ssh/rsync/launchctl/status server lifecycle/test runner orchestration).

These are out of scope for this sprint and explicitly named in the closeout's `pending-with-next-step` column.
