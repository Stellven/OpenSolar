# Contract — Tool Plane Sandbox Default Routing

Sprint: `sprint-20260513-tool-plane-sandbox-default-routing`
Priority: P0
Lane: reliability
Owner: Solar-Harness
Status: active
Phase: planning_complete
Handoff_to: graph_scheduler
Target_role: graph_scheduler
Bypass_PM: false
PRD_ref: sprint-20260513-tool-plane-sandbox-default-routing.prd.md
Plan_ref: sprint-20260513-tool-plane-sandbox-default-routing.plan.md
Design_ref: sprint-20260513-tool-plane-sandbox-default-routing.design.md
Workflow_note: PM PRD ready → Planner artifacts written (design.md, plan.md, task_graph.json) → graph_scheduler dispatches batches per task_graph DAG. Legacy Bypass_PM=true overridden 2026-05-13 per workflow guard violation.

## Intent

Continue the local-only disposable runtime hardening by moving user-triggered tool/data-plane execution paths onto `SandboxHand` by default. Do not migrate control-plane internals that require direct host side effects, such as tmux pane dispatch, SSH/rsync remote dispatch, status server process control, or test runner orchestration.

## Scope

Already completed baseline:

- `SandboxHand` supports argv-mode execution and write-guard evidence.
- `solar-harness mirage exec` routes through `SandboxHand`.
- Ruflo runtime smoke routes help/version/mcp_help through `SandboxHand`.
- Activation proof currently reports 11/11 PASS with Mirage and Ruflo sandbox evidence.

This sprint continues from that baseline and lets Solar-Harness builders implement the next routing layer.

## Acceptance

- A concrete inventory classifies remaining `subprocess.run` call sites as `tool_plane`, `data_plane`, `control_plane`, `test_only`, or `background_worker`.
- At least one additional user-triggered tool/data-plane path beyond Mirage and Ruflo is routed through `SandboxHand`, with `executor=sandbox`, `execution_mode=argv`, and evidence file.
- QMD and document extraction paths are analyzed separately; long-running embed workers must not be forced into foreground sandbox smoke.
- Activation proof fails if migrated paths regress to naked host execution.
- Regression tests prove host path blocks, allowed write paths, and evidence generation.
- `_raw` knowledge document is updated with what was migrated, what was intentionally not migrated, and remaining P1/P2 work.

## Stop Rules

- Do not route `tmux`, `ssh`, `rsync`, `launchctl`, status server lifecycle, or test runner orchestration through `SandboxHand` in this sprint.
- Do not run foreground long QMD embedding.
- Do not claim full kernel isolation; current boundary is local process sandbox plus policy/evidence.
- If a write scope must expand, write a scope-change note in node handoff instead of editing outside scope.

## Required Verification

```bash
python3 -m py_compile \
  ~/.solar/harness/lib/hands_runtime.py \
  ~/.solar/harness/lib/solar_mirage.py \
  ~/.solar/harness/lib/ruflo_adapter.py \
  ~/.solar/harness/lib/capability_activation_proof.py

bash ~/.solar/harness/tests/runtime/test-hands-runtime.sh
bash ~/.solar/harness/tests/test-status-capability-health-projection.sh
bash ~/.solar/harness/tests/test-mirage-substrate.sh
bash ~/.solar/harness/tests/test-mirage-unified-vfs.sh
bash ~/.solar/harness/tests/plugins/test-ruflo-integration.sh
solar-harness integrations activation-proof --json
```

## Deliverables

- `reports/tool-plane-sandbox-routing/inventory.{json,md}`
- Updated runtime code and tests for newly migrated tool/data-plane path
- Updated `capability_activation_proof.py`
- Updated `_raw` knowledge report:
  `/Users/sihaoli/Knowledge/_raw/solar-harness-local-disposable-sandbox-assessment-20260513.md`
