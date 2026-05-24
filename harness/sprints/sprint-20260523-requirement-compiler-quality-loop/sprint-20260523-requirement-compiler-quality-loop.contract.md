# Compiled Contract — 为 PM pane / Requirement Compiler 建立 Quality Loop：以 Requirement IR 为唯一事实源，补齐 gold

## Canonical Sources

- `requirement_ir.json` is the source of truth.
- `contracts/*.yaml` are canonical structured contracts.
- `.contract.md` is a compiled human-readable view.

## Product Contract

- goal: 为 PM pane / Requirement Compiler 建立 Quality Loop：以 Requirement IR 为唯一事实源，补齐 golden set、误分类/误编译 failure replay、planner 修改差异回流、evaluator 驳回原因回流、compile quality metrics 与 gate。要求把需求编译质量从 prompt 经验升级成 schema+contract+validator+eval+feedback 的闭环；不得把 doc-only/contract-only 冒充 implemented；必须兼容现有 PM -> Planner -> Builder 主链，并支持 Codex/Solar handoff 质量评估。首批聚焦后端编译质量底座，不做大规模 UI 重写。
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
