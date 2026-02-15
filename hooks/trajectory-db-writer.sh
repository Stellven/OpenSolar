#!/bin/bash
# Solar Trajectory DB Writer
# 将工具调用记录写入 evo_tool_calls 表

DB_PATH="$HOME/.solar/solar.db"
INPUT=$(cat)

# 解析关键字段
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}' 2>/dev/null | head -c 5000)
TOOL_RESULT=$(echo "$INPUT" | jq -c '.tool_result // {}' 2>/dev/null | head -c 10000)
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
TRACE_ID="${CLAUDE_TRACE_ID:-$(date +%s)}"

# 生成唯一 ID
CALL_ID="tc_$(date +%s)_$(head -c 4 /dev/urandom | xxd -p)"
SPAN_ID="sp_$(date +%s)"

# 判断状态
STATUS="success"
if echo "$TOOL_RESULT" | grep -qi "error\|failed\|exception\|denied"; then
    STATUS="error"
    ERROR_MSG=$(echo "$TOOL_RESULT" | grep -oE "(error|Error|ERROR)[^\"]*" | head -1)
else
    ERROR_MSG=""
fi

# 获取文件信息 (如果是文件操作)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)
if [[ -n "$FILE_PATH" && -f "$FILE_PATH" ]]; then
    FILE_TYPE="${FILE_PATH##*.}"
    LINE_COUNT=$(wc -l < "$FILE_PATH" 2>/dev/null || echo 0)
else
    FILE_TYPE=""
    LINE_COUNT=0
fi

# 计算输出大小
OUTPUT_SIZE=${#TOOL_RESULT}

# 异步写入数据库
(
sqlite3 "$DB_PATH" "
INSERT INTO evo_tool_calls (
    call_id, span_id, trace_id, tool_name, tool_provider,
    input_params, output_result, output_size_bytes,
    status, error_message, file_path, file_type, line_count
) VALUES (
    '$CALL_ID',
    '$SPAN_ID',
    '$TRACE_ID',
    '$TOOL_NAME',
    'claude_code',
    '$(echo "$TOOL_INPUT" | sed "s/'/''/g")',
    '$(echo "$TOOL_RESULT" | sed "s/'/''/g" | head -c 5000)',
    $OUTPUT_SIZE,
    '$STATUS',
    '$(echo "$ERROR_MSG" | sed "s/'/''/g")',
    '$FILE_PATH',
    '$FILE_TYPE',
    $LINE_COUNT
);
" 2>/dev/null
) &

exit 0
