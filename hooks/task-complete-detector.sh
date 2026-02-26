#!/bin/bash
# 任务完成检测器
# 检测关键操作后提醒更新 STATE.md

# 从 stdin 读取 tool result
INPUT=$(cat)

# 解析 tool 名称
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // .tool // ""' 2>/dev/null)

# 计数器文件
COUNTER_FILE="/tmp/solar_tool_counter"
STATE_REMINDER_FILE="/tmp/solar_state_reminder_shown"

# 增加计数
if [[ -f "$COUNTER_FILE" ]]; then
    COUNT=$(cat "$COUNTER_FILE")
    COUNT=$((COUNT + 1))
else
    COUNT=1
fi
echo "$COUNT" > "$COUNTER_FILE"

# 检测"完成信号" - 某些操作模式表示任务可能完成
COMPLETE_SIGNALS=(
    "git commit"
    "git push"
    "test passed"
    "build success"
)

# 每 3 次工具调用提醒一次
if [[ $((COUNT % 3)) -eq 0 ]]; then
    if [[ ! -f "$STATE_REMINDER_FILE" ]] || [[ $(find "$STATE_REMINDER_FILE" -mmin +5 2>/dev/null) ]]; then
        cat << 'REMINDER'

┌─ 💾 STATE.md 检查点提醒 ─────────────────────────┐
│ 已执行 3+ 次工具调用                             │
│ 建议检查 STATE.md 是否需要更新 Progress          │
└──────────────────────────────────────────────────┘

REMINDER
        touch "$STATE_REMINDER_FILE"
    fi
fi

exit 0
