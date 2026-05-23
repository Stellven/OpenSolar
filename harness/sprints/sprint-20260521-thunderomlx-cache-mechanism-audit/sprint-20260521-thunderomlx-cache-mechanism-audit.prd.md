# PRD — ThunderOMLX Cache Mechanism Audit

Sprint: `sprint-20260521-thunderomlx-cache-mechanism-audit`
Created: 2026-05-21T12:17:50Z
Priority: P0
Lane: analysis / performance

## 背景
用户认为此前 ThunderOMLX 缓存机制盘点不完整，要求由 Mac mini 的 solar-harness 基于 `/Users/lisihao/ThunderOMLX` 源码、文档、测试和当前运行态，重新做全量缓存机制分析，而不是凭记忆总结。

## 目标
形成一份可执行的 ThunderOMLX 缓存机制全景报告，覆盖 ContextPilot、Prompt Cache、Paged KV/SSD、RAM hot cache、Shared KV、Two-tier cache、KVTC、workflow/cache warmer、predictive prefetch、tool-call pinning、cache VM、semantic/memcollab/cache advisor 等所有可发现机制，并区分：存在/启用/可安全启用/风险/下一步实验。

## 验收标准
- 报告必须基于源码/文档/测试/运行态证据，列出每项机制的文件路径、配置开关、当前运行状态和证据。
- 必须包含当前 Mac mini 运行态：8002 服务、Qwen3.6 模型、RAID0 cache、8GB hot cache、unsafe skip features 状态。
- 必须输出一张中文总表：机制、层级、存在、当前启用、收益路径、风险、建议优先级。
- 必须输出 P0/P1/P2 实验计划，包含指标、命令、回滚和禁止项。
- 不允许重新启用 partial block cache / full skip / approximate skip；只能分析或建议 gated experiment。
- 不打印任何 token/API key。

## 非目标
- 不直接修改 ThunderOMLX 代码。
- 不删除缓存目录。
- 不重启 8002 服务，除非后续用户明确授权。

## 输出物
- `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-cache-mechanism-audit.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-thunderomlx-cache-mechanism-audit.N1-handoff.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-thunderomlx-cache-mechanism-audit.N2-handoff.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-thunderomlx-cache-mechanism-audit.N3-handoff.md`
