# Handoff — S02 Architecture: TUI Pane Recover 与 Clean Pane 生命周期治理

sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s02-architecture`
epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
node: `A5_traceability_handoff`
generated_at: `2026-05-27T21:00:00Z`

---

## A1-A4 各产出路径与摘要

### A1 — Architecture (passed)

**路径**: `sprints/...-s02-architecture.architecture.md`

**摘要**: 10 节系统架构: 6 组件全景图 (PaneHygieneRegistry/RecoverDetector/PaneClearManager/PersonaReinjector/LedgerWriter/DispatchScheduler); control plane vs data plane 分离; 6 状态 FSM (11 合法转移 + 4 禁止); 3 类 prompt 检测器 (tmux capture-pane + 正则); /clear 三件齐成功判定; clean→running 注入策略; spillover 轮询+去重; 5 错误码处理路径; 9 dashboard 观测指标; S03/S04 接力清单。

### A2 — Data Models (passed)

**路径**: `sprints/...-s02-architecture.data_models.md`

**摘要**: 5 节数据模型: pane-hygiene.json schema (19 字段 + atomic write + flock); ledger 双引擎 (dispatch-ledger.jsonl 11 字段 + model_call_ledger.sqlite DDL); spillover_config.yaml (5 pane pool + round_robin + reassign rules); 持久化策略 (内存缓存 + transition 即写盘 + POSIX atomic rename + flock); 数据生命周期 (30-90 天归档/TTL/每日备份/磁盘预算 ~234 MB/90d)。

### A3 — Interfaces (reviewing)

**路径**: `sprints/...-s02-architecture.interfaces.md`

**摘要**: 6 节 API 签名草案: PaneHygieneRegistry (get_pane_state/transition_state/query_clean_panes/register_pane/unregister_pane); RecoverDetector (detect_proceed/detect_queued/detect_permission/classify_prompt); PaneClearManager (clear_pane/verify_clear_success/clear_with_retry); PersonaReinjector (inject_persona/inject_runtime_policy/inject_solar_context/verify_injection); LedgerWriter (record_recover/record_clear/record_reassign/query_history + 双写一致性); DispatchScheduler (select_pane/spillover_select/mark_busy/mark_idle)。

### A4 — Open Questions Resolutions (passed)

**路径**: `sprints/...-s02-architecture.open_questions_resolutions.md`

**摘要**: 5 OQ 全部决议 (无"待定"): OQ-01 内存缓存+atomic write; OQ-02 3 retry+5s backoff+needs_respawn; OQ-03 clean→running 全量注入+session 内不重注; OQ-04 5 pane pool (1 主+4 lab); OQ-05 tmux kill-pane+split-window+等待 ready marker。每 OQ 含 6 字段 (decision/rationale≥3/alternatives≥2/risks/owner/fallback)。

---

## 7 决议摘要 (D1-D7)

| Dec | 主题 | 决议 | 文档 |
|-----|------|------|------|
| D1 | pane-hygiene.json schema | 19 字段 + 内存缓存 + atomic write + flock | data_models.md §1 |
| D2 | 6 状态 FSM | 11 合法转移 + 4 禁止 + retry 3次 5s backoff + cooldown 30s | architecture.md §4 |
| D3 | prompt 检测器 | tmux capture-pane + 正则 (DET-PROCEED/DET-QUEUED/DET-PERMISSION) + 2s 轮询 | architecture.md §5 |
| D4 | /clear 成功判定 | capture-pane 三件齐 (空 prompt + 无 queued + 无确认框) + 3 次 retry | architecture.md §6 |
| D5 | 重注入策略 | clean→running 全量注入 + session 内不重注 persona/policy | architecture.md §7 |
| D6 | Ledger schema | 双引擎: dispatch-ledger.jsonl (11 字段) + model_call_ledger.sqlite (WAL) + 同步双写 | data_models.md §2 |
| D7 | Spillover 调度 | 5 pane 轮询 + 去重 + round_robin + 结构化失败 | architecture.md §8 |

---

## 5 OQ 决议摘要 (OQ-01..OQ-05)

| OQ | 问题 | 决议 | Owner |
|----|------|------|-------|
| OQ-01 | 持久化频率 | 内存缓存 + 状态转移即 atomic write | S03 |
| OQ-02 | /clear retry 阈值 | 3 次 + 5s/10s/15s backoff + 第 4 次 needs_respawn | S03 |
| OQ-03 | 重注入频率 | clean→running 全量注入 + session 内不重注 (轻策略) | S03 |
| OQ-04 | spillover 池规模 | 5 pane = 1 主 + 4 lab (与现有配置对齐) | S03 |
| OQ-05 | respawn 命令 | tmux kill-pane + split-window + 等待 ready marker | S03 |

---

## S03+S04 启动 Checklist

### S03 Core-Runtime 启动

- [ ] 实施 PaneHygieneRegistry (`harness/lib/pane_hygiene_registry.py`): 接口见 interfaces.md §1; atomic write + flock 见 data_models.md §1.4-1.5
- [ ] 实施 RecoverDetector (`harness/lib/recover_detector.py`): 接口见 interfaces.md §2; 3 检测器正则见 architecture.md §5.1; 2s 轮询
- [ ] 实施 PaneClearManager (`harness/lib/pane_clear_manager.py`): 接口见 interfaces.md §3; 三件齐判定见 architecture.md §6.3; retry 逻辑见 OQ-02
- [ ] 实施 PersonaReinjector (`harness/lib/persona_reinjector.py`): 接口见 interfaces.md §4; 注入策略见 architecture.md §7; 模板路径见 D5
- [ ] 实施 LedgerWriter (`harness/lib/ledger_writer.py`): 接口见 interfaces.md §5; 双引擎 DDL 见 data_models.md §2.2-2.3; 双写策略见 §2.4
- [ ] 实施 DispatchScheduler (`harness/lib/dispatch_scheduler.py`): 接口见 interfaces.md §6; spillover 算法见 architecture.md §8; SafetyGuard 内嵌
- [ ] pane-hygiene.json 初始化脚本: tmux list-panes 发现 + 全 clean 初始化; 见 data_models.md §1.5
- [ ] 5 错误码常量表: PROCEED_PROMPT_STUCK / QUEUED_PROMPT_STUCK / PERMISSION_LOOP / CLEAR_FAILED_EXHAUSTED / RESPAWN_FAILED; 见 architecture.md §9.1
- [ ] spillover_config.yaml 初始配置: 见 data_models.md §3.1 (5 pane + round_robin)
- [ ] 数据生命周期定时任务: archive/TTL/backup; 见 data_models.md §5

### S04 Orchestration-UI 启动

- [ ] 9 项 dashboard 指标: 见 architecture.md §9.3
- [ ] `pane-status --json` 输出 schema: 见 architecture.md §10.6
- [ ] config UI 集成点: 轮询频率 + 检测间隔 + spillover 池配置可编辑; 见 architecture.md §10.6
- [ ] Spillover 池配置 UI: 见 data_models.md §3

---

## 剩余风险

1. **spillover pool 硬编码 5 pane**: data_models.md §3.2 列出具体 pane ID; S03 必须从 pane-hygiene.json 动态读取，不能硬编码
2. **Ledger 双写最终一致性**: 两个引擎可能一方写入失败; fallback file 作为缓冲但需 ATLAS repair 对账
3. **/clear retry 30s 窗口**: 3 次 retry 总等待 30s 期间该 pane 不可分配; 若所有 pane 都在 retry → 结构化失败
4. **flock advisory lock**: 仅在合作进程间有效; 外部工具绕过 flock 可能导致并发冲突
5. **tmux capture-pane 依赖**: RecoverDetector 和 PaneClearManager 强依赖 tmux; tmux 不可用 → 全 pane 标 needs_respawn
6. **A3 interfaces 状态**: A3 当前 reviewing，eval 尚未通过; 若 A3 最终 fail 需重新实施接口签名

---

## 禁止乐观词声明

本文档不含 已修复/稳定/完美/无需担忧/done/complete/implemented 等乐观词汇。S02 是 architecture 切片，只产出规约文档，不实施任何代码或运行时变更。

---

## 禁止把 cooldown 当作最终修复声明

cooldown 只是 /clear 或 recover 失败后的临时等待缓冲，不是最终修复手段。cooldown 结束后必须重新评估 pane 状态（per architecture.md §9.2 硬约束）:
- cooldown 结束 pane 仍被卡住 → transition(cooling → needs_recover) 继续恢复流程
- cooldown 结束 pane 未被卡住 → transition(cooling → dirty) 回到待清理
- 禁止 cooling 直接 transition → running

---

Knowledge Context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
Harness Modules Used: harness-knowledge (Read: A1 architecture.md + A2 data_models.md + A3 interfaces.md + A4 open_questions_resolutions.md + S01 traceability.json + S01 handoff.md)
