#!/bin/bash
# Solar Skill Tracking Hook
# Skill 调用时记录
# 位置: ~/.claude/hooks/solar-skill-track.sh

DB_PATH="${SOLAR_DB:-$HOME/.solar/solar.db}"
INPUT=$(cat)

# 如果数据库不存在，跳过
if [[ ! -f "$DB_PATH" ]]; then
    exit 0
fi

# 从输入中提取 Skill 名称 (格式: /skillname 或 skill:xxx)
# 使用 sed 兼容 macOS (无 grep -P)
SKILL_NAME=$(echo "$INPUT" | sed -n 's|.*/\([a-z][a-z0-9-]*\).*|\1|p' | head -1)

if [[ -z "$SKILL_NAME" ]]; then
    # 尝试从 command-name tag 提取
    SKILL_NAME=$(echo "$INPUT" | sed -n 's|.*<command-name>/\([a-z][a-z0-9-]*\).*|\1|p' | head -1)
fi

if [[ -z "$SKILL_NAME" ]]; then
    exit 0
fi

# 转换为 resource_id 格式
SKILL_ID="skill:$SKILL_NAME:1.0"
SESSION_ID="${SOLAR_SESSION_ID:-session:unknown}"

# 记录 Skill 调用
sqlite3 "$DB_PATH" <<SQL 2>/dev/null
INSERT INTO sys_invocations (
    resource_id, invocation_type, session_id,
    latency_ms, status, created_at
)
VALUES (
    '$SKILL_ID',
    'skill_call',
    '$SESSION_ID',
    0,
    'success',
    datetime('now')
);
SQL

exit 0
