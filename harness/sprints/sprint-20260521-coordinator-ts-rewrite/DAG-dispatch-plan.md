# DAG Dispatch Plan: Coordinator TypeScript Rewrite

本文档规划了如何将 `PRD-coordinator-ts-rewrite.md` 的需求转化为可无头并行执行的开发任务 DAG（Directed Acyclic Graph）。

## 并行度策略 (Concurrency Strategy)
*   **目标最大并行度**：3 (避免本地 CPU/内存瓶颈，同时保持开发节奏紧凑)。
*   **Tmux Session**：`solar-build-ts-rewrite`。

## 任务 DAG 定义

### 阶段 1: 基础设施 (基础设施准备与类型定义)
*   **Task A1 [独立节点]**: 
    *   **描述**: 初始化配置与类型定义 (`types.ts`, `tsconfig.json`)。梳理原 `coordinator.sh` 的数据结构。
    *   **资源**: Pane 1
    *   **前置依赖**: 无

### 阶段 2: 核心模块开发 (高并发)
在 Task A1 完成后启动。这些模块彼此解耦，可以完全并行开发。

*   **Task B1 [状态管理子模块]**: 
    *   **描述**: 开发 `state.ts`。实现带文件锁的原子化 `save_state` 和 `load_state` 函数。
    *   **资源**: Pane 1
    *   **前置依赖**: Task A1
*   **Task B2 [事件监听与路由子模块]**: 
    *   **描述**: 开发 `router.ts`。复现原先处理请求和派发子系统的逻辑。
    *   **资源**: Pane 2
    *   **前置依赖**: Task A1
*   **Task B3 [并发压力测试脚本]**:
    *   **描述**: 编写一个基于 bun 的高频并发读写测试，用于验证 `state.ts` 的健壮性。
    *   **资源**: Pane 3
    *   **前置依赖**: Task A1

### 阶段 3: 组装与联调
*   **Task C1 [主入口集成]**:
    *   **描述**: 编写 `coordinator.ts` 主函数入口，整合 `state.ts` 和 `router.ts`，并调整对外暴露接口。
    *   **资源**: Pane 1
    *   **前置依赖**: Task B1, Task B2
*   **Task C2 [旧版测试套件适配与回归]**:
    *   **描述**: 运行并修正现存的 `test-coordinator*.sh`，确保通过率。
    *   **资源**: Pane 2
    *   **前置依赖**: Task C1

## 派单脚本 (Execution)
对应的 tmux 调度脚本已生成在 `execute-dag.sh`。
