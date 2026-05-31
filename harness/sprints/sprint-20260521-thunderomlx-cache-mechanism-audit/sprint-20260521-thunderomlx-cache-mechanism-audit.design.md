# Design — ThunderOMLX Cache Mechanism Audit (sprint-level)

sprint_id: `sprint-20260521-thunderomlx-cache-mechanism-audit`
epic_id: null (standalone analysis sprint)
role: planner
status: planning_complete
generated_at: 2026-05-28T13:17:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
detail_reference: `<sid>.prd.md` (11K, 7 FRs + 5 user stories + Stop Rules + 9-section report template)
historical_status: **PASSED + .finalized 2026-05-23T10:42** (gates 3/3 passed: cache inventory / runtime evidence / final report)
graph_doctor_drift: 2026-05-26T17:56:55Z — N1/N2/N3 reset to `reviewing`; PM 5/27 backfill PRD; Planner 5/28 backfill artifacts

## 0. Sprint 性质

**Standalone analysis sprint** — 全量盘点 ThunderOMLX 缓存机制 (≥30 mechanisms / 7 layers), 输出可执行的中文 audit + P0/P1/P2 实验菜单。3-node DAG (N1 static inventory → N2 runtime audit → N3 final synthesis) **已 builder 完成 + 3 gates PASS + .finalized 5/23**. 本 Planner 切片 backfill sprint-level artifacts, 不重做 N1-N3。

## 1. 现状快照

| 维度 | 事实 |
|------|------|
| Sprint finalized | 2026-05-23T10:42 ✅ |
| 3 Gates | 全 passed (cache inventory complete @ 5/21 12:21:47 / runtime cache evidence complete @ 5/21 12:21:34 / final report written @ 5/21 12:31:16) |
| N1 static inventory | builder PASS @ 5/21 08:21, handoff 4912 bytes |
| N2 runtime audit | builder PASS @ 5/21 08:21, handoff 4857 bytes |
| N3 final report | builder PASS @ 5/21 08:30, handoff 4059 bytes |
| 实际产出 | `~/.solar/harness/monitor-reports/thunderomlx-cache-mechanism-audit.md` (21K, 31 机制, 7 层, 完整证据链) |
| Drift trigger | 2026-05-26T17:56:55Z graph_doctor reset N1-N3 (与 MTSPR / smoke 同源) |
| PM gate trigger | 2026-05-27 PRD backfill (11K, schema PASS) |

## 2. 实施成果 (per N1-N3 handoffs + monitor report)

### N1 静态盘点 (FR-1)
≥30 mechanisms 扫描完成, 每条含文件路径 + 配置 key + 默认值 + 单元测试位置。覆盖: ContextPilot / Prompt Cache / Paged KV / SSD / RAM hot cache / Shared KV / Two-tier cache / KVTC / workflow + cache warmer / predictive prefetch / tool-call pinning / cache VM / semantic + memcollab + cache advisor。

### N2 运行态审计 (FR-2)
8002 服务日志窗口 (2026-05-20 21:14 → 2026-05-21 08:12) 实测: 哪些机制触发 / 命中率 / 冷恢复 / 被 unsafe-skip 关掉的项。Mac mini 配置: Qwen3.6 MLX-4bit / RAID0 27 GB / 8 GB hot RAM cache / unsafe-skip features 状态。

### N3 最终综合 (FR-3, 9 sections in monitor report)
- §1 中文分类表 (机制 / 层级 / 存在 / 当前启用 / 收益路径 / 风险 / 优先级)
- §2 ASCII 交互图 (L1 → L2 → 冷恢复 / AnthropicProxy 绕过 / 预取并行)
- §3 P0/P1/P2 实验菜单 (指标 / 命令 / 回滚 / 禁止项)
- §4 已实测速度 (4.5× 热命中加速 + 日志行号锚定)
- §5 量化数据 vs 估算 vs 待 A/B 显式区分
- §6 "明确不建议立即开启"表 (KVTC / FlashMLX / CacheVM / MemCollab / block_size_enlargement)
- §7 未验证声明专章

### FR-4..FR-7 安全约束 (per PRD)
- ✅ 不重启 8002 (N1-N3 全只读)
- ✅ 不打印 secrets (redact)
- ✅ 不改 ThunderOMLX 源码
- ✅ 不删缓存目录
- ✅ PRD 11 节 schema PASS

## 3. 3-Node DAG

```
N1 static inventory (sonnet, PASS, depends_on=[])
N2 runtime audit (sonnet, PASS, depends_on=[])  -- 与 N1 并行 (read-only, write_scope 互斥)
N3 final synthesis (sonnet, PASS, depends_on=[N1, N2])
```

**N1 N2 并行** (per task_graph: 两者 depends_on=[]); **N3 join** 等 N1+N2 完成。

## 4. 写范围

| 节点 | write_scope |
|------|-------------|
| N1 | `<sid>.N1-handoff.md` + monitor `thunderomlx-cache-mechanism-audit-N1-inventory.md` |
| N2 | `<sid>.N2-handoff.md` + monitor `thunderomlx-cache-mechanism-audit-N2-runtime.md` |
| N3 | `<sid>.N3-handoff.md` + monitor `thunderomlx-cache-mechanism-audit.md` (final report) |
| Planner (本切片) | `<sid>.{design,plan,planning.html}` + `<sid>.task_graph.json` patch + `<sid>.status.json` + ACK |
| **严格禁止** | 改 ThunderOMLX 源码 / 配置 / 缓存目录; 重启 8002; 打印 secrets; 重做 N1-N3 |

## 5. Stop Rules (per PRD §约束)

- 不动 ThunderOMLX 源码 (`/Users/lisihao/ThunderOMLX` read-only)
- 不重启 8002 (除非显式用户授权)
- 不删缓存目录
- 不启 partial block cache / full skip / approximate skip / unsafe-skip (只允许"分析"或"gated 实验菜单")
- 不打印 secrets (token / API key / OAuth)
- 报告必须有"未验证声明"专章
- 不写实施代码以外的乐观词

## 6. 失败恢复 / 同期 sprint 关系

- Drift recurrence: 复用本 backfill pattern (与 MTSPR / smoke / UAKG 同源 graph_doctor 问题)
- N1-N3 已 builder PASS, 不重做; 二次审查 FAIL → `graph-dispatch node-verdict` sanctioned CLI
- pane_not_idle (events seq=10): TUI epic S03 实施后稳定
- 同期 sprint: MTSPR / smoke / KVTC / FlashMLX 多个相关 ThunderOMLX sprint 共同推进

## 7. Knowledge Context

29K total sprint evidence (PRD 11K + N1 4.9K + N2 4.9K + N3 4.1K + monitor 21K + contract 1.2K) 已 self-contained。

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; 10 capability `injectable_only`, 不重新执行。
