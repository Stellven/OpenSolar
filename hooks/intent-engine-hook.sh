#!/bin/bash
# Solar Intent Engine Hook
# 在处理用户请求前，解析意图并注入上下文提示
# 触发: UserPromptSubmit

INPUT=$(cat)
USER_PROMPT=$(echo "$INPUT" | jq -r '.user_prompt // ""' 2>/dev/null)

# 如果没有用户提示，直接退出
[ -z "$USER_PROMPT" ] && exit 0

# 去除首尾空格
PROMPT_TRIMMED=$(echo "$USER_PROMPT" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

# ========================================
# 快速模式匹配 (不调用 bun，毫秒级响应)
# ========================================

# 1. 确认词检测 + 反馈记录
if echo "$PROMPT_TRIMMED" | grep -qxiE '好|可|可以|OK|确认|通过|不错|行|对|是的?|批准|approved|go|yes|y'; then
    # 异步记录反馈到 evo_feedback_v2 (不阻塞主流程)
    (bun ~/.claude/core/intent-engine/engine.ts feedback "$PROMPT_TRIMMED" >/dev/null 2>&1 &)
    echo '<intent-detected type="confirm" confidence="0.95">'
    echo '用户输入为确认/批准信号。'
    echo '如果有待批准的操作或主动请求，应立即执行。'
    echo '如果是 Solar 启动后的批准，执行宣告中的所有主动请求。'
    echo '[反馈已记录到 evo_feedback_v2: explicit_positive]'
    echo '</intent-detected>'
    exit 0
fi

# 1b. 否定词检测 + 反馈记录
if echo "$PROMPT_TRIMMED" | grep -qxiE '不对|错了|重来|不行|不是|错误|问题|不好|差|糟糕|N|No|否|取消|拒绝|停|算了'; then
    # 异步记录反馈到 evo_feedback_v2
    (bun ~/.claude/core/intent-engine/engine.ts feedback "$PROMPT_TRIMMED" >/dev/null 2>&1 &)
    echo '<intent-detected type="reject" confidence="0.95">'
    echo '用户输入为否定/纠正信号。'
    echo '应停止当前操作，询问用户期望的行为。'
    echo '[反馈已记录到 evo_feedback_v2: explicit_negative]'
    echo '</intent-detected>'
    exit 0
fi

# 2. 保存/休息检测 - 触发中途宣告
if echo "$PROMPT_TRIMMED" | grep -qiE '^(保存|休息|我先走|暂停|save|pause)'; then
    echo '<intent-detected type="save" confidence="0.9">'
    echo '用户希望保存状态或暂停。应输出中途宣告并执行 /save。'
    echo '</intent-detected>'
    exit 0
fi

# 3. 修复/继续检测 + 隐式正向反馈
if echo "$PROMPT_TRIMMED" | grep -qxiE '修复|继续|修|改|做|执行|开始|fix|continue|do|start|下一步|接着|next'; then
    # 继续执行 = 隐式正向反馈
    (bun ~/.claude/core/intent-engine/engine.ts feedback "$PROMPT_TRIMMED" >/dev/null 2>&1 &)
    echo '<intent-detected type="execute" confidence="0.9">'
    echo '用户希望执行上一个提议的操作。应立即开始执行，无需再次确认。'
    echo '[反馈已记录到 evo_feedback_v2: implicit_positive]'
    echo '</intent-detected>'
    exit 0
fi

# 4. Solar 启动检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^(solar|打开solar|加载solar|启动solar)$'; then
    echo '<intent-detected type="solar_start" confidence="1.0">'
    echo '用户触发 Solar 启动。必须执行 /ontology load 并显示启动宣告。'
    echo '</intent-detected>'
    exit 0
fi

# 5. 开发模式检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^我要开发'; then
    PROJECT=$(echo "$PROMPT_TRIMMED" | sed 's/^我要开发[[:space:]]*//')
    if [ -n "$PROJECT" ] && [ "$PROJECT" != "我要开发" ]; then
        echo "<intent-detected type=\"dev_mode\" project=\"$PROJECT\" confidence=\"0.95\">"
        echo "用户希望开发项目: $PROJECT"
        echo '按项目装载流程执行：识别路径 → 装载状态 → 显示横幅 → 恢复上下文'
        echo '</intent-detected>'
    else
        echo '<intent-detected type="dev_mode" confidence="0.9">'
        echo '用户希望进入开发模式。显示项目选择或询问要开发什么。'
        echo '</intent-detected>'
    fi
    exit 0
fi

# 6. 办公模式检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^我要办公'; then
    echo '<intent-detected type="office_mode" confidence="0.95">'
    echo '用户希望进入办公模式。执行 /office 显示办公助手界面。'
    echo '</intent-detected>'
    exit 0
fi

# 7. 展示请求检测 (TVS 渲染)
if echo "$PROMPT_TRIMMED" | grep -qiE '^(我要看|我想看|给我看|展示|显示|呈现)'; then
    echo '<intent-detected type="display" confidence="0.9">'
    echo '用户希望查看/展示内容。使用 TVS 渲染完整的仪表盘输出。'
    echo '</intent-detected>'
    exit 0
fi

# ========================================
# 对于复杂输入，不阻塞，让 Claude 处理
# 未来可以考虑调用完整的 Intent Engine
# ========================================

exit 0
