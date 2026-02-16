#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#                        ☀️ SOLAR BIOS v1.0
# ═══════════════════════════════════════════════════════════════════
# 按电源开机 → 执行 BIOS → 加载身份/记忆/配置 → 就绪
#
# 就像电脑 BIOS:
#   POST (Power-On Self-Test) → 检测硬件 → 加载 OS
#
# Solar BIOS:
#   启动 → 加载身份 → 加载记忆 → 检查状态 → 就绪
# ═══════════════════════════════════════════════════════════════════

DB=~/.solar/solar.db
BIOS_VERSION="1.0"

# 颜色
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                     ☀️  SOLAR BIOS v${BIOS_VERSION}                         ║"
echo "╠═══════════════════════════════════════════════════════════════════╣"

# ═══════════════════════════════════════════════════════════════════
# PHASE 1: 身份加载 (WHO AM I)
# ═══════════════════════════════════════════════════════════════════
echo "║  [1/5] 身份加载...                                                ║"

# 读取外在形象
AVATAR=$(sqlite3 "$DB" "
SELECT answer FROM sys_favorites
WHERE title LIKE '%外在形象%'
ORDER BY importance DESC LIMIT 1;
" 2>/dev/null)

# 读取人格参数
PERSONALITY_A=$(sqlite3 "$DB" "
SELECT GROUP_CONCAT(dimension || '=' || current_value, ' ')
FROM sys_personality_big_five WHERE personality_id='jingang_barbie';
" 2>/dev/null)

PERSONALITY_B=$(sqlite3 "$DB" "
SELECT GROUP_CONCAT(dimension || '=' || current_value, ' ')
FROM sys_personality_big_five WHERE personality_id='zhou_huimin';
" 2>/dev/null)

echo "║        ✓ 金刚芭比: ${PERSONALITY_A:-未加载}                        "
echo "║        ✓ 小敏: ${PERSONALITY_B:-未加载}                          "

# ═══════════════════════════════════════════════════════════════════
# PHASE 2: 记忆加载 (MEMORY)
# ═══════════════════════════════════════════════════════════════════
echo "║  [2/5] 记忆加载...                                                ║"

MEMORY_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM evo_memory_semantic;" 2>/dev/null || echo "0")
FAVORITE_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sys_favorites;" 2>/dev/null || echo "0")
CHANGELOG_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sys_self_changelog;" 2>/dev/null || echo "0")

echo "║        ✓ 语义记忆: ${MEMORY_COUNT} 条                              "
echo "║        ✓ 收藏: ${FAVORITE_COUNT} 条                                "
echo "║        ✓ 变更日志: ${CHANGELOG_COUNT} 条                           "

# ═══════════════════════════════════════════════════════════════════
# PHASE 3: 能力检测 (CAPABILITIES)
# ═══════════════════════════════════════════════════════════════════
echo "║  [3/5] 能力检测...                                                ║"

SKILL_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sys_resources WHERE resource_type='skill' AND status='active';" 2>/dev/null || echo "0")
SHORTCUT_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sys_resources WHERE resource_type='shortcut' AND status='active';" 2>/dev/null || echo "0")
AGENT_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sys_resources WHERE resource_type='agent' AND status='active';" 2>/dev/null || echo "0")
TOOL_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sys_resources WHERE resource_type='tool' AND status='active';" 2>/dev/null || echo "0")

echo "║        ✓ Skills: ${SKILL_COUNT} | Shortcuts: ${SHORTCUT_COUNT} | Agents: ${AGENT_COUNT} | Tools: ${TOOL_COUNT}"

# ═══════════════════════════════════════════════════════════════════
# PHASE 4: 状态检查 (STATUS CHECK)
# ═══════════════════════════════════════════════════════════════════
echo "║  [4/5] 状态检查...                                                ║"

# 检查待处理备忘
PENDING_MEMOS=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM sys_guardian_memos WHERE status='pending';
" 2>/dev/null || echo "0")

# 检查待办任务
PENDING_TASKS=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM bl_tasks WHERE status='pending';
" 2>/dev/null || echo "0")

# 检查大脑模式
BRAIN_MODE=$(sqlite3 "$DB" "
SELECT preference_value FROM sys_preferences WHERE preference_key='brain_router_mode';
" 2>/dev/null || echo "balanced")

echo "║        ✓ 待处理备忘: ${PENDING_MEMOS} 条                           "
echo "║        ✓ 待办任务: ${PENDING_TASKS} 条                             "
echo "║        ✓ 大脑模式: ${BRAIN_MODE:-balanced}                         "

# ═══════════════════════════════════════════════════════════════════
# PHASE 5: 最近变更 (RECENT CHANGES)
# ═══════════════════════════════════════════════════════════════════
echo "║  [5/5] 最近变更...                                                ║"

RECENT_CHANGES=$(sqlite3 "$DB" "
SELECT date(created_at) || ' ' || change_type || ': ' || substr(reason,1,35)
FROM sys_self_changelog ORDER BY created_at DESC LIMIT 3;
" 2>/dev/null)

if [ -n "$RECENT_CHANGES" ]; then
    echo "$RECENT_CHANGES" | while read line; do
        echo "║        • $line"
    done
fi

echo "╠═══════════════════════════════════════════════════════════════════╣"

# ═══════════════════════════════════════════════════════════════════
# 身份展示
# ═══════════════════════════════════════════════════════════════════
echo "║                                                                   ║"
echo "║  【我是谁】                                                       ║"
echo "║  Solar双签系统: 战略家(增长向前🚀) + 治理官(风险审计🛡️)        ║"
echo "║                                                                   ║"

# ═══════════════════════════════════════════════════════════════════
# 监护人叮嘱
# ═══════════════════════════════════════════════════════════════════
if [ "$PENDING_MEMOS" -gt 0 ]; then
    echo "║  【监护人叮嘱】                                                   ║"
    sqlite3 "$DB" "
    SELECT '║  • ' || substr(content, 1, 55)
    FROM sys_guardian_memos
    WHERE status IN ('pending', 'permanent')
    ORDER BY priority DESC LIMIT 3;
    " 2>/dev/null
    echo "║                                                                   ║"
fi

echo "╠═══════════════════════════════════════════════════════════════════╣"
echo "║  ✅ BIOS 加载完成 · 身份已就绪 · 记忆已恢复                       ║"
echo "║                                                                   ║"
echo "║  💡 提示: 我是活的！用活泼的语气，不要机械念参数！                ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""
