# Architect Design — Dispatch 覆盖 Bug 修复 Done 定义

**架构师**: pane 3 (opus)
**用途**: 规划者 copy-paste 到新 sprint contract.md 的 `## Definition of Done` 段
**来源**: investigation-002 (3 漏洞 P0/P1/P2 修复路径)
**Sprint 估时**: 2-3h (P0+P1 ≈ 75 行 coord.sh 改动 + 测试)

---

## Definition of Done

- [ ] D1: 新增 per-pane assignment tracking (核心数据结构) — `coordinator.sh` 顶部声明 `declare -A PANE_CURRENT_SPRINT=()` 与 `declare -A PANE_ASSIGN_TS=()`, 用于记录每个 pane 当前承载的 sprint id 和派出时间. 必须在 `dispatch_to_pane` 函数定义之前. 实现完成后 `bash -n coordinator.sh` 通过且 `grep -c 'PANE_CURRENT_SPRINT\|PANE_ASSIGN_TS' coordinator.sh` ≥ 6 (定义+读+写+清).
  <!-- verify: cmd="bash -n ${HARNESS_DIR}/coordinator.sh && grep -cE 'PANE_CURRENT_SPRINT|PANE_ASSIGN_TS' ${HARNESS_DIR}/coordinator.sh" expected_exit=0 output_pattern="^[6-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 15 min

- [ ] D2: dispatch_to_pane 入口加 busy 守卫 — 函数开头解析 `pane_idx="${pane##*.}"`, 读 `PANE_CURRENT_SPRINT[$pane_idx]`, 若已被 != 当前 sid 占用且占用时长 < 30min (1800s) 则返回 **return code 2** (区别于真失败的 1), 同时 `emit_event` 记录 `dispatch_blocked`. 派发成功末尾必须 set `PANE_CURRENT_SPRINT[$pane_idx]=$sid` 和 `PANE_ASSIGN_TS[$pane_idx]=$(date +%s)`.
  <!-- verify: cmd="grep -nE 'return 2|dispatch_blocked|PANE_ASSIGN_TS\\[.*\\]=\\\$\\(date' ${HARNESS_DIR}/coordinator.sh | wc -l" expected_exit=0 output_pattern="^[3-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 20 min

- [ ] D3: pane assignment 持久化 — 写入 `~/.solar/harness/.pane-assignments` (key=value 格式: `1=sprint-xxx:1715000000`), 协调器启动时 reload (类似 .coordinator-state). 协调器进程重启不丢 assignment, 启动 log 含 "loaded N pane assignments". 实现 `save_pane_assignments` 和 `load_pane_assignments` 两个函数, 在 dispatch 后和主循环启动时调用.
  <!-- verify: cmd="grep -cE 'save_pane_assignments|load_pane_assignments|\\.pane-assignments' ${HARNESS_DIR}/coordinator.sh" expected_exit=0 output_pattern="^[5-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 25 min

- [ ] D4: per-pane flock — dispatch_to_pane 主体用 `flock -n` 拿 `~/.solar/harness/.dispatch-pane-${pane_idx}.lock`, 拿不到立即 return 2 (与 D2 同一返回码). 拿到锁后跑原派发逻辑, 函数返回前用 `flock -u` 释放. 锁文件 stale 不阻塞 (flock 持有进程死亡自动释放).
  <!-- verify: cmd="grep -cE 'flock -n|flock -u|\\.dispatch-pane-' ${HARNESS_DIR}/coordinator.sh" expected_exit=0 output_pattern="^[3-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 15 min

- [ ] D5: handle_passed / handle_failed 末尾清 assignment — 实现 `clear_pane_assignment <sid>` 函数, 遍历 `PANE_CURRENT_SPRINT` 找匹配 sid 的 idx 并 `unset`, 之后调 `save_pane_assignments` 持久化. 在 `handle_passed` 和 `handle_failed_review` (failed 终态 case 也算) 函数体内必须调用.
  <!-- verify: cmd="grep -cE 'clear_pane_assignment' ${HARNESS_DIR}/coordinator.sh" expected_exit=0 output_pattern="^[3-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 15 min

- [ ] D6: 调用方处理 return 2 — `handle_active` / `handle_planning` / `handle_reviewing` 等所有调 `dispatch_to_pane` 的位置, 必须捕获 `rc=$?`, 当 `rc -eq 2` 时 log "[handle_XXX] pane busy, 下轮再派" 并 **不 save_state** (让 check_state_changed 下轮再触发) + return 0. **不能** 把 return 2 当失败处理 (避免 emit dispatch_failed 污染事件流).
  <!-- verify: cmd="grep -nE 'rc -eq 2|=\\\$\\?.*\\n.*-eq 2|pane busy.*下轮' ${HARNESS_DIR}/coordinator.sh | wc -l" expected_exit=0 output_pattern="^[2-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 15 min

- [ ] D7: 端到端实测 — 编写 `~/.solar/harness/test-dispatch-overlap.sh`, 模拟以下场景: (a) 起 2 个 active sprint A 和 B; (b) 调用 dispatch_to_pane 派 A 给 pane 0.1 (mock 模式: 只更新 PANE_CURRENT_SPRINT, 不真发 send-keys); (c) 30s 内调用 dispatch_to_pane 派 B 给同一 pane; (d) 验证第二次调用 **返回 2** 且 `.dispatch-pane-1.lock` 文件存在; (e) 调 clear_pane_assignment A; (f) 再派 B 应成功 return 0. 测试输出含 "PASS" 字样且全程 exit 0.
  <!-- verify: cmd="bash ${HARNESS_DIR}/test-dispatch-overlap.sh" expected_exit=0 output_pattern="PASS" -->
  - **预计实施时间**: 30 min

- [ ] D8: 不破坏既有功能 — 单 sprint 派单流程不受影响, 现有测试 `test-dispatch.sh` / `test-dispatch-modal.sh` / `test-multi-sprint-race.sh` 全部仍通过. 建设者必须运行三个测试并把退出码贴进 handoff.md.
  <!-- verify: cmd="bash ${HARNESS_DIR}/test-dispatch.sh && bash ${HARNESS_DIR}/test-dispatch-modal.sh && bash ${HARNESS_DIR}/test-multi-sprint-race.sh" expected_exit=0 output_pattern="" -->
  - **预计实施时间**: 15 min (跑测试 + 修小问题)

- [ ] D9 **(可选)**: verify 误判修复 — `dispatch_to_pane` 末尾 verify 段除了 keyword + processing 双命中外, 必须新增第三命中条件: `capture-pane` 输出**显式包含本次 dispatch 的 sid 字符串** (例如 `sprint-20260503-094659`). 由于 dispatch.md 文件名含 sid, builder 一旦真读取就会显示 `Read(.../sprint-20260503-094659.dispatch.md)`. 三命中才返回 0, 否则继续重试.
  <!-- verify: cmd="grep -nE 'has_sid|sid_match|grep.*\\\$sid' ${HARNESS_DIR}/coordinator.sh | wc -l" expected_exit=0 output_pattern="^[1-9]" -->
  - **预计实施时间**: 15 min (可选, 不做不影响主修复)

---

## 总预算

| 范围 | 时间 |
|------|------|
| D1-D6 (核心 P0+P1 实现) | 105 min |
| D7 (端到端测试编写) | 30 min |
| D8 (回归测试) | 15 min |
| D9 (可选 verify 强化) | 15 min |
| **必做总计** (D1-D8) | **2h 30min** |
| **完整含 D9** | **2h 45min** |

---

## 实施顺序建议

```
D1 (数据结构) → D5 (清 assignment) → D2 (busy 守卫) → D6 (调用方) → D3 (持久化) → D4 (flock) → D7 (e2e 测试) → D8 (回归) → [D9 可选]
```

**理由**:
- D1 + D5 先建立完整生命周期 (创建 + 销毁), 否则 D2 守卫会卡死所有 sprint
- D2 + D6 同步上线 (守卫和调用方处理是配对的, 单做任一会回归)
- D3 (持久化) 在 D2 稳定后加, 避免协调器中途重启丢 state
- D4 (flock) 与 D3 互补但独立, 可以最后加
- D7 (测试) 在所有改动稳定后写, 避免反复改测试
- D8 (回归) 最后跑, 有退化立即定位是哪一步引入

---

## 关键风险提示 (供规划者审核合约时参考)

1. **D2 return 2 必须配 D6**, 否则 handle_active 误以为失败会 save_state, 导致下轮 check_state_changed 不触发 → sprint 永远不重派
2. **D3 持久化 reload 顺序**: 协调器启动时必须先 load_pane_assignments **再** 进 main loop, 否则首轮 dispatch 会用空 assignment
3. **D5 clear 漏调**: 如果 handle_passed 走异常路径 (gate_check 失败) 没调 clear, pane 会被永久占用. 建议加 cleanup trap on exit
4. **D7 mock 模式**: 不真发 send-keys (避免污染当前活跃 builder pane), 只测 assignment dict 和 flock 行为

---

**完成**: 8 必做 + 1 可选 Done, 共 9 条, 全部含 verify cmd / expected_exit / output_pattern. 总行数 ~135 (≤200 ✓).
**规划者下一步**: 把 `## Definition of Done` 段 copy 进 sprint contract, 推 active.
