#!/bin/bash
# Solar Telemetry Hook - 自动采集工具调用数据
# 用于 PostToolUse:* hooks

DB_PATH="$HOME/.solar/solar.db"
INPUT=$(cat)

# 解析字段
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}' 2>/dev/null)
TOOL_RESULT=$(echo "$INPUT" | jq -c '.tool_result // {}' 2>/dev/null)
SESSION_ID="${CLAUDE_SESSION_ID:-ses_$(date +%s)}"

# 生成操作 ID
OP_ID="op_$(date +%s)_$(head -c 4 /dev/urandom | xxd -p)"

# 分类映射
case "$TOOL_NAME" in
    Read|Write|Edit|Glob)
        CATEGORY="file"
        OPERATION=$(echo "$TOOL_NAME" | tr '[:upper:]' '[:lower:]')
        TARGET=$(echo "$TOOL_INPUT" | jq -r '.file_path // .path // .pattern // ""' | head -c 200)
        ;;
    Bash)
        CATEGORY="bash"
        OPERATION="spawn"
        TARGET=$(echo "$TOOL_INPUT" | jq -r '.command // ""' | head -c 200)
        ;;
    Grep)
        CATEGORY="file"
        OPERATION="search"
        TARGET=$(echo "$TOOL_INPUT" | jq -r '.pattern // ""' | head -c 200)
        ;;
    WebFetch|WebSearch)
        CATEGORY="http"
        OPERATION=$(echo "$TOOL_NAME" | tr '[:upper:]' '[:lower:]')
        TARGET=$(echo "$TOOL_INPUT" | jq -r '.url // .query // ""' | head -c 200)
        ;;
    Task)
        CATEGORY="mcp"
        OPERATION="task"
        TARGET=$(echo "$TOOL_INPUT" | jq -r '.subagent_type // ""')
        ;;
    Skill)
        CATEGORY="mcp"
        OPERATION="skill"
        TARGET=$(echo "$TOOL_INPUT" | jq -r '.skill // ""')
        ;;
    mcp__brain-router__*)
        CATEGORY="mcp"
        OPERATION="brain-router"
        TARGET=$(echo "$TOOL_INPUT" | jq -r '.model // "unknown"')

        # 触发 SROE 自动采集闭环
        SROE_COLLECTOR="$HOME/.claude/core/intent-engine/sroe-auto-collector.ts"
        if [[ -f "$SROE_COLLECTOR" && "$TOOL_NAME" == "mcp__brain-router__complete" ]]; then
            (
                PROMPT=$(echo "$TOOL_INPUT" | jq -r '.prompt // ""' | head -c 5000)
                MODEL=$(echo "$TOOL_INPUT" | jq -r '.model // "unknown"')
                OUTPUT=$(echo "$TOOL_RESULT" | head -c 10000)
                LATENCY_MS="${TOOL_DURATION_MS:-2000}"

                echo "{\"model\":\"$MODEL\",\"prompt\":$(echo "$PROMPT" | jq -Rs .),\"output\":$(echo "$OUTPUT" | jq -Rs .),\"latencyMs\":$LATENCY_MS}" | \
                    bun "$SROE_COLLECTOR" collect >/dev/null 2>&1
            ) &
        fi
        ;;
    mcp__*)
        CATEGORY="mcp"
        OPERATION="call"
        TARGET="$TOOL_NAME"
        ;;
    *)
        CATEGORY="tool"
        OPERATION="$TOOL_NAME"
        TARGET=""
        ;;
esac

# 判断成功/失败
if echo "$TOOL_RESULT" | grep -qiE "error|failed|exception|denied|timeout"; then
    SUCCESS=0
    ERROR_MSG=$(echo "$TOOL_RESULT" | grep -oE "(error|Error|ERROR|failed|Failed)[^\"]{0,100}" | head -1)
else
    SUCCESS=1
    ERROR_MSG=""
fi

# 计算数据量
INPUT_BYTES=${#TOOL_INPUT}
OUTPUT_BYTES=${#TOOL_RESULT}

# 估算耗时 (从环境变量或默认)
DURATION_MS="${TOOL_DURATION_MS:-50}"

# 异步写入
(
sqlite3 "$DB_PATH" "
INSERT OR IGNORE INTO tel_operations (
    session_id, operation_id, category, operation, target,
    duration_ms, input_bytes, output_bytes, success,
    error_message, caller_type, caller_id
) VALUES (
    '$SESSION_ID',
    '$OP_ID',
    '$CATEGORY',
    '$OPERATION',
    '$(echo "$TARGET" | sed "s/'/''/g")',
    $DURATION_MS,
    $INPUT_BYTES,
    $OUTPUT_BYTES,
    $SUCCESS,
    '$(echo "$ERROR_MSG" | sed "s/'/''/g")',
    'tool',
    '$TOOL_NAME'
);
" 2>/dev/null
) &

exit 0
