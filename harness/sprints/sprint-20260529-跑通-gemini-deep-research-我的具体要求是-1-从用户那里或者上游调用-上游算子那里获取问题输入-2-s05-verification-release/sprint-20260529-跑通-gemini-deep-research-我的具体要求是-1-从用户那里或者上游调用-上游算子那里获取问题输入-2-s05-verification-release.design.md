# Design — S05 验证、回归与发布证据

> slice = verification-release · depends_on S03_core_runtime + S04_orchestration_ui
> Knowledge Context: solar-harness context inject used (degraded)

## 0. 定位
建立端到端测试、负控、回归报告、文档与验收证据, **防止半截完成**。这是 epic 关闭的最终 gate。

## 1. 范围
- **端到端**: 跑通 O1-O6 完整链路一次 (取输入→优化提示词→调用 DR→点确定→监控重试→输出分类文献)。
- **负控**: 故意失败/降级场景 (Gemini 不可用、DR 失败重试到上限) 必须产生明确失败而非静默成功。
- **activation-proof**: ready 子任务激活、派发到正确角色可复现。
- **发布证据**: 回归报告 + 文档 + 写入知识库 raw; 父 epic 在所有 required gate 通过前不得关闭。

## 2. 验收对齐
- 单测/集成/负控/activation-proof 全部可复现 → V1+V2。
- 父 epic 不能在所有 required gate 通过前关闭 → V4 epic-close-guard。
- 产出最终 handoff/eval/report 并写入知识库 raw → V3+V4。

## 3. Stop Rules
缺 task_graph 不派 builder; 缺可复现验证不标 passed; scope 冲突回写父级 traceability; 不得用『已完成』替代证据。
