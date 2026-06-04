# Plan — S02 架构设计与接口契约

> epic_id: `epic-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2` · slice = architecture · depends_on S01_requirements
> Knowledge Context: solar-harness context inject used

## 依赖门控 (重要)

S02 在 epic DAG 中 depends_on S01_requirements。当前 S01 未 passed, autopilot 正抑制派发
(epic_waiting_dependency)。本计划为**预备产物**: builder 派发须等 S01 gate 通过, 本 Planner
不解除门控、不将状态翻成 active。

## DAG 概览

```
A1 (系统分层 + control/data plane + 状态归属 + O1 输入契约定型)
   ├─> A2 (接口契约 + 数据模型 + 阶段交接 schema)    ┐
   └─> A3 (失败恢复 + 重试边界 + O5 成功判据 + 观测)  ┘──> A4 (兼容/迁移 + 冲突/依赖/降级 + 父级 traceability 回写)
```

## 并行性分析
- A2 与 A3 都只依赖 A1, 写不同文件, write_scope 不冲突 → **可同批并行** (batch 2)。
- A4 join A2+A3。关键路径 A1→(A2∥A3)→A4, 长度 3, max-parallel=2。

## 节点 / Gate / Write Scope

| 节点 | 目标 | depends_on | gate | write_scope |
|---|---|---|---|---|
| A1 | 系统分层、control/data plane、状态归属; 定型 O1 上游算子输入契约 | — | layering-and-input-contract | `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s02-architecture.architecture.md` |
| A2 | 接口边界、数据模型、阶段交接 schema (ResearchRequest/OptimizedPrompt/DRPlan/DRResult) | A1 | interface-and-data-model | `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s02-architecture.interface-contracts.md` |
| A3 | 失败恢复、重试边界(上限/超时/退避)、O5 成功判据、观测设计 | A1 | failure-recovery-and-observability | `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s02-architecture.failure-recovery.md` |
| A4 | 旧系统兼容、迁移、冲突/依赖/降级策略; 必要时回写父级 traceability.json | A2,A3 | compat-conflict-degradation | `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s02-architecture.compat-migration.md`, `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s02-architecture.handoff.md` |

## Required Gates (parent-ready)
1. layering-and-input-contract (A1)
2. interface-and-data-model (A2)
3. failure-recovery-and-observability (A3)
4. compat-conflict-degradation (A4)

## 验收对齐 (contract)
- 设计覆盖 control/data plane、状态、失败恢复和观测 → A1 + A3。
- 写清楚接口边界和旧系统兼容方式 → A2 + A4。
- 列出冲突、依赖和降级策略 → A4。

## Stop / 安全规则
- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标 passed。
- 发现 scope 冲突必须回写父级 traceability。

## 上游/下游
- 上游: 消费 S01 的 requirements-matrix.md / traceability-map.md / non-builder-work.md (尚未生成, builder 派发时须已就绪)。
- 下游: A1-A4 设计是 S03_core_runtime (实现) 与 S04_orchestration_ui (调度/UI) 的输入。
