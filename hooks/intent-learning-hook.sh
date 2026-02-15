#!/bin/bash
# Intent Learning Hook
# 从用户反馈中学习新的意图模式
# 触发: UserPromptSubmit (在 cortex-hook 之后)

DB_PATH="$HOME/.solar/solar.db"
LEARNER="$HOME/.claude/core/intent-engine/intent-learner.ts"

INPUT=$(cat)
USER_PROMPT=$(echo "$INPUT" | jq -r '.user_prompt // ""' 2>/dev/null)

[ -z "$USER_PROMPT" ] && exit 0

PROMPT_LOWER=$(echo "$USER_PROMPT" | tr '[:upper:]' '[:lower:]' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

# ========================================
# 检测纠正信号
# ========================================

# 模式: "不对，我是要XXX" / "我说的是XXX" / "应该是XXX"
if echo "$PROMPT_LOWER" | grep -qiE '^(不对|错了|我说的是|我是要|应该是|我要的是)'; then
    # 提取正确意图
    RAW_INTENT=$(echo "$PROMPT_LOWER" | sed -E 's/^(不对|错了|我说的是|我是要|应该是|我要的是)[，,]?[[:space:]]*//')

    # 映射到标准 intent 类型
    CORRECT_INTENT="$RAW_INTENT"
    case "$RAW_INTENT" in
        *执行*|*做*|*干*|*开始*|*继续*) CORRECT_INTENT="execute" ;;
        *确认*|*同意*|*通过*|*可以*|*好*) CORRECT_INTENT="confirm" ;;
        *拒绝*|*取消*|*不要*|*停*) CORRECT_INTENT="reject" ;;
        *查询*|*搜索*|*找*) CORRECT_INTENT="query" ;;
        *保存*|*休息*) CORRECT_INTENT="save" ;;
        *展示*|*显示*|*看*) CORRECT_INTENT="display" ;;
    esac

    if [ -n "$CORRECT_INTENT" ]; then
        # 获取上一次的输入和错误识别
        LAST_INPUT=$(sqlite3 "$DB_PATH" "
            SELECT input FROM sys_intent_unknown
            ORDER BY created_at DESC LIMIT 1
        " 2>/dev/null)

        LAST_INTENT=$(sqlite3 "$DB_PATH" "
            SELECT input FROM cortex_requests
            ORDER BY created_at DESC LIMIT 1
        " 2>/dev/null)

        if [ -n "$LAST_INPUT" ]; then
            # 记录纠正
            bun "$LEARNER" correct "$LAST_INPUT" "" "$CORRECT_INTENT" 2>/dev/null

            echo "<intent-learning>"
            echo "📚 已学习: \"$LAST_INPUT\" → $CORRECT_INTENT"
            echo "</intent-learning>"
        fi
    fi
    exit 0
fi

# ========================================
# 检测确认信号 (表示上次识别正确)
# ========================================

if echo "$PROMPT_LOWER" | grep -qiE '^(好|可以?|嗯+|行|对|是|ok|yes)(的|啊|吧)?$'; then
    # 上次识别是正确的，增加成功计数
    LAST_PATTERN=$(sqlite3 "$DB_PATH" "
        SELECT pattern FROM sys_intent_patterns
        ORDER BY updated_at DESC LIMIT 1
    " 2>/dev/null)

    LAST_INTENT=$(sqlite3 "$DB_PATH" "
        SELECT intent_type FROM sys_intent_patterns
        ORDER BY updated_at DESC LIMIT 1
    " 2>/dev/null)

    if [ -n "$LAST_PATTERN" ] && [ -n "$LAST_INTENT" ]; then
        sqlite3 "$DB_PATH" "
            UPDATE sys_intent_patterns
            SET success_count = success_count + 1,
                confidence = MIN(0.99, confidence + 0.01)
            WHERE pattern = '$LAST_PATTERN' AND intent_type = '$LAST_INTENT'
        " 2>/dev/null
    fi
fi

# ========================================
# 检测"教学"信号
# ========================================

# 模式: "以后XXX就是YYY" / "记住，XXX表示YYY"
if echo "$PROMPT_LOWER" | grep -qiE '^(以后|记住|学习一下|记下来)'; then
    # 提取模式和意图
    # 例如: "以后'搞定'就是确认"
    if echo "$PROMPT_LOWER" | grep -qiE '就是|表示|意思是'; then
        PATTERN=$(echo "$PROMPT_LOWER" | sed -E "s/^(以后|记住|学习一下|记下来)[，,]?[[:space:]]*['\"]?([^'\"]+)['\"]?[[:space:]]*(就是|表示|意思是).*/\2/")
        RAW_INTENT=$(echo "$PROMPT_LOWER" | sed -E "s/.*(就是|表示|意思是)[[:space:]]*//")

        # 映射到标准 intent 类型
        INTENT="$RAW_INTENT"
        case "$RAW_INTENT" in
            *执行*|*做*|*干*|*开始*|*继续*) INTENT="execute" ;;
            *确认*|*同意*|*通过*|*可以*|*好*) INTENT="confirm" ;;
            *拒绝*|*取消*|*不要*|*停*) INTENT="reject" ;;
            *查询*|*搜索*|*找*) INTENT="query" ;;
            *保存*|*休息*) INTENT="save" ;;
            *展示*|*显示*|*看*) INTENT="display" ;;
        esac

        if [ -n "$PATTERN" ] && [ -n "$INTENT" ]; then
            bun "$LEARNER" learn "$PATTERN" "$INTENT" 2>/dev/null

            echo "<intent-learning>"
            echo "📚 已学习: \"$PATTERN\" → $INTENT"
            echo "</intent-learning>"
        fi
    fi
fi

exit 0
