# Sprint Contract: MIA Native Runtime Closure

Priority: P1
Lane: integration
Owner: builder
Status: queued

## Intent

Close the remaining gap between Solar's MIA adapter and a real ECNU-SII/MIA Memory-Serve runtime. The adapter is now callable and fail-open; this sprint must make the native upstream service runnable in an isolated Solar-managed environment without mutating upstream source or polluting the user's shell.

## Current Evidence

- Vendored upstream exists at `~/.solar/harness/vendor/MIA`.
- Solar adapter exists at `lib/experience/mia_adapter.py`.
- Runtime manager exists at `lib/experience/memory_serve_daemon.py`.
- Adapter tests pass with a protocol-compatible Memory-Serve server.
- Native upstream start is still blocked by:
  - missing Python module `flask` in the current interpreter
  - missing upstream import target `memory_functions.py`
  - hardcoded BERT path `/your_path/bert/sup-simcse-bert-base-uncased`

## Acceptance

1. Create an isolated venv under `~/.solar/harness/venvs/mia-memory-serve`; do not install into system Python.
2. Produce `reports/mia-runtime/native-inventory.{json,md}` covering imports, entrypoints, missing files, model paths, ports, and env vars.
3. Resolve the missing `memory_functions.py` import without editing vendored upstream files; acceptable approaches are an external compatibility shim or documented upstream-only replacement if the import is proven unused.
4. Replace the hardcoded BERT dependency with a configurable runtime path or a safe local embedding backend, without editing upstream in place unless a patch file is generated and tracked separately.
5. Start Memory-Serve on `127.0.0.1:5197` via `solar-harness experience mia-start`.
6. `solar-harness experience mia-status --json` returns `ok=true`.
7. `solar-harness experience mia-query "queue block repair" --json` returns `ok=true` with non-empty context from the native runtime.
8. Existing fallback behavior remains intact when MIA is stopped.
9. Tests cover native readiness, adapter success, fallback, dependency reporting, and no vendor dirty diff.

## Stop Rules

- Stop if a dependency requires GPU-only runtime or downloads more than 5GB without explicit opt-in.
- Stop if fixing upstream requires destructive edits to `vendor/MIA`.
- Stop if native runtime cannot be made deterministic enough for local smoke tests; keep adapter path as production fallback and document the blocker.

## Verification

Run:

```bash
bash tests/test-mia-runtime-adapter.sh
python3 lib/experience_runner.py mia-status --json
python3 lib/experience_runner.py mia-query "queue block repair" --json
git -C vendor/MIA status --porcelain
```

Expected:

- adapter tests pass
- native status is `ok=true`
- native query returns context
- vendor tree remains clean

