#!/bin/bash
# Solar Memory Hook - 记录工具使用
# 由 PostToolUse hook 调用

TOOL_NAME="$1"
SUCCESS="$2"
DURATION="$3"

# 异步执行，不阻塞主流程
(
  bun ~/.claude/core/memory/memory-hook.ts record "$TOOL_NAME" "$SUCCESS" "$DURATION" 2>/dev/null
) &

exit 0
