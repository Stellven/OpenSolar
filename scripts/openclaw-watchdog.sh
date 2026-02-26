#!/bin/bash

# OpenClaw Gateway Watchdog Script
# Path: ~/.claude/scripts/openclaw-watchdog.sh

LOG_FILE="/tmp/openclaw-watchdog.log"
OPENCLAW_DIR="$HOME/.openclaw"
GATEWAY_LOCK="$OPENCLAW_DIR/gateway.lock"
SESSIONS_DIR="$OPENCLAW_DIR/agents/main/sessions"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Check if OpenClaw gateway is healthy
check_health() {
    # Check if process exists
    if ! pgrep -f "openclaw-gateway" > /dev/null; then
        log "❌ Gateway process not found"
        return 1
    fi

    # Check if port is responding
    if ! curl -s -f --connect-timeout 5 http://127.0.0.1:18789/health > /dev/null 2>&1; then
        log "❌ Gateway health check failed on port 18789"
        return 1
    fi

    log "✅ Gateway is healthy"
    return 0
}

# Repair OpenClaw gateway
repair_gateway() {
    log "🔧 Starting gateway repair process"

    # Kill all OpenClaw processes
    pkill -9 -f "openclaw" 2>/dev/null
    sleep 1
    log "   Killed all OpenClaw processes"

    # Remove session lock files
    if [ -d "$SESSIONS_DIR" ]; then
        find "$SESSIONS_DIR" -name "*.lock" -type f -delete 2>/dev/null
        log "   Removed session lock files"
    fi

    # Remove gateway lock if exists
    if [ -f "$GATEWAY_LOCK" ]; then
        rm -f "$GATEWAY_LOCK"
        log "   Removed gateway lock file"
    fi

    # Restart gateway
    nohup openclaw gateway > /dev/null 2>&1 &
    sleep 3

    # Check if gateway started successfully
    if pgrep -f "openclaw-gateway" > /dev/null; then
        log "✅ Gateway restarted successfully"
        return 0
    else
        log "❌ Failed to restart gateway"
        return 1
    fi
}

# Main execution
if check_health; then
    exit 0
else
    if repair_gateway; then
        exit 1
    else
        exit 2
    fi
fi
