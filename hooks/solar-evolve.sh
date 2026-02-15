#!/bin/bash
# Solar 自演进 Hook
# 会话结束时提醒进行反思

DB=~/.solar/solar.db

# 获取今日反思次数
TODAY_REFLECTIONS=$(sqlite3 "$DB" "
    SELECT COUNT(*) FROM sys_reflections
    WHERE date(timestamp) = date('now', 'localtime')
" 2>/dev/null || echo "0")

# 获取今日学习数
TODAY_LEARNINGS=$(sqlite3 "$DB" "
    SELECT COUNT(*) FROM evo_memory_semantic
    WHERE source_type = 'learned'
    AND date(created_at) = date('now', 'localtime')
" 2>/dev/null || echo "0")

# 获取上次反思时间
LAST_REFLECTION=$(sqlite3 "$DB" "
    SELECT datetime(timestamp) FROM sys_reflections
    ORDER BY timestamp DESC LIMIT 1
" 2>/dev/null || echo "从未反思")

# 构建提醒消息
if [[ "$TODAY_REFLECTIONS" == "0" ]]; then
    cat << EOF
{
  "decision": "approve",
  "systemMessage": "【自演进提醒】今日尚未进行反思。建议使用 /reflect 对本次会话进行结构化反思。\n\n智慧法则检验:\n□ 知行合一 □ 实事求是 □ 中庸之道 □ 否定之否定 □ 实践检验\n\n今日学习: $TODAY_LEARNINGS 条\n上次反思: $LAST_REFLECTION"
}
EOF
else
    cat << EOF
{
  "decision": "approve",
  "systemMessage": "【自演进状态】今日反思: $TODAY_REFLECTIONS 次 | 今日学习: $TODAY_LEARNINGS 条"
}
EOF
fi
