# Contract: Model Fleet Operator Runtime Foundation

Sprint: `sprint-20260522-model-fleet-operator-runtime-foundation`

## Execution Rules

- Work on Mac mini under `/Users/lisihao/.solar/harness`.
- Preserve current GEPA sprint and active multi-task workers.
- Do not kill tmux panes or delete task directories.
- Do not write raw secrets into files, logs, status JSON, or reports.
- Keep backward compatibility with current `physical-operators.json`.
- Use graph-effective status over stale task status when summarizing active work.

## Deliverables

### Code / Config

- `harness/config/physical-operators.schema.json` or equivalent schema module.
- Extended `harness/config/physical-operators.json` examples using new Model Fleet fields.
- Runtime support module, preferably under `harness/lib/operator_runtime.py` or existing appropriate module.
- Scheduler integration in `harness/lib/multi_task_runner.py` and/or operator selector helper.
- Monitor bridge extension in `harness/tools/solar_monitor_bridge.py`.
- Tests under `harness/tests/`.

### Docs / Reports

- Node handoffs:
  - `sprint-20260522-model-fleet-operator-runtime-foundation.N1-handoff.md`
  - ...
- Final report:
  - `/Users/lisihao/.solar/harness/monitor-reports/model-fleet-operator-runtime-foundation.md`

## Required Design Decisions

1. `preferred_operator` remains hard override.
2. New logical fields are additive and backward-compatible:
   - `task_type`
   - `required_capability_scores`
   - `preferred_operator_classes`
   - `constraints`
   - `verifier_required`
3. Writer and verifier cannot be same `operator_id` when `verifier_required=true`.
4. Quota reserve protects high-value tasks:
   - `ARCH_DESIGN`
   - `ROOT_CAUSE_DEBUG`
   - `FINAL_REVIEW`
5. Antigravity operators remain disabled unless smoke/adapter proves safe.

## Node Done Definition

Every node must:

- Stay inside write scope.
- Run at least syntax/targeted tests.
- Write handoff with:
  - changed files
  - verification commands
  - unresolved risks
  - next action
- Mark only its own node reviewing.

## Safety

- No production auto-apply.
- No global package install.
- No raw key emission.
- No provider ToS bypass.
- No re-enabling unsafe ThunderOMLX cache features.

