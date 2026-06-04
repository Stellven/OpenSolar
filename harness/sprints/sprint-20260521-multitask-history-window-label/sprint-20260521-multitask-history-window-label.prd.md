# PRD — multi-task history window labels and safe archive

Sprint: `sprint-20260521-multitask-history-window-label`
Priority: P1
Lane: operations/runtime

## Problem

After stale Python scheduler runners were fixed, `solar-harness multi-task status --no-clear` still shows terminal task windows as `completed/live`. The word `live` is technically the tmux window state, but operators read it as active work. This caused confusion after stale runner cleanup.

Live evidence:

- No `multi_task_runner.py start` process remains.
- `solar-harness multi-task stale-schedulers` reports no stale scheduler PID files.
- `multi-task status` still lists many historical windows as `completed/live`.

## Goals

1. Change status rendering so terminal tasks with open tmux windows show as history, not active live work.
2. Preserve visibility that the old tmux window still exists.
3. Add or document a safe archive path for old terminal worker windows.
4. Keep active/running/dispatched task behavior unchanged.

## Non-goals

- Do not delete task directories.
- Do not kill active/running/reviewing task windows.
- Do not hide historical task evidence.
- Do not change scheduler auto-exit behavior from the previous sprint.

## Acceptance

- Terminal task rows display a non-misleading state such as `completed/history-window-open` or split fields `status=completed`, `work=history`, `tmux=window-open`.
- Active tasks still display `ACTIVE` or equivalent.
- A safe archive/reap path only targets terminal task windows older than a configurable TTL or explicit task ids.
- `multi-task status --no-clear` before/after evidence is captured.
- `stale-schedulers` remains clean after changes.

