#!/bin/bash
# executor-auditor.sh
# AssistantResponse hook: 检查 Claude 回复是否以 <Executor> 标签开头
#
# Claude Code hook 机制:
# - CLAUDE_RESPONSE 环境变量或 stdin 包含 Claude 的回复
# - 此 hook 在回复后运行，用于审计记录

# 配置
SOLAR_DIR="$HOME/.solar"
VIOLATIONS_LOG="$SOLAR_DIR/executor-violations.log"
STATS_FILE="$SOLAR_DIR/executor-stats.json"

# 确保目录存在
mkdir -p "$SOLAR_DIR"

# 读取回复内容 (从 stdin 或环境变量)
if [ -n "$CLAUDE_RESPONSE" ]; then
    RESPONSE="$CLAUDE_RESPONSE"
else
    RESPONSE=$(cat)
fi

# 如果回复为空，跳过检查
[ -z "$RESPONSE" ] && exit 0

# 初始化统计文件
if [ ! -f "$STATS_FILE" ]; then
    echo '{"total": 0, "violations": 0, "compliance_rate": "N/A"}' > "$STATS_FILE"
fi

# 读取当前统计 (使用 jq 如果有，否则用 grep)
if command -v jq &> /dev/null; then
    TOTAL=$(jq -r '.total // 0' "$STATS_FILE")
    VIOLATIONS=$(jq -r '.violations // 0' "$STATS_FILE")
else
    TOTAL=$(grep -o '"total": *[0-9]*' "$STATS_FILE" | grep -o '[0-9]*' || echo 0)
    VIOLATIONS=$(grep -o '"violations": *[0-9]*' "$STATS_FILE" | grep -o '[0-9]*' || echo 0)
fi

# 增加总次数
TOTAL=$((TOTAL + 1))

# 获取回复的第一行（跳过空行）
FIRST_LINE=$(echo "$RESPONSE" | grep -v '^$' | head -1)

# 检查是否以 <Executor> 开头
if echo "$FIRST_LINE" | grep -q '^<Executor>'; then
    # 合规 ✓
    COMPLIANT=true
else
    # 违规 ✗
    COMPLIANT=false
    VIOLATIONS=$((VIOLATIONS + 1))

    # 记录违规
    TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
    {
        echo "========================================"
        echo "[$TIMESTAMP] 违规 #$VIOLATIONS (总交互 #$TOTAL)"
        echo "首行内容: $FIRST_LINE"
        echo "----------------------------------------"
        echo "$RESPONSE" | head -20
        echo "..."
        echo ""
    } >> "$VIOLATIONS_LOG"
fi

# 计算合规率
if [ "$TOTAL" -gt 0 ]; then
    COMPLIANT_COUNT=$((TOTAL - VIOLATIONS))
    RATE=$(awk "BEGIN {printf \"%.1f\", ($COMPLIANT_COUNT / $TOTAL) * 100}")
else
    RATE="N/A"
fi

# 更新统计文件
cat > "$STATS_FILE" << EOF
{
  "total": $TOTAL,
  "violations": $VIOLATIONS,
  "compliant": $((TOTAL - VIOLATIONS)),
  "compliance_rate": "${RATE}%",
  "last_check": "$(date '+%Y-%m-%d %H:%M:%S')",
  "last_result": "$COMPLIANT"
}
EOF

# 如果违规，输出警告 (会显示给用户)
if [ "$COMPLIANT" = "false" ]; then
    echo ""
    echo "⚠️ [Executor Auditor] 检测到违规: 回复未以 <Executor> 标签开头"
    echo "   合规率: ${RATE}% ($((TOTAL - VIOLATIONS))/$TOTAL)"
fi

exit 0
