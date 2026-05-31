# PRD — ThunderOMLX 知识抽取缓存基准

## 背景

当前已经证明 Mac mini 上的 ThunderOMLX 可以通过无头 multi-task tmux worker 完成知识抽取，并在同一批文档复跑时出现高前缀 KV cache 命中。单次冷/热对比不足以作为稳定性能结论，需要用小样本矩阵验证缓存命中率口径、延迟收益、乱码风险和热缓存路径。

## 目标

在 Mac mini 上用 ThunderOMLX/Qwen3.6 执行知识抽取缓存基准：

- 3 种文档长度：short、medium、large。
- 每种长度 3 次冷跑 + 3 次热跑。
- 记录 wall latency、input/output tokens、cache_read_input_tokens、cache_creation_input_tokens、cache_hit_ratio、bad_chars。
- 输出 p50/p95、热跑平均 cache hit、p50 speedup。

## 非目标

- 不重启 ThunderOMLX。
- 不删除 cache。
- 不启用 Partial Block Cache、Full Skip、Approximate Skip。
- 不暴露 API key/token。
- 不用 Claude/Gemini 执行粗活。

## 验收

- `thunderomlx-benchmark` profile 为 `backend=command` 且 `model=thunderomlx`。
- 报告存在：`/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-knowledge-cache-benchmark.md`。
- JSON 结果存在：`/Users/lisihao/.solar/harness/run/thunderomlx-knowledge-cache-benchmark/results.json`。
- 每档长度至少 6 行结果，合计至少 18 行。
- 所有行 `bad_chars=false`。
- 热跑行必须记录 `cache_read_input_tokens` 与 `cache_hit_ratio`。
- 报告必须明确说明：cache_hit_ratio 是前缀 KV block 命中率，不等同于端到端成本节省率。

---

## 用户问题 / Problem

- **PB-1 缓存收益没有数据基线**：之前只看到"同一批文档复跑明显快"的体感，但没有 p50/p95、cache_hit_ratio、speedup 等定量数据，调参 / 资源规划没法做。
- **PB-2 单次冷热对比不能下结论**：单次跑可能受 RAID0 cache 状态 / 其他 pane 抢占 / 系统抖动影响；需要小样本矩阵（3 档 × 3 冷 + 3 热 = 18 行）才能算 p50/p95。
- **PB-3 cache_hit_ratio 容易被误读**：前缀 KV block 命中率 ≠ 端到端成本节省率（cache hit 0.97 不等于 token 计费 -97%）；之前的对外结论可能高估了节省。
- **PB-4 乱码风险无监控**：cache 优化路径如果触发 partial block / full skip / approximate skip，可能产乱码（bad_chars=true）；基准必须把 `bad_chars=false` 作为门禁。
- **PB-5 backend / model 标识容易飘**：tmux 多 pane 跑时如果走 Claude/Gemini 而不是 ThunderOMLX，"基准"就成了别家的；profile 必须显式 pinned。
- **PB-6 PRD schema gate 阻塞**：sprint 已 finalized 2026-05-23T14:44:02Z（N1 verdict PASS，含 3 档真实数据），但 PRD 缺 7 schema 节，coordinator gate_prd_schema 把状态拉回 `drafting/prd_ready`；本切片即修复入口。

## 用户故事 / User Stories

- **US-01 (性能工程师)**：作为性能工程师，我希望看到 3 档文档长度 × 冷/热 各 3 次的 p50/p95 wall latency + cache_hit_ratio + speedup_p50，能直接给资源规划和调参做决策。
  - 验收：N1-handoff §关键结论 JSON 已含 short/medium/large 三档 cold_p50/p95 + hot_p50/p95 + hot_cache_hit_avg + speedup_p50（实测 1.32×/2.01×/3.00×）+ bad_chars=false ✅。
- **US-02 (调参 / Cache Tuning)**：作为调参人，我希望看到 cache_read_input_tokens 与 cache_creation_input_tokens 的分布，区分"前缀命中 vs 重新创建"。
  - 验收：PRD §验收第 6 条 + N1 每行结果含两字段 ✅。
- **US-03 (安全 / Eval)**：作为 evaluator，我希望 18 行结果**全部** bad_chars=false；任一为 true 视为基准失败。
  - 验收：PRD §验收第 5 条 + N1 三档 bad_chars=false ✅。
- **US-04 (对外结论审计)**：作为对外写报告的人，我希望 cache_hit_ratio 必须被显式标注为"前缀 KV block 命中率，不等同于端到端成本节省率"，避免误导。
  - 验收：PRD §验收末条 + N1 报告含该免责声明 ✅。
- **US-05 (Backend pinning)**：作为运维，我希望基准 profile 显式 pin `backend=command, model=thunderomlx`（不是 Claude proxy / Gemini）。
  - 验收：PRD §验收第 1 条 + N1 已验证 `backend=ThunderOMLX` / `base_url=http://127.0.0.1:8002` / `local_model=Qwen3.6-35b-a3b` ✅。
- **US-06 (PM / Coordinator)**：作为 coordinator，本 PRD 通过 gate_prd_schema 不再循环。
  - 验收：本切片即修复，`validate.sh prd` → PASS。

## 功能需求 / Requirements

- **FR-1 基准矩阵 3 × 6**：3 档文档长度（short / medium / large）× 6 次（3 冷 + 3 热）= 18 行结果。冷跑前必须清 hot cache 或确保进程 fresh；热跑紧接冷跑，复用同一批 prompt。
- **FR-2 字段必含**：每行结果记 `wall_latency_s` / `input_tokens` / `output_tokens` / `cache_read_input_tokens` / `cache_creation_input_tokens` / `cache_hit_ratio` / `bad_chars` / `pane` / `prompt_hash` / `model` / `backend`。
- **FR-3 聚合指标**：每档输出 `cold_p50` / `cold_p95` / `hot_p50` / `hot_p95` / `hot_cache_hit_avg` / `speedup_p50` (= cold_p50 / hot_p50)。
- **FR-4 全局 bad_chars 门禁**：18 行任一 `bad_chars=true` 视为基准失败，evaluator 必须 alert。
- **FR-5 Profile 锁定**：基准必须 `backend=command, model=thunderomlx`（不是 Claude/Gemini proxy）；如果检测到 proxy_model 是 `claude-3-5-sonnet-latest` 等代理名，必须额外记录 `local_model=Qwen3.6-35b-a3b` 证明实际跑在 ThunderOMLX 上。
- **FR-6 cache_hit_ratio 免责声明**：报告必须含明文"`cache_hit_ratio` 是前缀 KV block 命中率，不等同于端到端成本节省率"。
- **FR-7 不启用 unsafe**：partial block cache / full skip / approximate skip 必须保持 disabled；evaluator 检 audit log。
- **FR-8 持久化产物**：
  - 报告 `~/.solar/harness/monitor-reports/thunderomlx-knowledge-cache-benchmark.md`
  - JSON 结果 `~/.solar/harness/run/thunderomlx-knowledge-cache-benchmark/results.json`
- **FR-9 PRD schema 合规**：通过 `validate.sh prd`（本切片即修复 gate_prd_schema）。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / ThunderOMLX 8002 / Qwen3.6-35b-a3b 模型 `/Volumes/toshiba/models/Qwen3.6-35b-a3b` / RAID0 SSD cache `/Volumes/RAID0-Main/omlx-cache/` / hot RAM 8 GB / 4-pane Solar Harness。
- **路径白名单**：报告 `~/.solar/harness/monitor-reports/`；JSON `~/.solar/harness/run/thunderomlx-knowledge-cache-benchmark/`；handoff `~/.solar/harness/sprints/<sid>.N*-handoff.md`；禁 `/tmp`、禁用户 home 根、禁 Solar 仓库 git 提交。
- **不重启 ThunderOMLX**：除非用户明确授权；基准跑期间假设服务持续在线。
- **不删 cache**：`/Volumes/RAID0-Main/omlx-cache/` 不允许 rm；冷跑通过 prompt 唯一性或 pane reset 实现，不靠删盘。
- **不启用 unsafe 路径**：partial block cache / full skip / approximate skip 禁用；明示非目标。
- **不用 Claude/Gemini 跑粗活**：基准必须实际跑 ThunderOMLX Qwen3.6，不允许偷渡到 Claude/Gemini proxy。
- **不打印 secrets**：API token / OAuth 不打印 / 不持久化；报告中所有 token 引用必须 redact。
- **API 兼容**：ThunderOMLX 8002 对外 API 不变；基准只读消费 `/v1/chat/completions`。
- **PM 角色边界**：不写代码、不动 `.finalized` / status.json / N1-handoff / monitor-report / results.json；本 PRD 修复后保持 `status=drafting`。

## 风险 / Risks

| 风险 | 影响 | 缓解 / 状态 |
|------|------|--------------|
| 单次跑受系统抖动影响 | p50/p95 不稳 | FR-1 强制 3 × 6 = 18 行矩阵 + N1 实测 large hot_p95 高达 10.48s 暴露抖动但 p50 仍稳 ✅ |
| cache_hit_ratio 被外推为"成本节省" | 误导决策 | FR-6 报告必须含免责声明 + N1 已含该声明 ✅ |
| 跑期间走 Claude proxy 而不是 ThunderOMLX | 假基准 | FR-5 profile pinning + 记录 `local_model=Qwen3.6-35b-a3b` + N1 已验证 ✅ |
| Unsafe 路径偷启 | 乱码 | FR-7 + bad_chars 门禁；N1 18 行 bad_chars=false ✅ |
| RAID0 cache 状态污染冷跑 | 假"冷"跑 | FR-1 强制 prompt 唯一或 pane fresh；N1 通过 prompt 选型避免重复 |
| `cache_creation_input_tokens` 与 `cache_read_input_tokens` 解读颠倒 | 调参错向 | FR-2 两字段分别记录 + 报告说明各自语义 ✅ |
| 18 行任一 bad_chars=true 但被聚合掩盖 | 漏检 | FR-4 全局门禁 + N1 evaluator 逐行校验 ✅ |
| 测试样本太小 → p50/p95 置信度低 | 结论不稳 | N1 large hot_p95 与 p50 差异大（10.48 vs 5.41）已暴露这一点；OQ-01 留增大样本 |
| 报告里贴 API token | 安全事故 | secrets redact + N1 已抽查 ✅ |
| 报告中模型名拼错 → 历史对比失效 | 长期追溯丢 | FR-2 model + backend 字段强制；N1 标准化 |
| Sprint 已 finalized 但 PRD schema fail → coordinator 拉回 drafting | 链路循环 | 本切片即修复 ✅ |
| Mac mini 休眠中断基准 | 18 行跑一半丢 | basemark 期间用 caffeinate（OQ-04） |

## 开放问题 / Open Questions

- **OQ-01** 样本规模是否需要从 3 × 6 = 18 扩到 3 × 10 = 30？large hot_p95 (10.48s) 与 hot_p50 (5.41s) 差异大暗示样本不够。**Owner**：calibration sprint。
- **OQ-02** "short / medium / large" 文档长度的具体 token 数没定义；N1 报告应当回写，便于未来对比。**Owner**：报告改进 sprint。
- **OQ-03** 基准是否需要加 "超大文档" (≥ 16K token) 档？当前 large 只到中等量。**Owner**：matrix expansion sprint。
- **OQ-04** 基准期间是否需要 `caffeinate` 防 Mac mini 休眠？短跑 (<10 min) 可能不需要，长矩阵需要。**Owner**：launcher 设计。
- **OQ-05** 是否需要把 cache_hit_ratio 拆成更细：prefix_block_hit / mid_block_hit / suffix_block_hit？当前是聚合一个数。**Owner**：advisor evolution sprint。
- **OQ-06** results.json schema 是否要 versioned (`schema_version: v1`) 便于未来对比？**Owner**：schema 设计。
- **OQ-07** 是否需要把基准接入 dashboard，自动 7 天 trend 图？当前是一次性跑。**Owner**：dashboard sprint。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（含 4 原始节 + 本次补的 7 schema 必需节）。
- `<sid>.contract.md` — Scope / Required Work / Constraints / Verification / Deliverables。
- 实际 sprint 产出（PM 不动）：
  - `<sid>.N1-handoff.md` — 含 §已完成 + §已验证 + §关键结论 (short/medium/large 三档 JSON)
  - `<sid>.task_graph.json` — 单节点 N1
  - `<sid>.finalized` — 标记 2026-05-23T14:44:02Z passed
  - `~/.solar/harness/monitor-reports/thunderomlx-knowledge-cache-benchmark.md` — 完整基准报告
  - `~/.solar/harness/run/thunderomlx-knowledge-cache-benchmark/results.json` — 18 行原始结果

### 当前实施状态（已交付，回溯不重做）

| 功能 | 状态 | 证据 |
|------|------|------|
| FR-1 3 × 6 = 18 行矩阵 | ✅ | N1 三档冷热齐全 |
| FR-2 12 个必填字段 | ✅ | N1 已验证 backend / model / proxy_model / local_model 等 |
| FR-3 聚合指标 | ✅ | N1 §关键结论 含 cold_p50/p95 + hot_p50/p95 + hot_cache_hit_avg + speedup_p50 |
| FR-4 bad_chars 门禁 | ✅ | N1 三档 bad_chars=false |
| FR-5 Profile pinning | ✅ | N1 backend=ThunderOMLX / base_url=8002 / local_model=Qwen3.6 |
| FR-6 cache_hit_ratio 免责声明 | ✅ | N1 报告已含 |
| FR-7 unsafe disabled | ✅ | N1 audit |
| FR-8 报告 + JSON 持久化 | ✅ | 两路径全部存在 |
| FR-9 PRD schema 合规 | 本切片即满足 | validate.sh prd → PASS |

### 关键定量结论（N1 已交付）

| 档位 | cold_p50 (s) | cold_p95 (s) | hot_p50 (s) | hot_p95 (s) | hot_cache_hit | speedup_p50 |
|------|------|------|------|------|------|------|
| short | 6.25 | 6.52 | 4.73 | 4.75 | 0.9054 | **1.32×** |
| medium | 10.02 | 10.40 | 4.98 | 5.17 | 0.9638 | **2.01×** |
| large | 16.25 | 16.85 | 5.41 | 10.48 | 0.9753 | **3.00×** |

**Speedup 随文档长度增长**（1.3 → 2.0 → 3.0×），cache hit 也升（0.91 → 0.96 → 0.98）；但 large hot_p95=10.48s 与 p50=5.41s 差异提示样本量不够（OQ-01）。

### 给 Coordinator 的明确指令

- **不要重做 sprint**：sprint 已 `.finalized` 2026-05-23T14:44:02Z（N1 verdict PASS，18 行真实数据）。Coordinator 当前拉回 `drafting/prd_ready` 仅为 gate_prd_schema 回溯副作用。
- **触发机制**：PRD mtime 已刷新；coordinator 下一 tick 重跑 `validate.sh prd` → PASS → 关闭 gate；识别 `.finalized` 后让 sprint 回到 passed，不要 advance 到 planner。
- **不动 N1 handoff / monitor-report / results.json**。

### 未尽事项（留给后续 sprint）

- **OQ-01..OQ-07** 全部留后续 sprint。
- **样本扩到 3 × 10 = 30**（OQ-01）+ **超大文档档**（OQ-03）需要 matrix expansion sprint。
- **dashboard trend 图**（OQ-07）需要 observability sprint。
- **results.json schema 版本化**（OQ-06）+ **cache_hit_ratio 细分**（OQ-05）需要 schema/advisor evolution sprint。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context block)。
