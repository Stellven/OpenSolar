# Compiled Contract — 对 Solar Harness 做一轮架构收口，目标是降低接入新大模型供应商和新型号时的边际成本。必须把统一 selector、provider adapter

## Canonical Sources

- `requirement_ir.json` is the source of truth.
- `contracts/*.yaml` are canonical structured contracts.
- `.contract.md` is a compiled human-readable view.

## Product Contract

- goal: 对 Solar Harness 做一轮架构收口，目标是降低接入新大模型供应商和新型号时的边际成本。必须把统一 selector、provider adapter registry、以及 actor 从 physical operator 派生这三件事设计并拆成可落地迁移路径。需要识别并消除当前调度、provider 适配、actor registry 三套分裂实现中的硬编码与漂移点，形成正式的 PRD、contract、task DAG、handoff，并为后续实现保留兼容迁移与验证门禁。重点包括：1）所有调度入口统一走单一 selector；2）provider 级认证、quota、error classification、command builder 下沉到 adapter registry；3）actor 不再手工重复维护，而是从 physical operator 或 templ
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
