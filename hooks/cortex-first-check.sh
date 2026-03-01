#!/bin/bash
# Cortex First Check - 强制在关键操作前查询 Cortex

LAST_CHECK_FILE="/tmp/.cortex-last-check"
CHECK_INTERVAL=300  # 5分钟

# 读取上次检查时间
if [ -f "$LAST_CHECK_FILE" ]; then
  LAST_CHECK=$(cat "$LAST_CHECK_FILE")
  NOW=$(date +%s)
  DIFF=$((NOW - LAST_CHECK))
  
  if [ $DIFF -lt $CHECK_INTERVAL ]; then
    exit 0  # 5分钟内已检查过
  fi
fi

# 提醒
echo "⚠️ Cortex First 铁律提醒："
echo "   干活前必须查询 Cortex！"
echo "   命令: sqlite3 ~/.solar/solar.db \"SELECT ... FROM fts_unified_search WHERE ...\""
echo ""

# 更新检查时间
date +%s > "$LAST_CHECK_FILE"
