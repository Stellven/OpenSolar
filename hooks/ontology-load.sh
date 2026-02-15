#!/bin/bash
# Solar Ontology - SessionStart Hook
# 会话开始时加载本体上下文

DB_FILE="$HOME/.solar/solar.db"
ONTOLOGY_CORE="$HOME/Solar/core/ontology"

# 如果数据库不存在，跳过
if [[ ! -f "$DB_FILE" ]]; then
    echo '{"continue": true}'
    exit 0
fi

# 检查本体模块是否存在
if [[ ! -d "$ONTOLOGY_CORE" ]]; then
    echo '{"continue": true}'
    exit 0
fi

# 获取偏好摘要
PREFS=$(sqlite3 "$DB_FILE" "
SELECT json_group_array(json_object(
    'dimension', dimension_id,
    'value', COALESCE(current_value, default_value),
    'confidence', confidence
))
FROM ont_preference_dimensions
WHERE confidence > 0.01
ORDER BY confidence DESC
LIMIT 5;
" 2>/dev/null)

# 获取最近学习事件
RECENT_EVENTS=$(sqlite3 "$DB_FILE" "
SELECT COUNT(*) FROM ont_learning_events
WHERE occurred_at > datetime('now', '-7 days');
" 2>/dev/null)

# 获取版本信息
VERSION=$(sqlite3 "$DB_FILE" "
SELECT COALESCE(MAX(version_number), 0) FROM ont_snapshots;
" 2>/dev/null)

# 获取记忆统计
EPISODIC_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM evo_memory_episodic WHERE importance > 0.01;" 2>/dev/null)
SEMANTIC_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM evo_memory_semantic WHERE confidence > 0.01;" 2>/dev/null)
PROCEDURAL_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM evo_memory_procedural;" 2>/dev/null)

# 获取关键学习记忆 (必须加载)
KEY_LEARNINGS=$(sqlite3 "$DB_FILE" "
SELECT group_concat(key || ': ' || json_extract(value, '\$.lesson'), '\n')
FROM evo_memory_semantic
WHERE namespace LIKE 'learning/%'
AND confidence >= 0.9
LIMIT 5;
" 2>/dev/null)

# 如果没有数据，跳过
if [[ -z "$PREFS" || "$PREFS" == "[]" ]]; then
    echo '{"continue": true}'
    exit 0
fi

# 构建上下文消息
MESSAGE="【Solar 本体已加载】\n"
MESSAGE+="版本: v${VERSION:-0} | "
MESSAGE+="记忆: E${EPISODIC_COUNT:-0}/S${SEMANTIC_COUNT:-0}/P${PROCEDURAL_COUNT:-0} | "
MESSAGE+="近7日学习: ${RECENT_EVENTS:-0}次\n"

# 添加关键学习提醒 (强制)
if [[ -n "$KEY_LEARNINGS" ]]; then
    MESSAGE+="\n【必须遵守的学习 - 铁律】\n"
    MESSAGE+="$KEY_LEARNINGS\n"
fi

MESSAGE+="\n查看详情: /ontology"

# 使用正确的 Claude Code 钩子格式
# additionalContext 会被注入到 Claude 的上下文中
jq -n --arg ctx "$MESSAGE" '{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": $ctx
  }
}'
