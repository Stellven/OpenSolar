# Plan — S01 需求拆解与追踪矩阵

> epic_id: `epic-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2` · slice = requirements
> Knowledge Context: solar-harness context inject used

## DAG 概览

需求工程链: 先枚举 outcome, 再并行做「边界分析」与「追踪映射」, 最后汇总 handoff。

```
R1 (outcome 矩阵枚举 O1-O6 + 验收 + 风险边界)
   ├─> R2 (非-builder 工作边界清单)        ┐
   └─> R3 (epic→子sprint 追踪矩阵)          ┘──> R4 (handoff 汇总 + 可复现验证说明)
```

## 并行性分析

- R2 与 R3 都只依赖 R1, 且写入**不同文件** (R2→non-builder-work.md, R3→traceability-map.md), write_scope 不冲突 → **可同批并行** (batch 2)。
- R4 join R2+R3 后产出 handoff。
- 关键路径: R1 → (R2∥R3) → R4, 长度 3。max-parallel=2。

## 节点 / Gate / Write Scope

| 节点 | 目标 | depends_on | gate | write_scope |
|---|---|---|---|---|
| R1 | 枚举 O1-O6, 每条给验收标准+风险边界+机器可验证信号 | — | outcomes-enumerated | `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s01-requirements.requirements-matrix.md` |
| R2 | 列出不能直接派 builder 的工作 + 理由 | R1 | non-builder-boundary-defined | `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s01-requirements.non-builder-work.md` |
| R3 | O1-O6 → S02-S05 追踪映射, 标上游依赖/下游影响/未闭环 | R1 | traceability-map-complete | `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s01-requirements.traceability-map.md` |
| R4 | 汇总 R1-R3, 写上游依赖/下游影响/未闭环 + 可复现验证 | R2,R3 | requirements-handoff-consolidated | `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s01-requirements.handoff.md` |

## Required Gates (parent-ready)
1. outcomes-enumerated (R1)
2. non-builder-boundary-defined (R2)
3. traceability-map-complete (R3)
4. requirements-handoff-consolidated (R4)

## Stop / 安全规则 (contract)
- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突必须回写父级 traceability.json。
- 只交付本切片; 不得用「已完成」替代可复现证据; 不得用单个大 PRD 覆盖所有实现细节。

## 下游影响 (供 coordinator)
- R3 的追踪矩阵是 S02_architecture 的输入 (epic traceability 中 S02 depends_on requirements)。
- 输入契约 (O1 上游算子接口)、成功判据 (O5)、重试边界等开放项必须传递给 S02, 不在本切片闭环。
