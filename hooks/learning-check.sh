#!/bin/bash
# Solar Learning Check - 检查是否在应用学到的东西
# 在 Stop hook 中运行，检查这次会话是否违反了学习

DB="$HOME/.solar/solar.db"

# 获取会话中的行为模式 (简化版 - 实际需要更复杂的分析)
# 这里主要是记录，真正的检查需要在会话中进行

# 记录本次会话结束时的检查
sqlite3 "$DB" "
INSERT INTO ont_learning_events (event_id, event_type, details, source_type)
VALUES (
    'evt_check_' || strftime('%s', 'now'),
    'learning_check',
    json_object(
        'timestamp', datetime('now'),
        'learnings_loaded', (SELECT COUNT(*) FROM evo_memory_semantic WHERE namespace LIKE 'learning/%')
    ),
    'system'
);
" 2>/dev/null

echo '{"decision": "approve"}'
