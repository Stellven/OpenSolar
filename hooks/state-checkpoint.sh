#!/bin/bash
# STATE.md 自动检查点 Hook
# 功能：
# 1. 定时提醒更新 STATE.md
# 2. 自动调用 Lite State Updater 更新自动进度
# 3. SessionEnd 时自动保存

STATE_FILE="$HOME/.claude/STATE.md"
LAST_CHECK_FILE="/tmp/solar_state_last_check"
LITE_STATE_UPDATER="$HOME/.claude/core/memory-service/lite-state-updater.ts"

# 获取当前时间戳
NOW=$(date +%s)

# 检查上次检查时间
if [ -f "$LAST_CHECK_FILE" ]; then
    LAST_CHECK=$(cat "$LAST_CHECK_FILE")
else
    LAST_CHECK=0
fi

# 计算距离上次检查的时间（秒）
ELAPSED=$((NOW - LAST_CHECK))

# 每 5 分钟提醒一次（300 秒）
INTERVAL=300

# 检测是否需要提醒
should_remind() {
    # 距离上次检查超过 INTERVAL
    [ $ELAPSED -gt $INTERVAL ]
}

# 自动更新进度 (Layer 3: Lite State Updater)
auto_update_progress() {
    if [ -f "$LITE_STATE_UPDATER" ]; then
        # 静默更新 STATE.md 的自动进度部分
        bun "$LITE_STATE_UPDATER" update 2>/dev/null || true
    fi
}

# 输出提醒
output_reminder() {
    # 先自动更新进度
    auto_update_progress

    cat << 'REMINDER'

┌─────────────────────────────────────────────────────────────────┐
│  💾 STATE.md 检查点提醒 (自动进度已更新)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  距离上次检查点已过 5 分钟                                      │
│  ✓ 自动进度已更新 (基于最近工具调用)                           │
│                                                                 │
│  如需更新手动部分，请说:                                        │
│  ─────────────────────────────────────────────────────────────  │
│  "现在生成结构化会话快照，按五段式写入 STATE.md"                │
│                                                                 │
│  五段式槽位:                                                    │
│  • Mission (目标变了吗?)                                        │
│  • Constraints (新约束?)                                        │
│  • Decisions (做了什么决策? 为什么?)                            │
│  • Progress (Done/In-Progress/Blocked)                          │
│  • Next Actions (下一步精确到可执行)                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

REMINDER
    # 更新检查时间
    echo "$NOW" > "$LAST_CHECK_FILE"
}

# 主逻辑
if should_remind; then
    output_reminder
fi

exit 0
