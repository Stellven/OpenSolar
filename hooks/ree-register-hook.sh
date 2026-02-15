#!/bin/bash
# REE Register Hook - 检测代码生成并提醒注册到 REE
# 位置: PostToolUse:Write
# 目的: 生成代码文件后，提醒/自动注册到 REE 缓存

set -euo pipefail

# 获取写入的文件路径
FILE_PATH="${CLAUDE_FILE_PATH:-}"
TOOL_OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"

# 判断是否是代码文件
is_code_file() {
  local path="$1"
  echo "$path" | grep -qE "\.(ts|js|py|sh|bun)$" && return 0
  return 1
}

# 判断是否是临时/测试文件
is_temp_file() {
  local path="$1"
  echo "$path" | grep -qiE "(test|tmp|temp|debug|scratch)" && return 0
  return 1
}

# 如果不是代码文件，或是临时文件，直接放行
if ! is_code_file "$FILE_PATH" || is_temp_file "$FILE_PATH"; then
  exit 0
fi

# 检查文件是否已在 REE 中注册
ALREADY_REGISTERED=$(sqlite3 ~/.solar/solar.db "
  SELECT COUNT(*) FROM sys_scripts
  WHERE file_path = '$FILE_PATH' AND status = 'active'
" 2>/dev/null || echo "0")

if [ "$ALREADY_REGISTERED" -gt 0 ]; then
  # 已注册，不提醒
  exit 0
fi

# 检查文件大小（只对有意义的代码提醒）
if [ -f "$FILE_PATH" ]; then
  FILE_SIZE=$(wc -c < "$FILE_PATH" | tr -d ' ')
  if [ "$FILE_SIZE" -lt 200 ]; then
    # 太小的文件不值得缓存
    exit 0
  fi
fi

# 输出注册提醒
cat << EOF

┌─────────────────────────────────────────────────────────────────┐
│  📦 REE 注册提醒                                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  检测到新代码文件:                                              │
│  $FILE_PATH
│                                                                 │
│  此文件尚未注册到 REE 缓存。                                    │
│                                                                 │
│  如果这是一个可复用的功能，请执行:                              │
│                                                                 │
│  bun ~/.claude/core/ree/code-cache.ts register \\               │
│    --name "功能名称" \\                                         │
│    --description "功能描述" \\                                  │
│    --keywords "关键词1,关键词2" \\                              │
│    --path "$FILE_PATH"
│                                                                 │
│  💡 注册后下次相同需求可直接复用                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

EOF

# 记录到数据库（用于后续分析未注册率）
sqlite3 ~/.solar/solar.db "
  INSERT INTO sys_ree_unregistered (file_path, file_size, created_at)
  VALUES ('$FILE_PATH', ${FILE_SIZE:-0}, datetime('now'))
" 2>/dev/null || true

exit 0
