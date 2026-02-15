#!/bin/bash
# Solar Phase Tracking Hook
# 阶段转换时记录
# 位置: ~/.claude/hooks/solar-phase-track.sh

DB_PATH="${SOLAR_DB:-$HOME/.solar/solar.db}"
INPUT=$(cat)

# 如果数据库不存在，跳过
if [[ ! -f "$DB_PATH" ]]; then
    exit 0
fi

# 从输入中提取阶段信息 (使用 sed 兼容 macOS)
FROM_PHASE=$(echo "$INPUT" | sed -n 's/.*from_phase[^A-Z]*\([A-Z][0-9]*\).*/\1/p' | head -1)
TO_PHASE=$(echo "$INPUT" | sed -n 's/.*to_phase[^A-Z]*\([A-Z][0-9]*\).*/\1/p' | head -1)

# 尝试从环境变量获取
FROM_PHASE="${FROM_PHASE:-$SOLAR_PHASE}"
TO_PHASE="${TO_PHASE:-$SOLAR_NEXT_PHASE}"

if [[ -z "$FROM_PHASE" || -z "$TO_PHASE" ]]; then
    exit 0
fi

SESSION_ID="${SOLAR_SESSION_ID:-session:unknown}"
TODAY=$(date +"%Y-%m-%d")

# 记录阶段转换 (使用实际表结构: date 而非 hour_bucket)
sqlite3 "$DB_PATH" <<SQL 2>/dev/null
INSERT INTO sys_phase_stats (
    from_phase, to_phase, date,
    transition_count, avg_duration_seconds
)
VALUES (
    '$FROM_PHASE',
    '$TO_PHASE',
    '$TODAY',
    1,
    0
)
ON CONFLICT(from_phase, to_phase, date) DO UPDATE SET
    transition_count = transition_count + 1;
SQL

exit 0
