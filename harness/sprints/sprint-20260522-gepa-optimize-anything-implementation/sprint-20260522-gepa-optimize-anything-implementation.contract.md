# Contract: GEPA optimize_anything Stage 1 Implementation

Created: 2026-05-22T16:55:00Z
Status: active
Sprint: sprint-20260522-gepa-optimize-anything-implementation
Project: /Users/lisihao/.solar/harness

## Summary

Build the first safe implementation of Solar's GEPA optimizer package. This sprint is allowed to write only under `integrations/gepa_optimizer/`, `tests/integrations/gepa_optimizer/`, sprint handoff artifacts, optimizer run artifacts, and the final monitor report.

## Hard Safety Rules

- No auto-apply into production configs, prompts, hooks, skills, or operator registry.
- No global package installation.
- No secrets printed or written.
- No cloud LLM spend except mocked/unit tests.
- Real `GEPA optimize_anything` may be imported or inspected, but real optimization loops must remain disabled unless the CLI has explicit `--execute` and budget caps.
- Promotion target for E2E must be `/tmp/gepa_seed.txt`; production paths must be rejected.

## Package Boundary

All implementation files must live under:

```text
/Users/lisihao/.solar/harness/integrations/gepa_optimizer/
```

Tests must live under:

```text
/Users/lisihao/.solar/harness/tests/integrations/gepa_optimizer/
```

## Required Modules

| Module | Responsibility |
|---|---|
| `__init__.py` | export stable API, no side effects |
| `adapter.py` | GEPA import wrapper, config builder, evaluator wrapper |
| `cli.py` | `propose/run/review/promote/rollback/status` commands |
| `evaluator.py` | subprocess JSON evaluator sandbox with timeout/RLIMIT fallback |
| `artifact_store.py` | run dirs, candidates, pareto, summary, audit, cache, secret scan |
| `operator_router.py` | physical operator selection and multimodal gate |
| `budgets.py` | budget and stopper protocols |
| `promote.py` | promote/backup/diff/rollback |

## Done

- All DAG nodes passed.
- Final report includes evidence paths and command outputs.
- Test suite passes on Mac mini.
- No GEPA production run or auto-promotion occurred.

