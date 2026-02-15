#!/bin/bash
# observation-compress-hook.sh
# PostToolUse hook: 压缩工具输出并存储为语义记忆
#
# Claude Code PostToolUse hook 机制:
# - TOOL_NAME: 工具名称
# - TOOL_RESULT: 工具执行结果 (通过 stdin 或环境变量)
# - 此 hook 在工具执行后运行

# 跳过这些工具 (读取类工具不需要压缩)
SKIP_TOOLS=("Read" "Glob" "Grep" "List" "TodoWrite" "AskUserQuestion")

# 检查是否在跳过列表中
for skip in "${SKIP_TOOLS[@]}"; do
    if [[ "$TOOL_NAME" == "$skip" ]]; then
        exit 0
    fi
done

# 获取工具结果
if [ -n "$TOOL_RESULT" ]; then
    RESULT="$TOOL_RESULT"
else
    RESULT=$(cat)
fi

# 检查结果长度 (只压缩超过 500 字符的输出)
RESULT_LEN=${#RESULT}
if [ "$RESULT_LEN" -lt 500 ]; then
    exit 0
fi

# 构造 JSON 输入
JSON_INPUT=$(jq -n \
    --arg tool_name "$TOOL_NAME" \
    --arg tool_args "${TOOL_ARGS:-{}}" \
    --arg tool_result "$RESULT" \
    '{tool_name: $tool_name, tool_args: ($tool_args | fromjson? // {}), tool_result: $tool_result}')

# 调用压缩器 (后台执行，不阻塞主流程)
echo "$JSON_INPUT" | bun ~/.claude/core/observation-compressor/index.ts 2>/dev/null &

exit 0
