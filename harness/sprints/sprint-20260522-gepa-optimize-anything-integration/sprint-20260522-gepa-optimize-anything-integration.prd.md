# PRD: GEPA optimize_anything Integration for Solar-Harness

Created: 2026-05-22T15:07:46Z
Sprint: sprint-20260522-gepa-optimize-anything-integration
Owner: Codex PM coordinator
Target: Mac mini solar-harness
Source: https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/

## Summary

Design a safe Solar-Harness integration for GEPA `optimize_anything`, a declarative API that optimizes text-serializable artifacts by combining an evaluator, diagnostic feedback as Actionable Side Information, and LLM proposer/search logic.

The first delivery is a researched integration plan and implementation contract. It must not auto-apply optimized artifacts into production. Any future execution must be sandboxed, budgeted, observable, and routed through physical operators.

## Problem

Solar already has several optimizer-like pieces: autoresearch pane optimizer, Meta-Harness outer loop, physical operators, DAG workers, evaluator gates, and benchmark/report artifacts. GEPA adds a general "optimize any text artifact" loop that could improve prompts, skills, configs, agent architectures, policies, and small code artifacts. Without a clear integration boundary, it can become unsafe: unbounded LLM spend, unreviewed code changes, evaluator side effects, and unclear responsibility between Builder, Evaluator, and optimizer.

## Goals

- Map GEPA `optimize_anything` concepts to Solar-Harness primitives.
- Define safe product surfaces: CLI, config schema, evaluator adapter, artifact store, monitor UI, and approval gate.
- Identify the first high-value use cases:
  - prompt/system prompt optimization for fixed eval sets;
  - skill/rule tuning with held-out validation;
  - multi-task physical operator routing policy optimization;
  - benchmark harness parameter optimization;
  - visual/multimodal artifact optimization only behind a multimodal operator.
- Produce a next implementation DAG with concrete file boundaries and tests.

## Non-Goals

- Do not install GEPA into production by default.
- Do not enable auto-apply of optimized code, prompts, skills, hooks, configs, or physical operator registry entries.
- Do not run unbounded cloud LLM loops.
- Do not print or store secrets.
- Do not route bulk optimization to expensive Claude unless explicitly justified.

## Required Research Questions

1. What GEPA APIs and concepts are needed for Solar?
2. Which Solar artifacts are safe to optimize first?
3. How should evaluator score, ASI diagnostics, multi-objective/Pareto results, and candidate lineage be stored?
4. How should budgets, stoppers, cache, dry-run, and human approval be enforced?
5. How should GEPA use Solar physical operators for proposer/reflection/evaluation models?
6. How does this coexist with autoresearch and Meta-Harness?
7. What is the minimal implementation sprint after this design sprint?

## Acceptance Criteria

- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/gepa-optimize-anything-integration.md`.
- Report includes source-backed GEPA summary with direct URL and current API assumptions.
- Report includes Solar architecture mapping table.
- Report includes safety policy: dry-run default, budget caps, no auto-apply, evaluator sandboxing, secret handling, artifact lineage.
- Report includes first implementation backlog with exact files, tests, and rollout plan.
- Task graph all nodes passed and bridge monitor latest shows `all_passed=true`.

