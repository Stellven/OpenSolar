# Compiled Contract — 对 Solar Harness 正式接入 understand-anything 做一轮 full PRD 发单。目标不是让 Claude 手动执行 /unde

## Canonical Sources

- `requirement_ir.json` is the source of truth.
- `contracts/*.yaml` are canonical structured contracts.
- `.contract.md` is a compiled human-readable view.

## Product Contract

- goal: 对 Solar Harness 正式接入 understand-anything 做一轮 full PRD 发单。目标不是让 Claude 手动执行 /understand，而是把 understand-anything 产品化为 Solar Harness 编排、调度、管理、执行机制中的正式能力。需要设计并拆解：1）logical operators，至少覆盖 CodebaseIndexer、CodeExplainer、DiffSemanticAnalyzer、OnboardingCurator 这类代码理解任务；2）physical operator，封装 Claude 插件侧 understand-anything 执行面；3）capability capsule 与 artifact contract，明确输入输出、知识图、explain、semantic diff、onboard
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
