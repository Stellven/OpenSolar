# Design — S03 核心实现与数据模型

> slice = core-runtime · depends_on S02_architecture · package-first: `lib/capabilities/gemini_deep_research/`
> Knowledge Context: solar-harness context inject used (degraded)

## 0. 定位
按 S02 架构落地核心库: 状态机、schema、持久化、向后兼容适配层。**新能力独立成包, 不改 harness 核心** (PROTECTED_CORE 禁区: solar-harness.sh / coordinator.sh / graph_scheduler.py 等)。

## 1. 组件
- **schemas/**: ResearchRequest / OptimizedPrompt / DRPlan / DRRunHandle / DRResult(references[]{category,title,url})。
- **state_machine.py**: states = INPUT→OPTIMIZE→SUBMIT→CONFIRM→MONITOR→{DONE|RETRY|FAIL}; 状态可由事件/元数据重建 (contract 验收)。
- **persistence**: 事件流落盘, 支持重建。
- **compat adapter**: 接入但不破坏现有 wake/dispatch/status 主路径。

## 2. 验收对齐
- 核心 API 有单测覆盖 → C4。
- 旧路径兼容, 不破坏 wake/dispatch/status → C3。
- 状态变更可由元数据或事件重建 → C2 设计 + C4 event-replay 证明。

## 3. Stop Rules
缺 task_graph 不派 builder; 缺可复现验证不标 passed; scope 冲突回写父级 traceability; 只交付本切片。
