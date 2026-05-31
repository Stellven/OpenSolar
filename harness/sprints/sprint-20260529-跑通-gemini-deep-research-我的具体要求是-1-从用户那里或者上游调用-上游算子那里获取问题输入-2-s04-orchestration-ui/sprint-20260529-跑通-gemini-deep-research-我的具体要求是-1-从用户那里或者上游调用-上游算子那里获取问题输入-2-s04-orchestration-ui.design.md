# Design — S04 调度、自动化与可视化

> slice = orchestration-ui · depends_on S02_architecture · package-first: `integrations/gemini_deep_research/`
> Knowledge Context: solar-harness context inject used (degraded)

## 0. 定位
把 S03 核心能力接入 autopilot / DAG 调度 / status UI / pane 可视化 / 运行时证据。**作为集成层独立成包**, 通过既有扩展点接入, 不直接改 PROTECTED_CORE。

## 1. 组件
- **orchestration**: ready 子任务自动激活并派到正确角色 (接 autopilot/DAG)。
- **status UI**: 显示 epic、child sprint、能力使用、阻塞原因。
- **runtime evidence**: pane 输出不再只靠自然语言声称完成 (结构化证据 + 截图/事件)。

## 2. 验收对齐
- ready 子任务自动激活并派到正确角色 → U1。
- UI 显示 epic/child/能力/阻塞 → U2。
- pane 输出有结构化运行时证据 → U3。

## 3. Stop Rules
缺 task_graph 不派 builder; 缺可复现验证不标 passed; scope 冲突回写父级 traceability; 只交付本切片。
