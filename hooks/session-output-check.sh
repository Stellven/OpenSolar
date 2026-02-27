#!/bin/bash
# session-output-check.sh
# SessionEnd Hook - 检查本会话是否有知识固化

SESSION_START_TIME=$(date -u +"%Y-%m-%d %H:%M:%S" -v-1H 2>/dev/null || date -u +"%Y-%m-%d %H:%M:%S" -d "1 hour ago")

# 查询本会话存储的知识条目数
STORAGE_COUNT=$(sqlite3 ~/.solar/solar.db "
SELECT COUNT(*) FROM sys_favorites
WHERE created_at >= '$SESSION_START_TIME';
" 2>/dev/null || echo "0")

if [ "$STORAGE_COUNT" -eq 0 ]; then
    echo ""
    echo "⚠️ [SessionEnd 检查] 本会话没有知识固化！"
    echo "   铁律提醒: 每次分析/总结/设计后必须存入知识库"
    echo "   如果本会话有有价值输出，请手动补充存储"
else
    echo ""
    echo "✅ [SessionEnd 检查] 本会话已固化 $STORAGE_COUNT 条知识"
fi
