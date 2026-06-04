# S05 Regression Report — ActorHost Taxonomy And Actor-First Runtime

## Scope

Sprint: `sprint-20260530-p0-修复单-actorhost-taxonomy-与-actor-first-runtime-落地补齐-s05-verification-release`

This report covers S05 verification only. It verifies upstream S01-S04 status, ActorHost schema/registry coverage, runtime status visibility, and the legacy physical-operators negative control. It does not claim parent Epic closeout.

## Results

| Node | Area | Verdict | Evidence |
| --- | --- | --- | --- |
| N1 | Upstream artifact collection | PASS | `harness/tests/s05-collected-artifacts.json`: `N1_gate_status=PASSED`, `upstream_passed=true`, `blocked_by=[]` |
| N2 | Schema validation | PASS | `harness/tests/s05-schema-results.json`: `total=5`, `passed=5`, `failed=0` |
| N3 | Runtime E2E smoke | PASS | `harness/tests/s05-e2e-results.json`: `total=4`, `passed=4`, `failed=0` |
| N4 | Negative control | PASS | `harness/tests/s05-negctl-results.json`: `total=5`, `passed=5`, `failed=0` |

## Acceptance Coverage

| Requirement | Verdict | Evidence |
| --- | --- | --- |
| AC1: reproducible unit/integration/negative-control/activation evidence | PASS | N2, N3, N4 scripts and result JSONs are reproducible and pass. |
| AC2: parent Epic must not close before all gates pass | PASS | S05 handoff/eval state that this is S05-only verification and not parent Epic closeout. |
| AC3: handoff/eval/report artifacts exist | PASS | Sprint handoff/eval plus this report and activation proof are produced. |
| US1: E2E suite verifies 8 host types | PASS | N2 validates schema/registry 8 host types; N3 validates host status layer coverage. |
| US2: legacy physical-operator negative control | PASS | N4 validates read-only/deprecated compat-only registry and compat mapping tests. |
| US3: activation proof | PASS | `harness/_raw/s05-activation-proof.json`. |
| US4: S1-S4 acceptance status report | PASS | N1 collected current S01-S04 `passed/completed` statuses and sidecar counts. |

## Commands

- `harness/tests/s05-schema-validation.sh`
- `harness/tests/s05-e2e-runtime.sh`
- `harness/tests/s05-negative-control.sh`
- `bash -n harness/tests/s05-schema-validation.sh harness/tests/s05-e2e-runtime.sh harness/tests/s05-negative-control.sh`
- `python3 -m pytest -q harness/tests/runtime/test_compat_mapping.py`
- `python3 harness/tools/graph_scheduler.py validate --graph /Users/lisihao/.solar/harness/sprints/sprint-20260530-p0-修复单-actorhost-taxonomy-与-actor-first-runtime-落地补齐-s05-verification-release.task_graph.json`

## Residual Notes

- The older S05 sprint eval was a valid N1 blocked-path assessment from before S03/S04 passed. It is superseded for current scheduling by the new N1 sidecar and full S05 evidence.
- `harness/lib/multi_task_status.py` currently has library loaders but no active JSON CLI output; N3 uses library-level smoke instead of claiming a nonexistent CLI contract.
- The historical plan mentioned `legacy_physical_route()`, but that callable is not present. N4 verifies the actual current negative-control contract: physical-operators is read-only/deprecated compat metadata, not primary Host identity.
