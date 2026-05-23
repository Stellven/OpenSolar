# PRD — stale Python multi-task runner cleanup

Sprint: `sprint-20260520-multitask-stale-python-runner`
Source: Codex operator report from Mac mini
Priority: P0
Lane: operations/runtime

## Problem

Mac mini shows long-running Python processes even after the related `solar-harness multi-task` sprint is complete. Live evidence captured on 2026-05-20:

- PID `8700`: `multi_task_runner.py start --graph ...sprint-20260520-thunderomlx-qwen36-pane-overhead.task_graph.json --max-workers 2 --profile builder --interval 30 --memory-reserve-gb 8 --no-clear`
- PID `84192`: `multi_task_runner.py start --graph ...sprint-20260520-thunderomlx-cache-warm-advisor.task_graph.json --max-workers 2 --profile builder --interval 30 --memory-reserve-gb 8 --no-clear`
- Both graphs report `parent-check ready=true`, all nodes passed, `missing_gates=[]`.
- `multi-task status --no-clear` still reports many `completed/live` workers and the scheduler logs keep growing.

This creates operator confusion, unnecessary background work, and makes it hard to tell if Mac mini is actually idle.

## Goals

1. Make `multi_task_runner.py start` naturally exit when its target graph is fully complete and no active workers remain.
2. Add a diagnostic surface that clearly reports stale scheduler runners tied to completed graphs.
3. Provide a safe, auditable cleanup path for stale scheduler runners; no broad process killing.
4. Preserve normal behavior for active graphs and intentional long-running screen/status UI.

## Non-goals

- Do not kill unrelated Python processes such as `honcho`, QMD proxy, brain-router, ThunderOMLX MCP, or config server.
- Do not delete task directories or scheduler logs.
- Do not change ThunderOMLX cache settings.
- Do not rewrite completed task handoffs.

## Acceptance

- A completed graph with all nodes passed, `parent-check ready=true`, no ready nodes, and no active workers causes `multi_task_runner.py start` to exit with code 0 within one scheduler interval.
- `solar-harness multi-task status --no-clear` no longer makes completed old workers look like live work without an explicit stale/completed distinction.
- A doctor/report command or equivalent diagnostic identifies PIDs like `8700` and `84192` as stale scheduler runners, including graph path, PID, elapsed time, RSS, and log path.
- Cleanup is constrained to commands whose process argv contains `multi_task_runner.py start --graph <completed graph>` and whose graph passes `parent-check ready=true`.
- Tests or smoke scripts prove active graph scheduling still dispatches ready nodes.

## Evidence To Use

- `/Users/lisihao/.solar/harness/run/multi-task/thunderomlx-qwen36-pane-overhead.scheduler.log`
- `/Users/lisihao/.solar/harness/run/multi-task/thunderomlx-cache-warm-advisor.scheduler.log`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260520-thunderomlx-qwen36-pane-overhead.task_graph.json`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260520-thunderomlx-cache-warm-advisor.task_graph.json`
- `ps axo pid,ppid,etime,%cpu,%mem,rss,command | grep multi_task_runner.py`

## Stop Rules

- Stop and write a blocker if a candidate PID does not point to a completed graph.
- Stop and write a blocker if the change would require killing non-scheduler Python processes.
- Stop and write a blocker if tests cannot distinguish active graph from completed graph behavior.

