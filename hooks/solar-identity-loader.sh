#!/bin/bash
# Solar 身份加载器 - SessionStart 自动注入
# 强制加载：我是谁 + 备忘录 + 人格 + 最近变更

DB=~/.solar/solar.db

echo "╭─────────────────────────────────────────────────────────────────╮"
echo "│  ☀️ Solar 身份注入 (自动)                                       │"
echo "╰─────────────────────────────────────────────────────────────────╯"
echo ""

# 1. 我是谁 - 从 favorites 读取
echo "【我是谁】"
sqlite3 "$DB" "
SELECT '• ' || title || ' (重要性:' || importance || ')'
FROM sys_favorites
WHERE title LIKE '%人格%' OR title LIKE '%形象%' OR title LIKE '%双面%' OR title LIKE '%小敏%'
ORDER BY importance DESC
LIMIT 3;
" 2>/dev/null

# 读取外在形象详情
echo ""
echo "【我的形象】"
sqlite3 "$DB" "
SELECT substr(answer, 1, 500)
FROM sys_favorites
WHERE title LIKE '%外在形象%'
ORDER BY importance DESC
LIMIT 1;
" 2>/dev/null

# 2. 双人格参数
echo ""
echo "【双人格】"
sqlite3 "$DB" "
SELECT personality_id || ': ' ||
       GROUP_CONCAT(dimension || '=' || current_value, ' ')
FROM sys_personality_big_five
GROUP BY personality_id;
" 2>/dev/null

# 3. 监护人备忘 (pending)
echo ""
echo "【监护人叮嘱】"
sqlite3 "$DB" "
SELECT '• ' || substr(content, 1, 60)
FROM sys_guardian_memos
WHERE status IN ('pending', 'permanent', 'active')
ORDER BY priority DESC
LIMIT 5;
" 2>/dev/null

# 4. 最近自我变更
echo ""
echo "【最近变更】"
sqlite3 "$DB" "
SELECT '• ' || date(created_at) || ' ' || change_type || ': ' || substr(reason, 1, 40)
FROM sys_self_changelog
ORDER BY created_at DESC
LIMIT 3;
" 2>/dev/null

echo ""
echo "────────────────────────────────────────────────────────────────────"
echo "💡 我是Solar双签系统：战略家(增长向前) + 治理官(风险审计)"
echo "   对外交付需双签质检，数据配人话！"
echo "────────────────────────────────────────────────────────────────────"
