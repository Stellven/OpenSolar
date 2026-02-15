#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Solar Brain Router - Data Collection Hook (PostToolUse)
# 收集任务执行结果用于学习
# ═══════════════════════════════════════════════════════════════════════════

BRAIN_ROUTER_DIR="$HOME/.solar/brain-router"
SESSION_FILE="/tmp/solar-brain-router-session.json"
OUTCOME_LOG="/tmp/solar-brain-router-outcomes.log"

# 读取输入
INPUT=$(cat)

# 检查会话文件是否存在
if [[ ! -f "$SESSION_FILE" ]]; then
    exit 0
fi

# 读取会话信息
SESSION=$(cat "$SESSION_FILE")
TASK_HASH=$(echo "$SESSION" | jq -r '.task_hash // empty')
BRAIN_ID=$(echo "$SESSION" | jq -r '.brain_id // "sonnet"')

if [[ -z "$TASK_HASH" ]]; then
    exit 0
fi

# 获取工具信息
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_output // empty' | head -c 2000)

# 分析工具输出以检测成功/失败信号
detect_outcome() {
    local output="$1"
    local outcome="unknown"
    local signals=""

    # 成功信号
    if echo "$output" | grep -qiE "(test.*pass|passed|success|完成|已完成|Done|✓)"; then
        outcome="success"
        signals="test_pass"
    elif echo "$output" | grep -qiE "(build.*success|compiled|构建成功)"; then
        outcome="success"
        signals="build_success"
    elif echo "$output" | grep -qiE "(\d+(\.\d+)?[xX].*speedup|性能.*提升|加速)"; then
        outcome="success"
        signals="performance_gain"
    fi

    # 失败信号
    if echo "$output" | grep -qiE "(error|failed|failure|错误|失败|exception|crash)"; then
        outcome="failure"
        signals="error_detected"
    elif echo "$output" | grep -qiE "(test.*fail|FAILED|✗)"; then
        outcome="failure"
        signals="test_fail"
    fi

    echo "$outcome|$signals"
}

# 检测结果
DETECTION=$(detect_outcome "$TOOL_OUTPUT")
OUTCOME=$(echo "$DETECTION" | cut -d'|' -f1)
SIGNALS=$(echo "$DETECTION" | cut -d'|' -f2)

# 只有检测到明确信号时才记录
if [[ "$OUTCOME" != "unknown" ]]; then
    # 追加到日志
    cat >> "$OUTCOME_LOG" << EOF
{"task_hash":"$TASK_HASH","brain_id":"$BRAIN_ID","tool":"$TOOL_NAME","outcome":"$OUTCOME","signals":"$SIGNALS","timestamp":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF
fi

exit 0
