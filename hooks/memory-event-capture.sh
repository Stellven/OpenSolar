#!/bin/bash
# Memory Event Capture Hook - Layer 1: Event Sourcing
# 功能: 捕获工具调用并写入 mem_events 表
# 触发: PostToolUse (通过 post-tool-dispatcher.sh)

set -e

# 从 stdin 读取 JSON 数据
INPUT=$(cat)

# 解析必要字段
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // .tool // "unknown"')
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // .input // "{}" | tostring' | head -c 500)
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_result // .output // "" | tostring' | head -c 1000)
SUCCESS=$(echo "$INPUT" | jq -r 'if .error then "false" else "true" end')

# 检测 stderr (如果有)
STDERR=$(echo "$INPUT" | jq -r '.stderr // ""' | head -c 500)

# 获取会话 ID (如果有)
SESSION_ID="${CLAUDE_SESSION_ID:-}"

# 获取当前任务 (从 STATE.md 读取，如果存在)
TASK_ID=""
if [ -f "$HOME/.claude/STATE.md" ]; then
    TASK_ID=$(grep -m1 "^# Mission" -A1 "$HOME/.claude/STATE.md" 2>/dev/null | tail -1 | head -c 100 || echo "")
fi

# 调用 EventCollector 记录事件
bun "$HOME/.claude/core/memory-service/event-collector.ts" record \
    --type tool_call \
    --command "$TOOL_NAME" \
    --input "$TOOL_INPUT" \
    --output "$TOOL_OUTPUT" \
    --stderr "$STDERR" \
    --success "$SUCCESS" \
    --session "$SESSION_ID" \
    --task "$TASK_ID" \
    2>/dev/null || true

exit 0
