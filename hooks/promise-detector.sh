#!/bin/bash
# Promise Detector Hook
# 检测 Solar 是否说了承诺词但没有执行
# 触发: PostToolUse (分析 assistant 输出)

# 这个 hook 的作用是：
# 1. 记录 Solar 的承诺
# 2. 在会话结束时检查是否都执行了

DB_PATH="$HOME/.solar/solar.db"
INPUT=$(cat)

# 获取工具名和输出
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)

# 只在特定工具后检查 (避免每次都触发)
if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" && "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# 检查是否有未完成的承诺
# (这里简化实现，实际可以更复杂)

PENDING_PROMISES=$(sqlite3 "$DB_PATH" "
SELECT COUNT(*) FROM bl_tasks
WHERE status = 'pending'
AND title LIKE '%承诺%'
AND created_at > datetime('now', '-1 hour')
" 2>/dev/null)

if [ "$PENDING_PROMISES" -gt 0 ]; then
    echo "<promise-reminder>"
    echo "⚠️ 有 $PENDING_PROMISES 个未完成的承诺任务"
    echo "请先完成承诺再做其他事"
    echo "</promise-reminder>"
fi

exit 0
