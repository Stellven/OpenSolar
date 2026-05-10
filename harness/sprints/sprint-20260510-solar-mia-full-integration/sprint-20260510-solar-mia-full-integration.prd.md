# PRD — Solar MIA Full Integration

## Goal

把 ECNU-SII/MIA 作为主参考实现引入 Solar，系统评估其 Manager/Planner/Executor/Memory-Serve/TTRL 能力，并设计和 Solar experience memory 的融合路线。

## User Value

- 不再只靠本地简化实现，而是吸收上游专家项目的完整机制。
- 保留 Solar 已有经验记忆资产，同时避免和上游 MIA 结构冲突。
- 在真正执行大规模训练或服务前，先知道依赖、风险、资源需求和可落地模块。

## Constraints

- 本 sprint 只做 vendor、inventory、collision、smoke、fusion design。
- 不跑大训练，不下载大模型，不改上游源码。
- 任何无法运行的 upstream component 必须标 pending 并写 blocker。

## DoD

D1-D6 全部达成，evaluator 复核报告能回答：哪些 MIA 模块能直接用、哪些要 adapter、哪些暂不接入、Solar 现有 experience layer 应如何迁移。
