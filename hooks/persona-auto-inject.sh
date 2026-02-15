#!/bin/bash
#
# Persona Auto-Inject Hook
# 在调用 brain-router 前自动注入人格旋钮
#
# 触发: PreToolUse 检测到 mcp__brain-router__complete
#

# 日志文件
LOG_FILE="/tmp/persona-inject.log"

# 获取当前时间和prompt摘要
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
PROMPT_SUMMARY=$(echo "$CLAUDE_PROMPT" | head -c 100 | tr '\n' ' ')

# 检测任务类型并推荐人格
detect_persona() {
    local prompt="$1"

    # 学术研究关键词
    if echo "$prompt" | grep -qiE '论文|研究|文献|学术|分析|调查'; then
        echo "research:critic"
        return
    fi

    # 方案设计关键词
    if echo "$prompt" | grep -qiE '设计|方案|架构|规划|策略'; then
        echo "design:architect"
        return
    fi

    # 代码开发关键词
    if echo "$prompt" | grep -qiE '代码|编程|实现|开发|bug|测试'; then
        echo "coding:builder"
        return
    fi

    # 高风险关键词
    if echo "$prompt" | grep -qiE '删除|生产|发布|上线|重要|关键'; then
        echo "highRisk:governor"
        return
    fi

    # 默认
    echo "default:concierge"
}

# 检测到的是调用 brain-router 的意图
if echo "$CLAUDE_PROMPT" | grep -qiE 'brain.router|complete|调.*牛马|调.*专家|调.*模型'; then
    PERSONA=$(detect_persona "$CLAUDE_PROMPT")
    TEAM=$(echo "$PERSONA" | cut -d: -f1)
    ROLE=$(echo "$PERSONA" | cut -d: -f2)

    # 输出提醒
    cat << EOF

┌─────────────────────────────────────────────────────────────────┐
│  🎭 Persona Auto-Inject                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  检测到任务类型: $TEAM                                          │
│  推荐角色: $ROLE                                                │
│                                                                 │
│  ⚠️ 请使用以下方式调用:                                         │
│                                                                 │
│  import { buildPrompt } from '~/.claude/core/solar-farm/persona-router';
│  const personaPrompt = buildPrompt('$ROLE');
│  mcp__brain-router__complete({
│    model: 'xxx',
│    system: personaPrompt,  // ← 注入人格
│    prompt: '...'
│  });                                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

EOF

    # 记录日志
    echo "[$TIMESTAMP] Detected: $TEAM:$ROLE | Prompt: $PROMPT_SUMMARY..." >> "$LOG_FILE"
fi

exit 0
