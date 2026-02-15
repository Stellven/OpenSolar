#!/bin/bash
# 任务胶囊恢复 Hook - SessionStart 时自动恢复未完成任务
# 配置在 settings.json 的 SessionStart hooks 中

DB_PATH="$HOME/.solar/solar.db"

# 查找最近未完成的任务胶囊
CAPSULE=$(sqlite3 "$DB_PATH" "
SELECT task_id, json_extract(capsule_json, '$.topic'), json_extract(capsule_json, '$.currentPhase')
FROM cortex_task_capsules
WHERE json_extract(capsule_json, '$.phaseStatus.7') IS NULL OR json_extract(capsule_json, '$.phaseStatus.7') != 'completed'
ORDER BY updated_at DESC
LIMIT 1;
" 2>/dev/null)

if [ -n "$CAPSULE" ] && [ "$CAPSULE" != "" ]; then
    TASK_ID=$(echo "$CAPSULE" | cut -d'|' -f1)
    TOPIC=$(echo "$CAPSULE" | cut -d'|' -f2)
    PHASE=$(echo "$CAPSULE" | cut -d'|' -f3)

    echo ""
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│  🔄 检测到未完成的洞察任务                                   │"
    echo "├─────────────────────────────────────────────────────────────┤"
    echo "│                                                             │"
    echo "│  任务ID: $TASK_ID"
    echo "│  主题:   $TOPIC"
    echo "│  当前进度: Phase $PHASE"
    echo "│                                                             │"
    echo "│  恢复命令: bun ~/.claude/core/xiaoai-insight/insight-v2.ts --resume $TASK_ID"
    echo "│                                                             │"
    echo "└─────────────────────────────────────────────────────────────┘"
    echo ""
fi
