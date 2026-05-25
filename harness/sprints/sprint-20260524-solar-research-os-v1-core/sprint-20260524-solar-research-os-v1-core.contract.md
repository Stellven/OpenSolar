# Compiled Contract — 请基于以下两版战略需求，为 Solar-Harness 开启一个正式实现 sprint：

## Canonical Sources

- `requirement_ir.json` is the source of truth.
- `contracts/*.yaml` are canonical structured contracts.
- `.contract.md` is a compiled human-readable view.

## Product Contract

- goal: 请基于以下两版战略需求，为 Solar-Harness 开启一个正式实现 sprint： 目标不是做“增强版 GPT Deep Research agent”，而是做一个建立在 solar-harness 现有 DAG scheduler、physical operators、APO/optimizer、evidence ledger、quality gate、status-server 之上的 Solar Research OS / Research Compiler。 核心产品定义： - 面向技术、产业、科研、战略决策的证据驱动研究操作系统。 - 默认输出 2-5 万字技术洞察报告，图文并茂。 - 报告必须包含：技术架构图、技术栈分析、技术趋势分析、跨领域技术洞察、论文/产品/峰会/关键人物近半年言论分析。 - 报告不是直接由 LLM 自由生成，而是从结构化 evidence / cl
- success_metrics:
  - paper/source inventory 完整可追溯。
  - claim -> evidence -> implication 映射完整。
  - 研究结论具备 adoption/rejection criteria。
- non_goals:
  - 不把论文总结直接当作实现结论。
  - 不在缺证据时进入生产实现。

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
  - 缺少 evidence ledger 或 critique gate 时不得推进到 adoption。

## Research Contract

- hypothesis: 请基于以下两版战略需求，为 Solar-Harness 开启一个正式实现 sprint： 目标不是做“增强版 GPT Deep Research agent”，而是做一个建立在 solar-harness 现有 DAG scheduler、physical operators、APO/optimizer、evidence ledger、quality gate、status-server 之上的 Solar Research OS / Research Compiler。 核心产品定义： - 面向技术、产业、科研、战略决策的证据驱动研究操作系统。 - 默认输出 2-5 万字技术洞察报告，图文并茂。 - 报告必须包含：技术架构图、技术栈分析、技术趋势分析、跨领域技术洞察、论文/产品/峰会/关键人物近半年言论分析。 - 报告不是直接由 LLM 自由生成，而是从结构化 evidence / cl
- source_papers:
- rejection_criteria:
  - No evidence ledger available
  - No verifier/critique gate
