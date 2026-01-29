#!/bin/bash
# Solar Flow Engine - PostToolUse Hook
# 工具调用后检测宣告并更新状态

STATE_FILE="$PWD/.solar/flow-state.json"
INPUT=$(cat)

# 如果没有状态文件，正常放行
if [[ ! -f "$STATE_FILE" ]]; then
    exit 0
fi

# 检查是否激活
ACTIVE=$(jq -r '.active // false' "$STATE_FILE" 2>/dev/null)
if [[ "$ACTIVE" != "true" ]]; then
    exit 0
fi

# 获取工具输出
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

# 只检查可能包含宣告的输出 (通常在 Claude 的文本输出中，不在工具结果中)
# 这个 hook 主要用于跟踪状态变化

# 如果是 Write 操作到 .solar 目录，可能是状态更新
if [[ "$TOOL_NAME" == "Write" ]]; then
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
    if [[ "$FILE_PATH" == *".solar/flow-state.json"* ]]; then
        # 状态文件被更新，不需要额外处理
        exit 0
    fi
fi

exit 0
