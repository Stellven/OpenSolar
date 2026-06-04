# Compiled Contract — RawIntent Consumer Request - [entrypoint_metadata]

## Canonical Sources

- `requirement_ir.json` is the source of truth.
- `contracts/*.yaml` are canonical structured contracts.
- `.contract.md` is a compiled human-readable view.

## Product Contract

- goal: # RawIntent Consumer Request - [entrypoint_metadata] ## Source - intent_id: intent-20260525-155416-c7d24d4b84 - channel: pm_dispatch - actor: user - device: mac_mini_pm_dispatch - thread_ref: ## Rewritten Objective [entrypoint_metadata] ## Problem [entrypoint_metadata] sprint_id: N/A node_id: N1 role: builder [raw_request] PM trusted auto planner handoff smoke 1779724456 ## Constraints - All execu
- success_metrics:
  - PRD、contract、TaskDAG 互相对齐。
  - 实施、验证、兼容/发布路径均已显式表达。
  - 每条验收标准都能追溯到验证或 gate。
- non_goals:
  - 不在首批交付中做完整四区 PM pane 重构。
  - 不绕过 planner 直接进入 builder。

## Interface Contract

- name: RequirementCompilerAdapters
- version: 1.0
- invariants:
  - Requirement IR is the only source of truth.
  - DAG nodes[*].id must be unique.
  - Every acceptance criterion maps to at least one validation step.

## Agent Execution Contract

- allowed_paths:
  - apps/pm-pane/**
  - packages/requirement-ir/**
  - harness/**
- forbidden_paths:
  - infra/prod/**
  - .env*
  - secrets/**
- approval_required_when:
  - new production dependency
  - database migration
  - network access
  - touching auth or billing
- stop_conditions:
  - 缺少可验证 acceptance 不得标记为完成。
  - 缺少 verifier 决策不得进入 DONE。
