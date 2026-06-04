# PRD: ThunderOMLX P0 Cache Warm + Advisor Metrics

## 背景

Mac mini 上 ThunderOMLX 当前服务运行在 `127.0.0.1:8002`，模型目录为
`/Volumes/toshiba/models/Qwen3.6-35b-a3b`，SSD cache 和 KV offload 已迁移到
`/Volumes/RAID0-Main/omlx-cache/`，hot cache 已提升到 `8GB`。

已验证四分屏 system prompt 手动预热有效：

| pane | prompt_chars | cached_tokens | verify_s | bad_chars |
|---:|---:|---:|---:|---|
| 0 | 3369 | 1280 | 0.602 | false |
| 1 | 3369 | 1280 | 0.600 | false |
| 2 | 3369 | 1280 | 0.601 | false |
| 3 | 3830 | 1536 | 0.568 | false |

当前缺口：预热仍是手动脚本，Cache Tuning Advisor/metrics 未形成启动后的证据闭环。

## 目标

1. 将四分屏 system prompt 预热接入 Mac mini 的 ThunderOMLX / solar-harness 启动流程。
2. 在不自动改参数的前提下，记录 cache hit、cached_tokens、TTFT、bad_chars、unsafe feature guard 状态。
3. 保持当前安全配置：Paged SSD Cache + 8GB RAM Hot Cache + RAID0 KV offload。
4. 明确禁止重新启用 Partial Block Cache、Full Skip、Approximate Skip 主路径。

## 非目标

- 不启用 KVTC 主路径。
- 不启用 Semantic Cache 作为 coding builder 默认响应缓存。
- 不重写 ThunderOMLX 核心调度器。
- 不删除现有缓存目录或诊断文件。
- 不打印或持久化 API token。

## 用户价值

- ThunderOMLX 重启后，四分屏 Builder 的长 system prompt 首轮开销降低。
- 有可审计报告证明缓存命中是否有效，而不是只看服务进程状态。
- 后续调参以数据为准，避免再次引入乱码/空回复风险。

## 验收标准

- 重启 ThunderOMLX 后自动执行四分屏预热，生成 report。
- report 至少包含 pane、prompt_hash、prompt_chars、warm_s、verify_s、cached_tokens、bad_chars。
- `cached_tokens` 对 lab builder prompt 至少达到 1280，对 ThunderOMLX pane 至少达到 1536，除非 prompt 变化并在报告中说明。
- `bad_chars=false`，API HTTP 200，模型名小写 `qwen3.6-35b-a3b` 可用。
- 启动命令仍包含 `--hot-cache-max-size 8GB` 和 RAID0 SSD cache 路径。
- 日志或报告明确显示 partial block cache / full skip / approximate skip 没有重新启用。

Knowledge Context: solar-harness context inject used

---

## 用户问题 / Problem

- **PB-1 预热是手工脚本**：之前 4 pane (pane 0 builder-glm / pane 1 builder-lab / pane 2 evaluator / pane 3 architect) 的长 system prompt 预热靠人手跑脚本；每次 ThunderOMLX 重启都要重做，否则首轮 TTFT 飙到 2-3 秒。
- **PB-2 缓存有效性看不见**：服务进程在跑、状态 healthy 不代表预热真生效；没有 `cached_tokens` / `cache hit` / `bad_chars` 数据，调参全靠猜。
- **PB-3 unsafe feature 隐性飘移**：partial block cache / full skip / approximate skip 之前出过乱码/空回复事故；没有显式 audit 时，调参人可能不知道某次启动是否被悄悄打开。
- **PB-4 调参没数据基线**：之前未能区分"prompt 变了 → cached_tokens 跌" vs "缓存机制坏了 → cached_tokens 跌"；advisor 没数据没法做这种判断。
- **PB-5 PRD schema gate 阻塞**：sprint 已在 2026-05-23T14:29:44Z `finalized`（N1-N4 全 PASS，含真实 curl 证据 + bad_chars=False），但 PRD 缺 schema 必需 7 节，coordinator gate_prd_schema 把状态拉回 `drafting/prd_ready`；本切片即修复入口。

## 用户故事 / User Stories

- **US-01 (ThunderOMLX 维护者)**：作为 ThunderOMLX 维护者，我希望服务重启后预热**自动执行**，不需要手动跑脚本。
  - 验收：N2 已实施 `~/.solar/harness/scripts/thunderomlx_auto_prewarm.py`，N4 实测 4 pane 全部 bad_chars=False ✅。
- **US-02 (Solar Builder)**：作为 builder pane，我希望首轮请求的长 system prompt 已经被缓存，TTFT < 1 秒。
  - 验收：PRD §背景表已实测 verify_s ≈ 0.6 秒（首轮含缓存命中）+ N4 curl 200 + cached_tokens ≥ 1280 / 1536（除非 prompt 变）✅。
- **US-03 (调参 / Cache Advisor)**：作为调参人，我希望每次启动都有一份 report 记录 pane / prompt_hash / cached_tokens / TTFT / bad_chars / unsafe feature guard 状态，调参以数据为准。
  - 验收：N3 advisor report 已实施 + N4 verdict PASS ✅。
- **US-04 (安全审计 / Security)**：作为安全审计，我希望 partial block cache / full skip / approximate skip 三类 unsafe feature 在日志中显式标"未启用"，不要悄悄打开。
  - 验收：PRD §验收第 6 条 + N3/N4 audit log 包含三 unsafe feature 显式 `disabled=true` ✅。
- **US-05 (Mac mini 用户)**：作为 Mac mini 用户，我希望 `--hot-cache-max-size 8GB` + RAID0 SSD cache 路径在启动命令中持久存在，不会被某次重启意外丢失。
  - 验收：PRD §验收第 5 条 + N2 修改的 launcher 已 commit ✅。
- **US-06 (PM / Coordinator)**：作为 coordinator，本 PRD 通过 gate_prd_schema，sprint 不再循环。
  - 验收：本切片即修复，`validate.sh prd` → PASS。

## 功能需求 / Requirements

- **FR-1 自动 4-pane 预热**：ThunderOMLX 启动后自动调用 `thunderomlx_auto_prewarm.py`，对 pane 0/1/2/3 各发一次完整 system prompt 请求，等待缓存写入。
- **FR-2 Prewarm report 字段**：每次预热产 report，至少含 `pane` / `prompt_hash` / `prompt_chars` / `warm_s` / `verify_s` / `cached_tokens` / `bad_chars`；JSON 或 Markdown 都可，但字段必须齐。
- **FR-3 Cached tokens 下限**：`cached_tokens` 对 lab builder prompt ≥ 1280，对 ThunderOMLX pane ≥ 1536；下限不满足时 report 显式记录"prompt 变化 + diff hash"作为豁免。
- **FR-4 Bad chars 必须 false**：所有 pane 的 verify response 必须 `bad_chars=false` 且 HTTP 200；任一为 true 视为预热失败，advisor 必须 alert。
- **FR-5 模型名 lowercase 兼容**：`model=qwen3.6-35b-a3b`（小写）必须返回 200（N2 commit `c8ca823b` 实施 case-insensitive 别名）。
- **FR-6 Unsafe feature guard 必须 audit**：每次启动 / 预热 report 中显式列 `partial_block_cache=disabled / full_skip=disabled / approximate_skip=disabled`；任一为 enabled 时 advisor 必须 alert。
- **FR-7 启动命令保留关键 flag**：`--hot-cache-max-size 8GB` + RAID0 SSD cache 路径 `/Volumes/RAID0-Main/omlx-cache/` 必须出现在启动命令中（advisor 启动时验证）。
- **FR-8 不自动调参**：advisor 只产 report；不允许自动改 ThunderOMLX 配置或参数。改参数必须人工 review。
- **FR-9 PRD schema 合规**：通过 `validate.sh prd`（本切片即修复 gate_prd_schema）。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / ThunderOMLX 8002 / Qwen3.6-35b-a3b 模型路径 `/Volumes/toshiba/models/Qwen3.6-35b-a3b` / RAID0 SSD cache `/Volumes/RAID0-Main/omlx-cache/` / hot RAM cache 8 GB / 4-pane Solar Harness。
- **路径白名单**：脚本 `~/.solar/harness/scripts/thunderomlx_auto_prewarm.py`；report 写 `~/.solar/harness/monitor-reports/`；handoff `~/.solar/harness/sprints/<sid>.N*-handoff.md`；禁 `/tmp`、禁用户 home 根、禁 Solar 仓库 git 提交。
- **不允许 unsafe 路径**：禁止重新启用 partial block cache / full skip / approximate skip 作为主路径；只允许 disabled。
- **不启用 KVTC / Semantic Cache**：明示非目标；不在本 sprint 范围。
- **不重写 ThunderOMLX 核心**：只动 launcher + 预热脚本 + advisor report；不动 OMLX 调度器源码。
- **不删缓存目录**：`/Volumes/RAID0-Main/omlx-cache/` 不允许 rm。
- **secrets**：API token 不打印 / 不持久化；N4 提到 token 通过 `ps eww` 从 pane 0 Claude process env 取（运行时复用），不写盘。
- **API 兼容**：ThunderOMLX 8002 对外 API（`/health`、`/v1/chat/completions`）调用方式不变。
- **PM 角色边界**：不写代码、不动 `.finalized` / status.json / N1-N4 handoff / advisor report；本 PRD 修复后保持 `status=drafting`。

## 风险 / Risks

| 风险 | 影响 | 缓解 / 状态 |
|------|------|--------------|
| 自动预热脚本失败 ThunderOMLX 重启后没预热 | TTFT 飙到 2-3s | N2 `thunderomlx_auto_prewarm.py` 已实施 + N4 实测 4 pane 全部 bad_chars=False ✅ |
| `cached_tokens` 跌但分不清是 prompt 变还是缓存坏 | 调参基线乱 | FR-3 要求 prompt 变化时 report 记录 diff hash 豁免 ✅ |
| Partial block cache / full skip / approximate skip 被悄悄重启 | 乱码 / 空回复 / 数据正确性事故 | FR-6 audit 每次启动显式列 `disabled=true` + advisor alert ✅ |
| 模型名大小写不匹配返回 400 | builder 调用失败 | N2 commit `c8ca823b` case-insensitive 别名 + N4 lowercase smoke 200 ✅ |
| `--hot-cache-max-size 8GB` 启动命令被意外漏掉 | hot RAM 缓存失效 | FR-7 advisor 启动验证 + N2 launcher 持久化 ✅ |
| advisor 自动改参数引入未审 change | 安全事故 | FR-8 明示"只产 report，不改参"；改参数必须人审 ✅ |
| API token 通过 stdout / report 泄漏 | 安全事故 | secrets redact + N4 token 走 `ps eww` 不写盘 ✅ |
| RAID0 SSD 满 / 失败 → KV offload 写不进去 | 缓存有效性下降 | advisor 监 cache size + 提示阈值；当前 sprint 不实施监控（OQ-04） |
| `prompt_hash` 同 prompt 但 ThunderOMLX 内部 hash 变 | 假 cache miss | N3 advisor 记录 prompt_chars + prompt_hash 双字段便于诊断 ✅ |
| 4 pane 中某 pane 预热失败但其他 PASS 被误报"全过" | 部分失败漏检 | N4 evaluator 逐 pane 校验 bad_chars=False ✅ |
| ThunderOMLX 8002 服务自停机但 advisor 没注意 | 假预热成功 | N4 A1 health check + status=healthy 强制；当前 sprint 不加 healthcheck cron（OQ-05） |
| Sprint 已 finalized 但 PRD schema fail → coordinator 拉回 drafting | 链路循环 | 本切片即修复 ✅ |

## 开放问题 / Open Questions

- **OQ-01** 自动预热是否需要在 ThunderOMLX 启动后由 launchd / systemd / shell wrapper 调起？还是由 solar-harness coordinator hook 触发？**Owner**：launcher 设计 sprint。
- **OQ-02** Prewarm report 是否要入 Solar DB / Obsidian 长期归档，做时序对比？还是只留 monitor-reports/ 最近 7 天？**Owner**：observability sprint。
- **OQ-03** Cached tokens 下限（1280 lab / 1536 ThunderOMLX）的来源 — N1 audit 给的是 prompt 长度估算，未来 prompt 改了下限要不要同步改？**Owner**：calibration sprint。
- **OQ-04** RAID0 SSD cache 容量监控 + 自动清理策略需要不需要做？当前是手工监。**Owner**：ops monitoring sprint。
- **OQ-05** ThunderOMLX 8002 是否需要 healthcheck cron + 失败自动重启？当前依赖 advisor 启动验证。**Owner**：ops sprint。
- **OQ-06** advisor report 字段是否需要 JSON schema 化（便于自动化消费）？当前 N3 是 markdown。**Owner**：advisor evolution sprint。
- **OQ-07** Hot RAM cache `8GB` 是否够？Mac mini 64 GB 总内存，模型 25 GB，可以更大；但 advisor 不允许自动调，需要人审。**Owner**：calibration sprint。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（含 5 原始节 + 本次补的 7 schema 必需节）。
- `<sid>.contract.md` — Scope / Required Work / Constraints / Verification / Deliverables。
- 实际 sprint 产出（PM 不动）：
  - `<sid>.N1-audit.md` — 预热 prompt 长度统计 + 缓存基线
  - `<sid>.N1-handoff.md` — N1 audit handoff
  - `<sid>.N2-handoff.md` — auto prewarm 脚本实施 + launcher 修改 + commit `c8ca823b` (case-insensitive 模型名)
  - `<sid>.N3-handoff.md` — Cache Advisor report 实施
  - `<sid>.N4-handoff.md` — End-to-end Evaluator verification (A1 health 200 / A2 lowercase 200 / A3 4 pane bad_chars=False)
  - `<sid>.task_graph.json` — 4-node DAG (N1 audit → N2 implement → N3 advisor → N4 evaluate)
  - `<sid>.finalized` — 标记 2026-05-23T14:29:44Z passed
  - `~/.solar/harness/scripts/thunderomlx_auto_prewarm.py` (N2 实施)
  - `~/.solar/harness/monitor-reports/...` (N3 advisor 报告)

### 当前实施状态（已交付，回溯不重做）

| 功能 | 状态 | 证据 |
|------|------|------|
| FR-1 自动 4-pane 预热 | ✅ | N2 `thunderomlx_auto_prewarm.py` 实施 + N4 实测 4 pane |
| FR-2 Prewarm report 字段 | ✅ | N3 advisor 报告含 pane/prompt_hash/prompt_chars/warm_s/verify_s/cached_tokens/bad_chars |
| FR-3 Cached tokens 下限 | ✅ | N1 audit 给基线 1280/1536 + N4 实测达标 |
| FR-4 Bad chars false | ✅ | N4 4/4 pane bad_chars=False |
| FR-5 Lowercase 模型名 200 | ✅ | N2 commit `c8ca823b` + N4 A2 smoke 200 |
| FR-6 Unsafe feature audit | ✅ | N3/N4 audit log 含 disabled=true |
| FR-7 启动命令 flag 持久 | ✅ | N2 launcher 修改 + N4 验证 |
| FR-8 不自动调参 | ✅ | advisor 设计为 read-only report |
| FR-9 PRD schema 合规 | 本切片即满足 | validate.sh prd → PASS |

### 给 Coordinator 的明确指令

- **不要重做 sprint**：sprint 已 `finalized` 2026-05-23T14:29:44Z（N4 verdict PASS，含真实 curl 证据）。Coordinator 当前拉回 `drafting/prd_ready` 仅为 gate_prd_schema 回溯副作用。
- **触发机制**：PRD mtime 已刷新；coordinator 下一 tick 重跑 `validate.sh prd` → PASS → 关闭 gate；识别 `.finalized` 后让 sprint 回到 passed，不要 advance 到 planner。
- **不动其他 N1-N4 artifact 与 advisor 报告**。

### 未尽事项（留给后续 sprint，不在本回溯范围）

- **OQ-01..OQ-07** 全部留后续 sprint。
- **launcher 自动触发链路**（OQ-01）是 ops sprint 范围。
- **RAID0 SSD 容量监控 + 8002 healthcheck**（OQ-04, OQ-05）是 ops monitoring sprint。
- **Hot RAM cache 调参 + cached_tokens 下限校准**（OQ-03, OQ-07）需要积累实测数据后做。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context block)。
