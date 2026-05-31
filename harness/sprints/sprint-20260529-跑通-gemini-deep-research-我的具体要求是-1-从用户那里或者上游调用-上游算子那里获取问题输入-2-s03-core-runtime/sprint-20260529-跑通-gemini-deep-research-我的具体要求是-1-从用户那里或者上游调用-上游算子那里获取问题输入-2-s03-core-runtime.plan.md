# Plan — S03 核心实现与数据模型

> depends_on S02_architecture (passed 前不得派 builder; 当前 epic_waiting_dependency)
> Knowledge Context: solar-harness context inject used

## DAG
```
C1 (schemas + 数据模型 + 持久化)
  └─> C2 (状态机 + 核心 API, 状态可由事件重建)
        ├─> C3 (向后兼容适配层, 不破坏 wake/dispatch/status) ┐
        └─> C4 (单测覆盖 + event-replay 重建证明)            ┘
```
并行: C3 与 C4 都依赖 C2, 写不同路径 → batch 并行。关键路径 C1→C2→(C3∥C4)。

## 节点
| 节点 | 目标 | depends_on | gate | write_scope |
|---|---|---|---|---|
| C1 | schema/数据模型/持久化 | — | schemas-and-persistence | `lib/capabilities/gemini_deep_research/schemas/` |
| C2 | 状态机 + 核心 API | C1 | core-state-machine | `lib/capabilities/gemini_deep_research/core/` |
| C3 | 向后兼容适配层 | C2 | backward-compat | `lib/capabilities/gemini_deep_research/compat/` |
| C4 | 单测 + event-replay 证明 | C2 | unit-tests-and-replay | `lib/capabilities/gemini_deep_research/tests/` |

## Stop Rules
缺 task_graph 不派 builder; 缺可复现验证不标 passed; scope 冲突回写父级 traceability。
## 上下游
上游消费 S02 接口契约/数据模型/状态机设计; 下游被 S04(调度接入) 与 S05(端到端验证) 依赖。
