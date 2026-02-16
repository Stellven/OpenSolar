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
    # 支持两种格式:
    # - v1.x: Big Five, traits, O:/C:/E:/A:/N:
    # - v2.0: SYSTEM CORE, HARD RULES, KNOBS:, ROLE:, OUTPUT_SCHEMA:
    if echo "$TOOL_INPUT" | grep -qiE 'SYSTEM CORE|HARD RULES|KNOBS:|ROLE:|OUTPUT_SCHEMA|Big Five|人格|traits|O:|C:|E:|A:|N:|buildPrompt|personaPrompt|compilePromptV2'; then
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
│  正确做法 (v2.0):                                               │
│  ─────────────────────────────────────────────────────────────  │
│  import { compilePromptV2 } from '~/.claude/core/solar-farm/prompt-runtime';
│  const { system } = compilePromptV2({ role: 'builder' });       │
│  // 或: bun prompt-runtime.ts role builder --level=5            │
│  mcp__brain-router__complete({                                  │
│    model: 'glm-4-plus',                                         │
│    system,  // ← 自动包含 SYSTEM CORE + ROLE PATCH              │
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
