#!/usr/bin/env bash
# sprint-20260503-104819 D7: 端到端测试 — dispatch 同 pane 连派覆盖防护
set -uo pipefail

HARNESS_DIR="$HOME/.solar/harness"
SPRINTS_DIR="$HARNESS_DIR/sprints"
PASS=0; FAIL=0

# 准备: 备份当前状态
backup_state() {
  cp "$HARNESS_DIR/.pane-assignments" /tmp/pa.bak.$$ 2>/dev/null || true
  cp "$HARNESS_DIR/.coordinator-state" /tmp/cs.bak.$$ 2>/dev/null || true
}
restore_state() {
  mv /tmp/pa.bak.$$ "$HARNESS_DIR/.pane-assignments" 2>/dev/null || rm -f "$HARNESS_DIR/.pane-assignments"
  mv /tmp/cs.bak.$$ "$HARNESS_DIR/.coordinator-state" 2>/dev/null || rm -f "$HARNESS_DIR/.coordinator-state"
}
trap restore_state EXIT
backup_state

# (a) 创建 2 个 disposable test sprint
SID_A="sprint-test-overlap-a-$$"
SID_B="sprint-test-overlap-b-$$"
echo "{\"id\":\"$SID_A\",\"status\":\"active\",\"round\":0,\"history\":[]}" > "$SPRINTS_DIR/${SID_A}.status.json"
echo "{\"id\":\"$SID_B\",\"status\":\"active\",\"round\":0,\"history\":[]}" > "$SPRINTS_DIR/${SID_B}.status.json"

# 加载 coordinator 函数 (source 不执行主循环)
COORD_NO_MAIN=1 source "$HARNESS_DIR/coordinator.sh" 2>/dev/null

# 清空 assignments
PANE_CURRENT_SPRINT=()
PANE_ASSIGN_TS=()

# (b) 第一次 dispatch (mock 模式: 只更新 PANE_CURRENT_SPRINT, 不真发 send-keys)
DISPATCH_MOCK=1 dispatch_to_pane "solar-harness:0.1" "" "$SID_A"
rc1=$?
if [[ $rc1 -eq 0 ]]; then ((PASS++)); else echo "FAIL: dispatch A rc=$rc1"; ((FAIL++)); fi
if [[ "${PANE_CURRENT_SPRINT[1]}" == "$SID_A" ]]; then ((PASS++)); else echo "FAIL: assign A 未记录"; ((FAIL++)); fi

# (c) 30s 内第二次 dispatch 给同 pane, 必须 return 2 (D2 busy 守卫)
DISPATCH_MOCK=1 dispatch_to_pane "solar-harness:0.1" "" "$SID_B"
rc2=$?
if [[ $rc2 -eq 2 ]]; then ((PASS++)); else echo "FAIL: dispatch B rc=$rc2 (期望 2)"; ((FAIL++)); fi
if [[ "${PANE_CURRENT_SPRINT[1]}" == "$SID_A" ]]; then ((PASS++)); else echo "FAIL: assign 被覆盖为 ${PANE_CURRENT_SPRINT[1]}"; ((FAIL++)); fi

# (d) 验证 D4 per-pane mkdir lock: 清除 assignment, 创建 stale lock, 派发应被 lock 拦截
clear_pane_assignment "$SID_A" 2>/dev/null || true
mkdir "$HARNESS_DIR/.dispatch-pane-1.lock" 2>/dev/null
echo $$ > "$HARNESS_DIR/.dispatch-pane-1.lock/pid"
DISPATCH_MOCK=1 dispatch_to_pane "solar-harness:0.1" "" "$SID_B"
rc_lock=$?
rm -rf "$HARNESS_DIR/.dispatch-pane-1.lock"
if [[ $rc_lock -eq 2 ]]; then ((PASS++)); else echo "FAIL: D4 lock 未拦截 (rc=$rc_lock)"; ((FAIL++)); fi

# (e) clear A → 再派 B 应成功
clear_pane_assignment "$SID_A" 2>/dev/null || true
if [[ -z "${PANE_CURRENT_SPRINT[1]:-}" ]]; then ((PASS++)); else echo "FAIL: clear 后 assign 未清空"; ((FAIL++)); fi

DISPATCH_MOCK=1 dispatch_to_pane "solar-harness:0.1" "" "$SID_B"
rc3=$?
if [[ $rc3 -eq 0 ]]; then ((PASS++)); else echo "FAIL: dispatch B retry rc=$rc3"; ((FAIL++)); fi
if [[ "${PANE_CURRENT_SPRINT[1]}" == "$SID_B" ]]; then ((PASS++)); else echo "FAIL: assign 未切换到 B (got ${PANE_CURRENT_SPRINT[1]:-empty})"; ((FAIL++)); fi

# (f) 持久化验证
save_pane_assignments
if [[ -f "$HARNESS_DIR/.pane-assignments" ]]; then ((PASS++)); else echo "FAIL: .pane-assignments 文件不存在"; ((FAIL++)); fi

# 清理
rm -f "$SPRINTS_DIR/${SID_A}".* "$SPRINTS_DIR/${SID_B}".*
rm -rf "$HARNESS_DIR/.dispatch-pane-1.lock"

echo ""
echo "=== Results: PASS=$PASS FAIL=$FAIL ==="
if (( FAIL == 0 )); then
  echo "PASS"
  exit 0
fi
echo "FAIL"
exit 1
