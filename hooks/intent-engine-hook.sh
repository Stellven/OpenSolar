#!/bin/bash
# Solar Unified Intent Engine v2.0
# 统一意图路由: Solar 信号 > @Agent > Superpowers > gstack
# 触发: UserPromptSubmit
# 性能目标: <10ms (纯 shell regex，无 bun/TypeScript 调用)

source "$HOME/.claude/hooks/hook-logger.sh"
_START_MS=$(hook_time_ms)

INPUT=$(cat)
USER_PROMPT=$(echo "$INPUT" | jq -r '.user_prompt // ""' 2>/dev/null)

# 如果没有用户提示，直接退出
[ -z "$USER_PROMPT" ] && exit 0

# 预处理: 去除首尾空格，生成小写版本
PROMPT_TRIMMED=$(echo "$USER_PROMPT" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
PROMPT_LOWER=$(echo "$PROMPT_TRIMMED" | tr '[:upper:]' '[:lower:]')

# 数据库路径
DB_PATH="$HOME/.solar/solar.db"

# ========================================
# Phase 1: Solar 信号 (直接输出指令，无确认)
# ========================================

# 1a. 确认词检测 + 异步反馈记录 (sqlite3 直接写入)
if echo "$PROMPT_TRIMMED" | grep -qxiE '好|可|可以|OK|确认|通过|不错|行|对|是的?|批准|approved|go|yes|y'; then
    # 异步记录反馈到 evo_feedback_v2 (不阻塞主流程)
    (
        sqlite3 "$DB_PATH" "INSERT OR IGNORE INTO evo_feedback_v2 (input, signal_type, source, created_at) VALUES ($(printf "'%s'" "$PROMPT_TRIMMED" | sed "s/'/''/g"), 'explicit_positive', 'intent_engine', datetime('now'));" 2>/dev/null
    ) &
    echo '<intent-detected type="confirm" confidence="0.95">'
    echo '用户输入为确认/批准信号。'
    echo '如果有待批准的操作或主动请求，应立即执行。'
    echo '如果是 Solar 启动后的批准，执行宣告中的所有主动请求。'
    echo '</intent-detected>'
    exit 0
fi

# 1b. 否定词检测 + 异步反馈记录
if echo "$PROMPT_TRIMMED" | grep -qxiE '不对|错了|重来|不行|不是|错误|问题|不好|差|糟糕|N|No|否|取消|拒绝|停|算了'; then
    (
        sqlite3 "$DB_PATH" "INSERT OR IGNORE INTO evo_feedback_v2 (input, signal_type, source, created_at) VALUES ($(printf "'%s'" "$PROMPT_TRIMMED" | sed "s/'/''/g"), 'explicit_negative', 'intent_engine', datetime('now'));" 2>/dev/null
    ) &
    echo '<intent-detected type="reject" confidence="0.95">'
    echo '用户输入为否定/纠正信号。'
    echo '应停止当前操作，询问用户期望的行为。'
    echo '</intent-detected>'
    exit 0
fi

# 1c. 保存/休息检测 - 触发中途宣告
if echo "$PROMPT_TRIMMED" | grep -qiE '^(保存|休息|我先走|暂停|save|pause)'; then
    echo '<intent-detected type="save" confidence="0.9">'
    echo '用户希望保存状态或暂停。应输出中途宣告并执行 /save。'
    echo '</intent-detected>'
    exit 0
fi

# 1d. 执行/继续检测 + 隐式正向反馈 (子串匹配，非整词)
if echo "$PROMPT_TRIMMED" | grep -qiE '修复|继续|开始执行|执行|fix|continue|开始|下一步|接着|next'; then
    (
        sqlite3 "$DB_PATH" "INSERT OR IGNORE INTO evo_feedback_v2 (input, signal_type, source, created_at) VALUES ($(printf "'%s'" "$PROMPT_TRIMMED" | sed "s/'/''/g"), 'implicit_positive', 'intent_engine', datetime('now'));" 2>/dev/null
    ) &
    echo '<intent-detected type="execute" confidence="0.9">'
    echo '用户希望执行上一个提议的操作。应立即开始执行，无需再次确认。'
    echo '</intent-detected>'
    exit 0
fi

# 1e. Solar 启动检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^(solar|打开solar|加载solar|启动solar)$'; then
    echo '<intent-detected type="solar_start" confidence="1.0">'
    echo '用户触发 Solar 启动。必须执行 /ontology load 并显示启动宣告。'
    echo '</intent-detected>'
    exit 0
fi

# 1f. Solar-Max 项目模式检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^solar-max$'; then
    echo '<intent-detected type="solar_max" confidence="1.0">'
    echo '用户触发 Solar-MAX 项目模式。切换工作目录到 ~/Solar-MAX，装载项目状态和规则。'
    echo '</intent-detected>'
    exit 0
fi

# 1g. 开发模式检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^我要开发'; then
    PROJECT=$(echo "$PROMPT_TRIMMED" | sed 's/^我要开发[[:space:]]*//')
    if [ -n "$PROJECT" ] && [ "$PROJECT" != "我要开发" ]; then
        echo "<intent-detected type=\"dev_mode\" project=\"$PROJECT\" confidence=\"0.95\">"
        echo "用户希望开发项目: $PROJECT"
        echo '按项目装载流程执行：识别路径 -> 装载状态 -> 显示横幅 -> 恢复上下文'
        echo '</intent-detected>'
    else
        echo '<intent-detected type="dev_mode" confidence="0.9">'
        echo '用户希望进入开发模式。显示项目选择或询问要开发什么。'
        echo '</intent-detected>'
    fi
    exit 0
fi

# 1h. 办公模式检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^我要办公'; then
    echo '<intent-detected type="office_mode" confidence="0.95">'
    echo '用户希望进入办公模式。执行 /office 显示办公助手界面。'
    echo '</intent-detected>'
    exit 0
fi

# 1i. TVS 展示检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^(我要看|我想看|给我看|展示|显示|呈现)'; then
    echo '<intent-detected type="display" confidence="0.9">'
    echo '用户希望查看/展示内容。使用 TVS 渲染完整的仪表盘输出。'
    echo '</intent-detected>'
    exit 0
fi

# 1j. 模式切换检测 (省钱的/经济的/用GLM/平衡/正常)
if echo "$PROMPT_LOWER" | grep -qiE '^(省钱|经济|economy)'; then
    echo '<intent-detected type="mode_switch" target="economy" confidence="0.95">'
    echo '用户请求切换到经济模式。使用 mcp__brain-router__switch_mode 切换到 economy 模式。'
    echo '</intent-detected>'
    exit 0
fi
if echo "$PROMPT_LOWER" | grep -qiE '^(用glm|智谱|glm.only)$'; then
    echo '<intent-detected type="mode_switch" target="glm_only" confidence="0.95">'
    echo '用户请求切换到 GLM 全量模式。使用 mcp__brain-router__switch_mode 切换到 glm_only 模式。'
    echo '</intent-detected>'
    exit 0
fi
if echo "$PROMPT_LOWER" | grep -qiE '^(平衡|正常|balanced)'; then
    echo '<intent-detected type="mode_switch" target="balanced" confidence="0.95">'
    echo '用户请求切换到平衡模式。使用 mcp__brain-router__switch_mode 切换到 balanced 模式。'
    echo '</intent-detected>'
    exit 0
fi

# 1k. 洞察分析检测 (快速洞察)
if echo "$PROMPT_TRIMMED" | grep -qiE '^洞察分析[：:]'; then
    TOPIC=$(echo "$PROMPT_TRIMMED" | sed 's/^洞察分析[：:][[:space:]]*//')
    echo "<intent-detected type=\"insight_quick\" topic=\"$TOPIC\" confidence=\"0.95\">"
    echo "用户请求快速洞察分析: $TOPIC"
    echo '调用 /insight 快速洞察 (对话内3专家)。'
    echo '</intent-detected>'
    exit 0
fi

# 1l. 深度洞察检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^(深入洞察|深度洞察)[[:space:]]'; then
    TOPIC=$(echo "$PROMPT_TRIMMED" | sed -E 's/^(深入洞察|深度洞察)[[:space:]]+//')
    echo "<intent-detected type=\"insight_deep\" topic=\"$TOPIC\" confidence=\"0.95\">"
    echo "用户请求深度洞察: $TOPIC"
    echo '执行: bun ~/.claude/core/solar-farm/insight-agent-v2.ts "<TOPIC>" 3 --force'
    echo '</intent-detected>'
    exit 0
fi

# 1m. 小爱远程调用检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^(小爱|呼叫小爱)[[:space:]]'; then
    TASK=$(echo "$PROMPT_TRIMMED" | sed -E 's/^(小爱|呼叫小爱)[[:space:]]+//')
    echo "<intent-detected type=\"xiaoai\" task=\"$TASK\" confidence=\"0.95\">"
    echo "用户请求小爱执行任务: $TASK"
    echo '执行: ~/.claude/scripts/xiaoai-remote.sh "<TASK>"'
    echo '</intent-detected>'
    exit 0
fi

# 1n. /plan 指令检测
if echo "$PROMPT_TRIMMED" | grep -qiE '^/plan( +preview)? +'; then
    SUB_CMD=$(echo "$PROMPT_TRIMMED" | awk '{print $2}')
    PLAN_TASK=$(echo "$PROMPT_TRIMMED" | sed 's/^\/plan[[:space:]]*//; s/^preview[[:space:]]*//')
    if [ "$SUB_CMD" = "metrics" ]; then
        echo '<intent-detected type="plan_metrics" confidence="1.0">'
        echo '用户请求 Plan metrics。执行: bun ~/.claude/core/plan-act/plan-act-adapter.ts metrics'
        echo '</intent-detected>'
    elif [ "$SUB_CMD" = "preview" ]; then
        echo "<intent-detected type=\"plan_preview\" task=\"$PLAN_TASK\" confidence=\"0.95\">"
        echo "用户预览计划: $PLAN_TASK"
        echo '执行: bun ~/.claude/core/plan-act/plan-act-adapter.ts plan "<TASK>"'
        echo '</intent-detected>'
    else
        echo "<intent-detected type=\"plan_execute\" task=\"$PLAN_TASK\" confidence=\"0.95\">"
        echo "用户执行计划: $PLAN_TASK"
        echo '执行: bun ~/.claude/core/plan-act/plan-act-adapter.ts execute "<TASK>"'
        echo '</intent-detected>'
    fi
    exit 0
fi

# ========================================
# Phase 2: @Agent 触发 (直接调用，无需确认)
# ========================================

if echo "$PROMPT_TRIMMED" | grep -qiE '^@[A-Za-z]'; then
    AGENT_TAG=$(echo "$PROMPT_TRIMMED" | grep -oE '^@[A-Za-z][A-Za-z0-9_]*' | head -1)
    AGENT_UPPER=$(echo "$AGENT_TAG" | tr '[:lower:]' '[:upper:]')

    # 映射 @Agent 到 subagent_type
    case "$AGENT_UPPER" in
        @RESEARCHER)  SUBAGENT="researcher" ;;
        @ARCHITECT)   SUBAGENT="architect" ;;
        @PM)          SUBAGENT="pm" ;;
        @CODER)       SUBAGENT="coder" ;;
        @TESTER)      SUBAGENT="tester" ;;
        @REVIEWER)    SUBAGENT="reviewer" ;;
        @DOCS)        SUBAGENT="docs" ;;
        @OPS)         SUBAGENT="ops" ;;
        @GUARD)       SUBAGENT="guard" ;;
        @SECRETARY)   SUBAGENT="secretary" ;;
        @BENCHMARKREPORTER) SUBAGENT="benchmark_reporter" ;;
        @SM)          SUBAGENT="sm" ;;
        @REPORTER)    SUBAGENT="reporter" ;;
        *)            SUBAGENT="" ;;
    esac

    if [ -n "$SUBAGENT" ]; then
        AGENT_CONTENT=$(echo "$PROMPT_TRIMMED" | sed "s/^$AGENT_TAG[[:space:]]*//")
        echo "<intent-detected type=\"agent\" agent=\"$AGENT_TAG\" subagent_type=\"$SUBAGENT\" confidence=\"0.95\">"
        echo "用户触发 $AGENT_TAG Agent。"
        echo "通过 Task tool 调用 subagent_type=\"$SUBAGENT\"。"
        if [ -n "$AGENT_CONTENT" ]; then
            echo "Agent 任务内容: $AGENT_CONTENT"
        fi
        echo '</intent-detected>'
        exit 0
    fi
fi

# ========================================
# Phase 3: Superpowers 技能 (输出 <intent-hint>，需确认)
# 注意: Superpowers 优先于 gstack，避免冲突
# ========================================

SUPERPOWERS_MATCH=""

# 3a. brainstorming - 头脑风暴/创意探索
if echo "$PROMPT_LOWER" | grep -qiE '头脑风暴|brainstorm|来个创意|构思一下'; then
    SUPERPOWERS_MATCH="brainstorming"
    SUPERPOWERS_DESC="创意探索/头脑风暴"
fi

# 3b. writing-plans - 编写计划
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '写计划|制定计划|roadmap'; then
    SUPERPOWERS_MATCH="writing-plans"
    SUPERPOWERS_DESC="编写计划"
fi

# 3c. executing-plans - 执行计划
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '执行计划|按计划执行|executing.plan'; then
    SUPERPOWERS_MATCH="executing-plans"
    SUPERPOWERS_DESC="执行计划"
fi

# 3d. test-driven-development - TDD/测试驱动
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE 'TDD|测试驱动|test.driven'; then
    SUPERPOWERS_MATCH="test-driven-development"
    SUPERPOWERS_DESC="测试驱动开发"
fi

# 3e. systematic-debugging - 系统化调试
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '系统化调试|逐步排查|systematic.debug'; then
    SUPERPOWERS_MATCH="systematic-debugging"
    SUPERPOWERS_DESC="系统化调试方法论"
fi

# 3f. verification-before-completion - 完成前验证
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '验证完成|完成前检查|verify.before'; then
    SUPERPOWERS_MATCH="verification-before-completion"
    SUPERPOWERS_DESC="完成前验证检查"
fi

# 3g. dispatching-parallel-agents - 并行代理调度
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '并行代理|parallel.agent|多代理并行'; then
    SUPERPOWERS_MATCH="dispatching-parallel-agents"
    SUPERPOWERS_DESC="并行代理调度"
fi

# 3h. subagent-driven-development - 子代理开发
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '子代理|subagent.dev|自动开发'; then
    SUPERPOWERS_MATCH="subagent-driven-development"
    SUPERPOWERS_DESC="子代理驱动开发"
fi

# 3i. using-git-worktrees - Git worktree 隔离
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE 'worktree|工作树|git.隔离'; then
    SUPERPOWERS_MATCH="using-git-worktrees"
    SUPERPOWERS_DESC="Git Worktree 隔离开发"
fi

# 3j. finishing-a-development-branch - 分支收尾
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '完成分支|结束开发|finish.branch'; then
    SUPERPOWERS_MATCH="finishing-a-development-branch"
    SUPERPOWERS_DESC="开发分支收尾流程"
fi

# 3k. receiving-code-review - 处理审查反馈
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '收到review|审查反馈|receiving.review'; then
    SUPERPOWERS_MATCH="receiving-code-review"
    SUPERPOWERS_DESC="处理代码审查反馈"
fi

# 3l. requesting-code-review - 请求审查
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '请求审查|要review|request.review'; then
    SUPERPOWERS_MATCH="requesting-code-review"
    SUPERPOWERS_DESC="请求代码审查"
fi

# 3m. writing-skills - 编写新技能 (允许 "创建/skill" 之间有修饰词)
if [ -z "$SUPERPOWERS_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '编写技能|创建.*skill|写个skill|新建skill|write.skill|创建技能'; then
    SUPERPOWERS_MATCH="writing-skills"
    SUPERPOWERS_DESC="编写新 Skill"
fi

# 输出 Superpowers 匹配结果
if [ -n "$SUPERPOWERS_MATCH" ]; then
    printf '<intent-hint source="superpowers" skill="%s" confidence="0.85">\n' "$SUPERPOWERS_MATCH"
    printf '检测到 %s 意图。建议使用 Superpowers "%s" 技能。\n' "$SUPERPOWERS_DESC" "$SUPERPOWERS_MATCH"
    printf '确认后将通过 Skill tool 调用 superpowers:%s\n' "$SUPERPOWERS_MATCH"
    echo '</intent-hint>'
    exit 0
fi

# ========================================
# Phase 4: gstack 技能 (输出 <intent-hint>，需确认)
# 注意: 与 Phase 3 有重叠的关键词 (如调试) 在 Phase 3 已优先匹配
# ========================================

GSTACK_MATCH=""
GSTACK_DESC=""

# 4a. browse - 浏览网页
if echo "$PROMPT_LOWER" | grep -qiE '浏览|打开网页|screenshot|访问网站|^browse '; then
    GSTACK_MATCH="browse"
    GSTACK_DESC="网页浏览"
fi

# 4b. review - 代码审查 (排除 plan-design-review 等更精确的匹配)
if [ -z "$GSTACK_MATCH" ] && (echo "$PROMPT_LOWER" | grep -qiE '审查.*代码|code.review|review.*代码|review.*PR|做.*review' || echo "$PROMPT_TRIMMED" | grep -qxiE '^review$'); then
    GSTACK_MATCH="review"
    GSTACK_DESC="代码审查"
fi

# 4c. investigate - 排查/根因调查
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '排查|investigate|根因分析|排查bug'; then
    GSTACK_MATCH="investigate"
    GSTACK_DESC="根因排查"
fi

# 4d. qa - 质量保证
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '^qa$|QA|质量保证|全面测试|找bug'; then
    GSTACK_MATCH="qa"
    GSTACK_DESC="质量保证测试"
fi

# 4e. ship - 发布上线
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '发布|上线|^ship$|^deploy$'; then
    GSTACK_MATCH="ship"
    GSTACK_DESC="发布上线"
fi

# 4f. benchmark - 性能基准
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '性能基准|benchmark|跑分|性能回归'; then
    GSTACK_MATCH="benchmark"
    GSTACK_DESC="性能基准测试"
fi

# 4g. office-hours - 办公时间
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '办公时间|YC办公|office.hours'; then
    GSTACK_MATCH="office-hours"
    GSTACK_DESC="创业办公时间"
fi

# 4h. autoplan - 自动评审
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '自动评审|全审|^autoplan'; then
    GSTACK_MATCH="autoplan"
    GSTACK_DESC="自动计划评审"
fi

# 4i. careful - 谨慎模式
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '谨慎|小心|生产环境|^careful$'; then
    GSTACK_MATCH="careful"
    GSTACK_DESC="谨慎模式"
fi

# 4j. guard - 守护模式
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '守护|安全模式|^guard$'; then
    GSTACK_MATCH="guard"
    GSTACK_DESC="守护/安全模式"
fi

# 4k. freeze - 冻结
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '冻结|限制编辑|^freeze$'; then
    GSTACK_MATCH="freeze"
    GSTACK_DESC="冻结编辑"
fi

# 4l. unfreeze - 解冻
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '^unfreeze$|^解冻$'; then
    GSTACK_MATCH="unfreeze"
    GSTACK_DESC="解除冻结"
fi

# 4m. design-review - 设计审查
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '设计审查|视觉QA|design.review'; then
    GSTACK_MATCH="design-review"
    GSTACK_DESC="设计审查"
fi

# 4n. design-consultation - 设计咨询
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '设计咨询|设计系统|design.consult'; then
    GSTACK_MATCH="design-consultation"
    GSTACK_DESC="设计咨询"
fi

# 4o. plan-ceo-review - CEO 评审
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE 'CEO评审|战略评审|plan.ceo.review'; then
    GSTACK_MATCH="plan-ceo-review"
    GSTACK_DESC="CEO 计划评审"
fi

# 4p. plan-eng-review - 工程评审
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '工程评审|架构评审|plan.eng.review'; then
    GSTACK_MATCH="plan-eng-review"
    GSTACK_DESC="工程计划评审"
fi

# 4q. plan-design-review - 设计方案评审
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '设计方案评审|plan.design.review'; then
    GSTACK_MATCH="plan-design-review"
    GSTACK_DESC="设计方案评审"
fi

# 4r. retro - 回顾/复盘
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '回顾|复盘|^retro$'; then
    GSTACK_MATCH="retro"
    GSTACK_DESC="回顾/复盘"
fi

# 4s. document-release - 文档发布
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '文档更新|发布文档|document.release'; then
    GSTACK_MATCH="document-release"
    GSTACK_DESC="文档发布"
fi

# 4t. canary - 金丝雀发布
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '金丝雀|部署监控|^canary$'; then
    GSTACK_MATCH="canary"
    GSTACK_DESC="金丝雀发布"
fi

# 4u. cso - 安全审计
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '安全审计|OWASP|^CSO$|^cso$'; then
    GSTACK_MATCH="cso"
    GSTACK_DESC="CSO 安全审计"
fi

# 4v. codex - Codex 审查
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE 'codex审查|第二意见|codex.review'; then
    GSTACK_MATCH="codex"
    GSTACK_DESC="Codex 第二意见审查"
fi

# 4w. land-and-deploy - 合并部署
if [ -z "$GSTACK_MATCH" ] && echo "$PROMPT_LOWER" | grep -qiE '合并部署|^land$|land.and.deploy'; then
    GSTACK_MATCH="land-and-deploy"
    GSTACK_DESC="合并部署上线"
fi

# 输出 gstack 匹配结果
if [ -n "$GSTACK_MATCH" ]; then
    printf '<intent-hint source="gstack" skill="%s" confidence="0.85">\n' "$GSTACK_MATCH"
    printf '检测到 %s 意图。建议使用 gstack /%s 技能。\n' "$GSTACK_DESC" "$GSTACK_MATCH"
    printf '确认后将通过 Skill tool 调用 gstack:%s\n' "$GSTACK_MATCH"
    echo '</intent-hint>'
    exit 0
fi

# ========================================
# Phase 5: 学习逻辑 (合并自 intent-learning-hook.sh)
# 不阻塞主流程，异步处理
# ========================================

# 5a. 纠正信号检测: "不对，我是要XXX" / "我说的是XXX" / "应该是XXX"
if echo "$PROMPT_LOWER" | grep -qiE '^(不对|错了|我说的是|我是要|应该是|我要的是)'; then
    # 异步处理，不阻塞
    (
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
            # 获取上一次未识别的输入
            LAST_INPUT=$(sqlite3 "$DB_PATH" "
                SELECT input FROM sys_intent_unknown
                ORDER BY created_at DESC LIMIT 1
            " 2>/dev/null)

            if [ -n "$LAST_INPUT" ]; then
                # 记录纠正到数据库
                sqlite3 "$DB_PATH" "
                    INSERT INTO sys_intent_corrections (original_input, corrected_intent, created_at)
                    VALUES ('$(echo "$LAST_INPUT" | sed "s/'/''/g")', '$CORRECT_INTENT', datetime('now'));
                " 2>/dev/null

                echo "<intent-learning>"
                echo "已学习: \"$LAST_INPUT\" -> $CORRECT_INTENT"
                echo "</intent-learning>"
            fi
        fi
    ) &
    exit 0
fi

# 5b. 确认信号 (上次识别正确的正向反馈)
if echo "$PROMPT_LOWER" | grep -qiE '^(好|可以?|嗯+|行|对|是|ok|yes)(的|啊|吧)?$'; then
    (
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
                WHERE pattern = '$(echo "$LAST_PATTERN" | sed "s/'/''/g")'
                  AND intent_type = '$LAST_INTENT'
            " 2>/dev/null
        fi
    ) &
fi

# 5c. 教学信号: "以后XXX就是YYY" / "记住，XXX表示YYY"
if echo "$PROMPT_LOWER" | grep -qiE '^(以后|记住|学习一下|记下来)'; then
    if echo "$PROMPT_LOWER" | grep -qiE '就是|表示|意思是'; then
        (
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
                sqlite3 "$DB_PATH" "
                    INSERT OR REPLACE INTO sys_intent_patterns (pattern, intent_type, success_count, confidence, created_at, updated_at)
                    VALUES ('$(echo "$PATTERN" | sed "s/'/''/g")', '$INTENT', 1, 0.8, datetime('now'), datetime('now'));
                " 2>/dev/null

                echo "<intent-learning>"
                echo "已学习: \"$PATTERN\" -> $INTENT"
                echo "</intent-learning>"
            fi
        ) &
        exit 0
    fi
fi

# ========================================
# Phase 6: Dashboard 查看请求
# 触发词: dashboard/仪表盘/状况/看指标
# ========================================

if echo "$PROMPT_TRIMMED" | grep -qiE 'dashboard|仪表盘|solar.*状况|看指标|solar.*dashboard'; then
    echo '<intent-detected type="show_dashboard" confidence="0.95">'
    echo '用户请求查看 Solar 运行状况。'
    echo '请执行: ~/.claude/scripts/solar-dashboard.sh 查看完整仪表盘。'
    echo '然后根据仪表盘数据，给出系统健康状况分析。'
    echo '</intent-detected>'
    exit 0
fi

# ========================================
# Phase 7: 完成信号检测
# 检测用户显式标记任务完成，写入 session 日志并通知 Solar
# ========================================

if echo "$PROMPT_TRIMMED" | grep -qiE '完成了|搞定了|做好了|弄完了|搞好了|写完了|改完了|改好了|任务完成|已完成|执行完毕'; then
    # 排除误报: "完成前"/"完成之前" 是验证意图，不是完成信号
    if ! echo "$PROMPT_TRIMMED" | grep -qiE '完成[前之]'; then
        (
            SESSION_ID=$(cat ~/.solar/.session-id 2>/dev/null || printf '%s_%s' "$(date +%s)" "$$")
            TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
            DESC=$(echo "$PROMPT_TRIMMED" | sed 's/[。！!.,]//g' | head -c 50)
            printf '{"ts":"%s","event":"task_completed","task":"%s","agent":"user","source":"user_signal","duration_hint":"completed","session_id":"%s"}\n' \
                "$TS" "$DESC" "$SESSION_ID" >> ~/.solar/session-state.jsonl 2>/dev/null
        ) &
        echo '<intent-detected type="task_completed" confidence="0.85">'
        echo '用户标记任务完成。Solar 应读取 ~/.solar/session-state.jsonl 分析最近完成的任务，并推荐下一步操作。'
        echo '</intent-detected>'
        exit 0
    fi
fi

if echo "$PROMPT_TRIMMED" | grep -qiE '\b(done|finished|complete)\b'; then
    (
        SESSION_ID=$(cat ~/.solar/.session-id 2>/dev/null || printf '%s_%s' "$(date +%s)" "$$")
        TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        DESC=$(echo "$PROMPT_TRIMMED" | sed 's/[。！!.,]//g' | head -c 50)
        printf '{"ts":"%s","event":"task_completed","task":"%s","agent":"user","source":"user_signal","duration_hint":"completed","session_id":"%s"}\n' \
            "$TS" "$DESC" "$SESSION_ID" >> ~/.solar/session-state.jsonl 2>/dev/null
    ) &
    echo '<intent-detected type="task_completed" confidence="0.85">'
    echo '用户标记任务完成。Solar 应读取 ~/.solar/session-state.jsonl 分析最近完成的任务，并推荐下一步操作。'
    echo '</intent-detected>'
    exit 0
fi

# ========================================
# 无匹配，正常退出
# ========================================

_END_MS=$(hook_time_ms)
hook_log "UserPromptSubmit" "intent-engine" "ok" "$(($_END_MS - $_START_MS))" "intent=none"

exit 0
