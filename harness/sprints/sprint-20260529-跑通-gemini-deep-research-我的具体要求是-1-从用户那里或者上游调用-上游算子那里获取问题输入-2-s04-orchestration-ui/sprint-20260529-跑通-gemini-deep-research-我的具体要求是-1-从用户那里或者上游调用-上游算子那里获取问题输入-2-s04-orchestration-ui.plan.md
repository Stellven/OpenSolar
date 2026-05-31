# Plan — S04 调度、自动化与可视化

> depends_on S02_architecture (passed 前不得派 builder)
> Knowledge Context: solar-harness context inject used

## DAG
```
U1 (orchestration: ready 自动激活 + 派到正确角色)
  ├─> U2 (status UI: epic/child/能力/阻塞)      ┐
  └─> U3 (runtime evidence: 结构化完成证据)      ┘──> U4 (集成 handoff)
```
并行: U2 与 U3 依赖 U1, 写不同路径 → batch 并行。U4 join。

## 节点
| 节点 | 目标 | depends_on | gate | write_scope |
|---|---|---|---|---|
| U1 | autopilot/DAG 自动激活并派到正确角色 | — | auto-activation | `integrations/gemini_deep_research/orchestration/` |
| U2 | status UI 显示 epic/child/能力/阻塞 | U1 | status-ui-surfacing | `integrations/gemini_deep_research/ui/` |
| U3 | 运行时结构化完成证据 (反『自然语言声称完成』) | U1 | runtime-evidence | `integrations/gemini_deep_research/evidence/` |
| U4 | 集成 handoff + scope 冲突回写 | U2,U3 | orchestration-handoff | `sprints/sprint-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2-s04-orchestration-ui.handoff.md` |

## Stop Rules
缺 task_graph 不派 builder; 缺可复现验证不标 passed; scope 冲突回写父级 traceability。
## 上下游
上游消费 S02 设计 + S03 核心 API; 与 S03 同为 S05 的依赖。
