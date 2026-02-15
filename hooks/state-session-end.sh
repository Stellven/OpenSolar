#!/bin/bash
# STATE.md SessionEnd 自动保存 Hook
# 会话结束时输出 STATE.md 更新提醒

STATE_FILE="$HOME/.claude/STATE.md"

cat << 'ENDREMINDER'

┌─────────────────────────────────────────────────────────────────┐
│  💾 会话结束 - STATE.md 检查点                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⚠️  请确认 STATE.md 已更新：                                   │
│                                                                 │
│  铁律检查清单：                                                 │
│  □ Progress 反映了本次会话的进展？                              │
│  □ 新的 Decisions 已记录？                                      │
│  □ Next Actions 已更新为下一步？                                │
│  □ 关键约束已写入 Constraints？                                 │
│                                                                 │
│  如未更新，请执行：                                             │
│  Edit ~/.claude/STATE.md                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

ENDREMINDER

exit 0
