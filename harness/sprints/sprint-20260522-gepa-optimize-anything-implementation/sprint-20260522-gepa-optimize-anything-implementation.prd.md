# PRD: GEPA optimize_anything Stage 1 Implementation

Created: 2026-05-22T16:55:00Z
Sprint: sprint-20260522-gepa-optimize-anything-implementation
Target: Mac mini solar-harness
Upstream design: `/Users/lisihao/.solar/harness/monitor-reports/gepa-optimize-anything-integration.md`

## Summary

Implement a safe, package-bounded Solar-Harness integration for GEPA `optimize_anything` under `integrations/gepa_optimizer/`. The implementation must provide CLI surfaces, budget/stopper enforcement, evaluator sandboxing, artifact lineage, physical-operator routing, promote/rollback controls, and CPU-only tests. It must not auto-apply optimized artifacts or run unbounded cloud LLM loops.

## Gate Result

I0 dry-run install verification passed with a namespace adjustment:

```python
from gepa.optimize_anything import optimize_anything, GEPAConfig, EngineConfig
```

Do not import `gepa.optimize_anything` as the callable function from top-level package.

## Goals

- Add package `integrations/gepa_optimizer/` with 8 modules:
  - `__init__.py`
  - `adapter.py`
  - `cli.py`
  - `evaluator.py`
  - `artifact_store.py`
  - `operator_router.py`
  - `budgets.py`
  - `promote.py`
- Add tests under `tests/integrations/gepa_optimizer/`.
- Add a CLI entry path that can be wired by `solar-harness optimizer gepa` in a later shell-router patch, while still being runnable directly as Python in this sprint.
- Demonstrate `propose -> review -> promote -> rollback` against `/tmp/gepa_seed.txt` only.

## Non-Goals

- Do not wire this into production automations.
- Do not modify hooks, global prompts, live skills, or physical operator registry.
- Do not run real GEPA LLM optimization unless explicitly budgeted in a later sprint.
- Do not install packages into the main Solar environment.

## Acceptance

- `python3 -m py_compile integrations/gepa_optimizer/*.py` passes.
- `python3 -m pytest tests/integrations/gepa_optimizer/ -q` passes.
- CLI rejects `run --execute` unless `--budget-usd`, `--budget-evals`, and `--max-wall-time-min` are supplied.
- Artifact writes redact/stop on secret-like content.
- Promote creates backup and rollback restores it.
- E2E smoke uses only `/tmp/gepa_seed.txt` and `~/.solar/harness/optimizer-runs/<run_id>/`.
- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/gepa-optimize-anything-implementation.md`.

