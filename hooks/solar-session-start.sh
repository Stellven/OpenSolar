#!/bin/bash
# Solar Flow Engine - SessionStart Hook
# 会话开始时加载流程状态

STATE_FILE="$PWD/.solar/flow-state.json"

# 如果没有状态文件，正常放行
if [[ ! -f "$STATE_FILE" ]]; then
    echo '{"continue": true}'
    exit 0
fi

# 检查是否激活
ACTIVE=$(jq -r '.active // false' "$STATE_FILE" 2>/dev/null)
if [[ "$ACTIVE" != "true" ]]; then
    echo '{"continue": true}'
    exit 0
fi

# 读取状态
PHASE=$(jq -r '.flow.current_phase // "unknown"' "$STATE_FILE")
AGENT=$(jq -r '.flow.current_agent // "unknown"' "$STATE_FILE")
TASK=$(jq -r '.task.description // "unknown"' "$STATE_FILE")

# 获取 Agent emoji
get_emoji() {
    case "$1" in
        "Researcher") echo "🔬" ;;
        "Architect") echo "🏗️" ;;
        "Coder") echo "💻" ;;
        "Tester") echo "🧪" ;;
        "Reviewer") echo "👁️" ;;
        "Docs") echo "📖" ;;
        "Ops") echo "⚙️" ;;
        "PM") echo "📊" ;;
        *) echo "🤖" ;;
    esac
}

EMOJI=$(get_emoji "$AGENT")

# 构建恢复消息
MESSAGE="【Solar 状态恢复】\\n"
MESSAGE+="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
MESSAGE+="任务: $TASK\\n"
MESSAGE+="阶段: $PHASE | Agent: $EMOJI $AGENT\\n"
MESSAGE+="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
MESSAGE+="请继续执行。如需切换阶段，使用 /phase next"

cat << EOF
{
  "continue": true,
  "systemMessage": "$MESSAGE"
}
EOF
