# Contract — make completed multi-task windows visibly historical

Sprint: `sprint-20260521-multitask-history-window-label`

## Required Work

1. Audit current status rendering in `/Users/lisihao/.solar/harness/lib/multi_task_runner.py`:
   - `enrich_task_row`
   - plain status table
   - screen status lines
   - TVS task rows
2. Implement clear status wording:
   - terminal task + tmux window present => `history-window-open` or equivalent;
   - terminal task + no window => `history-archived` or equivalent;
   - active task + tmux live => active/live remains clear.
3. Verify old completed task windows no longer read as active live work.
4. If there is an existing `reap` command, document and test the safe dry-run path. Only extend it if necessary.

## Constraints

- Do not terminate active tasks.
- Do not delete run directories.
- Do not alter ThunderOMLX settings or model routing.
- Keep the change small and localized.

## Verification

- `python3 -m py_compile lib/multi_task_runner.py`
- `solar-harness multi-task status --no-clear`
- `solar-harness multi-task stale-schedulers`
- If archive/reap is used, run `reap --dry-run` first and record output.

## Deliverables

- Code change in `lib/multi_task_runner.py`.
- Handoff with before/after status excerpts.
- Optional monitor report under `/Users/lisihao/.solar/harness/monitor-reports/`.

