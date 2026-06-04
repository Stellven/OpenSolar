# Design — P0 Solar KB Default QMD Fallback

**Sprint**: sprint-20260508-kb-qmd-default-fallback
**Created**: 2026-05-08T15:50:47Z
**By**: codex_pm fast-path unblock

## Decision

Implement a bounded qmd fallback inside `solar-knowledge-context.py` after existing DB/FTS retrieval returns no useful hits. Preserve fail-open behavior and the existing JSON schema.

## Architecture

```
UserPromptSubmit
  -> ~/.claude/hooks/solar-knowledge-context.sh
  -> ~/.solar/harness/lib/solar-knowledge-context.py --query ...
  -> existing DB/FTS retrieval
  -> if budget remains and hits are empty or insufficient:
       qmd search <query> -c solar-wiki --json -n <limit>
  -> normalize qmd result into existing hit schema
  -> dedupe by path/title
  -> enforce max-chars
```

## Dispatch Context Decision

Planner must verify whether dispatched pane text triggers `UserPromptSubmit`. If not proven, builder should add a minimal sourced-context append path at coordinator dispatch time in a separate guarded change, using the sprint title and contract summary as the query. This fallback must be bounded and fail-open.

## Safety

- Use argv arrays with `subprocess.run`, never shell string interpolation.
- qmd output is untrusted retrieved text; it must only be emitted as sourced context, never executed.
- On qmd missing, timeout, bad JSON, or DB lock, return valid JSON and do not block prompt submission.
- Preserve `SOLAR_KB_CONTEXT=0`.

## Write Scope

- `/Users/lisihao/.solar/harness/lib/solar-knowledge-context.py`
- `/Users/lisihao/.claude/hooks/solar-knowledge-context.sh` only if hook behavior must be adjusted
- `/Users/lisihao/.solar/harness/tests/test-solar-kb-qmd-fallback.sh`
- `/Users/lisihao/.solar/harness/runbooks/kb-default-context.md`
- Optional dispatch-context note under `/Users/lisihao/.solar/harness/docs/`
