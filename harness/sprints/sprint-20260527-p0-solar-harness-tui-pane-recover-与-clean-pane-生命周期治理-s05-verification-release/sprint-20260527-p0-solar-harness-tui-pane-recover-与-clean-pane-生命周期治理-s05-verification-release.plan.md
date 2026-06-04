# Plan — TUI Pane Recover S05 Verification-Release (epic 最后切片)

gate: `G_S05_VERIFICATION_RELEASE_PASSED`
knowledge_context: solar-harness context inject used
upstream: S03 passed (141 tests + 8 V) + S04 passed (C1-C4 spec)
downstream: epic close (parent-check ready=true → epic_decomposer auto-close)

## 0. DAG (5 V-nodes + 1 join)

```
V1_real_production_e2e (sonnet, 关键路径)
   ├─→ V2_autopilot_respawn_e2e (sonnet, fixture pane only)
   ├─→ V3_concurrent_stress (glm-5.1, ledger + spillover 真并发)
   └─→ V4_regression_aggregation (glm-5.1, S01 32 AC + S02 7 决议 + 5 OQ)
                                  └─→ V5_release_docs_epic_close_prep (sonnet)
                                        └─→ V6_join_epic_close_ready (sonnet)
```

**Wave 1**: V1 (关键路径)
**Wave 2 (3 并行)**: V2, V3, V4 (V1 完成后)
**Wave 3**: V5 (V2+V3+V4 完成后)
**Wave 4 (join)**: V6

## 1. 节点验收

| 节点 | 关键验收 |
|------|----------|
| **V1** real_production_e2e | 真 tmux `solar-harness-test` session ≥3 fixture panes; init_pane_hygiene.py 真跑产 pane-hygiene.json; RecoverDetector 接 real `tmux capture-pane -p` 50 行; PaneClearManager 真 `tmux send-keys` `/clear Enter`; PersonaReinjector 真注入; 5 evidence JSON 全产 |
| **V2** autopilot_respawn_e2e | **仅 `solar-harness-test` session**; 4 用例 (成功 + 3 失败); PROTECTED_PANES 强校验; ATLAS structured repair 兜底; respawn_max_concurrent=0 可禁用; 4 evidence JSON |
| **V3** concurrent_stress | Ledger 双写并发 ≥10 线程 + JSONL/SQLite 一致性; Spillover 3 并发零撞同; 写延迟 p99 ≤ 200ms; 3 evidence JSON |
| **V4** regression_aggregation | S01 32 AC (O1-O7 全) + S02 7 决议 D1-D7 + 5 OQ 决议 (OQ-01..OQ-05); regression_report.json 全 PASS/FAIL 表 |
| **V5** release_docs_epic_close_prep | `docs/tui-pane-recover/RELEASE.md` (epic 总览 + S01-S05 摘要 + 证据路径 + rollback + ATLAS hook 指引 + OQ-S03-01..03 carried-over); 禁止乐观词 |
| **V6** join | handoff (V1-V5 摘要 + epic close checklist) + traceability (parent_check_ready=true + epic_required_gates_status S01..S05 all passed); **不主动 close epic** |

## 2. 写范围 (per S04 §环境约束)

| 节点 | write_scope |
|------|-------------|
| V1 | `~/.solar/harness/run/pane-hygiene.json` (首次 init) + `reports/tui-pane/s05-acceptance/V1-*.json` + `<sid>.V1-handoff.md` |
| V2 | `reports/tui-pane/s05-acceptance/V2-*.json` (4 用例) + `<sid>.V2-handoff.md` |
| V3 | `reports/tui-pane/s05-acceptance/V3-*.json` (ledger + spillover + p99) + `<sid>.V3-handoff.md` |
| V4 | `reports/tui-pane/s05-acceptance/V4-regression_report.json` + `<sid>.V4-handoff.md` |
| V5 | `docs/tui-pane-recover/RELEASE.md` + `<sid>.V5-handoff.md` + `<sid>.eval.{md,json}` |
| V6 | `<sid>.handoff.md` + `<sid>.traceability.json` |

**严格禁止 PROTECTED set**:
- 杀生产 8 panes: `solar-harness:0.0-0.3` + `solar-harness-lab:0.0-0.3`
- 改生产 `spillover_config.yaml` (V1 首次 init 例外)
- 重启 ThunderOMLX / ASR / honcho / brain-router / qmd-proxy / config-server
- 修改 `~/.claude/settings.json` / Solar 仓库源
- 关闭 epic.* (V6 仅 mark ready, 不动 epic artifacts)
- 不用乐观词

## 3. 并发边界

- Wave 1 单线性 (V1)
- Wave 2 三并行 (V2/V3/V4 write_scope 互斥)
- Wave 3 单线性 (V5 join V2+V3+V4)
- Wave 4 join (V6)

## 4. 验证命令

### V1 真跑

```bash
# 创建专用测试 session
tmux new-session -d -s solar-harness-test
# 创建 3 fixture panes
tmux split-window -t solar-harness-test
tmux split-window -t solar-harness-test
# Init
python3 ~/.solar/harness/scripts/init_pane_hygiene.py --session solar-harness-test
# Capture-pane test
tmux capture-pane -p -S -50 -t solar-harness-test:0.0
# Clear test (fixture pane only!)
tmux send-keys -t solar-harness-test:0.1 "/clear" Enter
```

### V2 respawn (fixture only)

```bash
# Per OQ-05 命令序列 — 仅 solar-harness-test
tmux kill-pane -t solar-harness-test:0.2  # 测试用 fixture
tmux split-window -t solar-harness-test
# 等 ready marker (claude-code session ready)
```

### V3 concurrent

```bash
python3 -c "
from concurrent.futures import ThreadPoolExecutor
from harness.lib.ledger_writer import LedgerWriter
lw = LedgerWriter()
with ThreadPoolExecutor(max_workers=10) as ex:
    fs = [ex.submit(lw.record_recover, ...) for _ in range(100)]
    [f.result() for f in fs]
# 验证 JSONL + SQLite 一致性
"
```

### V4 regression

```bash
# 完整 pytest 套件 (S03 141 tests)
pytest ~/.solar/harness/tests/ -v --tb=short
# 32 AC 自动化校验
python3 ~/.solar/harness/scripts/run_s01_ac_regression.py --json
```

### V5 release docs

```bash
# 生成 release notes
ls -la ~/.solar/harness/docs/tui-pane-recover/RELEASE.md
```

## 5. no-live-pane-mutation 保护 (STRONG)

- **绝不** `tmux send-keys` / `tmux kill-pane` / `tmux respawn-pane` 到生产 8 panes
- PROTECTED set hardcoded: `solar-harness:0.{0,1,2,3}`, `solar-harness-lab:0.{0,1,2,3}`
- V2 所有 respawn 操作必须先校验 `pane_id.session == 'solar-harness-test'`, 否则立即 SIGTERM 自己
- 不重启 harness / coordinator / chain-watcher
- 不动 `~/.claude/plugins/` / `~/.claude/settings*.json`

## 6. Rollback / Stop Rules

### Rollback

- V1 失败 → `solar-harness-test` session 重起, pane-hygiene.json 删后重 init (生产 pane-hygiene 不受影响)
- V2 失败 → fixture pane 重建; 真 respawn 流程标 fail + ATLAS
- V3 失败 (ledger 不一致 / spillover 撞同) → 触发 S03 round-2 (bug 在实施层)
- V4 任一 AC FAIL → 触发对应 S01-S03 round-2
- V5/V6 失败 → 单节点重派
- 任何 PROTECTED pane 被触动 → 立即 sprint FAIL + 写 incident report + 触发紧急人工介入

### Stop Rules

- 缺 task_graph 不派 builder
- 缺可复现验证不标 passed
- 任一节点 acceptance FAIL → 不进下一节点
- 不杀 PROTECTED panes
- 不重启 service 进程
- 不动 prod config (V1 init 例外)
- 不主动 close epic
- 不用乐观词

## 7. SLO

| 指标 | hard | soft |
|------|------|------|
| 5 V 节点全 PASS | < 5 → sprint FAIL | n/a |
| PROTECTED pane 被触动 | > 0 → 立即 FAIL + incident | n/a |
| V2 respawn 任一用例 FAIL | > 0 → FAIL (4 用例必须 4/4) | n/a |
| V3 spillover 撞同 | > 0 → FAIL → S03 round-2 | n/a |
| V3 ledger 不一致 | > 0 → FAIL → S03 round-2 | n/a |
| V4 S01 AC FAIL | > 0 → FAIL → 对应 sprint round-2 | n/a |
| V5 RELEASE.md 缺 rollback 段 | 缺 → FAIL | n/a |
| V6 主动 close epic | > 0 → FAIL (违规) | n/a |
| 乐观词 | > 0 → FAIL | n/a |

## 8. 失败恢复路径

- V1: tmux session issue → 重起 `solar-harness-test`
- V2: kill-pane fail → ATLAS structured repair + log evidence
- V3: 并发问题 → 标 S03 bug, round-2 派给 S03 修
- V4: AC FAIL → 标 source sprint (S01/S02/S03) round-2
- ATLAS 兜底全跑过仍失败 → 人工介入

## 9. 给后续接力

V6 traceability `parent_check_ready=true` 后, coordinator/epic_decomposer 自动 parent-check 关闭 epic:
- S01 passed ✅
- S02 passed ✅
- S03 passed ✅
- S04 passed ✅
- S05 passed (本 sprint)
- Epic close (自动)

之后 dogfood 闭环达成: 所有 sprint 的 builder pane 卡死问题由 TUI epic 治理能力自动 detect+clear+reassign。

## 10. Knowledge Context

S03 6.6K handoff + 16K traceability + S04 5.4K handoff + 10.8K traceability + S02 4 docs + S01 3 requirements + epic.task_graph = ~80K total upstream evidence。`context inject` 已跑, mirage degraded → QMD + Obsidian + Solar DB。

11 capability `injectable_only`; V1-V2 真 tmux 交互 (非 capability 模拟)。
