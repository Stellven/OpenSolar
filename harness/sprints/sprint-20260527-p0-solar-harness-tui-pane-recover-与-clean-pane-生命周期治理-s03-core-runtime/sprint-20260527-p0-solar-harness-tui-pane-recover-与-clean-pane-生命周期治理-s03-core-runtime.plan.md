# Plan — S03 Core-Runtime (TUI Pane Recover 6 模块实施切片)

gate: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s03-core-runtime:passed`
knowledge_context: solar-harness context inject used
upstream: S02 architecture passed (D1-D7, OQ-01..OQ-05 全决议; 6 模块 + 4 schema 字段全细节)
downstream: S04 orchestration-ui (parallel) → S05 verification-release

## 0. 切片定位（区别于 S01/S02/S04）

S03 是 **实施切片**, 必须真写 Python 代码 + 测试。`evidence_policy.no_code=false` (允许写代码), 但仍禁止真改生产 pane-hygiene.json / 真跑 tmux 命令在生产 pane / 真调 /clear 在生产 pane。

## 1. DAG (3 phase 串行 + 验收 + join)

```
B1_foundation_state_machine (PaneHygieneRegistry + atomic write + flock + 5 错误码 + 初始化脚本)
    └─→ B2_detection_and_clear (RecoverDetector 3 正则 + PaneClearManager 三件齐 + retry; mock tmux)
          └─→ B3_reinject_ledger_scheduler (PersonaReinjector + LedgerWriter 双引擎双写 + DispatchScheduler spillover + spillover_config.yaml + lifecycle jobs)
                └─→ B4_acceptance_gates (8 V 验收报告 + py_compile + 整合测试)
                      └─→ B5_traceability_handoff (join)
```

**Phase 内部聚合**: 每节点一次性实施多个相关模块, 减少 dispatch 开销。

## 2. 每节点验收

| 节点 | 关键验收 |
|------|----------|
| **B1** foundation + state machine | PaneHygieneRegistry 5 method + 6 状态 FSM 11 合法+4 禁止 + atomic write/flock + 5 错误码 + 初始化脚本; pytest ≥80% coverage + 并发原子性测试 |
| **B2** detection + clear | RecoverDetector 4 method + 3 类正则 + 2s 轮询; PaneClearManager 3 method + 三件齐 + 3 retry 5/10/15s backoff + 第 4 次 needs_respawn (per OQ-02); pytest ≥80% + mock tmux fixture (4 类 ≥3 sample) |
| **B3** reinject + ledger + scheduler | PersonaReinjector 4 method + clean→running 全量注 + session 内不重注 persona (per OQ-03); LedgerWriter 4 method + dispatch-ledger.jsonl 11 字段 + model_call_ledger.sqlite WAL 13 列 + 同步双写 + fallback (per D6); DispatchScheduler 4 method + round_robin + 去重 + --max-items 3 (per D7); spillover_config.yaml 5 pane (1 主 + 4 lab per OQ-04); lifecycle archive/TTL/backup; pytest ≥80% + ledger 双写一致性测试 + spillover 不撞同测试 |
| **B4** acceptance gates | 8 V 验收报告 (V1+V2→O2 / V3+V4→O3 / V5→O4 / V6→O5 / V7→O6 / V8→O7) 全 PASS; py_compile 通过所有 lib/*.py + scripts/*.py; 整合 test_tui_pane_e2e.py 端到端 (proceed/queued/permission → recover → clear → reassign + spillover 3 并发到 3 pane) |
| **B5** join | traceability.json 12 字段 (含 modules_implemented[6] / schemas_initialized[4] / acceptance_reports[8] / s04+s05 dependencies); handoff 含 B1-B4 摘要 + 8 报告路径 + S04/S05 启动 checklist + 剩余风险 |

## 3. Stop Rules

- 缺 task_graph.json 不得派 builder (已满足)
- 任一 phase 验收不通过不进下一 phase
- 不真改 `~/.solar/harness/run/pane-hygiene.json` (S04 实施才初始化)
- 不真跑 tmux kill-pane / split-window / send-keys 在生产 pane (mock + fixture pane only)
- 不真调 `/clear` 在生产 pane (mock capture-pane)
- 不动 S02 artifacts (有问题 → B5 OQ-new)
- 不主动 close 父 epic
- 不杀主 pane 即使 needs_respawn 触发 (S03 仅触发状态, 真 respawn 留 S04 autopilot)
- 不删用户数据 / 不重启 ThunderOMLX
- 不把 cooldown 当作最终修复 (S02 D2: cooling → needs_recover 或 dirty, 禁止 cooling → running)
- 不切换到 API 默认路径 (PRD G1)
- 不用乐观词

## 4. SLO

| 指标 | hard | soft |
|------|------|------|
| 6 模块实施 | < 6 → FAIL | n/a |
| 4 schema 初始化 | < 4 → FAIL | n/a |
| 5 错误码常量 | < 5 → FAIL | n/a |
| pytest line coverage | < 70% → FAIL | < 80% → WARN |
| 状态机非法转移测试 | 任一非法转移未抛 IllegalTransitionError → FAIL | n/a |
| atomic write 并发测试 | partial write > 0 → 立即 FAIL | n/a |
| ledger 双写一致性 | mock 一方失败后另一方未 fallback → FAIL | n/a |
| spillover 不撞同 pane | 3 并发任务派同一 pane → FAIL | n/a |
| 真跑 tmux / 真改生产 pane-hygiene / 真调 /clear 生产 pane | > 0 → 立即 FAIL | n/a |
| "cooldown 当最终修复" 在代码出现 | > 0 → 立即 FAIL | n/a |
| 8 V 验收报告全 PASS | < 8 → FAIL | n/a |

## 5. 失败恢复

- B1 失败: B2/B3/B4 阻塞; 单 B1 重派
- B2/B3 失败: 单节点重派; 反复失败 → ATLAS structured repair
- B4 失败: 回到对应 B1-B3 修复; 不放过任何 V 验收
- B5 失败: 诊断 phase 偏离 S02 决议, 不擅自修 S02
- **Dogfood 风险**: builder pane 撞 proceed/queued → 现有 5 panes 天然 spillover (S04 实施前唯一保护)

## 6. 给下游接力

B5 traceability `downstream_sprint_kickoff_package`:
- **S04 (并行) inputs**: 6 模块 Python API + 4 schema 初始化协议 + 5 错误码; S04 实施 dashboard / config UI / autopilot respawn / pane-status --json
- **S05 verification-release inputs**: 8 V 验收报告 + 真生产 pane 端到端验证

S03 + S04 都 passed 后 coordinator 激活 S05。

## 7. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; ATLAS / Solar-Harness Runtime / Superpowers / solar-graph-scheduler capabilities injected。S02 5 份 artifacts (25K+17K+33K+19K+7K) 是 self-contained 输入。
