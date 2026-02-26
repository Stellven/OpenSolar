#!/bin/bash
# feedback-loop-hook.sh — SessionEnd 自动触发反馈闭环
# Part of Phase 4: 反馈闭环强化
# @created 2026-02-24

SCRIPT="$HOME/.claude/core/solar-farm/feedback-loop.ts"

if [ ! -f "$SCRIPT" ]; then
  exit 0
fi

# Run feedback loop (process up to 50 unscored requests with skill_id)
result=$(bun "$SCRIPT" run 50 2>&1)

# Extract key metrics for logging (macOS-compatible, no grep -P)
processed=$(echo "$result" | sed -n 's/.*处理: \([0-9]*\).*/\1/p' | head -1)
processed="${processed:-0}"
errors=$(echo "$result" | sed -n 's/.*错误: \([0-9]*\).*/\1/p' | head -1)
errors="${errors:-0}"
avg_q=$(echo "$result" | sed -n 's/.*平均质量: \([0-9.]*\).*/\1/p' | head -1)
avg_q="${avg_q:-N/A}"

if [ "$processed" -gt 0 ]; then
  echo "🔄 反馈闭环: ${processed}条已评分 | 平均质量=${avg_q} | 错误=${errors}"
fi

exit 0
