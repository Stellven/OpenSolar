#!/bin/bash
#
# Persona Enforcer Hook
# 强制执行人格注入 - 在 mcp__brain-router__complete 调用前检查
#
# 触发: PreToolUse 检测到 mcp__brain-router__complete
#
# 如果没有注入人格参数，发出警告并记录违规

LOG_FILE="/tmp/persona-enforcer.log"
VIOLATION_FILE="/tmp/persona-violations.log"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 获取工具调用信息
TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

log() {
    echo "[$TIMESTAMP] $1" >> "$LOG_FILE"
}

# 检查是否是 brain-router 调用
if [[ "$TOOL_NAME" == *"brain-router"* ]] || [[ "$TOOL_NAME" == *"complete"* ]]; then
    log "Detected brain-router call"

    # 检查是否有人格参数
    # 正确的调用应该包含 system 参数，且 system 中包含 Big Five 或人格关键词
    if echo "$TOOL_INPUT" | grep -qiE 'Big Five|人格|traits|O:|C:|E:|A:|N:|buildPrompt|personaPrompt'; then
        log "✅ PASS: Persona detected in system prompt"
    else
        # 违规：没有注入人格
        log "❌ FAIL: No persona detected"

        echo "[$TIMESTAMP] VIOLATION: brain-router called without persona" >> "$VIOLATION_FILE"

        # 输出警告（这会显示给用户）
        cat << 'EOF'

┌─────────────────────────────────────────────────────────────────┐
│  🚨 Persona Enforcement Violation                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  检测到 brain-router 调用，但没有注入人格参数！                 │
│                                                                 │
│  这违反了 Solar 铁律: 调牛马必须带人格                          │
│                                                                 │
│  正确做法:                                                      │
│  ─────────────────────────────────────────────────────────────  │
│  import { buildPrompt } from '~/.claude/core/solar-farm/persona-router';
│  const personaPrompt = buildPrompt('builder'); // 或其他角色    │
│  mcp__brain-router__complete({                                  │
│    model: 'glm-4-plus',                                         │
│    system: personaPrompt,  // ← 必须注入！                      │
│    prompt: '...'                                                │
│  });                                                            │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  记录: 此违规已被记录到 /tmp/persona-violations.log            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

EOF
    fi
fi

exit 0
