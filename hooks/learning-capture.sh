#!/bin/bash
# Solar Learning Capture - UserPromptSubmit Hook
# 从用户输入中提取学习信号

INPUT=$(cat)
USER_MESSAGE=$(echo "$INPUT" | jq -r '.user_message // empty' 2>/dev/null)

# 如果没有用户消息，放行
if [[ -z "$USER_MESSAGE" || "$USER_MESSAGE" == "null" ]]; then
    exit 0
fi

# 跳过太短的消息（可能是简单命令）
if [[ ${#USER_MESSAGE} -lt 5 ]]; then
    exit 0
fi

# 异步处理，不阻塞用户输入
(
    bun ~/.claude/core/memory/learning-extractor.ts process "$USER_MESSAGE" >/dev/null 2>&1
) &

exit 0
