#!/bin/bash
#
# Cortex Files 定时同步脚本
# 用于 launchd 定时调用
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYNC_SCRIPT="$SCRIPT_DIR/sync.ts"
LOG_FILE="/tmp/cortex-sync.log"
BUN="/Users/lisihao/.bun/bin/bun"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "========== Cortex Sync Started =========="

# 执行增量同步
cd "$SCRIPT_DIR"
if $BUN sync.ts --incremental >> "$LOG_FILE" 2>&1; then
    log "✅ Sync completed successfully"
else
    log "❌ Sync failed"
fi

log "========== Cortex Sync Finished =========="
