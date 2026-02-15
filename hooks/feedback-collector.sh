#!/bin/bash
# Solar Feedback Collector Hook
# 在工具执行后自动记录成功/失败反馈
# 触发: PostToolUse:*

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // ""' 2>/dev/null)
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_output // ""' 2>/dev/null)
IS_ERROR=$(echo "$INPUT" | jq -r '.is_error // false' 2>/dev/null)

# 跳过读取类工具 (不产生有意义的成功/失败反馈)
case "$TOOL_NAME" in
    Read|Glob|Grep|WebSearch|WebFetch)
        exit 0
        ;;
esac

# 检测执行结果
if [ "$IS_ERROR" = "true" ] || echo "$TOOL_OUTPUT" | grep -qiE 'error|failed|failure|exception|denied'; then
    SIGNAL_TYPE="task_failure"
    FEEDBACK_VALUE="-0.3"
else
    SIGNAL_TYPE="task_success"
    FEEDBACK_VALUE="0.2"
fi

# 获取 Session ID (如果可用)
SESSION_ID="${CLAUDE_SESSION_ID:-}"

# 异步写入 evo_feedback_v2 (不阻塞主流程)
sqlite3 ~/.solar/solar.db "
INSERT INTO evo_feedback_v2 (
    feedback_id, session_id, signal_type, feedback_value, trigger_text,
    related_tool, task_type
) VALUES (
    'fb_' || strftime('%s', 'now') || '_' || hex(randomblob(4)),
    '$SESSION_ID',
    '$SIGNAL_TYPE',
    $FEEDBACK_VALUE,
    '$(echo "$TOOL_NAME" | sed "s/'/''/g")',
    '$TOOL_NAME',
    'tool_execution'
)
" 2>/dev/null &

exit 0
