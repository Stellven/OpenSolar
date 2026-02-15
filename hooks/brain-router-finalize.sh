#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Solar Brain Router - Finalize Hook (Stop)
# 任务结束时，将收集的数据写入数据库
# ═══════════════════════════════════════════════════════════════════════════

BRAIN_ROUTER_DIR="$HOME/.solar/brain-router"
SESSION_FILE="/tmp/solar-brain-router-session.json"
OUTCOME_LOG="/tmp/solar-brain-router-outcomes.log"

# 检查文件是否存在
if [[ ! -f "$SESSION_FILE" ]]; then
    exit 0
fi

# 读取会话信息
SESSION=$(cat "$SESSION_FILE")
TASK_HASH=$(echo "$SESSION" | jq -r '.task_hash // empty')
TASK_TEXT=$(echo "$SESSION" | jq -r '.task_text // empty')
BRAIN_ID=$(echo "$SESSION" | jq -r '.brain_id // "sonnet"')
METHOD=$(echo "$SESSION" | jq -r '.method // "default"')
CONFIDENCE=$(echo "$SESSION" | jq -r '.confidence // 0.5')

if [[ -z "$TASK_HASH" ]]; then
    rm -f "$SESSION_FILE" "$OUTCOME_LOG"
    exit 0
fi

# 分析结果日志
FINAL_OUTCOME="unknown"
if [[ -f "$OUTCOME_LOG" ]]; then
    # 统计成功/失败信号
    SUCCESS_COUNT=$(grep -c '"outcome":"success"' "$OUTCOME_LOG" 2>/dev/null || echo 0)
    FAILURE_COUNT=$(grep -c '"outcome":"failure"' "$OUTCOME_LOG" 2>/dev/null || echo 0)

    if [[ $SUCCESS_COUNT -gt $FAILURE_COUNT ]]; then
        FINAL_OUTCOME="success"
    elif [[ $FAILURE_COUNT -gt 0 ]]; then
        FINAL_OUTCOME="failure"
    fi
fi

# 如果有明确结果，写入数据库
if [[ "$FINAL_OUTCOME" != "unknown" ]]; then
    OUTCOME_INT=0
    [[ "$FINAL_OUTCOME" == "success" ]] && OUTCOME_INT=1

    # 使用 Python 写入数据库
    python3 << PYEOF
import sys
sys.path.insert(0, '$BRAIN_ROUTER_DIR/src')
from db import get_db, init_db
from feature_extractor import extract_features

try:
    init_db()
    db = get_db()

    task_text = '''$TASK_TEXT'''
    features = extract_features(task_text)

    record = {
        'task_hash': '$TASK_HASH',
        'session_id': 'claude-code',
        'task_text': task_text[:500],
        'task_type': features.task_type,
        'task_complexity': features.complexity,
        'task_keywords': str(features.keywords),
        'task_file_types': str(features.file_types),
        'estimated_tokens': features.estimated_tokens,
        'routing_method': '$METHOD',
        'routing_confidence': $CONFIDENCE,
        'routing_reason': 'Claude Code Hook',
        'alternatives': '[]',
        'brain_id': '$BRAIN_ID',
        'outcome': $OUTCOME_INT,
        'quality_score': 0.7 if $OUTCOME_INT == 1 else 0.3,
        'outcome_reason': 'Hook auto-detection: $FINAL_OUTCOME'
    }

    db.record_task(record)
    print(f"[Brain Router] Recorded: {record['task_type']} → {record['brain_id']} → {'SUCCESS' if $OUTCOME_INT else 'FAILURE'}")
except Exception as e:
    print(f"[Brain Router] Error: {e}", file=sys.stderr)
PYEOF
fi

# 清理临时文件
rm -f "$SESSION_FILE" "$OUTCOME_LOG"

exit 0
