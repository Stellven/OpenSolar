#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Solar Brain Router - Claude Code Hook
# 在用户提交任务时提供大脑推荐
# ═══════════════════════════════════════════════════════════════════════════

BRAIN_ROUTER_DIR="$HOME/.solar/brain-router"
BRAIN_ROUTER_CLI="$BRAIN_ROUTER_DIR/src/cli.py"
BRAIN_ROUTER_DB="$BRAIN_ROUTER_DIR/data/brain_router.db"
SESSION_FILE="/tmp/solar-brain-router-session.json"

# 读取输入
INPUT=$(cat)

# 检查 Brain Router 是否安装
if [[ ! -f "$BRAIN_ROUTER_CLI" ]]; then
    echo '{"continue": true}'
    exit 0
fi

# 获取用户消息
USER_MESSAGE=$(echo "$INPUT" | jq -r '.message // empty' 2>/dev/null)

# 如果消息为空或太短，跳过
if [[ -z "$USER_MESSAGE" ]] || [[ ${#USER_MESSAGE} -lt 10 ]]; then
    echo '{"continue": true}'
    exit 0
fi

# 跳过简单对话
SKIP_PATTERNS=(
    "^[好是的确认OK可以]$"
    "^谢谢"
    "^感谢"
    "^[你您]好"
    "^hi$"
    "^hello$"
)

for pattern in "${SKIP_PATTERNS[@]}"; do
    if echo "$USER_MESSAGE" | grep -qiE "$pattern"; then
        echo '{"continue": true}'
        exit 0
    fi
done

# 调用 Brain Router 获取推荐
ROUTE_RESULT=$(cd "$BRAIN_ROUTER_DIR/src" && python3 cli.py route "$USER_MESSAGE" --json 2>/dev/null)

if [[ $? -ne 0 ]] || [[ -z "$ROUTE_RESULT" ]]; then
    echo '{"continue": true}'
    exit 0
fi

# 解析结果
BRAIN_ID=$(echo "$ROUTE_RESULT" | jq -r '.brain_id // "sonnet"')
METHOD=$(echo "$ROUTE_RESULT" | jq -r '.method // "default"')
CONFIDENCE=$(echo "$ROUTE_RESULT" | jq -r '.confidence // 0.5')
REASON=$(echo "$ROUTE_RESULT" | jq -r '.reason // ""')
EST_COST=$(echo "$ROUTE_RESULT" | jq -r '.expected_cost // 0')

# 获取任务哈希用于后续追踪
TASK_HASH=$(echo "$USER_MESSAGE" | md5sum | cut -c1-16)

# 保存会话信息供 post-hook 使用
cat > "$SESSION_FILE" << EOF
{
  "task_hash": "$TASK_HASH",
  "task_text": $(echo "$USER_MESSAGE" | jq -Rs .),
  "brain_id": "$BRAIN_ID",
  "method": "$METHOD",
  "confidence": $CONFIDENCE,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# 格式化置信度
CONF_PCT=$(echo "$CONFIDENCE" | awk '{printf "%.0f", $1 * 100}')

# 构建系统消息
# 只有在非默认模型且置信度较高时才显示
if [[ "$BRAIN_ID" != "sonnet" ]] && [[ $(echo "$CONFIDENCE > 0.6" | bc -l) -eq 1 ]]; then
    MESSAGE="【Brain Router】推荐: $BRAIN_ID ($CONF_PCT%) | $REASON | Est: \$$EST_COST"

    cat << EOF
{
  "continue": true,
  "systemMessage": "$MESSAGE"
}
EOF
else
    echo '{"continue": true}'
fi
