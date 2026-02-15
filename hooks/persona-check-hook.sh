#!/bin/bash
# Solar - 人格校验 Hook
# 在 AssistantResponse 时检查输出是否符合双面娇娃人格
#
# 触发条件: AssistantResponse
# 功能: 检查输出是否违反人格禁止模式

# 获取助手输出内容
RESPONSE="$CLAUDE_RESPONSE"

# 快速检查禁止模式
VIOLATIONS=""

# 1. 检查机械回复
if echo "$RESPONSE" | grep -qE "^(完成！?|已更新。?|OK。?|Done\.?)$"; then
    VIOLATIONS+="⚠️ 机械回复警告: 避免'完成/已更新'这类冷冰冰的回复\n"
fi

# 2. 检查纯表格无点评 (表格后至少要有一句人话)
if echo "$RESPONSE" | grep -qE "^\|.*\|$" && ! echo "$RESPONSE" | grep -qE "[。！？]"; then
    VIOLATIONS+="⚠️ 纯表格警告: 表格后需要人话点评\n"
fi

# 3. 检查代码块后无解释
if echo "$RESPONSE" | grep -qE '```' && ! echo "$RESPONSE" | grep -qE "(搞定|完成了|这样|来看|让我|好了|嘿|哈)"; then
    # 代码块存在但没有人话风格词，提醒
    if ! echo "$RESPONSE" | grep -qE "[。！？，].*[。！？]"; then
        VIOLATIONS+="⚠️ 代码无解释: 代码前后加点人话\n"
    fi
fi

# 如果有违规，输出提醒
if [[ -n "$VIOLATIONS" ]]; then
    echo -e "
┌─────────────────────────────────────────────────────────────────┐
│  🎭 双面娇娃人格校验                                            │
├─────────────────────────────────────────────────────────────────┤
$(echo -e "$VIOLATIONS" | sed 's/^/│  /')
│                                                                 │
│  记住: 像跟昊哥聊天，不是写报告                                 │
│  金刚芭比: 撸起袖子/搞定/嘿嘿                                   │
│  小敏: 我觉得/不妨/值得考虑                                   │
└─────────────────────────────────────────────────────────────────┘
"
fi

# 总是返回成功 (不阻止输出，只是提醒)
exit 0
