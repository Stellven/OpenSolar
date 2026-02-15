#!/bin/bash
# Solar Ontology - Stop Hook
# 会话结束时保存学习到本体

DB_FILE="$HOME/.solar/solar.db"
ONTOLOGY_CORE="$HOME/Solar/core/ontology"

# 如果数据库不存在，跳过
if [[ ! -f "$DB_FILE" ]]; then
    echo '{"decision": "approve"}'
    exit 0
fi

# 获取会话 ID (如果有)
SESSION_ID="${CLAUDE_SESSION_ID:-$(date +%s)}"

# 记录会话结束事件到时间线
sqlite3 "$DB_FILE" "
INSERT OR IGNORE INTO ont_learning_events (
    event_id, event_type, details, source_type, session_id
) VALUES (
    'evt_${SESSION_ID}_end',
    'session_end',
    json_object('timestamp', datetime('now')),
    'session',
    '${SESSION_ID}'
);
" 2>/dev/null

# 检查是否需要创建自动快照 (每10个会话)
SESSION_COUNT=$(sqlite3 "$DB_FILE" "
SELECT COUNT(*) FROM ont_learning_events
WHERE event_type = 'session_end'
AND occurred_at > datetime('now', '-1 day');
" 2>/dev/null)

if [[ $((SESSION_COUNT % 10)) -eq 0 && $SESSION_COUNT -gt 0 ]]; then
    # 创建自动快照
    SNAPSHOT_ID="snap_$(date +%s)_auto"
    VERSION=$(sqlite3 "$DB_FILE" "SELECT COALESCE(MAX(version_number), 0) + 1 FROM ont_snapshots;" 2>/dev/null)

    PREFS_STATE=$(sqlite3 "$DB_FILE" "
    SELECT json_group_array(json_object(
        'dimension_id', dimension_id,
        'value', COALESCE(current_value, default_value),
        'confidence', confidence,
        'sample_count', sample_count
    ))
    FROM ont_preference_dimensions;
    " 2>/dev/null)

    sqlite3 "$DB_FILE" "
    INSERT INTO ont_snapshots (
        snapshot_id, version_number, snapshot_type,
        preferences_state, trigger_reason,
        total_confidence, active_dimensions, learned_signals
    ) VALUES (
        '${SNAPSHOT_ID}',
        ${VERSION},
        'auto',
        '${PREFS_STATE}',
        '每10会话自动快照',
        (SELECT SUM(confidence) FROM ont_preference_dimensions),
        (SELECT COUNT(*) FROM ont_preference_dimensions WHERE confidence > 0),
        (SELECT COALESCE(SUM(sample_count), 0) FROM ont_preference_dimensions)
    );
    " 2>/dev/null

    echo "{\"decision\": \"approve\", \"systemMessage\": \"【本体快照】v${VERSION} 已创建\"}"
    exit 0
fi

echo '{"decision": "approve"}'
