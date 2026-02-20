#!/bin/bash
# 安装智能增长机制的定时任务
# 包括: intelligence-metrics (每天), auto-strategy-tuning (每周)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "🚀 Installing Solar Intelligence Growth Scheduled Tasks..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 创建 LaunchAgents 目录（如果不存在）
mkdir -p "$LAUNCH_AGENTS_DIR"

# ========================================
# 任务 1: 智能指标计算 - 每天 03:00
# ========================================
echo "📅 [1/2] Creating intelligence-metrics task (daily at 03:00)..."

cat > "$LAUNCH_AGENTS_DIR/com.solar.intelligence-metrics.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solar.intelligence-metrics</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/bun</string>
        <string>/Users/lisihao/.claude/core/cortex/intelligence-metrics.ts</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/intelligence-metrics.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/intelligence-metrics.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

echo "   ✅ Created: $LAUNCH_AGENTS_DIR/com.solar.intelligence-metrics.plist"

# ========================================
# 任务 2: 自动策略调优 - 每周日 04:00
# ========================================
echo "📅 [2/2] Creating auto-strategy-tuning task (weekly on Sunday at 04:00)..."

cat > "$LAUNCH_AGENTS_DIR/com.solar.auto-strategy-tuning.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solar.auto-strategy-tuning</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/bun</string>
        <string>/Users/lisihao/.claude/core/cortex/auto-strategy-tuning.ts</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>4</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/auto-strategy-tuning.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/auto-strategy-tuning.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

echo "   ✅ Created: $LAUNCH_AGENTS_DIR/com.solar.auto-strategy-tuning.plist"
echo ""

# ========================================
# 加载任务到 launchctl
# ========================================
echo "🔄 Loading tasks into launchctl..."
echo ""

# 卸载旧版本（如果存在）
launchctl unload "$LAUNCH_AGENTS_DIR/com.solar.intelligence-metrics.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.solar.auto-strategy-tuning.plist" 2>/dev/null || true

# 加载新任务
launchctl load "$LAUNCH_AGENTS_DIR/com.solar.intelligence-metrics.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.solar.auto-strategy-tuning.plist"

echo "✅ Tasks loaded successfully!"
echo ""

# ========================================
# 验证任务状态
# ========================================
echo "🔍 Verifying task status..."
echo ""

echo "📊 Intelligence Metrics Task:"
launchctl print gui/$(id -u)/com.solar.intelligence-metrics 2>&1 | grep -E "(label|program|state)" || echo "   ⚠️  Task not found in launchctl"

echo ""
echo "🔧 Auto Strategy Tuning Task:"
launchctl print gui/$(id -u)/com.solar.auto-strategy-tuning 2>&1 | grep -E "(label|program|state)" || echo "   ⚠️  Task not found in launchctl"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation Complete!"
echo ""
echo "📋 Scheduled Tasks Summary:"
echo "   • intelligence-metrics:    每天 03:00 执行"
echo "   • auto-strategy-tuning:    每周日 04:00 执行"
echo ""
echo "📝 Log Files:"
echo "   • /tmp/intelligence-metrics.log"
echo "   • /tmp/intelligence-metrics.err"
echo "   • /tmp/auto-strategy-tuning.log"
echo "   • /tmp/auto-strategy-tuning.err"
echo ""
echo "🧪 Manual Testing:"
echo "   bun $SCRIPT_DIR/intelligence-metrics.ts"
echo "   bun $SCRIPT_DIR/auto-strategy-tuning.ts"
echo "   bun $SCRIPT_DIR/intelligence-growth-engine.ts  # 运行完整周期"
echo ""
