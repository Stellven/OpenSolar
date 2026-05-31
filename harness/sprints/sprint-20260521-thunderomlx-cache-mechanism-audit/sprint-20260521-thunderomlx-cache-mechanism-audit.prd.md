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

---

## 用户问题 / Problem

- **PB-1 旧盘点不可信**：用户认为之前的 ThunderOMLX 缓存机制总结是凭记忆做的，没有源码 / 配置 / 运行态对齐，导致看不准"哪些机制真的开了 / 哪些有路径但默认 off / 哪些被 unsafe-skip 关掉了"。
- **PB-2 多层缓存交互不明**：ThunderOMLX 在 Mac mini 8002 上跑 Qwen3.6，涉及 L1 RAM hot cache（8 GB）、L2 RAID0 SSD 冷盘、Paged KV、Shared KV、Two-tier、KVTC、Prompt Cache 等至少 7 层；交互路径（命中 → fallback → 预取 → AnthropicProxy 绕过）没有可视化，导致决策时只能猜。
- **PB-3 启用风险未量化**：用户怕开错 partial block cache / full skip / approximate skip 这类"近似"特性导致 perplexity 退化；目前没有按机制分级（已启用 / 可安全启用 / 需 gated / 不建议）的清单。
- **PB-4 实验路径缺失**：没有按 P0/P1/P2 排序的实验菜单（指标、命令、回滚、禁止项），导致优化没法分阶段推进。
- **PB-5 PRD schema 缺 7 节**：coordinator gate_prd_schema 反复触发，本次 dispatch 即为修复。

## 用户故事 / User Stories

- **US-01 (ThunderOMLX 运维)**：作为运维，我希望拿到一份基于源码 / 测试 / 8002 实时日志的全量盘点，每个机制都附文件路径 + 配置开关 + 当前运行态证据，不是凭记忆。
  - 验收：N3-handoff 已交付 21KB monitor report，31 个机制 / 7 个层 / 完整证据链 ✅。
- **US-02 (性能工程师)**：作为性能工程师，我希望知道哪几条机制现在没开但开了**安全**能拿增益，哪些必须 gated 实验。
  - 验收：N3 final report §6 "明确不建议立即开启的特性"表 + P0/P1/P2 实验菜单 ✅。
- **US-03 (架构师 / 决策层)**：作为决策层，我希望看到一张中文总表 + 一张交互拓扑图，10 分钟内能定优先级。
  - 验收：monitor-report §1 中文分类表 + §2 ASCII 交互图 ✅。
- **US-04 (Evaluator)**：作为 Evaluator，我希望本 sprint 留下"未验证声明"专章，让我能区分哪些数据是实测 / 估算 / 待 A/B 测试。
  - 验收：N3-handoff 已含独立"未验证"章节 ✅。
- **US-05 (PM / Coordinator)**：作为 coordinator，本次 PM 修复 PRD 后必须能通过 gate_prd_schema，避免无限循环重派。
  - 验收：本切片即修复，validate.sh prd → PASS。

## 功能需求 / Requirements

- **FR-1 静态盘点 (N1)**：扫描 `/Users/lisihao/ThunderOMLX` 源码 + 文档 + 测试，列出 ≥30 个缓存机制；每条含文件路径、配置 key、默认值、单元测试位置。
- **FR-2 运行时审计 (N2)**：基于 8002 服务的日志窗口（2026-05-20 21:14 → 2026-05-21 08:12），统计哪些机制实际触发、命中率、冷恢复路径、是否被 unsafe-skip 关掉。
- **FR-3 最终综合 (N3)**：把 N1 静态 + N2 运行时合成一份中文 audit，含：
  - §1 中文分类表（机制、层级、存在、当前启用、收益路径、风险、建议优先级）
  - §2 ASCII 交互图（L1 → L2 → 冷恢复 / AnthropicProxy 绕过 / 预取并行）
  - §3 P0/P1/P2 实验菜单（指标、命令、回滚、禁止项）
  - §4 已实测速度（4.5× 热命中加速等，必须附日志行号）
  - §5 量化数据 vs 估算 vs 待 A/B 显式区分
  - §6 "明确不建议立即开启"表（KVTC / FlashMLX / CacheVM / MemCollab / block_size_enlargement）
  - §7 未验证声明专章
- **FR-4 安全约束**：禁止重新启用 partial block cache / full skip / approximate skip；只允许写"分析"或"gated 建议"，不能写"应当现在开"。
- **FR-5 不打印 secrets**：报告中不出现 token / API key / OAuth code；日志摘录前 redact。
- **FR-6 不改 ThunderOMLX**：本切片只产报告，不改 ThunderOMLX 源码 / 配置 / 缓存目录；不重启 8002。
- **FR-7 PRD schema 合规**：本 PRD 含 schema 必需 11 节；通过 `validate.sh prd`。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / ThunderOMLX 8002 在线 / Qwen3.6 MLX-4bit / RAID0 cache 27 GB / 8 GB hot RAM cache。
- **路径白名单**：报告写 `~/.solar/harness/monitor-reports/`；handoff 写 `~/.solar/harness/sprints/<sid>.N*-handoff.md`；禁 `/tmp`、禁用户 home 根。
- **只读源码**：`/Users/lisihao/ThunderOMLX` 只读；不允许 git mutate、不允许写配置、不允许写缓存目录。
- **不重启 8002**：除非用户单独授权；本切片不动服务进程。
- **不允许 unsafe 特性**：partial block cache / full skip / approximate skip 不允许默认开启，只允许"分析"或"P2 gated 实验菜单"。
- **不打印 secrets**：所有日志摘录 redact。
- **API 兼容**：不破坏 ThunderOMLX 任何对外 API；本切片不动 server.py / cache.py 任何 export。
- **PM 角色边界**：PM 不写实施代码；本切片是回溯 PRD schema 补全；不动 `.finalized` / status.json / N1-N3 handoff / monitor-report。

## 风险 / Risks

| 风险 | 影响 | 缓解 / 状态 |
|------|------|--------------|
| 报告把估算当实测 | 决策误导 | N3 §7 "未验证声明"专章 + 4.5× 加速附日志行号 ✅ |
| 误推 P2 unsafe 特性立即开 | perplexity 退化 | §6 显式标 "不建议立即开启" + 开启前提条件 ✅ |
| 把 block_size_enlargement 当增益 | 原意是测试 skip logic | §6 表显式提示原意不明 + 实施前需代码审查 ✅ |
| KVTC <1% perplexity 承诺没量化到代码/数学任务 | 业务退化盲点 | §6 标记"不建议立即开启" ✅ |
| N2 日志窗口短（约 11 小时），Prewarm Pane 1-3 状态未验证 | 预热完整性存疑 | N3 已声明 "Prewarm 截断于行 69"，留 OQ ✅ |
| AME MemBoost 表名未明 | E0-A 修复时找不到目标表 | OQ-01 留给后续 |
| 服务曾自停机但无 traceback 可见 | 根因不明 | OQ-02 留给后续 |
| ContextPilot pip 包名可能不是 `contextpilot` | E1-B 实施前装错 | OQ-03 留给后续 |
| 报告打印 secrets | 安全违规 | FR-5 redact + N3 已抽查 ✅ |
| 本 PRD 缺 7 schema section 触发 gate 循环 | PM 反复重派 | 本切片即修复 ✅ |

## 开放问题 / Open Questions

- **OQ-01 AME MemBoost 修复目标表名**：E0-A 需要确认 `~/.omlx/*.db` 中具体哪张表 schema 异常。**Owner**：后续 ThunderOMLX 修复 sprint。
- **OQ-02 服务自停机根因**：N2 观察到曾停过，但无 crash traceback；可能与内存压力 / 系统休眠相关。**Owner**：后续 observability sprint。
- **OQ-03 ContextPilot 真实包名**：E1-B 需要 `pip show` 或源码确认；可能不是 `contextpilot`。**Owner**：实施 E1-B 之前 30s pre-flight。
- **OQ-04 E1-D / E2-A / E2-B / E2-C 实测增益**：报告中标"估算"；需要 A/B 跑通才能下结论。**Owner**：后续性能实验 sprint。
- **OQ-05 Prewarm Pane 1-3 完整性**：N2 日志被截断；需要重新跑或扩窗。**Owner**：后续 audit refresh。
- **OQ-06 8002 是否需要监控告警**：服务停机没人发现，需不需要加 healthcheck？**Owner**：未来 ops sprint。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（含 5 个用户故事 + 7 条功能需求 + 约束/风险/开放问题）。
- `…contract.md`、N1-handoff、N2-handoff、N3-handoff。
- 已交付的最终报告 `~/.solar/harness/monitor-reports/thunderomlx-cache-mechanism-audit.md`（21 KB，含 31 机制 / 7 层 / P0-P2 实验菜单 / 未验证声明专章）。
- N1 详细清单 `…N1-inventory.md` 和 N2 详细运行时 `…N2-runtime.md`（如存在于 monitor-reports/）。
- `.finalized` 标记（sprint 已 passed）。

### 当前实施状态（已交付，回溯不重做）

| 功能 | 状态 | 证据 |
|------|------|------|
| FR-1 静态盘点 (N1) | ✅ | 31 机制 / 7 层 / N1-handoff |
| FR-2 运行时审计 (N2) | ✅ | 11 小时日志窗口 / 4.5× 热命中加速实测 |
| FR-3 最终综合 (N3) | ✅ | monitor-report 21 KB / §1-§7 全 |
| FR-4 安全约束（不重启 unsafe） | ✅ | §6 表显式不建议 |
| FR-5 不打印 secrets | ✅ | N3 抽查通过 |
| FR-6 不改 ThunderOMLX | ✅ | 只读源码 |
| FR-7 PRD schema 合规 | ✅ | 本切片即修复 |

### 给 Coordinator 的明确指令

- **不要回写 status**：本 sprint 已 `.finalized`；coordinator 当前把状态拉回 `drafting/prd_ready` 仅为 gate_prd_schema 触发的回溯副作用。
- **触发机制**：PRD mtime 刷新；coordinator 下一 tick 重跑 `validate.sh prd` → PASS → 关闭 gate，**不要 advance 到 planner**，识别 `.finalized` 后恢复 passed。

### 未尽事项（留给后续 sprint）

- OQ-01..OQ-06 全部留给后续 sprint，特别是 OQ-01（AME MemBoost 表名）、OQ-03（ContextPilot 包名）作为实施 E0-A / E1-B 的 pre-flight。
- E1-D / E2-A / E2-B / E2-C 的 A/B 实测增益。
- 8002 服务 healthcheck / 告警。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch unified-context block)。
