# Compiled Contract — 对 Solar Harness 正式下单一轮 skill-to-capsule/operator auto-productization full PRD。目标

## Canonical Sources

- `requirement_ir.json` is the source of truth.
- `contracts/*.yaml` are canonical structured contracts.
- `.contract.md` is a compiled human-readable view.

## Product Contract

- goal: 对 Solar Harness 正式下单一轮 skill-to-capsule/operator auto-productization full PRD。目标是让已安装或新安装的 skill/plugin 能被系统自动发现、规范化、封装并有机接入 Solar Harness 的任务编排、调度、管理、执行机制，而不是停留在 inventory/readiness/记账层。必须覆盖：1）skill/plugin discovery 与 capability normalization；2）skill-to-capsule compiler，自动或半自动生成 capability capsule draft、artifact contract、physical operator binding、actor derivation；3）当调度过程中命中某个 capability capsule 时
- success_metrics:
  - PRD、contract、TaskDAG 互相对齐。
  - 实施、验证、兼容/发布路径均已显式表达。
  - 每条验收标准都能追溯到验证或 gate。
  - understand-anything 的 semantic backend 在设计、runtime 与 handoff 中均显式固定为 ThunderOMLX。
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
  - understand-anything case must preserve plugin-native deterministic phases and route semantic LLM phases to ThunderOMLX.

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
