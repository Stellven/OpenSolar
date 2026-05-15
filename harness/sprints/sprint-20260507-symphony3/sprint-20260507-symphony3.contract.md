# Sprint Contract Seed — sprint-20260507-symphony3

Status: seed
Source: /Users/lisihao/.solar/harness/sprints/sprint-20260507-symphony3.product-brief.md
Priority: P2
Lane: delivery

## Intent

Convert the product brief into the final Sprint 3 implementation contract and plan. The product brief is the source of truth for scope, acceptance criteria, gates, stop rules, deliverables, and schedule.

## Planner Instruction

1. Read the product brief:
   `cat ~/.solar/harness/sprints/sprint-20260507-symphony3.product-brief.md`
2. Produce or refine the final contract in this file, preserving the P2 delivery scope and Gate A / Gate B constraints.
3. Produce the implementation plan:
   `~/.solar/harness/sprints/sprint-20260507-symphony3.plan.md`
4. When the plan is ready, update status to `active` with `phase=planning_complete`.

## Non-Negotiables

- Do not write implementation code during planning.
- Do not restart harness or mutate live tmux panes.
- Preserve Sprint 1 + Sprint 2 regression gates.
- Keep HTTP server dependency-free: Python stdlib only, bound to 127.0.0.1.

