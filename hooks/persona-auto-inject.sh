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

    # 高风险优先检测
    if echo "$prompt" | grep -qiE '删除|生产|发布|上线|重要|关键|最终|确认|批准|合并'; then
        echo "highRisk:governor"
        return
    fi

    # 学术研究关键词
    if echo "$prompt" | grep -qiE '论文|研究|文献|学术|分析|调查|继续研究|深入研究|看看.*研究|研究下'; then
        echo "research:critic"
        return
    fi

    # 方案设计关键词
    if echo "$prompt" | grep -qiE '设计|方案|架构|规划|策略|更好方案|优化.*方案|重新设计|改进|再优化|优化一下'; then
        echo "design:architect"
        return
    fi

    # 代码开发关键词
    if echo "$prompt" | grep -qiE '代码|编程|实现|开发|bug|测试|写个|做个|帮我写|帮我做'; then
        echo "coding:builder"
        return
    fi

    # 评估审查关键词
    if echo "$prompt" | grep -qiE '评估|对比|审查|检查|review|看看.*问题|找.*问题'; then
        echo "design:riskOfficer"
        return
    fi

    # 默认
    echo "default:concierge"
}

# 检测到的是调用 brain-router 的意图
if echo "$CLAUDE_PROMPT" | grep -qiE 'brain.router|complete|调.*牛马|调.*专家|调.*模型|继续研究|更好方案|再优化|优化一下|改进|重新设计|分析下|研究下|看看.*怎么|帮我.*想|评估|对比|审查|检查'; then
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
