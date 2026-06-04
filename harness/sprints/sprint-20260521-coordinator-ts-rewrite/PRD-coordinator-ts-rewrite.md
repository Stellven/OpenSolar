# Product Requirements Document (PRD): Coordinator TypeScript Rewrite

## 1. 背景与目标 (Background & Objective)
当前 `solar-harness` 使用 `coordinator.sh` 作为核心协调器，负责状态管理和子脚本调用。然而在多进程并发环境下，`save_state` 遇到了不可忽视的资源竞争与竞态条件（例如 `.coordinator-state` 偶尔被损坏为 `:`），导致状态丢失，引发后续模块的级联故障。
**目标**：用 TypeScript（基于 Bun）完全重写 `coordinator.sh` 的核心状态管理及主循环逻辑，将其从脆弱的 bash 脚本转变为强类型的、能妥善处理并发读写的健壮守护进程。

## 2. 核心需求 (Core Requirements)
*   **强一致性状态管理**：使用文件锁或更高级的状态文件原子写机制（例如写临时文件后重命名），确保 `.coordinator-state` 永不损坏。
*   **向后兼容性**：新版 `coordinator.ts` 必须兼容现有的外部调用接口（如 `session.sh`、`archive.sh`），输入输出的数据结构和文件格式应保持一致。
*   **高并发事件处理机制**：利用 JS/TS 的异步事件循环模型（Event Loop），更高效地监听系统事件、处理子任务的派发和收尾，替代原来 bash 脚本中的 `sleep` 轮询和子进程锁竞争。
*   **性能提升**：Bun 拥有极快的启动和执行速度，需保证协调器处理指令延迟不超过原 bash 版本的水平（要求在几十毫秒级）。

## 3. 功能模块范围 (Scope)
*   **[In Scope]** 主循环事件轮询机制 (`event loop`) 的重写。
*   **[In Scope]** `save_state` 和 `load_state` 的 TypeScript 重构，引入互斥锁（如 `lockfile`）。
*   **[In Scope]** 协调器日志输出格式规范化。
*   **[Out of Scope]** 现有正常工作的子系统（如 `session.sh`, `token-tracker.sh`, `archive.sh`）本次不作修改。

## 4. 验收标准 (Acceptance Criteria)
1.  **单元测试覆盖**：新增的 state 管理模块包含至少 3 个高并发读写压力测试，不出现文件破坏或 `:` 的情况。
2.  **功能等效性测试**：现有的 `harness/tests/test-coordinator*.sh` 测试套件能够在使用 `coordinator.ts` 的情况下达到 100% 通过率。
3.  **内存与性能基准**：长期运行（模拟 24 小时）不存在内存泄漏，CPU 占用率不高于旧版。
