#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# SROE Auto Collect Hook
# 在 brain-router MCP 调用后自动触发采集闭环
#
# 触发点: PostToolUse (匹配 mcp__brain-router__complete)
# 功能:
#   1. 记录请求到 sroe_requests
#   2. 记录响应到 sroe_responses
#   3. 自动评估质量
#   4. 贝叶斯更新信念
# ═══════════════════════════════════════════════════════════════════════════

COLLECTOR="$HOME/.claude/core/intent-engine/sroe-auto-collector.ts"
LOG_FILE="/tmp/sroe-collect.log"

# 读取 stdin
INPUT=$(cat)

# 检查是否是 brain-router 调用
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

# 只处理 brain-router 的 complete 调用
if [[ "$TOOL_NAME" != "mcp__brain-router__complete" ]]; then
    exit 0
fi

# 提取参数
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // empty')
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_output // empty')

# 解析 model 和 prompt
MODEL=$(echo "$TOOL_INPUT" | jq -r '.model // "unknown"')
PROMPT=$(echo "$TOOL_INPUT" | jq -r '.prompt // ""' | head -c 5000)

# 响应内容
OUTPUT=$(echo "$TOOL_OUTPUT" | head -c 10000)

# 估算延迟 (从 timestamp 差异，这里简化为固定值)
LATENCY_MS=2000

# 构建采集数据
COLLECT_DATA=$(jq -n \
  --arg model "$MODEL" \
  --arg prompt "$PROMPT" \
  --arg output "$OUTPUT" \
  --argjson latency "$LATENCY_MS" \
  '{model: $model, prompt: $prompt, output: $output, latencyMs: $latency}')

# 调用采集器
if [[ -f "$COLLECTOR" ]]; then
    RESULT=$(echo "$COLLECT_DATA" | bun "$COLLECTOR" collect 2>/dev/null)

    if [[ $? -eq 0 ]]; then
        SCORE=$(echo "$RESULT" | jq -r '.score // "N/A"')
        echo "[SROE] Collected: $MODEL | Score: $SCORE" >> "$LOG_FILE"
    else
        echo "[SROE] Error collecting: $MODEL" >> "$LOG_FILE"
    fi
fi

exit 0
