#!/bin/bash
# Solar Agent Tracking Hook
# Agent 调用时记录执行数据
# 位置: ~/.claude/hooks/solar-agent-track.sh

DB_PATH="${SOLAR_DB:-$HOME/.solar/solar.db}"
INPUT=$(cat)

# 如果数据库不存在，跳过
if [[ ! -f "$DB_PATH" ]]; then
    exit 0
fi

# 从输入中提取 Agent 宣告信息
# 格式: ┌─ [emoji] [Agent名] ────────────────────┐
# 使用 sed 兼容 macOS (无 grep -P)
AGENT_NAME=$(echo "$INPUT" | sed -n 's/.*┌─[^A-Za-z]*\([A-Za-z][A-Za-z]*\).*/\1/p' | head -1)

if [[ -z "$AGENT_NAME" ]]; then
    # 尝试 @Agent 格式
    AGENT_NAME=$(echo "$INPUT" | sed -n 's/.*@\([A-Za-z][A-Za-z]*\).*/\1/p' | head -1)
fi

if [[ -z "$AGENT_NAME" ]]; then
    exit 0
fi

# 转换为 resource_id 格式
AGENT_ID="agent:$(echo "$AGENT_NAME" | tr '[:upper:]' '[:lower:]'):1.0"
EXEC_ID="exec:$(date +%s%N)"
SESSION_ID="${SOLAR_SESSION_ID:-session:unknown}"
PHASE="${SOLAR_PHASE:-P3}"

# 记录 Agent 执行开始
sqlite3 "$DB_PATH" <<SQL 2>/dev/null
INSERT INTO evo_agent_executions (
    execution_id, session_id, role_id, phase, model_used,
    input_tokens, output_tokens, latency_ms, cost_usd,
    execution_success, created_at
)
VALUES (
    '$EXEC_ID',
    '$SESSION_ID',
    '$AGENT_ID',
    '$PHASE',
    'sonnet',
    0, 0, 0, 0,
    TRUE,
    datetime('now')
);

-- 同时记录到 sys_invocations
INSERT INTO sys_invocations (
    resource_id, invocation_type, session_id,
    latency_ms, status, created_at
)
VALUES (
    '$AGENT_ID',
    'agent_call',
    '$SESSION_ID',
    0,
    'success',
    datetime('now')
);
SQL

exit 0
