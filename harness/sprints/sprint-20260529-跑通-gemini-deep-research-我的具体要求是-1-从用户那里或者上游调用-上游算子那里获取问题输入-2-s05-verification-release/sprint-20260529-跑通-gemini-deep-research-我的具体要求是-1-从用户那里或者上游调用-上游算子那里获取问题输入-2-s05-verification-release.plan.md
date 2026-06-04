# Plan — S05 验证、回归与发布证据

> depends_on S03_core_runtime + S04_orchestration_ui (二者皆 passed 前不得派 builder)
> Knowledge Context: solar-harness context inject used

## DAG
```
V1 (端到端 O1-O6 流程测试)
  ├─> V2 (负控 + activation-proof, 可复现)     ┐
  └─> V3 (文档 + README)                         ┘──> V4 (回归报告 + KB raw 导出 + epic-close-guard)
```
并行: V2 与 V3 依赖 V1, 写不同路径 → batch 并行。V4 join。

## 节点
| 节点 | 目标 | depends_on | gate | write_scope |
|---|---|---|---|---|
| V1 | 端到端 O1-O6 完整链路测试 (含成功判据) | — | e2e-flow-test | `tests/gemini_deep_research/e2e/` |
| V2 | 负控 + activation-proof, 全部可复现 | V1 | negative-and-activation-proof | `tests/gemini_deep_research/control/` |
| V3 | 文档 + README | V1 | docs | `integrations/gemini_deep_research/README.md` |
| V4 | 回归报告 + 知识库 raw 导出 + epic 关闭门控 | V2,V3 | regression-and-release-evidence | `reports/gemini_deep_research/`, `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s05-verification-release.handoff.md` |

## Stop Rules
缺 task_graph 不派 builder; 缺可复现验证不标 passed; 父 epic 在所有 required gate 通过前不得关闭。
## 上下游
上游消费 S03 核心实现 + S04 调度/UI/证据; 是 epic 终态 gate, 通过后父 epic 方可关闭。
