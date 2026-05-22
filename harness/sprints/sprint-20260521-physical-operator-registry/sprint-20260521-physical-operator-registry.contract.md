# Contract — Physical Operator Registry Implementation

## Sprint

`sprint-20260521-physical-operator-registry`

## Objective

Implement a first-class physical operator registry for Mac mini `solar-harness multi-task`, where each headless tmux pane is treated as a stable execution operator with concrete model/vendor/config/quota/health metadata.

## Hard Rules

- Use Solar context before analysis.
- Keep secrets redacted.
- Do not break existing `preferred_profile` dispatch.
- Do not kill unrelated tmux panes.
- Do not delete task directories.
- Do not re-enable ThunderOMLX unsafe cache features.
- Do not make Antigravity generally dispatchable unless smoke passes.

## Required Deliverables

```text
┌────────────┬──────────────────────────────────────────────────────┐
│ deliverable│ path                                                 │
├────────────┼──────────────────────────────────────────────────────┤
│ registry   │ ~/.solar/harness/config/physical-operators.json      │
│ loader     │ harness/lib module or multi_task_runner integration  │
│ selector   │ preferred_operator/operator_selector support          │
│ status     │ multi-task status operator columns                    │
│ tests      │ focused regression tests                              │
│ report     │ monitor-reports/physical-operator-registry.md        │
└────────────┴──────────────────────────────────────────────────────┘
```

## Operator Schema Minimum

```json
{
  "operator_id": "mini-op-07-thunderomlx-qwen36",
  "enabled": true,
  "available": true,
  "host": "mac-mini",
  "pane": "solar-harness-multi-task:op07",
  "role": "builder",
  "vendor": "local",
  "backend": "thunderomlx-anthropic-proxy",
  "model_id": "Qwen3.6-35b-a3b",
  "model_alias": "thunderomlx-qwen36",
  "model_config": {
    "thinking": "disabled",
    "hot_cache_gb": 8
  },
  "base_url": "http://127.0.0.1:8002",
  "key_ref": "local-thunderomlx",
  "quota": {
    "cycle": "local_resource",
    "refresh_at": null,
    "status": "resource_bound"
  },
  "health": {
    "auth_status": "ok",
    "last_smoke_at": "N/A",
    "last_error": ""
  },
  "best_for": ["knowledge_extraction", "batch_summary"],
  "not_for": ["final_review", "security_review"]
}
```

## Initial Operator Policy

```text
┌──────────────────────┬────────────────────┬────────────────────────────┐
│ task_type            │ preferred operator │ fallback                   │
├──────────────────────┼────────────────────┼────────────────────────────┤
│ knowledge_extraction │ thunderomlx-qwen36 │ gemini-flash if enabled    │
│ cache_benchmark      │ thunderomlx-qwen36 │ command-shell              │
│ architecture         │ claude-opus        │ codex if available         │
│ complex_debug        │ claude-opus        │ codex if available         │
│ implementation       │ claude-sonnet      │ codex-builder if available │
│ final_review         │ claude-opus        │ none without approval      │
│ parallel_experiment  │ antigravity-flash  │ claude-sonnet limited      │
│ google_ecosystem     │ antigravity-flash  │ gemini-pro if available    │
└──────────────────────┴────────────────────┴────────────────────────────┘
```

## Test Plan

- Unit/fixture:
  - registry loads.
  - invalid registry fails safe.
  - selector resolves by `preferred_operator`.
  - selector resolves by `operator_selector.task_type`.
  - disabled/unavailable operator is rejected with reason.
- Regression:
  - existing multi-task entrypoint test still passes.
  - profile-only task graph still dispatches.
  - status renderer includes operator fields.
- Mac mini smoke:
  - registry lists ThunderOMLX and Antigravity operators.
  - Antigravity smoke returns `AGY_OK`.
  - ThunderOMLX operator shows `127.0.0.1:8002` and model `Qwen3.6-35b-a3b`.

## Final Report Must Include

- Operator list table.
- Which operators are enabled/disabled.
- How to switch a DAG node to a specific operator.
- Known gaps and rollback.

