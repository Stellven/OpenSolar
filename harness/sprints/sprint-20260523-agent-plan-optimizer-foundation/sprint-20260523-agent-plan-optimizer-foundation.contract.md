# Contract: Agent Plan Optimizer Foundation

## Canonical Sources

- `requirement_ir.json` is the source of truth.
- `contracts/*.yaml` are canonical structured contracts.
- `.contract.md` is a compiled human-readable view.
- This sprint is blocked until predecessor Requirement Compiler sprints pass.

## Product Contract

- goal: Define APO/AQO as Solar-harness's optimizer layer over Requirement Compiler and operator runtime.
- success_metrics:
  - logical plan, physical plan, rule engine, cost model, enforcer, memo, and adaptive replan are explicitly specified
  - explain plan output can justify selected and rejected plans
  - sprint remains dependency-safe and does not conflict with predecessor implementation chains
- non_goals:
  - no learned optimizer in P0
  - no builder work before predecessor sprints finish

## Interface Contract

- name: AgentPlanOptimizerContracts
- version: 1.0
- invariants:
  - Intent IR, Logical Plan, Physical Plan, PlanMemo, and Runtime Feedback must be distinct artifacts
  - writer/verifier separation is preserved in physical plans
  - adaptive replan must consume runtime feedback, not mutate historical spec in place

## Agent Execution Contract

- allowed_paths:
  - harness/**
- forbidden_paths:
  - infra/prod/**
  - .env*
  - secrets/**
- approval_required_when:
  - enabling optimizer execution before predecessor sprint completion
  - introducing learned optimizer or opaque scoring
  - mutating verifier separation or evidence rules
- stop_conditions:
  - predecessor dependency gate cleared
  - logical/physical/enforcer boundaries explicit
  - explain plan and replay interfaces specified

## Dependency Contract

- blocked_by:
  - sprint-20260523-pm-pane-requirement-compiler-backend-foundation
  - sprint-20260523-requirement-compiler-quality-loop
- until both pass:
  - no planner wake
  - no builder dispatch
  - no active implementation
