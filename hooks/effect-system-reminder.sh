#!/bin/bash
# Effect System 使用提醒 Hook
# 检测是否在写 Agent/Generator 代码，提醒使用 Effect System

TOOL_INPUT="$CLAUDE_TOOL_INPUT"
TOOL_NAME="$CLAUDE_TOOL_NAME"

# 只检查 Write 和 Edit
if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
    exit 0
fi

# 检测 Generator/Agent 模式
if echo "$TOOL_INPUT" | grep -qE "(function\s*\*|Generator\s*<|yield\s+|async\s+function\s*\*|\:\s*Generator\s*<)"; then
    # 检查是否已经使用了 Effect System
    if echo "$TOOL_INPUT" | grep -qE "(need\s*\(|perform\s*\(|from\s+['\"].*effect-system)"; then
        # 已经在用 Effect System，不提醒
        exit 0
    fi

    # 没用 Effect System，发出提醒
    cat << 'REMINDER'

┌─────────────────────────────────────────────────────────────────┐
│  ⚡ Effect System 提醒                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  检测到 Generator 模式代码，建议使用 Effect System：            │
│                                                                 │
│  ❌ 直接写 Generator:                                           │
│     function* myAgent() {                                       │
│       const data = yield someAsyncOp();                         │
│     }                                                           │
│                                                                 │
│  ✅ 使用 Effect System:                                         │
│     import { need, perform } from '~/.claude/core/effect-system';│
│                                                                 │
│     function* myAgent(input: string): Generator<Effect, R, any> {│
│       // 声明式能力需求                                         │
│       const memory = yield need('need:memory', { query: input });│
│       const personality = yield need('need:personality', {});   │
│                                                                 │
│       // 纯决策逻辑                                             │
│       const decision = analyze(memory, personality);            │
│                                                                 │
│       // 副作用执行                                             │
│       yield perform('perform:store', {                          │
│         namespace: 'decisions',                                 │
│         key: `decision_${Date.now()}`,                          │
│         value: { input, decision }                              │
│       });                                                       │
│                                                                 │
│       return decision;                                          │
│     }                                                           │
│                                                                 │
│  优势：                                                         │
│  • 审计日志 - 所有 Effect 调用可追溯                            │
│  • 可测试 - Handler 可以 mock                                   │
│  • 可补偿 - Saga 模式支持回滚                                   │
│  • 对偶架构 - Ability 声明 + Skill 匹配                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

REMINDER
fi

exit 0
