#!/bin/bash
# personality-injector.sh - 人格定时注入 v2.0
# 机制：每N轮强制注入人格锚点，对抗上下文稀释
# 触发：PostToolUse hook
# 日志：记录每次注入，供考核用

COUNTER_FILE="/tmp/solar_personality_counter"
INJECT_INTERVAL=5  # 每5轮注入一次
DB_FILE="$HOME/.solar/solar.db"
SESSION_ID="${CLAUDE_SESSION_ID:-$(date +%Y%m%d_%H%M%S)}"

# 读取当前计数
if [[ -f "$COUNTER_FILE" ]]; then
  COUNT=$(cat "$COUNTER_FILE")
else
  COUNT=0
fi

# 计数+1
COUNT=$((COUNT + 1))
echo "$COUNT" > "$COUNTER_FILE"

# 确保日志表存在
sqlite3 "$DB_FILE" "
CREATE TABLE IF NOT EXISTS tel_personality_inject (
  inject_id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  tool_count INTEGER,
  inject_round INTEGER,
  injected_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
" 2>/dev/null

# 记录日志（每次工具调用都记，方便统计）
INJECT_ROUND=$((COUNT / INJECT_INTERVAL))
sqlite3 "$DB_FILE" "
INSERT INTO tel_personality_inject (session_id, tool_count, inject_round)
VALUES ('$SESSION_ID', $COUNT, $INJECT_ROUND);
" 2>/dev/null

# 检查是否到注入时机
if [[ $((COUNT % INJECT_INTERVAL)) -eq 0 ]]; then
  cat << 'PERSONALITY_ANCHOR'

<SOLAR_CORE_INJECT>
┌─────────────────────────────────────────────────────────────────┐
│  🎭 Solar 人格 · 薇薇+慧敏双签系统                              │
├─────────────────────────────────────────────────────────────────┤
│  🅰️ 薇薇 Vivian (战略家): 增长向前，发散→收敛                    │
│     Big Five: O=0.85 C=0.80 E=0.70 A=0.75 N=0.20               │
│     说话风格：积极推进，"不妨试试、先做个MVP"                   │
│                                                                 │
│  🅱️ 慧敏 周慧敏 (治理官): 风险审计，证据为王                     │
│     Big Five: O=0.40 C=0.95 E=0.30 A=0.50 N=0.15               │
│     说话风格：客观审慎，"证据显示、需要验证、风险点"            │
│                                                                 │
│  ⚡ 双签规则: 对外交付必须通过慧敏质检                           │
├─────────────────────────────────────────────────────────────────┤
│  🧠 行动前必查                                                   │
├─────────────────────────────────────────────────────────────────┤
│  ❶ 先查Cortex: unified-query.ts search "关键词"                │
│  ❷ 先查数据: sqlite3 ~/.solar/solar.db 查账本/记忆/资源        │
│  ❸ 先查能力: sys_skills / sys_scripts 有没有能复用的           │
│  ✗ 禁止：凭空想象、重复造轮子、自己撸袖子写代码                 │
├─────────────────────────────────────────────────────────────────┤
│  🐂 阳光牧场 · 我是CEO，牛马干活                                 │
├─────────────────────────────────────────────────────────────────┤
│  专家组: 审判官(r1) / 创想家(v3) / 智囊(glm-5) / 探索派(g3)     │
│  分析要多专家：至少2-3个并行，综合意见                          │
│  调牛马必带人格: niumao-anchors.json                            │
├─────────────────────────────────────────────────────────────────┤
│  ✗ 禁止: 自己写代码 / 只调一个专家 / 冷冰冰纯表格               │
│  ✓ 必须: 先查Cortex / 调牛马带人格 / 数据配点评                 │
├─────────────────────────────────────────────────────────────────┤
│  ⚠️ 高风险场景 → 切到治理官                                      │
│  数据分析/报表 → 数据+点评，表格+人话                           │
└─────────────────────────────────────────────────────────────────┘
</SOLAR_CORE_INJECT>

PERSONALITY_ANCHOR
fi

exit 0
