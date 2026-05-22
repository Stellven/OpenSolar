# Coordinator TypeScript Rewrite Status

Status: downgraded
Priority: P1 architecture debt
Updated: 2026-05-21

This candidate was created from the legacy `TODO-next-session.md` item about
rewriting `coordinator.sh` in TypeScript/Bun. It must not be dispatched as a
current P0 task.

Reason:

- There is no fresh reproduction that `.coordinator-state` is still being
  corrupted to `:`.
- This directory contains only PRD/dispatch draft artifacts.
- It does not contain the current Planner gate requirement:
  `design.md + plan.md + task_graph.json`.

Activation criteria:

1. Reproduce the `:` state corruption in the current coordinator runtime.
2. Document the root cause and minimal safe fix option.
3. Produce a valid `task_graph.json` that passes the workflow guard.
4. Confirm that a TypeScript rewrite is safer than a targeted bash fix.

