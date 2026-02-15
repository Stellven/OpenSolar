#!/bin/bash
# Solar AI OS - Token Alert Hook
# 监控 Token 使用，超过阈值时发出警告

# 配置
TOKEN_THRESHOLD=${SOLAR_TOKEN_THRESHOLD:-50000}
TOKEN_CRITICAL=${SOLAR_TOKEN_CRITICAL:-80000}
ALERT_FILE="$HOME/.solar/monitor/token-alerts.log"
USAGE_FILE="$HOME/.solar/monitor/current-usage.json"

# 确保目录存在
mkdir -p "$(dirname "$ALERT_FILE")"
mkdir -p "$(dirname "$USAGE_FILE")"

# 读取输入
INPUT=$(cat)

# 尝试从输入中提取 token 信息
# Claude Code 的响应中可能包含 usage 信息
TOKENS_USED=$(echo "$INPUT" | jq -r '.response.usage.total_tokens // .usage.total_tokens // empty' 2>/dev/null)
INPUT_TOKENS=$(echo "$INPUT" | jq -r '.response.usage.input_tokens // .usage.input_tokens // 0' 2>/dev/null)
OUTPUT_TOKENS=$(echo "$INPUT" | jq -r '.response.usage.output_tokens // .usage.output_tokens // 0' 2>/dev/null)

# 如果无法提取，退出
if [[ -z "$TOKENS_USED" ]] || [[ "$TOKENS_USED" == "null" ]]; then
    exit 0
fi

# 读取当前累计使用量
if [[ -f "$USAGE_FILE" ]]; then
    CURRENT_TOTAL=$(jq -r '.totalTokens // 0' "$USAGE_FILE" 2>/dev/null)
    SESSION_START=$(jq -r '.sessionStart // 0' "$USAGE_FILE" 2>/dev/null)
else
    CURRENT_TOTAL=0
    SESSION_START=$(date +%s)
fi

# 更新累计
NEW_TOTAL=$((CURRENT_TOTAL + TOKENS_USED))

# 保存更新后的使用量
cat > "$USAGE_FILE" << EOF
{
  "sessionStart": $SESSION_START,
  "totalTokens": $NEW_TOTAL,
  "lastUpdate": $(date +%s),
  "lastInput": $INPUT_TOKENS,
  "lastOutput": $OUTPUT_TOKENS
}
EOF

# 检查阈值
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

if [[ $NEW_TOTAL -ge $TOKEN_CRITICAL ]]; then
    # 临界警告
    ALERT_MSG="🔴 [CRITICAL] Token 使用已达临界值: $NEW_TOTAL / $TOKEN_CRITICAL"
    echo "$TIMESTAMP $ALERT_MSG" >> "$ALERT_FILE"

    # 输出到 stderr 以便显示
    echo "" >&2
    echo "╔════════════════════════════════════════════════════════════════╗" >&2
    echo "║  🔴 TOKEN CRITICAL ALERT                                       ║" >&2
    echo "╠════════════════════════════════════════════════════════════════╣" >&2
    echo "║  当前使用: $(printf '%,d' $NEW_TOTAL) tokens                              ║" >&2
    echo "║  临界阈值: $(printf '%,d' $TOKEN_CRITICAL) tokens                              ║" >&2
    echo "║                                                                ║" >&2
    echo "║  建议:                                                         ║" >&2
    echo "║  1. 保存当前工作 (/save)                                       ║" >&2
    echo "║  2. 考虑结束会话                                               ║" >&2
    echo "║  3. 或切换到 Haiku 模型降低消耗                                ║" >&2
    echo "╚════════════════════════════════════════════════════════════════╝" >&2
    echo "" >&2

elif [[ $NEW_TOTAL -ge $TOKEN_THRESHOLD ]]; then
    # 普通警告 (只在首次超过阈值时提醒)
    LAST_ALERT=$(jq -r '.lastThresholdAlert // 0' "$USAGE_FILE" 2>/dev/null)

    if [[ $LAST_ALERT -lt $TOKEN_THRESHOLD ]]; then
        ALERT_MSG="🟡 [WARNING] Token 使用超过阈值: $NEW_TOTAL / $TOKEN_THRESHOLD"
        echo "$TIMESTAMP $ALERT_MSG" >> "$ALERT_FILE"

        # 更新上次警告值
        jq ".lastThresholdAlert = $NEW_TOTAL" "$USAGE_FILE" > "${USAGE_FILE}.tmp" && mv "${USAGE_FILE}.tmp" "$USAGE_FILE"

        echo "" >&2
        echo "┌─ 🟡 Token 使用提醒 ─────────────────────────────────────────┐" >&2
        echo "│ 当前: $(printf '%,d' $NEW_TOTAL) / $(printf '%,d' $TOKEN_THRESHOLD) tokens ($(( NEW_TOTAL * 100 / TOKEN_THRESHOLD ))%)               │" >&2
        echo "│ 提示: 使用 /stats 查看详细统计                              │" >&2
        echo "└─────────────────────────────────────────────────────────────┘" >&2
        echo "" >&2
    fi
fi

# 每 10000 tokens 输出一次进度 (可选)
if [[ $((NEW_TOTAL % 10000)) -lt $TOKENS_USED ]] && [[ $NEW_TOTAL -lt $TOKEN_THRESHOLD ]]; then
    PROGRESS=$((NEW_TOTAL * 100 / TOKEN_THRESHOLD))
    BAR_WIDTH=20
    FILLED=$((PROGRESS * BAR_WIDTH / 100))
    EMPTY=$((BAR_WIDTH - FILLED))
    BAR=$(printf '█%.0s' $(seq 1 $FILLED 2>/dev/null))$(printf '░%.0s' $(seq 1 $EMPTY 2>/dev/null))

    echo "[Token] [$BAR] ${PROGRESS}% ($(printf '%,d' $NEW_TOTAL) tokens)" >&2
fi

exit 0
