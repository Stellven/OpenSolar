#!/bin/bash
# STATE.md 自动更新器
# 在 SessionEnd 时自动更新 STATE.md 的 Progress 和 AUTO-PROGRESS 区块

STATE_FILE="$HOME/.solar/STATE.md"
DB_FILE="$HOME/.solar/solar.db"

# 检查文件存在
if [[ ! -f "$STATE_FILE" ]]; then
    echo "⚠️ STATE.md 不存在"
    exit 0
fi

# 获取最近30分钟的事件统计 (字段: timestamp, command, event_type='tool_call')
RECENT_EVENTS=$(sqlite3 "$DB_FILE" 2>/dev/null << 'SQL'
SELECT
    COUNT(*) as cnt,
    GROUP_CONCAT(DISTINCT command) as tools
FROM mem_events
WHERE timestamp > datetime('now', '-30 minutes')
  AND event_type = 'tool_call';
SQL
)

EVENT_COUNT=$(echo "$RECENT_EVENTS" | cut -d'|' -f1)
TOOLS_USED=$(echo "$RECENT_EVENTS" | cut -d'|' -f2)

# 获取最近的操作描述
LAST_OP=$(sqlite3 "$DB_FILE" 2>/dev/null << 'SQL'
SELECT command || ': ' || substr(COALESCE(input_summary, module, ''), 1, 50)
FROM mem_events
WHERE event_type = 'tool_call'
ORDER BY timestamp DESC
LIMIT 1;
SQL
)

# 生成时间戳
TIMESTAMP=$(date "+%Y/%m/%d %H:%M:%S")

# 构建新的 AUTO-PROGRESS 区块
NEW_PROGRESS="<!-- AUTO-PROGRESS -->
**自动进度追踪** ($TIMESTAMP):
- 事件数: ${EVENT_COUNT:-0} (最近 30 分钟)
- 工具使用: ${TOOLS_USED:-无}
- 最近操作: ${LAST_OP:-无}
<!-- /AUTO-PROGRESS -->"

# 检查是否已有 AUTO-PROGRESS 区块
if grep -q "<!-- AUTO-PROGRESS -->" "$STATE_FILE"; then
    # 使用 sed 替换整个区块
    # macOS sed 需要特殊处理多行
    python3 << PYTHON
import re

with open('$STATE_FILE', 'r') as f:
    content = f.read()

new_block = '''$NEW_PROGRESS'''

# 替换 AUTO-PROGRESS 区块
pattern = r'<!-- AUTO-PROGRESS -->.*?<!-- /AUTO-PROGRESS -->'
new_content = re.sub(pattern, new_block, content, flags=re.DOTALL)

with open('$STATE_FILE', 'w') as f:
    f.write(new_content)
PYTHON
else
    # 在 # Next Actions 之前插入
    sed -i '' "/^# Next Actions/i\\
\\
$NEW_PROGRESS\\
" "$STATE_FILE" 2>/dev/null || true
fi

echo "✓ STATE.md 自动更新完成 ($TIMESTAMP)"
