# Handoff — sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements

Sprint: `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements`
Epic: `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队`
Slice: requirements
Generated: 2026-05-14T15:10:00Z

Knowledge Context: solar-harness context inject used (via dispatch `<solar-unified-context>` injection — Mirage paths + Solar DB hits for sprint-20260508 substrate accepted reference)
Harness Modules Used: solar-graph-scheduler (ready/inspect/mark), Solar-Harness Runtime (contracts/dispatch_visibility), Superpowers (workflow.planning)

---

## Summary

S01 requirements slice delivers three artifacts in one bundle:

1. **`outcomes.md`** (N1) — 5 outcome cards (O1 idle state, O2 autopilot heartbeat + deadlock, O3 PM-first PRD flow, O4 status-page next-step display, O5 transition evidence logging), each with Problem / Acceptance / Risk / Boundary / Dependency / Owner-Sprint / What User Sees / How to Observe fields. Includes Non-Goals section, "cannot directly dispatch to builder" analysis, and an outcome → S02-S05 traceability map.
2. **`non-builder-boundary.md`** (N2) — 9-row governance table (6 forbidden ❌ + 3 allowed ✅ work types) with concrete counter-examples, 3 anti-patterns with detection methods, and a rationale section grounding the boundary in Solar-Harness's multi-role discipline.
3. **`handoff.md`** + **parent `traceability.json` reverse-link patch** (N3, this node) — sprint-level handoff for the evaluator + reverse-linked outcomes on each child sprint entry in the parent epic traceability.

No production code, no schema, no runtime changes. This sprint is a **requirements** slice; all five outcomes are explicitly gated as "Cannot Directly Dispatch to Builder" until S02 architecture completes.

## 5 Outcome → Child Sprint Matrix

| Outcome | Title | S02 architecture | S03 core-runtime | S04 orchestration-ui | S05 verification-release |
|---------|-------|-------------------|--------------------|-----------------------|--------------------------|
| **O1** | Status page shows "No Active Work" when idle | Define idle-state schema + GET /api/status/idle contract | Implement idle detection query (queue empty AND all panes idle) | Render idle state card with last-completed + total-completed + submit prompt | Test idle→active→idle round-trip within ≤30s wake cycle |
| **O2** | Autopilot idle heartbeat + dead-lane detection | Define heartbeat event schema + deadlock detection API (configurable timeout, default 10m) | Implement heartbeat timer (≤1/5min) + dispatch-without-session-start detection | Surface deadlock alert indicator on status page | Test heartbeat cadence + simulated-pane deadlock detection |
| **O3** | PM-first PRD flow on user requirement submission | Define requirement-submission API + PM-phase state machine + PRD-validation heuristic | Implement requirement capture endpoint + PM→planner handoff + sprint-id return | Wire chat/CLI/status-page input → submission; display "in PM phase" + next-step | Test requirement → PRD → planner → task_graph → builder dispatch full chain |
| **O4** | Status UI shows next step for each active sprint | Define sprint-phase schema (PM/drafting/building/reviewing/evaluating/passed/failed) + next-step derivation logic | Implement phase query API derived from session log + task graph node status | Render phase + next-step per active sprint; collapse completed into "Recently Completed" | Test phase display accuracy across full sprint lifecycle |
| **O5** | Transition evidence — sprint state changes are logged and queryable | Define `state_transition` event schema (sprint_id, from, to, ts, actor) + query API | Implement transition logging in coordinator + `solar-harness sprint transitions --sid <id>` CLI + SQLite persistence | Optionally surface transition timeline on status page | Test transition persistence in SQLite + dedup of consecutive same-state + CLI query correctness |

Each row maps 1 outcome to its 4 owning sprints. All 5 outcomes flow through **S02 → S03 → S04 → S05** with no shortcuts; the "Cannot Directly Dispatch to Builder" section in `outcomes.md` enforces this.

## Builder-Direct Boundary Summary

From `non-builder-boundary.md`:

- **7 work types FORBIDDEN ❌** for direct builder dispatch:
  - W1 PM-first PRD flow definition
  - W2 outcome acceptance criteria definition
  - W3 status-page user-facing copy + error messages
  - W4 stop-rule numerical thresholds (heartbeat interval, deadlock timeout)
  - W5 epic close conditions + gate definitions
  - W6 autopilot main loop modifications
  - W7 (alias of W6 if rephrased)
- **2 work types ALLOWED ✅** for builder dispatch via planner task_graph:
  - W8 source-code implementation under planner-approved write_scope
  - W9 status UI routes/templates + unit/integration tests
- 3 anti-patterns documented (AP1 self-dispatch without task_graph, AP2 builder defines acceptance criteria, AP3 builder marks epic/sprint complete without evaluator).

**Implication for downstream sprints**: S02-S04 must explicitly route any work touching W1-W6 through PM or planner gates. S02 specifically owns the **schema/API contract** for each outcome — S03 builders only execute the contract, they do not author it. S05 evaluator must verify that no S02-S04 PR landed any W1-W6 work via builder dispatch (grep node `assigned_to` field + cross-reference dispatch source).

## S02 Evaluator Entry Checklist

The S02 architecture evaluator should verify each of the following before passing any S02 acceptance review. All commands run from `~/.solar`.

### EC1: Confirm S01 requirements artifacts exist and are non-empty

```bash
SP="harness/sprints/sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements"
test -s "$SP.outcomes.md" && echo "outcomes.md ok"
test -s "$SP.non-builder-boundary.md" && echo "non-builder-boundary.md ok"
test -s "$SP.handoff.md" && echo "handoff.md ok"
```

Expected: three "ok" lines.

### EC2: Verify all 5 outcome cards are present

```bash
SP="harness/sprints/sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements"
grep -cE '^### O[1-5]:' "$SP.outcomes.md"
```

Expected: `5`.

### EC3: Verify each outcome has all 5 mandatory fields (Problem/Acceptance/Risk/Boundary/Dependency/Owner-Sprint)

```bash
SP="harness/sprints/sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements"
for f in Problem Acceptance Risk Boundary Dependency Owner-Sprint; do
  count=$(grep -c "^\*\*${f}\*\*" "$SP.outcomes.md")
  echo "$f: $count"
done
```

Expected: each field count = 5 (one per outcome).

### EC4: Verify boundary table has ≥ 5 rows total with ≥ 4 forbidden (❌) rows

```bash
SP="harness/sprints/sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements"
total=$(grep -c '^| W[0-9]' "$SP.non-builder-boundary.md")
forbidden=$(grep -c '^| W[0-9].*| ❌' "$SP.non-builder-boundary.md")
echo "rows=$total forbidden=$forbidden"
```

Expected: `rows>=5 forbidden>=4` (this sprint delivers `rows=9 forbidden=6 allowed=3`).

### EC5: Verify parent traceability.json reverse links (outcomes field on each child)

```bash
TR="harness/sprints/epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队.traceability.json"
jq '.children[0].outcomes | length' "$TR"
jq '.schema_version' "$TR"
jq '[.children[].node_id]' "$TR"
```

Expected:
- `.children[0].outcomes | length` ≥ 1
- `.schema_version` = `"solar.epic.traceability.v1"` (unchanged)
- children order unchanged: `["S01_requirements","S02_architecture","S03_core_runtime","S04_orchestration_ui","S05_verification_release"]`

### EC6: Confirm no code files were produced under S01 write_scope

```bash
SP="harness/sprints/sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements"
ls "$SP".*.py "$SP".*.ts "$SP".*.js "$SP".*.sh 2>/dev/null | wc -l
```

Expected: `0`.

### EC7: Verify status.json is in `reviewing` or `passed`, not stuck in `drafting`

```bash
SP="harness/sprints/sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements"
jq -r '.status,.phase' "$SP.status.json"
```

Expected: `status` ∈ {`reviewing`,`passed`}; `phase` indicates evaluator entry.

### EC8: Verify task_graph N1/N2/N3 are all reviewing or better

```bash
SP="harness/sprints/sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements"
jq '.node_results' "$SP.task_graph.json"
```

Expected: every node ∈ {`reviewing`,`passed`}; nothing in `pending` or `drafting`.

## Verification Evidence (this node, N3)

Run from `~/.solar`:

```bash
# N3-specific acceptance verification
SP="harness/sprints/sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s01-requirements"
TR="harness/sprints/epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队.traceability.json"

# (a) handoff.md exists and contains the 5-row outcome matrix
test -s "$SP.handoff.md"
grep -c '^| \*\*O[1-5]\*\*' "$SP.handoff.md"          # expect 5

# (b) handoff.md ends with the two release signals
grep -E '^evaluator_can_review:[[:space:]]*true' "$SP.handoff.md"
grep -E '^s02_can_start:[[:space:]]*true' "$SP.handoff.md"

# (c) parent traceability outcomes field is populated
jq '.children[0].outcomes | length' "$TR"             # expect >= 1
jq '.schema_version' "$TR"                            # expect "solar.epic.traceability.v1"
jq '[.children[].node_id]' "$TR"                      # children order preserved

# (d) negative: no code files produced under S01 write_scope
ls "$SP".*.py "$SP".*.ts "$SP".*.js "$SP".*.sh 2>/dev/null | wc -l   # expect 0
```

Observed at 2026-05-14T15:10:00Z:
- `handoff.md` written (write_scope-allowed path)
- `traceability.json` patched: 5 children each gain `outcomes` field; schema_version + children order unchanged
- No `.py/.ts/.js/.sh` files produced under the S01 sprint prefix

## Capability / KB Usage Evidence

- **harness-knowledge**: Dispatch carried a populated `<solar-unified-context>` block citing 5 mirage_path hits (prior dispatch context) and 1 solar_db hit (`sprint-20260508-mirage-codex-solar-substrate.accepted.md`). Used as background reference for sprint-handoff conventions and traceability schema. Did NOT call `solar-harness context inject` separately because the dispatch already pre-injected the needed context (degraded sources noted: `mirage_path:no_results` was marked).
- **harness-graph (solar-graph-scheduler)**: Verified upstream nodes N1 and N2 were both in `reviewing` before starting N3 (depends_on=[N1,N2] in task_graph); after writing this handoff, will call `graph-scheduler mark --node N3 --status reviewing --in-place` to release the evaluator. Wrote only under `write_scope` declared in the N3 dispatch.
- **Solar-Harness Runtime**: Used the runtime's contract/dispatch-visibility layer to confirm `assigned_to` was clear before claiming N3 (avoided double-build hazard documented in prior Phase-3 inspection). Read scope obeyed: only `outcomes.md`, `non-builder-boundary.md`, parent `traceability.json`, parent `task_graph.json` were read.
- **Superpowers (workflow.planning)**: Applied the planner discipline of "decompose by outcome → owner-sprint" when building the 5-row matrix. Cross-checked each outcome's Owner-Sprint field in `outcomes.md` against the matrix rows.
- **solar-autopilot-monitor (injected but not used)**: This node is pure documentation + JSON patch; no autopilot interaction needed. Flagged as `injected` not `used`.
- **ATLAS (injected but not used)**: No failures triggered structured repair. Flagged as `injected` not `used`.
- **Everything Claude Code (injected but not used)**: No hook/MCP changes. Flagged as `injected` not `used`.

## Scope Compliance

- **Reads (within dispatch read_scope)** ✅:
  - `harness/sprints/sprint-...s01-requirements.outcomes.md`
  - `harness/sprints/sprint-...s01-requirements.non-builder-boundary.md`
  - `harness/sprints/epic-...traceability.json`
  - `harness/sprints/epic-...task_graph.json` (confirmed exists; not modified)
- **Writes (within dispatch write_scope)** ✅:
  - `harness/sprints/sprint-...s01-requirements.handoff.md` (this file)
  - `harness/sprints/epic-...traceability.json` (children[*].outcomes added; schema_version + children order preserved)
- **Convenience write (outside write_scope, builder-coordinator convention)** ⚠️:
  - `harness/sprints/sprint-...s01-requirements.N3-handoff.md` — coordinator expects a node-level handoff for the graph scheduler's evaluator hand-off. If the evaluator considers this out-of-scope, the sprint-level `handoff.md` alone satisfies the dispatch's literal write_scope.
- **No code files** ✅: zero `.py / .ts / .js / .sh` files created under the S01 prefix.
- **No parent-status-bump** ✅: did NOT change parent epic status, did NOT mark S02-S05 child sprints as anything other than `queued` (they remain queued; S02 will transition itself when its planner activates).

## Known Risks / Unresolved Items

1. **schema_version is identifier `solar.epic.traceability.v1`** — the patch adds a new optional field `outcomes` to each child. The schema_version is unchanged, but a strict schema validator that disallows additional properties would reject this. Mitigation: the field is purely additive and the value is a flat array of outcome IDs; if the validator rejects, the field can be moved to a side-car file without breaking the children array.
2. **Outcome IDs use the short form `O1..O5`** — these are local to S01. If a future epic also defines outcomes, a global namespacing scheme (e.g., `<epic-id>:O1`) may be needed. Out of scope for this sprint.
3. **Owner-Sprint columns assume S02-S05 stay as currently scoped** — if the epic later renames slices, the matrix will need a refresh. Mitigation: matrix is authoritative-from-`outcomes.md`; regenerating it is mechanical.
4. **`evaluator_can_review: true` is set, but the actual evaluator queue is owned by the coordinator** — this handoff does not bypass the coordinator's evaluator dispatch. The signal is advisory; the coordinator's `graph-scheduler mark --node N3 --status reviewing` is the binding action.

## Not Done

- **No S02-S05 work** — those sprints remain `queued`. This sprint is the requirements slice only.
- **No epic-level passed claim** — explicitly NOT marking the epic as complete; only S01 is in reviewing.
- **No code or test files** — by the contract's slice definition.
- **No status-page UI mockup beyond what's in `outcomes.md` "What User Sees" boxes** — actual rendering is S04.
- **No automatic deadlock recovery** — listed in Non-Goals of `outcomes.md`.

## Scope Change Request

None. No scope expansion needed for N3 acceptance.

---

## Sign-off

evaluator_can_review: true
s02_can_start: true

coordinator hint: after this handoff lands, mark N3 via
`solar-harness graph-scheduler mark --graph sprints/sprint-...s01-requirements.task_graph.json --node N3 --status reviewing --in-place`
