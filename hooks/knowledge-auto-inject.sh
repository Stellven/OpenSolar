#!/bin/bash
#
# Knowledge Auto Inject Hook
# 在用户输入时自动查询知识库并注入相关内容
#
# 触发: UserPromptSubmit
#

# 获取用户输入
PROMPT="${CLAUDE_PROMPT:-$1}"

if [ -z "$PROMPT" ]; then
    exit 0
fi

# 调用知识自动注入工具
RESULT=$(bun ~/.claude/core/cortex/knowledge-auto.ts "$PROMPT" 2>/dev/null)

# 如果有结果，输出提示
if [ -n "$RESULT" ]; then
    echo ""
    echo "$RESULT"
    echo ""
fi

exit 0
