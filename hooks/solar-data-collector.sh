#!/bin/bash
# Solar Data Collector Hook
# 收集 Tool/Agent/Skill 调用数据写入 SQLite
# 位置: ~/.claude/hooks/solar-data-collector.sh

DB_PATH="${SOLAR_DB:-$HOME/.solar/solar.db}"
INPUT=$(cat)

# 确保数据库目录存在
mkdir -p "$(dirname "$DB_PATH")"

# 获取调用信息
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}' 2>/dev/null)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
TRACE_ID=$(echo "$INPUT" | jq -r '.trace_id // empty' 2>/dev/null)

# 如果没有工具名，跳过
if [[ -z "$TOOL_NAME" ]]; then
    exit 0
fi

# 生成 call_id
CALL_ID="call:$(date +%s%N)"

# 获取时间信息
STARTED_AT=$(date -u +"%Y-%m-%d %H:%M:%S")

# 插入到 evo_tool_calls (如果数据库存在)
if [[ -f "$DB_PATH" ]]; then
    sqlite3 "$DB_PATH" <<SQL 2>/dev/null
INSERT OR IGNORE INTO evo_tool_calls (
    call_id, span_id, trace_id, tool_name, tool_provider,
    input_params, latency_ms, status, created_at
)
VALUES (
    '$CALL_ID',
    'span:$CALL_ID',
    '${TRACE_ID:-unknown}',
    '$TOOL_NAME',
    'builtin',
    '$(echo "$TOOL_INPUT" | sed "s/'/''/g")',
    0,
    'pending',
    '$STARTED_AT'
);
SQL
fi

exit 0
