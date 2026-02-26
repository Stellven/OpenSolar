#!/bin/bash
# State Update Enforcer - SessionEnd 前强制检查 STATE.md 是否更新
# 触发时机：SessionEnd

STATE_FILE="$HOME/.solar/STATE.md"
SESSION_START_TIME="/tmp/solar_session_start_time"

# 记录会话开始时间（如果不存在）
if [[ ! -f "$SESSION_START_TIME" ]]; then
    date +%s > "$SESSION_START_TIME"
fi

START_TIME=$(cat "$SESSION_START_TIME")
CURRENT_TIME=$(date +%s)
SESSION_DURATION=$((CURRENT_TIME - START_TIME))

# 如果会话时长小于 5 分钟，不检查
if [[ $SESSION_DURATION -lt 300 ]]; then
    exit 0
fi

# 检查 STATE.md 的修改时间
if [[ -f "$STATE_FILE" ]]; then
    STATE_MTIME=$(stat -f %m "$STATE_FILE" 2>/dev/null || echo "0")

    # 如果 STATE.md 在会话期间没有更新
    if [[ $STATE_MTIME -lt $START_TIME ]]; then
        cat << 'WARNING'

┌─ ⚠️  STATE.md 未更新警告 ───────────────────────┐
│                                                  │
│ 会话期间 STATE.md 未更新！                       │
│                                                  │
│ 请检查：                                         │
│ • 是否讨论了新任务但没写入 Mission/Plan？       │
│ • 是否完成了子任务但没更新 Progress？           │
│ • 是否做出了重要决策但没写入 Decisions？        │
│                                                  │
│ 违反后果：下次会话失忆，浪费监护人时间          │
│                                                  │
└──────────────────────────────────────────────────┘

WARNING
    fi
fi

# 清理会话开始时间标记
rm -f "$SESSION_START_TIME"

exit 0
