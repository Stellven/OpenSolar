# Design — S03 Core-Runtime 切片：TUI Pane Recover 6 模块 + 4 schema 实施

epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s03-core-runtime`
slice: `core-runtime`
role: planner
status: planning_complete
generated_at: 2026-05-27T19:05:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
upstream: S02 architecture passed (D1-D7 + OQ-01..OQ-05 全决议 + 6 模块/4 schema/19+11+13 字段 全细节)
downstream: S04 orchestration-ui (parallel) → S05 verification-release

## 0. 切片边界（区别于 S01/S02/S04）

- **S03 是实施切片**: 与 S01/S02/S04 不同, **本 sprint 必须真写代码** (6 个 Python 模块 + 4 个 schema + 初始化 + 测试)
- **本 sprint 允许的写范围**:
  - `~/.solar/harness/lib/pane_hygiene_registry.py` (B1)
  - `~/.solar/harness/lib/recover_detector.py` (B2)
  - `~/.solar/harness/lib/pane_clear_manager.py` (B2)
  - `~/.solar/harness/lib/persona_reinjector.py` (B3)
  - `~/.solar/harness/lib/ledger_writer.py` (B3)
  - `~/.solar/harness/lib/dispatch_scheduler.py` (B3)
  - `~/.solar/harness/lib/pane_constants.py` (B1, 5 错误码常量表)
  - `~/.solar/harness/lib/pane_lifecycle_jobs.py` (B3, archive/TTL/backup 任务)
  - `~/.solar/harness/scripts/init_pane_hygiene.py` (B1, 初始化脚本)
  - `~/.solar/harness/run/spillover_config.yaml` (B3, 初始配置 5 pane)
  - `~/.solar/harness/tests/test_pane_*.py` (各模块 pytest)
  - `~/.solar/harness/tests/test_recover_*.py`
  - `~/.solar/harness/tests/test_dispatch_scheduler.py`
  - `~/.solar/harness/tests/test_ledger_writer.py`
  - `~/.solar/harness/tests/integration/test_tui_pane_e2e.py`
  - `~/.solar/harness/reports/tui-pane/s03-acceptance/*.json` (B4 验收报告)
  - Sprint artifacts: `<s03-sid>.design.md` / `.plan.md` / `.task_graph.json` / `.planning.html` / `.handoff.md` / `.traceability.json` + 每 phase handoff
- **严格禁止**:
  - 真改 `~/.solar/harness/run/pane-hygiene.json` (S03 只写代码 + scripts, 真初始化留 S04 启动时)
  - 真跑 `tmux kill-pane` / `tmux split-window` 在生产 pane 上 (mock 测试 + 隔离测试 pane)
  - 真调 `/clear` 命令在生产 pane 上 (mock tmux capture-pane)
  - 改 S02 任何 artifact (有问题 → B5 OQ-new)
  - 修改父 epic 任何 artifact
  - **不杀主 pane 即使 needs_respawn 触发** (S03 实施只在 fixture pane 验证)
  - 删用户数据
  - 不重启 ThunderOMLX / ASR
  - 把 cooldown 当作最终修复 (S02 D2 已硬约束: cooling → needs_recover 或 dirty, 禁止 cooling → running)

## 1. 上游消费（从 S02 完整复用）

| S02 决议 | S03 实施 |
|----------|----------|
| D1 (pane-hygiene.json 19 字段 + 内存缓存 + atomic write + flock) | B1 实施 PaneHygieneRegistry + atomic write 协议 |
| D2 (6 状态 FSM 11 合法转移 + 4 禁止 + retry 3次 5s backoff + cooldown 30s) | B1 实施 transition_state() 含合法性校验 |
| D3 (tmux capture-pane + 3 正则 DET-PROCEED/DET-QUEUED/DET-PERMISSION + 2s 轮询 + 50 行) | B2 实施 RecoverDetector |
| D4 (capture-pane 三件齐 + 2 步验证 + 3 retry) | B2 实施 PaneClearManager |
| D5 (clean→running 全量注入 + session 内不重注 persona) | B3 实施 PersonaReinjector |
| D6 (dispatch-ledger.jsonl 11 字段 append + model_call_ledger.sqlite WAL 13 列 + 同步双写) | B3 实施 LedgerWriter 双引擎双写 |
| D7 (5 pane 轮询 + 去重 + round_robin + 结构化失败) | B3 实施 DispatchScheduler.spillover_select() |
| OQ-01 (内存缓存 + atomic write + flock + crash recovery) | B1 PaneHygieneRegistry persist 实施 |
| OQ-02 (3 retry + 5s/10s/15s backoff + 第 4 次 needs_respawn + cooldown 30s) | B2 PaneClearManager retry 逻辑 |
| OQ-03 (clean→running 全量注 + session 内不重注 + 跨 session 重注) | B3 PersonaReinjector 注入决策 |
| OQ-04 (5 pane = 1 主 solar-harness:0.3 + 4 lab solar-harness-lab:0.0..0.3) | B3 spillover_config.yaml 初始配置 |
| OQ-05 (tmux kill-pane + split-window + 等待 claude-code session ready marker) | B3 DispatchScheduler 不直接实施 respawn (仅触发 needs_respawn 状态, 真 respawn 留 S04 autopilot) |

## 2. S03 内部 DAG（3 phase 串行 + 验收 + join）

```
B1_foundation_state_machine (PaneHygieneRegistry + pane-hygiene.json schema + atomic write + flock + 5 错误码常量 + 初始化脚本)
    └─→ B2_detection_and_clear (RecoverDetector 3 正则 + PaneClearManager 三件齐 + retry; 都依赖 B1 state machine)
          └─→ B3_reinject_ledger_scheduler (PersonaReinjector + LedgerWriter 双引擎双写 + DispatchScheduler spillover + lifecycle jobs + spillover_config.yaml; 依赖 B1+B2)
                └─→ B4_acceptance_gates (8 V 验收 + py_compile + pytest 状态机/clear/spillover/ledger 4 类测试报告)
                      └─→ B5_traceability_handoff (join)
```

**为何串行**: B1 state machine 是所有其他模块的基础; B2 detection/clear 操作产生事件给 B3 ledger 记录; B3 scheduler 调用 B2 clear; B4 测试覆盖前 3 phase。

**Phase 内部聚合**: 每个 Bx 节点一次性实施多个相关模块，减少 dispatch 开销 (per Solar 4-pane 经验)。

## 3. 节点写范围（互斥）

| 节点 | write_scope (互斥) |
|------|---------------------|
| B1 | `lib/pane_hygiene_registry.py` + `lib/pane_constants.py` + `scripts/init_pane_hygiene.py` + `tests/test_pane_hygiene_registry.py` + `tests/test_pane_constants.py` + `tests/test_init_pane_hygiene.py` + `tests/fixtures/pane_hygiene_seed.json` |
| B2 | `lib/recover_detector.py` + `lib/pane_clear_manager.py` + `tests/test_recover_detector.py` + `tests/test_pane_clear_manager.py` + `tests/fixtures/tmux_capture_samples/{proceed,queued,permission,clean}.txt` |
| B3 | `lib/persona_reinjector.py` + `lib/ledger_writer.py` + `lib/dispatch_scheduler.py` + `lib/pane_lifecycle_jobs.py` + `run/spillover_config.yaml` + `tests/test_persona_reinjector.py` + `tests/test_ledger_writer.py` + `tests/test_dispatch_scheduler.py` + `tests/test_pane_lifecycle_jobs.py` |
| B4 | `tests/integration/test_tui_pane_e2e.py` + `tests/conftest.py` (TUI suite-level fixtures) + `reports/tui-pane/s03-acceptance/{V1-proceed,V2-queued,V3-builder_clear,V4-evaluator_clear,V5-reinject,V6-spillover,V7-pane_quarantine,V8-py_compile}.json` |
| B5 | `<s03-sid>.traceability.json` + `<s03-sid>.handoff.md` + `<s03-sid>.B5-handoff.md` |

## 4. 每节点验收

### B1 (foundation + state machine)
- PaneHygieneRegistry 实施 (per interfaces.md §1, 5 method): `get_pane_state` / `transition_state` / `query_clean_panes` / `register_pane` / `unregister_pane`
- 6 状态 FSM 11 合法转移 + 4 禁止转移硬性校验 (`cooling → running` 等禁止抛 IllegalTransitionError)
- atomic write 协议 (write-to-temp + os.rename) + flock (fcntl.LOCK_EX)
- 5 错误码常量 (`PROCEED_PROMPT_STUCK / QUEUED_PROMPT_STUCK / PERMISSION_LOOP / CLEAR_FAILED_EXHAUSTED / RESPAWN_FAILED`) 入 pane_constants.py
- pane-hygiene.json 初始化脚本: tmux list-panes (mock 测试) 发现 + 全 clean 初始化
- pytest B1 ≥80% coverage; atomic write 并发测试 (≥3 thread 同时 transition_state, 无 partial write)

### B2 (detection + clear)
- RecoverDetector 实施 (per interfaces.md §2, 4 method): 3 检测器 (proceed/queued/permission) 正则 + classify_prompt
- 正则 fixture (tmux_capture_samples) 4 类 (proceed / queued / permission / clean) 各 ≥3 sample
- 2s 轮询间隔 (config-driven)
- PaneClearManager 实施 (per interfaces.md §3, 3 method): clear_pane / verify_clear_success / clear_with_retry
- /clear 成功判定三件 (capture-pane 验空 prompt + 无 queued + 无确认框) 全实施
- retry 逻辑: 3 次 + 5s/10s/15s backoff (per OQ-02), 第 4 次 transition → needs_respawn
- pytest B2 ≥80% coverage; mock tmux capture-pane (绝不真跑生产 pane)

### B3 (reinject + ledger + scheduler)
- PersonaReinjector 实施 (per interfaces.md §4, 4 method): inject_persona / inject_runtime_policy / inject_solar_context / verify_injection
- 决策 (per OQ-03): clean→running 全量注 (persona + policy + context); session 内同 sprint 派发不重注 persona/policy, 仅 update solar context
- LedgerWriter 实施 (per interfaces.md §5, 4 method): record_recover / record_clear / record_reassign / query_history
- 双引擎: dispatch-ledger.jsonl (append-only 11 字段) + model_call_ledger.sqlite (WAL, 13 columns) + 同步双写
- DispatchScheduler 实施 (per interfaces.md §6, 4 method): select_pane / spillover_select / mark_busy / mark_idle
- spillover 算法: round_robin + 去重 + --max-items 3 (per D7)
- spillover_config.yaml 初始 = 5 pane (1 主 + 4 lab per OQ-04)
- pane_lifecycle_jobs 实施: archive (30 天) + TTL (90 天) + backup (每日)
- pytest B3 ≥80% coverage; ledger 双写一致性测试 (mock 一方失败, fallback 写入)

### B4 (acceptance gates)
- 8 V 验收映射到 outcome (V1+V2→O2 / V3+V4→O3 / V5→O4 / V6→O5 / V7→O6 / V8→O7)
- 报告: `V1-proceed.json` / `V2-queued.json` / `V3-builder_clear.json` / `V4-evaluator_clear.json` / `V5-reinject.json` / `V6-spillover.json` / `V7-pane_quarantine.json` / `V8-py_compile.json`
- py_compile 通过所有 lib/*.py + scripts/*.py
- 整合测试 test_tui_pane_e2e.py: 模拟 proceed/queued/permission prompt → recover → clear → reassign 端到端;
  - spillover 3 个并发任务分到 3 个不同 pane (per V6)
  - 坏 pane 不拖队列 (per V7)
- 8 报告全 PASS 才 acceptance 通过

### B5 (join handoff/traceability)
- traceability.json 12 字段 (含 modules_implemented[6] / schemas_initialized[4] / acceptance_reports[8] / s04_dependencies / s05_dependencies)
- handoff.md 含 B1-B4 摘要 + 8 acceptance 报告路径 + 剩余风险 + S04/S05 启动 checklist

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| B1-B4 | glm-5.1 | 实施代码 + 测试模板化 (per 4-pane 经验) |
| B5 | sonnet | 跨 phase 聚合 + S04/S05 接力 reasoning |

## 6. Stop Rules

- 缺 task_graph.json 不得派 builder (已满足)
- 任一 phase 验收不通过, 不得进下一 phase
- 不真改 `~/.solar/harness/run/pane-hygiene.json` (S03 写代码 + scripts, 不真初始化)
- 不真跑 `tmux kill-pane` / `tmux split-window` 在生产 pane (mock + fixture pane only)
- 不真调 `/clear` 在生产 pane (mock capture-pane)
- 不动 S02 artifacts (有问题 → B5 OQ-new)
- 不主动 close 父 epic
- 不杀主 pane 即使 needs_respawn (S03 仅触发状态, 真 respawn 留 S04)
- 不删用户数据 / 不重启 ThunderOMLX
- 不把 cooldown 当作最终修复 (S02 D2 已硬约束)
- 不切换到 API 默认路径 (PRD G1)
- 不用乐观词

## 7. SLO

| 指标 | hard | soft |
|------|------|------|
| 6 模块实施 | < 6 → FAIL | n/a |
| 4 schema 初始化 (pane-hygiene/dispatch-ledger/model_call_ledger/spillover_config) | < 4 → FAIL | n/a |
| 5 错误码常量 | < 5 → FAIL | n/a |
| pytest line coverage | < 70% → FAIL | < 80% → WARN |
| 状态机非法转移测试 | 任一非法转移未抛 IllegalTransitionError → FAIL | n/a |
| atomic write 并发测试 | partial write > 0 → 立即 FAIL | n/a |
| ledger 双写一致性 | mock 一方失败后另一方未 fallback → FAIL | n/a |
| spillover 不撞同 pane | 3 并发任务派同一 pane → FAIL | n/a |
| 真跑 tmux kill-pane / 真改 pane-hygiene.json / 真调 /clear 在生产 pane | > 0 → 立即 FAIL | n/a |
| "cooldown 当最终修复" 在代码或测试出现 | > 0 → 立即 FAIL | n/a |
| 8 V 验收报告全 PASS | < 8 PASS → FAIL | n/a |

## 8. 失败恢复

- B1 失败: B2/B3/B4 阻塞; 单 B1 重派
- B2 失败: B3 阻塞 (PersonaReinjector 不依赖 B2 但 ledger 记录 recover 事件依赖 B2 detection); 单 B2 重派
- B3 失败: B4 阻塞; 单 B3 重派
- B4 失败: 回到对应 B1-B3 修复; 不放过任何 V 验收
- B5 失败: 诊断 phase 偏离 S02 决议, 不擅自修 S02
- ATLAS structured repair: 任一 phase 反复失败时触发
- **Dogfood 风险**: B1-B5 builder pane 撞 proceed/queued → 现有 5 panes 天然 spillover; 卡死则 ATLAS

## 9. 非目标

- 不实施 S04 范围 (dashboard / config UI / 真初始化 / 实际 spillover 调度上线 / autopilot respawn 触发)
- 不真改生产 pane-hygiene.json (S04 实施时才初始化)
- 不真跑 tmux 命令在生产 pane
- 不实施 ATLAS structured repair 本身 (只触发, 不实施)
- 不实施 dashboard 9 指标 UI (留 S04)
- 不实施 status server (留 S04)
- 不主动 respawn worker pane (S03 只触发 needs_respawn 状态, 真 respawn 由 S04 autopilot)
- 不擅自修 S02 artifacts
- 不主动 close 父 epic

## 10. 给下游接力

- B5 traceability `downstream_sprint_kickoff_package`:
  - **S04 (并行) inputs**: 6 模块 Python API 实施 + 4 schema 初始化协议 + 5 错误码常量; S04 实施 dashboard / config UI / autopilot respawn / pane-status --json
  - **S05 verification-release inputs**: 8 V 验收报告 (本 sprint 已跑) + 端到端测试 + 真生产 pane 验证 (S03 仅 mock + fixture)

S03 + S04 都 passed 后 coordinator 激活 S05。

## 11. Dogfood 闭环

S03 实施完成后, S04 把这些模块接入实际 dispatch 链路。S05 验证后, **本 epic 治理能力将服务于后续 sprint 的派发**——届时 pane 卡死、queued prompt、proceed prompt 等问题自动 recover, 整个 multi-pane 派发链路更稳定。这是 dogfood 闭环关键节点。
